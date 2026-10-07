"""Campus Customs API.

Problem 3: read-only endpoints for products, inventory and product images.
Problem 4: create account / log in / log out with hashed passwords and session cookies.
Problem 8: logged-in chat history saved/reloaded (see "Customer memory" section); shopper + page context passed to the agent.
Problem 5: POST /api/chat runs the PydanticAI shop agent (agent.py, tools.py, models.py, prompts/prompt.md).

Run from the backend/ folder (with hw4/.venv activated):
    cd backend
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Sibling modules in backend/ (run from this folder: uvicorn main:app --reload --port 8000).
import tools
from agent import redact_sensitive, resolve_page, run_chat
from models import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    LoginRequest,
    ProductCard,
    RegisterRequest,
    ShopperContext,
    UserOut,
)

log = logging.getLogger("campus_customs")
logging.basicConfig(level=logging.INFO)

# =============================================================================
# Auth helpers: password hashing, validation, sessions, rate limiting (Problem 4)
# =============================================================================
"""Password hashing, validation and session helpers (stdlib only).

Password storage
----------------
* PBKDF2-HMAC-SHA256, 600,000 iterations (OWASP 2023 recommendation), 16-byte random salt.
* Stored as:  pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>
* The seed users in the database use an older 3-part format with 120,000 iterations:
      pbkdf2_sha256$<salt>$<digest_hex>
  verify_password() accepts both and needs_rehash() tells the caller to upgrade
  the stored hash after a successful login.
* Comparison uses hmac.compare_digest (constant time).
* Plain-text passwords are never stored, logged or returned.

Sessions
--------
* A random 32-byte token is sent to the browser in an HttpOnly cookie.
* Only the SHA-256 of the token is stored in the `sessions` table, so a leaked
  database cannot be used to hijack sessions."""

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
LEGACY_ITERATIONS = 120_000  # seed users in campus_customs.db
SALT_BYTES = 16

MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128  # cap so huge inputs can't be used to burn CPU
MAX_NAME_LEN = 50
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7


# ------------------------------------------------------------------ passwords
def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_pbkdf2(password, salt, ITERATIONS)}"


def _parse(stored: str) -> tuple[int, str, str] | None:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == ALGORITHM and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    if len(parts) == 3 and parts[0] == ALGORITHM:  # legacy seed format
        return LEGACY_ITERATIONS, parts[1], parts[2]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse(stored)
    if parsed is None:
        return False
    iterations, salt, digest = parsed
    return hmac.compare_digest(_pbkdf2(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    parsed = _parse(stored)
    return parsed is None or parsed[0] < ITERATIONS or len(stored.split("$")) != 4


# Hash used when the email doesn't exist, so login takes the same time either way.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def burn_time(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


# ------------------------------------------------------------------ validation
def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_registration(first: str, last: str, email: str, password: str, confirm: str) -> str | None:
    """Return an error message, or None if valid."""
    if not first.strip() or not last.strip():
        return "First and last name are required."
    if len(first.strip()) > MAX_NAME_LEN or len(last.strip()) > MAX_NAME_LEN:
        return f"Names must be {MAX_NAME_LEN} characters or fewer."
    if not EMAIL_RE.match(normalize_email(email)) or len(email) > 254:
        return "Please enter a valid email address."
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if len(password) > MAX_PASSWORD_LEN:
        return f"Password must be {MAX_PASSWORD_LEN} characters or fewer."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password must include at least one letter and one number."
    if password != confirm:
        return "Passwords do not match."
    return None


# ------------------------------------------------------------------ sessions
def init_sessions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, expires),
    )
    return token


def user_id_for_token(conn: sqlite3.Connection, token: str | None) -> int | None:
    if not token:
        return None
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > datetime('now')",
        (_token_hash(token),),
    ).fetchone()
    return row[0] if row else None


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


# ------------------------------------------------------------------ rate limiting
class LoginRateLimiter:
    """In-memory: max `limit` failed logins per key in `window` seconds."""

    def __init__(self, limit: int = 5, window: int = 15 * 60):
        self.limit, self.window = limit, window
        self.failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        q, cutoff = self.failures[key], time.time() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.limit

    def record_failure(self, key: str) -> None:
        self._prune(key).append(time.time())

    def reset(self, key: str) -> None:
        self.failures.pop(key, None)


# =============================================================================
# Customer memory: chat history persistence (Problem 8)
# =============================================================================
"""Customer memory: chat history persistence for logged-in shoppers (Problem 8).

Table: chat_messages (from the seed DB), extended here with
    context_json TEXT  -- page the shopper was on when they sent the message, e.g.
                          {"path": "/products/basic-hoodie-big-yale", "product_id": "basic-hoodie-big-yale"}
and an index on (user_id, id) for fast "last N messages for this user" reloads.

Guests are never saved. Every query is scoped by the session's user_id."""

HISTORY_FOR_MODEL = 20   # messages replayed to the agent each turn
HISTORY_FOR_WIDGET = 50  # messages shown when the chat panel reloads


def init_memory_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chat_messages)")}
    if "context_json" not in cols:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN context_json TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id, id)")


def load_history(conn: sqlite3.Connection, user_id: int, limit: int = HISTORY_FOR_MODEL) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT id, role, content, products_json, context_json, created_at FROM chat_messages "
        "WHERE user_id = ? AND role IN ('user', 'assistant') ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return list(reversed(rows))


def save_turn(
    conn: sqlite3.Connection,
    user_id: int,
    message: str,
    reply: str,
    cards: list[dict],
    context: dict | None,
) -> None:
    """Save one user message + the assistant reply (call inside a transaction)."""
    conn.execute(
        "INSERT INTO chat_messages (user_id, role, content, products_json, context_json) VALUES (?, 'user', ?, NULL, ?)",
        (user_id, message, json.dumps(context) if context else None),
    )
    conn.execute(
        "INSERT INTO chat_messages (user_id, role, content, products_json, context_json) VALUES (?, 'assistant', ?, ?, NULL)",
        (user_id, reply, json.dumps(cards)),
    )


def delete_history(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,)).rowcount


def shopper_stats(conn: sqlite3.Connection, user_id: int) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS n, MAX(created_at) AS last_at FROM chat_messages WHERE user_id = ? AND role = 'user'",
        (user_id,),
    ).fetchone()
    return {"past_messages": row["n"], "last_chat_at": row["last_at"]}


def context_of(row: sqlite3.Row) -> dict | None:
    try:
        return json.loads(row["context_json"]) if row["context_json"] else None
    except (ValueError, TypeError):
        return None


ROOT = Path(__file__).resolve().parent.parent  # hw4/
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
IMAGES_DIR = DATA_DIR / "products"
CUTOUT_DIR = DATA_DIR / "products_cutout"  # cached transparent-background versions (Problem 10)

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create the sessions table (if missing), clear expired sessions, and prepare chat memory
    # (chat_messages.context_json column + (user_id, id) index).
    conn = sqlite3.connect(DB_PATH)
    with conn:
        init_sessions_table(conn)
        init_memory_schema(conn)
    conn.close()
    yield


app = FastAPI(title="Campus Customs API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Images: catalogue.image_file_path is "products/<file>.jpg" (relative to data/),
# so it is served at /images/<file>.jpg.
# ---- product image cutouts (Problem 10) -------------------------------------------
# 73 of the 102 catalogue photos are transparent PNGs flattened onto black. On first request each
# photo's flat background is removed (flood fill from the border; garments untouched) and the
# result is cached in data/products_cutout/<name>.webp. Needs Pillow; without it, originals are served.
try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

MARK = (255, 0, 255)  # magenta marker for "background"


def cutout(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    work = im.copy()
    # seed the flood fill all around the border wherever the pixel looks like background
    step = max(4, min(w, h) // 60)
    # also seed a few pixels in: some photos have a thin black frame around a white background
    seeds = [(x, y) for x in range(0, w, step) for y in (0, 4, h - 5, h - 1)] + \
            [(x, y) for y in range(0, h, step) for x in (0, 4, w - 5, w - 1)]
    for x, y in seeds:
        px = work.getpixel((x, y))
        if px == MARK:
            continue
        # Decide per seed: some photos are black on two sides and white on the others.
        # Thresholds are deliberately tight so dark navy garments (~(27, 34, 53)) are kept.
        if max(px) <= 12:
            ImageDraw.floodfill(work, (x, y), MARK, thresh=30)
        elif min(px) >= 238:
            ImageDraw.floodfill(work, (x, y), MARK, thresh=30)
    # alpha = 0 where marked; soften the edge by one pixel so it doesn't look jagged
    r, g, b = work.split()
    mask = ImageChops.multiply(
        r.point(lambda v: 255 if v == 255 else 0),
        ImageChops.multiply(g.point(lambda v: 255 if v == 0 else 0), b.point(lambda v: 255 if v == 255 else 0)),
    )
    alpha = ImageChops.invert(mask).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out



def cutout_for(name: str) -> Path | None:
    """Cached cutout for data/products/<name>, creating it on first use. None if not possible."""
    target = CUTOUT_DIR / f"{Path(name).stem}.webp"
    if target.is_file():
        return target
    source = IMAGES_DIR / name
    if Image is None or not source.is_file():
        return None
    try:
        CUTOUT_DIR.mkdir(parents=True, exist_ok=True)
        cutout(source).save(target, "WEBP", quality=86, method=4)
        return target
    except Exception as exc:  # never break images because of the cutout step
        log.warning("cutout failed for %s: %s", name, exc)
        return None


@app.get("/images/{filename}")
def product_image(filename: str) -> FileResponse:
    """Product photo. Serves the transparent cutout (data/products_cutout/<stem>.webp) when it exists,
    (generated on first request), so every product sits cleanly on the ivory storefront;
    otherwise the original JPEG."""
    name = Path(filename).name  # no directory traversal
    cached = cutout_for(name)
    if cached:
        return FileResponse(cached, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})
    original = IMAGES_DIR / name
    if original.is_file() and original.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        return FileResponse(original, headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(status_code=404, detail="Image not found")


# ---------------------------------------------------------------- helpers
def get_db() -> sqlite3.Connection:
    # Read-only connection for catalogue browsing.
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_rw() -> sqlite3.Connection:
    # Read-write connection, used only by auth (and later chat) endpoints.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn




def image_url(image_file_path: str) -> str:
    return "/images/" + Path(image_file_path).name


def short_description(text: str, limit: int = 110) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def product_summary(row: sqlite3.Row) -> dict:
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "category": tools.category_of(row["garment_type"]),  # for the Products filter bar (Problem 9)
        "price": row["price"],
        "short_description": short_description(row["description"]),
        "description": row["description"],
        "colors": json.loads(row["colors"] or "[]"),
        "image_url": image_url(row["image_file_path"]),
        "in_stock": bool(row["total_stock"]),
        "sizes_in_stock": [s for s in SIZE_ORDER if s in (row["sizes_in_stock"] or "").split(",")],
    }


# ---------------------------------------------------------------- routes
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "db": DB_PATH.exists()}


@app.get("/api/products")
def list_products() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COALESCE(SUM(i.quantity), 0) AS total_stock,
                   GROUP_CONCAT(CASE WHEN i.quantity > 0 THEN i.size END) AS sizes_in_stock
            FROM catalogue c
            LEFT JOIN inventory i ON i.product_id = c.product_id
            GROUP BY c.product_id
            ORDER BY c.name
            """
        ).fetchall()
    return [product_summary(r) for r in rows]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        stock_rows = conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
        ).fetchall()

    stock = {r["size"]: r["quantity"] for r in stock_rows}
    sizes = [
        {"size": s, "quantity": stock[s], "in_stock": stock[s] > 0}
        for s in sorted(stock, key=lambda s: SIZE_ORDER.index(s) if s in SIZE_ORDER else 99)
    ]
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "colors": json.loads(row["colors"] or "[]"),
        "tags": json.loads(row["search_tags"] or "[]"),
        "price": row["price"],
        "image_url": image_url(row["image_file_path"]),
        "sizes": sizes,
        "total_stock": sum(stock.values()),
    }


# ---------------------------------------------------------------- auth
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # set true behind HTTPS
login_limiter = LoginRateLimiter()


def public_user(row: sqlite3.Row) -> dict:
    # Never include password_hash in anything sent to the browser or the model.
    return UserOut(
        id=row["id"], first_name=row["first_name"], last_name=row["last_name"],
        name=row["name"], email=row["email"],
    ).model_dump()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,  # not readable from JavaScript
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def current_user(token: str | None) -> dict | None:
    conn = get_db_rw()
    try:
        user_id = user_id_for_token(conn, token)
        if user_id is None:
            return None
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return public_user(row) if row else None
    finally:
        conn.close()


@app.post("/api/auth/register", status_code=201)
def register(req: RegisterRequest, response: Response) -> dict:
    error = validate_registration(
        req.first_name, req.last_name, req.email, req.password, req.confirm_password
    )
    if error:
        raise HTTPException(status_code=400, detail=error)

    first, last = req.first_name.strip(), req.last_name.strip()
    email = normalize_email(req.email)
    conn = get_db_rw()
    try:
        with conn:
            if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                raise HTTPException(status_code=409, detail="An account with that email already exists.")
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
                (f"{first} {last}", email, hash_password(req.password), first, last),
            )
            token = create_session(conn, cur.lastrowid)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    finally:
        conn.close()

    set_session_cookie(response, token)
    return {"user": public_user(row)}


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, response: Response) -> dict:
    email = normalize_email(req.email)
    ip = request.client.host if request.client else "unknown"
    keys = (f"email:{email}", f"ip:{ip}")
    if any(login_limiter.blocked(k) for k in keys):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    invalid = HTTPException(status_code=401, detail="Invalid email or password.")
    if not email or not req.password or len(req.password) > MAX_PASSWORD_LEN:
        raise invalid

    conn = get_db_rw()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            burn_time(req.password)  # same timing as a wrong password
            ok = False
        else:
            ok = verify_password(req.password, row["password_hash"])

        if not ok:
            for k in keys:
                login_limiter.record_failure(k)
            raise invalid  # same message whether the email exists or not

        for k in keys:
            login_limiter.reset(k)
        with conn:
            if needs_rehash(row["password_hash"]):  # upgrade legacy hashes
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password(req.password), row["id"]),
                )
            token = create_session(conn, row["id"])
    finally:
        conn.close()

    set_session_cookie(response, token)
    return {"user": public_user(row)}


@app.post("/api/auth/logout")
def logout(response: Response, cc_session: str | None = Cookie(default=None)) -> dict:
    conn = get_db_rw()
    try:
        with conn:
            delete_session(conn, cc_session)
    finally:
        conn.close()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(cc_session: str | None = Cookie(default=None)) -> dict:
    return {"user": current_user(cc_session)}


# ---------------------------------------------------------------- chat (agent) + customer memory
def cards_from_json(products_json: str | None) -> list[dict]:
    """Saved products_json may be old-style full products or our cards; rebuild cards from ids."""
    try:
        items = json.loads(products_json or "[]")
        ids = [i["product_id"] for i in items if isinstance(i, dict) and "product_id" in i]
    except (ValueError, TypeError):
        ids = []
    return tools.product_cards(ids)


CHAT_RATE_LIMIT = 20  # messages per shopper (or IP for guests) per 60 s
chat_limiter = LoginRateLimiter(limit=CHAT_RATE_LIMIT, window=60)


def shopper_for(conn: sqlite3.Connection, user: dict | None) -> ShopperContext:
    """WHO is chatting, built from the session user + DB (never from the browser)."""
    if not user:
        return ShopperContext(logged_in=False)
    created = conn.execute("SELECT created_at FROM users WHERE id = ?", (user["id"],)).fetchone()
    stats = shopper_stats(conn, user["id"])
    return ShopperContext(
        logged_in=True, first_name=user["first_name"], last_name=user["last_name"], email=user["email"],
        member_since=created["created_at"] if created else None, **stats,
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, cc_session: str | None = Cookie(default=None)) -> ChatResponse:
    """One chat turn: website message -> PydanticAI agent -> reply (+ product cards / page results).

    Logged-in users: history is loaded from chat_messages (with the page each message was sent from)
    and both turns are saved there. Guests: the browser sends recent history; nothing is saved.
    """
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty.")

    user = current_user(cc_session)
    # Safety (Problem 12): per-shopper rate limit, and sensitive data masked before it is saved or sent.
    key = f"user:{user['id']}" if user else f"ip:{request.client.host if request.client else 'unknown'}"
    if chat_limiter.blocked(key):
        raise HTTPException(status_code=429, detail="You're sending messages very quickly. Please wait a moment.")
    chat_limiter.record_failure(key)  # counts every message, not just failures
    message, redactions = redact_sensitive(message)
    page = resolve_page(req.page, req.current_product_id)  # validated against the catalogue
    conn = get_db_rw()
    try:
        shopper = shopper_for(conn, user)
        if user:
            history = [(r["role"], r["content"], context_of(r)) for r in load_history(conn, user["id"])]
        else:
            history = [(h.role, h.content) for h in req.history]
    finally:
        conn.close()

    try:
        response, tools_used = await run_chat(message, shopper, history, page, user["id"] if user else None,
                                              redactions)
    except Exception as exc:  # model/API failure: keep the site working
        log.exception("chat failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Sorry, the shop assistant is unavailable right now. Please try again in a moment.",
        )
    log.info("chat user=%s page=%s tools=%s cards=%d page_results=%s", user["id"] if user else "guest",
             page.path, tools_used, len(response.products), bool(response.page_results))

    if user:
        context = {"path": page.path, "product_id": page.product.product_id if page.product else None}
        conn = get_db_rw()
        try:
            with conn:
                save_turn(conn, user["id"], message, response.reply,
                                 [p.model_dump() for p in response.products], context)
        finally:
            conn.close()
    return response


@app.get("/api/chat/history")
def chat_history(cc_session: str | None = Cookie(default=None)) -> dict:
    """The logged-in user's saved messages, so the widget can restore the conversation on return."""
    user = current_user(cc_session)
    if not user:
        return {"logged_in": False, "messages": []}
    conn = get_db_rw()
    try:
        rows = load_history(conn, user["id"], limit=HISTORY_FOR_WIDGET)
    finally:
        conn.close()
    return {"logged_in": True, "messages": [
        ChatMessageOut(role=r["role"], content=r["content"], created_at=r["created_at"],
                       products=[ProductCard(**c) for c in cards_from_json(r["products_json"])]).model_dump()
        for r in rows
    ]}


@app.delete("/api/chat/history")
def clear_chat_history(cc_session: str | None = Cookie(default=None)) -> dict:
    """Let a logged-in shopper erase their saved chat (privacy)."""
    user = current_user(cc_session)
    if not user:
        raise HTTPException(status_code=401, detail="Log in to manage your chat history.")
    conn = get_db_rw()
    try:
        with conn:
            deleted = delete_history(conn, user["id"])
    finally:
        conn.close()
    return {"deleted": deleted}
