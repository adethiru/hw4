"""Pydantic / PydanticAI structured types for Campus Customs.

    Agent output   ShopReply                    what the model must return each turn
    Tool returns   FindProductResult, ProductDetails, SizeStockCheck, ProductStock,
                   SearchResult, CategoriesResult, ToolError (+ SizeStock, ProductMatch, ...)
    Chat API       ChatRequest -> ChatResponse  POST /api/chat  (ChatResponse.page_results -> Products page)
                   ChatMessageOut               GET  /api/chat/history
    Shared         ProductCard                  product cards under a chat reply
    Agent deps     ShopperContext, CurrentPage  who is chatting + what page they're on (Problem 8)
    Memory tool    ShopperProfile               get_shopper_profile return type
    Audit          AuditEvent                   one entry of output/audit_trail.json (Problem 12)
    Auth API       RegisterRequest, LoginRequest, UserOut
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["user", "assistant"]
Category = Literal["t-shirt", "long-sleeve shirt", "crewneck", "hoodie", "full-zip hoodie", "quarter-zip", "jacket"]
Size = Literal["XS", "S", "M", "L", "XL", "XXL"]


# ------------------------------------------------------------------ agent output
class PageResultsRequest(BaseModel):
    """The agent's half of the page-update contract: *that* the last search should be shown, and a title.

    The products themselves are NOT written by the model; the server re-runs that search_products call
    against the DB (same filters, page-sized limit) and fills PageResults.products.
    """

    heading: str = Field(description="Short page title for the results, e.g. 'Hoodies', 'Navy crewnecks under $60'.")


class ShopReply(BaseModel):
    """What the agent returns for every chat turn (PydanticAI output_type)."""

    reply: str = Field(
        description="The message shown to the shopper, in the Campus Customs voice. Plain text with optional "
        "**bold** and '- ' bullet lists. Prices, colors and stock must come from tool results."
    )
    product_ids: list[str] = Field(
        description="product_id values (from tool results this turn) to show as clickable cards under the "
        "reply, most relevant first, max 6. Empty list for small talk or when nothing matches."
    )
    suggestions: list[str] = Field(
        description="2-3 short follow-up questions the SHOPPER might tap next, written in their voice "
        "(e.g. 'Do you have it in M?', 'Show me gray ones', 'What's the cheapest hoodie?'). Max 60 characters "
        "each, no prices or stock numbers. Empty list only for refusals."
    )
    page_results: Optional[PageResultsRequest] = Field(
        description="Set this when the shopper is browsing a TYPE of item (e.g. 'what hoodies do you have?', "
        "'show me navy crewnecks under $60') and you called search_products: the website will show ALL "
        "matches of your most recent search_products call on the Products page. Null for questions about "
        "one specific product, price/stock checks, small talk, or when the search found nothing."
    )


# ------------------------------------------------------------------ tool return types (Problem 6)
# tools.py builds plain dicts from SQLite; agent.py validates them into these models before the
# model sees them. Validation catches any drift between the DB/tool code and what the prompt promises.

StockStatus = Literal["in_stock", "low_stock", "out_of_stock"]  # low_stock = 1-3 left


class ToolError(BaseModel):
    """Returned instead of a result when the lookup can't be done (unknown id, size or category)."""

    found: Literal[False] = False
    error: str = Field(description="What went wrong and which tool to use instead.")


class SizeStock(BaseModel):
    """Stock for one size of one product (one inventory row)."""

    size: Size
    quantity: int = Field(description="Units on hand right now, from inventory.quantity.")
    status: StockStatus = Field(description="in_stock, low_stock (1-3 left) or out_of_stock (0).")


class ProductMatch(BaseModel):
    """A candidate product for a name the shopper typed."""

    product_id: str
    name: str
    price: float
    category: Category


class FindProductResult(BaseModel):
    """Return type of find_product."""

    found: bool
    exact: bool = Field(description="True if the name or id matched exactly; False for a best-effort match.")
    matches: list[ProductMatch]
    note: Optional[str] = Field(default=None, description="E.g. ask the shopper which one when there are several.")


class ProductDetails(BaseModel):
    """Return type of get_product_details: everything the agent may say about one product."""

    found: Literal[True] = True
    product_id: str
    name: str
    category: Category
    garment_type: str = Field(description="Raw catalogue value, e.g. 'pullover hoodie'.")
    price: float = Field(description="USD; the same for every size.")
    price_display: str = Field(description="Price formatted for replies, e.g. '$68.00'.")
    description: str
    colors: list[str]
    colors_note: Optional[str] = Field(description="Set when no colors are listed, so the agent doesn't guess.")
    tags: list[str]
    stock: list[SizeStock] = Field(description="One entry per size, XS to XXL.")
    sizes_in_stock: list[Size]
    sizes_out_of_stock: list[Size]
    total_in_stock: int
    image_url: str
    source: str = Field(description="Where the facts came from (for audit / explanations).")


class SizeStockCheck(BaseModel):
    """Return type of check_stock when a size is given."""

    found: Literal[True] = True
    product_id: str
    name: str
    price: float
    size: Size
    quantity: int
    in_stock: bool
    status: StockStatus
    message: str = Field(description="Plain sentence the agent can relay, e.g. 'Size XS ... is OUT OF STOCK'.")
    sizes_in_stock: list[Size] = Field(description="Alternatives to offer when this size is out of stock.")
    sizes_out_of_stock: list[Size]


class ProductStock(BaseModel):
    """Return type of check_stock when no size is given (all sizes)."""

    found: Literal[True] = True
    product_id: str
    name: str
    price: float
    stock: list[SizeStock]
    total_in_stock: int
    sizes_in_stock: list[Size]
    sizes_out_of_stock: list[Size]
    message: str


class ProductSearchHit(BaseModel):
    """One product in search_products results."""

    product_id: str
    name: str
    category: Category
    price: float
    colors: list[str]
    description: str
    sizes_in_stock: list[Size]
    sizes_out_of_stock: list[Size]
    image_url: str


class SearchResult(BaseModel):
    """Return type of search_products."""

    query: str
    filters: dict[str, str | float] = Field(description="The filters actually applied (echoed back).")
    total_matches: int = Field(description="How many products matched before the limit was applied.")
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Misspelled query words that were auto-corrected, e.g. {'hoddie': 'hoodie'} (Problem 9).",
    )
    results: list[ProductSearchHit]


class CategorySummary(BaseModel):
    category: Category
    products: int
    min_price: float
    max_price: float


class CategoriesResult(BaseModel):
    """Return type of list_categories."""

    categories: list[CategorySummary]
    sizes: list[Size]
    not_carried: list[str]


# ------------------------------------------------------------------ product cards
class ProductCard(BaseModel):
    """Small product tile shown under a chat reply; links to /products/{product_id}.

    Built by the server from the catalogue (never from model text), so name, price and image are always real.
    """

    product_id: str
    name: str
    price: float
    category: str
    image_url: str = Field(description="Served by FastAPI at /images/<file>.jpg")


# ------------------------------------------------------------------ chat API
class ChatHistoryItem(BaseModel):
    role: Role
    content: str = Field(max_length=4000)


class PageContext(BaseModel):
    """What the shopper is looking at when they send a message (sent by the chat widget, Problem 8).

    Untrusted browser input: the server checks product_id against the catalogue before using it.
    """

    path: str = Field(default="/", max_length=200, description="Current URL path, e.g. '/products/basic-hoodie-big-yale'.")
    product_id: Optional[str] = Field(default=None, max_length=200, description="Set on /products/<id> pages.")
    results_heading: Optional[str] = Field(
        default=None, max_length=120, description="Heading of chat results shown on /products, e.g. 'Hoodies'."
    )


class ChatRequest(BaseModel):
    """Body of POST /api/chat sent by the chat widget."""

    message: str = Field(min_length=1, max_length=2000)
    page: Optional[PageContext] = None
    # Legacy (Problems 5-7): same as page.product_id. Still accepted.
    current_product_id: Optional[str] = Field(default=None, max_length=200)
    # Guests only: recent turns kept in the browser. Logged-in users' history is loaded from the DB.
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=20)


# ------------------------------------------------------------------ page results (Problem 7)
class ProductMatchCard(BaseModel):
    """One product card on the Products page when chat search updates it."""

    product_id: str
    name: str
    category: Category
    price: float
    image_url: str
    short_description: str = Field(description="~110-char cut of catalogue.description.")
    colors: list[str]
    sizes_in_stock: list[Size]


class PageResults(BaseModel):
    """Structured product matches the front end renders on the Products page (API contract)."""

    source: Literal["chat_search"] = "chat_search"
    heading: str = Field(description="From the agent, e.g. 'Hoodies'.")
    query: str = Field(description="Keywords of the search the agent ran.")
    filters: dict[str, str | float] = Field(description="Filters of that search (category, color, size, price, sort).")
    total_matches: int
    products: list[ProductMatchCard] = Field(description="All matches (up to 60), in the search's order.")


class ChatResponse(BaseModel):
    """Response of POST /api/chat."""

    reply: str
    products: list[ProductCard] = Field(default_factory=list, description="A few cards inside the chat bubble.")
    page_results: Optional[PageResults] = Field(
        default=None, description="When set, the website shows these matches on the Products page."
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Quick-reply chips shown under the reply (Problem 9); tapping one sends it."
    )


class ChatMessageOut(BaseModel):
    """One saved message from chat_messages, as returned by GET /api/chat/history."""

    role: Role
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    created_at: str


# ------------------------------------------------------------------ agent deps
class ShopperContext(BaseModel):
    """Who is chatting: the only user information the agent ever sees (never password_hash or other users).

    Built by the server from the session cookie + users table + chat_messages; the browser can't set it.
    """

    logged_in: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    member_since: Optional[str] = Field(default=None, description="users.created_at")
    past_messages: int = Field(default=0, description="Messages this shopper sent in earlier chats.")
    last_chat_at: Optional[str] = None

    @property
    def returning(self) -> bool:
        return self.logged_in and self.past_messages > 0


class ProductBrief(BaseModel):
    """The product on the page the shopper is viewing (resolved from PageContext.product_id)."""

    product_id: str
    name: str
    category: Category
    price: float
    colors: list[str]
    colors_note: Optional[str] = None


class CurrentPage(BaseModel):
    """Server-resolved page context placed in the agent's instructions each turn."""

    path: str
    page_type: Literal["home", "products", "product", "about", "login", "register", "other"]
    product: Optional[ProductBrief] = Field(default=None, description="Set on a product page: 'this' / 'it' = this product.")
    results_heading: Optional[str] = Field(default=None, description="Chat results currently shown on /products.")


class ShopperProfile(BaseModel):
    """Return type of the get_shopper_profile tool (the logged-in shopper's own data only)."""

    logged_in: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    member_since: Optional[str] = None
    past_messages: int = 0
    first_chat_at: Optional[str] = None
    last_chat_at: Optional[str] = None
    recently_recommended: list[ProductCard] = Field(default_factory=list, description="Cards shown in earlier chats.")
    recently_asked_about_on_product_pages: list[ProductCard] = Field(default_factory=list)
    note: Optional[str] = None


# ------------------------------------------------------------------ auth API
class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    """Public view of a user. Deliberately has no password_hash field."""

    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: str
    email: str


# ------------------------------------------------------------------ audit trail (Problem 12)
AuditEventKind = Literal["run_start", "tool_call", "validation_retry", "safety_flag", "run_end"]
StopReason = Literal[
    "completed",               # model answered; reply passed all checks
    "fallback_after_retries",  # model kept failing the grounding/safety checks -> DB-worded fallback reply
    "limit_reached",           # request / tool-call budget hit -> fallback reply
    "model_error",             # API / network error -> 503 to the browser
]


class AuditEvent(BaseModel):
    """One line of output/audit_trail.json. Short by design: enough to replay what the loop did,
    never personal data (no names, emails, passwords, tokens)."""

    timestamp: str = Field(description="UTC ISO-8601 with milliseconds.")
    run_id: str = Field(description="Groups all events of one chat turn.")
    event: AuditEventKind
    user: str = Field(description="'user:<id>' or 'guest' (never name/email).")
    page: str = Field(description="Page path the message was sent from.")
    model: str
    iteration: Optional[int] = Field(default=None, description="Agent-loop step (model request number).")
    tool: Optional[str] = None
    args: Optional[dict[str, str]] = Field(default=None, description="Tool arguments, each cut to 60 chars.")
    status: Optional[Literal["ok", "error", "blocked"]] = None
    result: Optional[str] = Field(default=None, description="One-line tool result summary (≤160 chars).")
    detail: Optional[str] = Field(default=None, description="Redacted message preview / retry reason / flag.")
    stop_reason: Optional[StopReason] = None
    requests: Optional[int] = Field(default=None, description="Model requests used this turn.")
    tool_calls: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cards: Optional[int] = None
    page_results: Optional[int] = None
    duration_ms: Optional[int] = None
