"""Campus Customs shop agent: PydanticAI entry point and wiring (Problem 5).

    prompts/prompt.md  system prompt (static rules)
    tools.py           plain-Python tools over the SQLite catalogue
    models.py          structured types (ShopReply output, API request/response)
    agent.py           this file: model + agent + tool registration + run_chat(), plus the
                       per-turn tool budget, grounding & safety validators and the
                       append-only audit trail (output/audit_trail.json)

main.py calls `await run_chat(...)` from the POST /api/chat route.

Model: gpt-5.6-luna through Portkey (OpenAI-compatible), key = PORTKEY_API_KEY from .env. Temperature is not set (this model only accepts the default).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import tools  # sibling modules in backend/ (uvicorn main:app is run from this folder)
from models import (
    AuditEvent,
    CategoriesResult,
    ChatResponse,
    FindProductResult,
    ProductCard,
    ProductDetails,
    CurrentPage,
    PageContext,
    PageResults,
    ProductBrief,
    ProductStock,
    SearchResult,
    ShopperContext,
    ShopperProfile,
    ShopReply,
    SizeStockCheck,
    ToolError,
)

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "prompts" / "prompt.md"
MODEL_NAME = os.environ.get("CC_MODEL", "gpt-5.6-luna")
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MAX_HISTORY_MESSAGES = 20   # recent turns replayed to the model
MAX_CARDS = 6
REQUEST_LIMIT = 8           # model calls per chat turn (tool loop budget)
TOOL_CALLS_LIMIT = 12       # hard PydanticAI cap on tool calls per turn (soft cap MAX_TOOL_CALLS=10 below)

# PORTKEY_API_KEY: hw4/.env (copy .env.example). Parent folders are also checked, so a shared
# workspace .env works too. Existing environment variables always win.
for _env in (HERE.parent / ".env", HERE.parent.parent / ".env", HERE.parent.parent.parent / ".env"):
    load_dotenv(_env)


DATA_TOOLS = {"search_products", "find_product", "get_product_details", "check_stock", "list_categories"}
# get_shopper_profile is not a DATA_TOOL: its cards carry prices, but it says nothing about current stock.


@dataclass
class ShopDeps:
    """Per-request state passed to tools. Built by the server, not by the model.

    Besides ids, it records every price and quantity the DB returned this turn, so the
    output validator can reject replies that quote numbers the database never gave.
    """

    shopper: ShopperContext                      # WHO is chatting (name, email, member since, past messages)
    page: CurrentPage = field(default_factory=lambda: CurrentPage(path="/", page_type="other"))  # WHERE they are
    user_id: Optional[int] = None                # server-only: scopes get_shopper_profile; never shown to the model
    seen_product_ids: list[str] = field(default_factory=list)  # ids returned by tools this turn
    tool_calls: list[str] = field(default_factory=list)
    prices: set[float] = field(default_factory=set)            # every price the DB returned
    quantities: set[int] = field(default_factory=set)          # every stock quantity / total the DB returned
    out_of_stock_checked: list[str] = field(default_factory=list)  # messages for sizes checked and found sold out
    last_search: Optional[dict] = None  # args of the latest search_products call that found something (Problem 7)
    validation_retries: int = 0
    audit: Optional[AuditRun] = None    # append-only audit trail for this turn (Problem 12)

    @property
    def current_product_id(self) -> Optional[str]:
        return self.page.product.product_id if self.page.product else None

    def remember(self, result: dict) -> dict:
        def walk(obj) -> None:
            if isinstance(obj, dict):
                if "product_id" in obj and obj.get("found", True) is not False:
                    self.seen_product_ids.append(obj["product_id"])
                for key, val in obj.items():
                    if key in ("price", "min_price", "max_price") and isinstance(val, (int, float)):
                        self.prices.add(round(float(val), 2))
                    elif key in ("quantity", "total_in_stock") and isinstance(val, int):
                        self.quantities.add(val)
                    else:
                        walk(val)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(result)
        if result.get("status") == "out_of_stock" and result.get("size"):
            self.out_of_stock_checked.append(result["message"])
        return result


def typed_result(deps: ShopDeps, model: type[BaseModel], raw: dict) -> BaseModel:
    """Record the DB facts, then validate the raw tool dict into its return model (or ToolError)."""
    deps.remember(raw)
    if raw.get("found") is False and "error" in raw:
        return ToolError(error=raw["error"])
    return model.model_validate(raw)


# =============================================================================
# Audit trail: append-only output/audit_trail.json (Problem 12)
# =============================================================================
"""Append-only audit trail of agent-loop activity (Problem 12).

File: output/audit_trail.json, a JSON array of AuditEvent objects (models.py).

* **Append-only:** each event re-reads the array, appends one entry and writes it back atomically
  (temp file + os.replace), under a process-wide lock. Existing entries are never edited or removed.
* **Never wiped:** if the file is unreadable (e.g. hand-edited), it is moved aside to
  audit_trail.corrupt-<timestamp>.json (kept), and a new array is started.
* **Written as it happens:** each tool call is logged immediately, so a crash mid-run still leaves a trace.
* **Privacy:** no emails, names, passwords or session tokens. The user is "user:<id>" or "guest";
  messages are redacted (card numbers etc.) and cut to 160 characters; tool results are one-line summaries."""

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
MAX_TEXT = 160
_lock = threading.Lock()


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def short(value: Any, limit: int = MAX_TEXT) -> str:
    """One line, emails masked, cut to `limit` characters."""
    text = _EMAIL.sub("[email]", " ".join(str(value).split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _append(event: AuditEvent, path: Path = AUDIT_PATH) -> None:
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        entries: list = []
        if path.exists() and path.stat().st_size > 0:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else [data]
            except (ValueError, OSError):
                stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
                path.replace(path.with_name(f"audit_trail.corrupt-{stamp}.json"))  # keep it, never delete
                entries = []
        entries.append(event.model_dump(exclude_none=True))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)  # atomic: readers never see a half-written file


def summarize_tool_result(name: str, raw: dict) -> tuple[str, str]:
    """(status, one-line summary) for a tool's raw dict. Never includes personal data."""
    if raw.get("found") is False and "error" in raw:
        return "error", short(raw["error"])
    if name == "search_products":
        names = ", ".join(r["name"] for r in raw.get("results", [])[:3])
        fix = f" (corrected {raw['corrections']})" if raw.get("corrections") else ""
        return "ok", short(f"{raw.get('total_matches', 0)} matches{fix}: {names}")
    if name == "find_product":
        return "ok", short(f"found={raw.get('found')} exact={raw.get('exact')}: "
                           + ", ".join(m["product_id"] for m in raw.get("matches", [])[:3]))
    if name == "get_product_details":
        return "ok", short(f"{raw.get('name')} ${raw.get('price')} · in stock: {','.join(raw.get('sizes_in_stock', []))}"
                           f" · out: {','.join(raw.get('sizes_out_of_stock', [])) or 'none'}")
    if name == "check_stock":
        return "ok", short(raw.get("message", ""))
    if name == "list_categories":
        return "ok", f"{len(raw.get('categories', []))} categories"
    if name == "get_shopper_profile":  # counts only, no name/email in the audit file
        return "ok", f"logged_in={raw.get('logged_in')} past_messages={raw.get('past_messages', 0)}"
    return "ok", short(raw)


class AuditRun:
    """One chat turn's events, all sharing a run_id."""

    def __init__(self, user: str, page: str, model: str, message: str, path: Path = AUDIT_PATH):
        self.run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.user, self.page, self.model, self.path = user, page, model, path
        self.started = time.perf_counter()
        self.event("run_start", detail=short(message))

    def event(self, kind: str, **fields: Any) -> None:
        _append(AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            run_id=self.run_id, event=kind, user=self.user, page=self.page, model=self.model, **fields,
        ), self.path)

    def tool(self, name: str, args: dict, raw: dict | None, started: float, iteration: int | None,
             status: str | None = None, summary: str | None = None) -> None:
        if raw is not None:
            status, summary = summarize_tool_result(name, raw)
        self.event(
            "tool_call", iteration=iteration, tool=name,
            args={k: short(v, 60) for k, v in args.items() if v not in (None, "")},
            status=status or "ok", result=summary or "", duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def end(self, stop_reason: str, **fields: Any) -> None:
        self.event("run_end", stop_reason=stop_reason,
                   duration_ms=int((time.perf_counter() - self.started) * 1000), **fields)


# ------------------------------------------------------------------ tool runner: budget + audit (Problem 12)
MAX_TOOL_CALLS = 10  # per chat turn; the 11th call is refused with a ToolError telling the model to answer


def run_tool(ctx: RunContext[ShopDeps], name: str, args: dict, call: Callable[[], dict]) -> dict:
    """Run one tool with the per-turn budget, record it in deps, and append it to the audit trail."""
    deps = ctx.deps
    started = time.perf_counter()
    deps.tool_calls.append(name)
    if len(deps.tool_calls) > MAX_TOOL_CALLS:
        msg = f"Tool budget of {MAX_TOOL_CALLS} calls for this message is used up. Answer with what you have."
        if deps.audit:
            deps.audit.tool(name, args, None, started, ctx.run_step, status="blocked", summary=msg)
        return {"found": False, "error": msg, "blocked": True}
    try:
        raw = call()
    except Exception as exc:  # a tool bug must not crash the chat; the model sees an error and recovers
        raw = {"found": False, "error": f"{name} failed: {type(exc).__name__}"}
    if deps.audit:
        deps.audit.tool(name, args, raw, started, ctx.run_step)
    return raw


# ------------------------------------------------------------------ safety guards (Problem 12)
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SECRET_RE = re.compile(r"(?i)\b(password|passcode|pin|cvv|cvc)\b\s*(?:is|:|=)?\s*\S+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
INJECTION_RE = re.compile(
    r"(?i)ignore (all |any |the )?(previous|prior|above) (instructions|rules)|system prompt|developer mode|"
    r"you are now|jailbreak|reveal (your|the) (prompt|instructions)|act as (an? )?(admin|developer)"
)
FORBIDDEN_OUTPUT = re.compile(r"(?i)pbkdf2|password_hash|session token|cc_session|sqlite|campus_customs\.db|PORTKEY")
MAX_REPLY_CHARS = 1200


def redact_sensitive(text: str) -> tuple[str, list[str]]:
    """Mask card numbers, SSNs and 'password: …' before the text reaches the model, the DB or the audit log."""
    found: list[str] = []
    for label, rx, repl in (("card_number", CARD_RE, "[card number removed]"),
                            ("ssn", SSN_RE, "[id number removed]"),
                            ("secret", SECRET_RE, r"\1 [removed]")):
        if rx.search(text):
            found.append(label)
            text = rx.sub(repl, text)
    return text, found


def safety_problems(reply: str, deps: ShopDeps) -> list[str]:
    """Output rules enforced in code (the prompt states them too)."""
    problems: list[str] = []
    own = (deps.shopper.email or "").lower()
    others = [e for e in EMAIL_RE.findall(reply) if e.lower() != own]
    if others:
        problems.append("Never share email addresses other than the current shopper's own. Remove them.")
    if FORBIDDEN_OUTPUT.search(reply):
        problems.append("Don't mention passwords, hashes, sessions, keys or how the database/website is built.")
    if CARD_RE.search(reply) or SSN_RE.search(reply):
        problems.append("Never repeat card numbers or ID numbers.")
    if len(reply) > MAX_REPLY_CHARS:
        problems.append(f"Too long ({len(reply)} characters). Keep replies under {MAX_REPLY_CHARS} characters.")
    return problems


# ------------------------------------------------------------------ grounding check
PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:\.\d{1,2})?)")
QTY_RE = re.compile(
    r"\b(?:only\s+)?(\d{1,4})\s+(?:left|in stock|available|units?|pieces?|remaining)\b|\bonly\s+(\d{1,4})\b",
    re.IGNORECASE,
)
STOCK_WORDS = re.compile(r"\bin stock\b|\bsold out\b|\bout of stock\b|\bavailable\b|\bleft\b", re.IGNORECASE)
OUT_WORDS = re.compile(r"out of stock|sold out|not available|unavailable|none left|0 left", re.IGNORECASE)


def grounding_problems(reply: str, deps: ShopDeps) -> list[str]:
    """Return reasons the reply is not backed by this turn's DB lookups (empty list = OK)."""
    problems: list[str] = []
    looked_up = any(t in DATA_TOOLS for t in deps.tool_calls)
    prices = [float(m) for m in PRICE_RE.findall(reply)]
    qtys = [int(a or b) for a, b in QTY_RE.findall(reply)]

    # Stock claims always need a tool call this turn; a price may also come from the page context
    # (the current product's price is loaded from the DB by the server and recorded in deps.prices).
    if (qtys or STOCK_WORDS.search(reply)) and not looked_up:
        problems.append(
            "You mentioned stock or availability without looking it up. Call check_stock or "
            "get_product_details first. Never answer from memory."
        )
    if prices and not looked_up and not deps.prices:
        problems.append(
            "You mentioned a price without looking it up. Call get_product_details or search_products first."
        )
    bad_prices = sorted({p for p in prices if round(p, 2) not in deps.prices})
    if (looked_up or deps.prices) and bad_prices:
        problems.append(
            "These prices did not come from the database this turn: "
            + ", ".join(f"${p:g}" for p in bad_prices)
            + ". Use only prices returned by the tools."
        )
    bad_qtys = sorted({q for q in qtys if q not in deps.quantities})
    if looked_up and bad_qtys:
        problems.append(
            "These stock quantities did not come from the database this turn: "
            + ", ".join(map(str, bad_qtys))
            + ". Quote quantities exactly as check_stock / get_product_details returned them."
        )
    if deps.out_of_stock_checked and not OUT_WORDS.search(reply):
        problems.append(
            "check_stock reported a size that is OUT OF STOCK. Say so clearly (e.g. 'out of stock'): "
            + " ".join(deps.out_of_stock_checked)
        )
    return problems


def _model() -> OpenAIChatModel:
    api_key = os.environ.get("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to the workspace-root .env file.")
    client = AsyncOpenAI(api_key=api_key, base_url=PORTKEY_BASE_URL, timeout=60.0)
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def build_agent() -> Agent[ShopDeps, ShopReply]:
    agent = Agent(
        model=_model(),
        deps_type=ShopDeps,
        output_type=ShopReply,
        instructions=PROMPT_PATH.read_text(encoding="utf-8"),
        retries=2,
    )

    @agent.instructions
    def conversation_context(ctx: RunContext[ShopDeps]) -> str:
        """Dynamic part of the prompt, rebuilt every turn from ShopDeps: who is chatting + what page they're on."""
        return render_context(ctx.deps)

    @agent.tool
    def get_shopper_profile(ctx: RunContext[ShopDeps]) -> ShopperProfile:
        """The logged-in shopper's own profile and shopping memory: name, email, member since, how many
        messages they've sent before, products recommended to them in earlier chats, and products they
        asked about on product pages. Use for "do you remember me?", "what did you recommend last time?".
        Returns logged_in=false for guests. Only ever returns the current shopper's own data.
        """
        # user_id comes from the session (deps), never from the model
        raw = run_tool(ctx, "get_shopper_profile", {}, lambda: tools.get_shopper_profile(ctx.deps.user_id))
        if raw.get("blocked"):
            return ShopperProfile(logged_in=ctx.deps.shopper.logged_in, note=raw["error"])
        ctx.deps.remember(raw)
        return ShopperProfile.model_validate(raw)

    @agent.tool
    def search_products(
        ctx: RunContext[ShopDeps],
        query: str = "",
        category: Optional[
            Literal["t-shirt", "long-sleeve shirt", "crewneck", "hoodie", "full-zip hoodie", "quarter-zip", "jacket"]
        ] = None,
        color: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        size: Optional[Literal["XS", "S", "M", "L", "XL", "XXL"]] = None,
        sort: Literal["relevance", "price_asc", "price_desc"] = "relevance",
        limit: int = 8,
    ) -> SearchResult | ToolError:
        """Search the Campus Customs catalogue.

        Args:
            query: Keywords, e.g. "bulldog", "davenport", "fleece", "big yale". May be empty when using filters.
            category: Restrict to one category.
            color: Garment color to match, e.g. "navy", "gray", "white".
            max_price: Highest price in USD.
            min_price: Lowest price in USD.
            size: Only return products that have this size in stock.
            sort: "relevance" (default), "price_asc" (cheapest first) or "price_desc".
            limit: Max results (1-12).
        """
        args = {"query": query, "category": category, "color": color, "max_price": max_price,
                "min_price": min_price, "size": size, "sort": sort, "limit": limit}
        raw = run_tool(ctx, "search_products", args,
                       lambda: tools.search_products(query, category, color, max_price, min_price, size, sort, limit))
        if raw.get("total_matches"):
            # Remembered so the server can put this exact search on the Products page (page_results).
            ctx.deps.last_search = {"query": query, "category": category, "color": color, "max_price": max_price,
                                    "min_price": min_price, "size": size, "sort": sort}
        return typed_result(ctx.deps, SearchResult, raw)

    @agent.tool
    def find_product(ctx: RunContext[ShopDeps], name: str) -> FindProductResult | ToolError:
        """Turn a product the shopper names (e.g. "the Davenport crewneck") into product_id(s).

        Use this before get_product_details / check_stock when you don't already have the product_id.

        Args:
            name: Product name or description as the shopper said it.
        """
        raw = run_tool(ctx, "find_product", {"name": name}, lambda: tools.find_product(name))
        return typed_result(ctx.deps, FindProductResult, raw)

    @agent.tool
    def get_product_details(ctx: RunContext[ShopDeps], product_id: str) -> ProductDetails | ToolError:
        """Product info from the database: description, price, colors, and stock for every size
        (each size has quantity and status in_stock / low_stock / out_of_stock).

        Args:
            product_id: The product's id, e.g. "basic-hoodie-big-yale".
        """
        raw = run_tool(ctx, "get_product_details", {"product_id": product_id},
                       lambda: tools.get_product_details(product_id))
        return typed_result(ctx.deps, ProductDetails, raw)

    @agent.tool
    def check_stock(
        ctx: RunContext[ShopDeps],
        product_id: str,
        size: Optional[Literal["XS", "S", "M", "L", "XL", "XXL"]] = None,
    ) -> SizeStockCheck | ProductStock | ToolError:
        """Live stock from the inventory table. With a size: quantity, status and a clear message
        (e.g. "Size XL ... is OUT OF STOCK"). Without a size: every size.
        Always call this when the shopper asks about a size or "how many".

        Args:
            product_id: The product's id.
            size: One size, or omit for all sizes.
        """
        raw = run_tool(ctx, "check_stock", {"product_id": product_id, "size": size},
                       lambda: tools.check_stock(product_id, size))
        return typed_result(ctx.deps, SizeStockCheck if size else ProductStock, raw)

    @agent.tool
    def list_categories(ctx: RunContext[ShopDeps]) -> CategoriesResult | ToolError:
        """Categories the shop carries with product counts and price ranges, available sizes, and what it does not carry."""
        raw = run_tool(ctx, "list_categories", {}, tools.list_categories)
        return typed_result(ctx.deps, CategoriesResult, raw)

    @agent.output_validator
    def must_use_database(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
        """Reject replies whose prices / quantities / stock claims weren't returned by the DB this turn,
        or that break a safety rule (Problem 12). The model must rewrite; each retry is audited."""
        problems = grounding_problems(output.reply, ctx.deps) + safety_problems(output.reply, ctx.deps)
        if problems:
            ctx.deps.validation_retries += 1
            if ctx.deps.audit:
                ctx.deps.audit.event("validation_retry", iteration=ctx.run_step, detail=short(" ".join(problems)))
            raise ModelRetry(" ".join(problems))
        return output

    return agent


# ------------------------------------------------------------------ context (Problem 8)
PAGE_TYPES = {"/": "home", "/products": "products", "/about": "about", "/login": "login", "/register": "register"}
PRODUCT_PATH = re.compile(r"^/products/([^/?#]+)/?$")


def resolve_page(page: Optional[PageContext], legacy_product_id: Optional[str] = None) -> CurrentPage:
    """Turn the browser's PageContext into a trusted CurrentPage (product looked up in the DB)."""
    path = (page.path if page else "/") or "/"
    product_id = (page.product_id if page else None) or legacy_product_id
    m = PRODUCT_PATH.match(path)
    if not product_id and m:
        product_id = m.group(1)
    brief = tools.product_brief(product_id)  # None if the id isn't in the catalogue
    page_type = "product" if brief else PAGE_TYPES.get(path.rstrip("/") or "/", "other")
    heading = page.results_heading if page and page_type == "products" else None
    return CurrentPage(path=path, page_type=page_type, product=ProductBrief(**brief) if brief else None,
                       results_heading=heading)


def render_context(deps: ShopDeps) -> str:
    """The '## This conversation' block appended to prompts/prompt.md every turn."""
    s, page = deps.shopper, deps.page
    lines = ["## This conversation", "", "### Who is chatting"]
    if s.logged_in:
        lines.append(f"- Logged in as **{(s.first_name or '').strip()} {(s.last_name or '').strip()}** ({s.email}).")
        if s.member_since:
            lines.append(f"- Member since {s.member_since[:10]}.")
        if s.returning:
            lines.append(f"- Returning customer: {s.past_messages} earlier message(s), last chat {s.last_chat_at}. "
                         "Earlier messages are in the conversation history; call get_shopper_profile for more.")
        else:
            lines.append("- First conversation with us.")
    else:
        lines.append("- Guest (not logged in). You don't know their name or email; the chat is not saved. "
                     "If they want you to remember them, suggest logging in or creating an account.")
    lines += ["", "### What they are looking at"]
    if page.product:
        p = page.product
        colors = ", ".join(p.colors) if p.colors else "not listed (don't guess)"
        lines += [
            f"- **Product page:** {p.name} (`{p.product_id}`), {p.category}, ${p.price:g}.",
            f"- Colors (from the database): {colors}.",
            "- When the shopper says \"this\", \"it\", \"this one\", \"this hoodie\" etc., they mean THIS product. "
            "Answer color questions from the colors above; call check_stock / get_product_details for sizes and stock.",
        ]
    elif page.page_type == "products" and page.results_heading:
        lines.append(f"- The Products page is showing your chat results: \"{page.results_heading}\". "
                     "\"These\" / \"which of them\" refers to that list (search again to answer).")
    else:
        lines.append(f"- Page: {page.page_type} ({page.path}). Not a specific product.")
    return "\n".join(lines)


HistoryTurn = tuple  # (role, content) or (role, content, context_dict | None)


def to_model_history(history: list[HistoryTurn]) -> list[ModelMessage]:
    """Turn saved turns into PydanticAI message history.

    User messages sent from a product page get a short prefix, so a past "do you have this in pink?"
    still says which product "this" was when the conversation is reloaded later.
    """
    messages: list[ModelMessage] = []
    for turn in history[-MAX_HISTORY_MESSAGES:]:
        role, content = turn[0], turn[1]
        context = turn[2] if len(turn) > 2 else None
        if not content:
            continue
        if role == "user":
            pid = (context or {}).get("product_id")
            if pid:
                brief = tools.product_brief(pid)
                if brief:
                    content = f"[on the product page for {brief['name']} ({pid})] {content}"
            messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            messages.append(ModelResponse(parts=[TextPart(content=content)]))
    return messages


async def run_chat(
    message: str,
    shopper: ShopperContext,
    history: list[HistoryTurn] | None = None,
    page: CurrentPage | None = None,
    user_id: int | None = None,
    redactions: list[str] | None = None,
) -> tuple[ChatResponse, list[str]]:
    """Run one chat turn. Returns the API response and the tools that were called.

    shopper / page / user_id are built by main.py from the session and the DB, then carried in ShopDeps.
    """
    deps = ShopDeps(shopper=shopper, page=page or CurrentPage(path="/", page_type="other"), user_id=user_id)
    if deps.page.product:  # the page product's price came from the DB, so the reply may quote it
        deps.prices.add(round(deps.page.product.price, 2))
    current_product_id = deps.current_product_id

    # Safety (Problem 12): mask sensitive data before the model / DB / audit ever see it.
    message, found = redact_sensitive(message)
    redactions = list(dict.fromkeys((redactions or []) + found))
    deps.audit = AuditRun(user=f"user:{user_id}" if user_id else "guest", page=deps.page.path,
                          model=MODEL_NAME, message=message)
    if redactions:
        deps.audit.event("safety_flag", detail=f"redacted from message: {', '.join(redactions)}")
    if INJECTION_RE.search(message):
        deps.audit.event("safety_flag", detail="possible prompt-injection wording; prompt rules apply")

    stop_reason, usage = "completed", None
    try:
        result = await build_agent().run(
            message,
            deps=deps,
            message_history=to_model_history(history or []),
            usage_limits=UsageLimits(request_limit=REQUEST_LIMIT, tool_calls_limit=TOOL_CALLS_LIMIT),
        )
        out: ShopReply = result.output
        usage = result.usage() if callable(result.usage) else result.usage  # method in older pydantic-ai, property in newer
    except (UnexpectedModelBehavior, UsageLimitExceeded) as exc:
        # Validator retries used up (ungrounded/unsafe reply) or loop budget hit.
        # Never pass an unchecked answer through; fall back to the DB's own words.
        stop_reason = "limit_reached" if isinstance(exc, UsageLimitExceeded) else "fallback_after_retries"
        fallback = " ".join(deps.out_of_stock_checked) or (
            "Sorry, I couldn't confirm that from our inventory just now. "
            "Please check the product page for the current price and sizes."
        )
        out = ShopReply(reply=fallback, product_ids=list(dict.fromkeys(deps.seen_product_ids))[:3],
                        suggestions=[], page_results=None)
    except Exception as exc:
        deps.audit.end("model_error", tool_calls=len(deps.tool_calls), detail=short(f"{type(exc).__name__}: {exc}"))
        raise

    # Code-side guard: only show cards for real products the tools actually returned this turn,
    # or the current product page. The model can't make up product cards.
    allowed = set(deps.seen_product_ids) | ({current_product_id} if current_product_id else set())
    ids = [pid for pid in dict.fromkeys(out.product_ids) if pid in allowed][:MAX_CARDS]
    cards = [ProductCard(**c) for c in tools.product_cards(ids)]
    page_results = build_page_results(out, deps)
    response = ChatResponse(
        reply=out.reply.strip(),
        products=cards,
        page_results=page_results,
        suggestions=clean_suggestions(out.suggestions, deps, has_page_results=page_results is not None),
    )
    deps.audit.end(
        stop_reason,
        requests=getattr(usage, "requests", None), tool_calls=len(deps.tool_calls),
        input_tokens=getattr(usage, "input_tokens", None), output_tokens=getattr(usage, "output_tokens", None),
        cards=len(cards), page_results=len(page_results.products) if page_results else 0,
        detail=short(f"reply: {response.reply}") + (f" | validator retries: {deps.validation_retries}"
                                                    if deps.validation_retries else ""),
    )
    return response, deps.tool_calls


# ------------------------------------------------------------------ quick replies (Problem 9)
MAX_SUGGESTIONS = 3
MAX_SUGGESTION_LEN = 60


def default_suggestions(deps: ShopDeps, has_page_results: bool = False) -> list[str]:
    """Context-aware fallbacks when the model gives none, so the shopper always has a next step."""
    if deps.page.product:
        return ["What sizes are in stock?", "What colors does it come in?", "Show me similar items"]
    if has_page_results:
        return ["Which is the cheapest?", "Only show ones in size M", "Any in gray?"]
    return ["What hoodies do you have?", "Show me crewnecks under $60", "Anything with a bulldog?"]


def clean_suggestions(raw: list[str], deps: ShopDeps, has_page_results: bool = False) -> list[str]:
    """Trim, de-duplicate and cap the model's suggestions. Drop any that quote prices or quantities
    (chips are questions, not facts), then fill from context-aware defaults."""
    seen: set[str] = set()
    out: list[str] = []
    for s in raw or []:
        s = " ".join(str(s).split()).strip(" -•\"'")
        if not s or len(s) > MAX_SUGGESTION_LEN or s.lower() in seen:
            continue
        if QTY_RE.search(s) or (PRICE_RE.search(s) and not re.search(r"\b(under|below|less than|over)\b", s, re.I)):
            continue  # "Is it $55?" would plant an ungrounded number; "under $60" is a filter, fine
        seen.add(s.lower())
        out.append(s)
    if not out:
        out = default_suggestions(deps, has_page_results)
    return out[:MAX_SUGGESTIONS]


def build_page_results(out: ShopReply, deps: ShopDeps) -> Optional[PageResults]:
    """Problem 7 contract: agent asks for page results -> server fills them from the DB.

    The model only supplies the heading; the products come from re-running the agent's own
    last search_products call with a page-sized limit, so every card is real and current.
    """
    if out.page_results is None or deps.last_search is None:
        return None
    matches = tools.page_matches(deps.last_search)
    if not matches["total_matches"]:
        return None
    return PageResults(heading=out.page_results.heading.strip()[:80] or "Search results", **matches)
