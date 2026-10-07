"""Tools the Campus Customs shop agent can call (Problem 5).

Plain Python over the SQLite catalogue, no AI and no framework imports, so each
tool can be tested on its own. agent.py wraps these functions as PydanticAI tools.

Safety rules enforced here, not just in the prompt:
* Read-only DB connection (mode=ro); tools cannot change data.
* No tool reads users.password_hash, sessions or other users' chat history.
* All SQL is parameterized; arguments from the model are validated and capped.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs.db"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
MAX_RESULTS = 12        # per tool call (keeps model context small)
PAGE_MAX_RESULTS = 60   # per page_results (the whole catalogue is 102 products)

# The DB has 22 spellings of garment_type; map them onto 7 shopper-facing categories.
CATEGORIES = ["t-shirt", "long-sleeve shirt", "crewneck", "hoodie", "full-zip hoodie", "quarter-zip", "jacket"]

# Words shoppers use -> words that appear in the catalogue.
SYNONYMS: dict[str, list[str]] = {
    "hoodie": ["hoodie", "hooded"],
    "hoodies": ["hoodie", "hooded"],
    "hood": ["hoodie", "hooded"],
    "tee": ["t-shirt", "t shirt"],
    "tees": ["t-shirt", "t shirt"],
    "tshirt": ["t-shirt", "t shirt"],
    "shirt": ["shirt", "t-shirt"],
    "crew": ["crewneck"],
    "sweatshirt": ["sweatshirt", "crewneck", "hoodie"],
    "sweater": ["sweater", "crewneck", "fleece"],
    "quarter": ["quarter-zip", "1/4 zip", "1-4-zip"],
    "1/4": ["quarter-zip", "1/4 zip"],
    "fleece": ["fleece"],
    "jacket": ["jacket"],
    "grey": ["gray", "grey"],
    "gray": ["gray", "grey"],
    "dan": ["bulldog"],          # Handsome Dan is Yale's bulldog mascot
    "mascot": ["bulldog"],
    "dog": ["bulldog"],
    "bulldogs": ["bulldog"],
    "shorts": ["shorts"],
    "pants": ["pants", "sweatpants"],
    "hats": ["hat", "cap", "beanie"],
    "hat": ["hat", "cap", "beanie"],
}
STOPWORDS = {
    "a", "an", "the", "and", "or", "with", "for", "of", "in", "on", "to", "any", "some", "do", "you",
    "have", "has", "i", "im", "i'm", "me", "my", "want", "need", "looking", "show", "something", "item",
    "items", "yale", "what", "whats", "is", "are", "got", "u", "it", "that", "this", "handsome",
}


# ------------------------------------------------------------------ helpers
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def category_of(garment_type: str) -> str:
    g = garment_type.lower()
    if "quarter-zip" in g:
        return "quarter-zip"
    if "full-zip hooded" in g:
        return "full-zip hoodie"
    if "jacket" in g:
        return "jacket"
    if "hood" in g:
        return "hoodie"
    if "crewneck" in g or "mockneck" in g:
        return "crewneck"
    if "performance shirt" in g or "long-sleeve" in g:
        return "long-sleeve shirt"
    return "t-shirt"


def _image_url(path: str) -> str:
    return "/images/" + Path(path).name


def _stock(conn: sqlite3.Connection, product_id: str) -> dict[str, int]:
    rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()
    stock = {r["size"]: r["quantity"] for r in rows}
    return {s: stock[s] for s in sorted(stock, key=lambda s: SIZE_ORDER.index(s) if s in SIZE_ORDER else 99)}


def _norm_size(size: str | None) -> str | None:
    if not size:
        return None
    s = size.strip().upper().replace("EXTRA ", "X").replace("2XL", "XXL")
    aliases = {"SMALL": "S", "MEDIUM": "M", "LARGE": "L", "XSMALL": "XS", "XLARGE": "XL", "XXLARGE": "XXL"}
    return aliases.get(s.replace(" ", "").replace("-", ""), s)


def _summary(row: sqlite3.Row, stock: dict[str, int]) -> dict:
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "category": category_of(row["garment_type"]),
        "price": row["price"],
        "colors": json.loads(row["colors"] or "[]"),
        "description": row["description"],
        "sizes_in_stock": [s for s, q in stock.items() if q > 0],
        "sizes_out_of_stock": [s for s, q in stock.items() if q == 0],
        "image_url": _image_url(row["image_file_path"]),
    }


def _has(term: str, text: str) -> bool:
    """Whole-word (prefix) match, so 'shorts' doesn't match 'short-sleeve'."""
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None or (
        len(term) > 3 and re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?:s|es)?(?![a-z0-9])", text) is not None
    )


@lru_cache(maxsize=1)
def _vocabulary() -> tuple[str, ...]:
    """Every word that appears in the catalogue (names, ids, tags, descriptions, colors) + synonym keys.

    Cached once per process; the catalogue is read-only for the agent.
    """
    words: set[str] = set(SYNONYMS)
    with _db() as conn:
        for r in conn.execute("SELECT product_id, name, description, colors, search_tags, garment_type FROM catalogue"):
            text = " ".join([r["product_id"].replace("-", " "), r["name"], r["description"], r["colors"],
                             r["search_tags"], r["garment_type"]]).lower()
            words.update(w for w in re.findall(r"[a-z]+", text) if len(w) >= 3)
    return tuple(sorted(words))


def _correct(word: str) -> str | None:
    """Usability (Problem 9): fix a misspelled search word ("hoddie" -> "hoodie"), or None if it's fine."""
    vocab = _vocabulary()
    if (len(word) < 4 or not word.isalpha() or word in STOPWORDS or word in SYNONYMS
            or word in vocab or word.rstrip("s") in vocab):
        return None
    close = difflib.get_close_matches(word, vocab, n=1, cutoff=0.8)
    return close[0] if close else None


def _terms(query: str, corrections: dict[str, str] | None = None) -> list[list[str]]:
    """Split a query into terms; each term is a list of alternative spellings.

    Misspelled words are corrected against the catalogue vocabulary; fixes are written into
    `corrections` so the agent can say "showing results for hoodie".
    """
    words = re.findall(r"[a-z0-9/'-]+", query.lower())
    terms = []
    for w in words:
        w = w.strip("'")
        if w in STOPWORDS or len(w) < 2:
            continue
        fixed = _correct(w)
        if fixed:
            if corrections is not None:
                corrections[w] = fixed
            w = fixed
        alts = SYNONYMS.get(w, [w.rstrip("s") if len(w) > 4 and w.endswith("s") else w])
        terms.append(list(dict.fromkeys(alts + [w])))
    return terms


# ------------------------------------------------------------------ tools
def search_products(
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size: str | None = None,
    sort: str = "relevance",
    limit: int = 8,
    max_results: int = MAX_RESULTS,
) -> dict:
    """Search the catalogue by keywords and optional filters.

    `max_results` caps `limit`: 12 for the model's tool call; the server uses a larger cap
    (PAGE_MAX_RESULTS) when it re-runs the same search to fill the Products page.
    """
    limit = max(1, min(int(limit or 8), max_results))
    size = _norm_size(size)
    if category and category not in CATEGORIES:
        return {"found": False, "error": f"Unknown category '{category}'. Use one of: {', '.join(CATEGORIES)}."}
    if size and size not in SIZE_ORDER:
        return {"found": False, "error": f"Unknown size '{size}'. Sizes are {', '.join(SIZE_ORDER)}."}

    corrections: dict[str, str] = {}
    terms = _terms(query or "", corrections)
    color_terms = SYNONYMS.get(color.lower(), [color.lower()]) if color else []

    with _db() as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()
        scored = []
        for row in rows:
            if category and category_of(row["garment_type"]) != category:
                continue
            if max_price is not None and row["price"] > max_price:
                continue
            if min_price is not None and row["price"] < min_price:
                continue
            colors = " | ".join(json.loads(row["colors"] or "[]")).lower()
            if color_terms and not any(c in colors for c in color_terms):
                continue

            name = row["name"].lower() + " " + row["product_id"].replace("-", " ")
            tags = row["search_tags"].lower()
            desc = row["description"].lower() + " " + row["garment_type"].lower()
            score, matched = 0.0, 0
            for alts in terms:
                s = max(
                    (3 if _has(a, name) else 0) + (2 if _has(a, tags) else 0)
                    + (1 if _has(a, desc) else 0) + (2 if _has(a, colors) else 0)
                    for a in alts
                )
                if s:
                    matched += 1
                    score += s
            if terms and matched == 0:
                continue
            # Prefer products that match more of the query's terms.
            score += 5 * matched
            stock = _stock(conn, row["product_id"])
            if size and stock.get(size, 0) == 0:
                continue
            scored.append((score, row, stock, matched))

    # Keep only products that match as many query terms as the best match does
    # (so "davenport college" returns Davenport, not every college).
    if terms and scored:
        best = max(m for *_, m in scored)
        scored = [t for t in scored if t[3] == best]

    if sort == "price_asc":
        scored.sort(key=lambda t: (t[1]["price"], -t[0]))
    elif sort == "price_desc":
        scored.sort(key=lambda t: (-t[1]["price"], -t[0]))
    else:
        scored.sort(key=lambda t: (-t[0], t[1]["name"]))

    results = [_summary(row, stock) for _, row, stock, _m in scored[:limit]]
    return {
        "query": query,
        "filters": {k: v for k, v in {"category": category, "color": color, "max_price": max_price,
                                       "min_price": min_price, "size": size, "sort": sort}.items() if v},
        "total_matches": len(scored),
        "corrections": corrections,
        "results": results,
    }


LOW_STOCK = 3  # "only N left" threshold


def _size_status(q: int) -> str:
    return "out_of_stock" if q == 0 else "low_stock" if q <= LOW_STOCK else "in_stock"


def _stock_lines(stock: dict[str, int]) -> list[dict]:
    return [{"size": s, "quantity": q, "status": _size_status(q)} for s, q in stock.items()]


def _not_found(product_id: str) -> dict:
    return {
        "found": False,
        "error": f"No product with id '{product_id}'. Use find_product or search_products to get a valid product_id.",
    }


def find_product(name: str) -> dict:
    """Resolve a product the shopper names ("the Davenport crewneck", "basic hoodie big yale") to product_ids."""
    name = (name or "").strip()
    if not name:
        return {"found": False, "error": "Give a product name or id.", "matches": []}
    with _db() as conn:
        rows = conn.execute("SELECT product_id, name, price, garment_type FROM catalogue").fetchall()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    exact = [r for r in rows if r["product_id"] == slug or r["name"].lower() == name.lower()]
    if exact:
        r = exact[0]
        return {"found": True, "exact": True, "matches": [
            {"product_id": r["product_id"], "name": r["name"], "price": r["price"], "category": category_of(r["garment_type"])}]}
    hits = search_products(query=name, limit=5)["results"]
    if not hits:  # fall back to fuzzy name similarity
        names = {r["name"].lower(): r for r in rows}
        close = difflib.get_close_matches(name.lower(), list(names), n=5, cutoff=0.5)
        hits = [{"product_id": names[n]["product_id"], "name": names[n]["name"], "price": names[n]["price"],
                 "category": category_of(names[n]["garment_type"])} for n in close]
    matches = [{k: h[k] for k in ("product_id", "name", "price", "category")} for h in hits]
    return {
        "found": bool(matches),
        "exact": False,
        "matches": matches,
        "note": "Several products match; confirm which one the shopper means." if len(matches) > 1
        else (None if matches else "No product matches that name."),
    }


def get_product_details(product_id: str) -> dict:
    """Description, price, colors and stock for every size of one product, straight from the DB."""
    with _db() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return _not_found(product_id)
        stock = _stock(conn, product_id)
    colors = json.loads(row["colors"] or "[]")
    in_stock = [s for s, q in stock.items() if q > 0]
    out_of_stock = [s for s, q in stock.items() if q == 0]
    return {
        "found": True,
        "product_id": row["product_id"],
        "name": row["name"],
        "category": category_of(row["garment_type"]),
        "garment_type": row["garment_type"],
        "price": row["price"],
        "price_display": f"${row['price']:.2f}",
        "description": row["description"],
        "colors": colors,
        "colors_note": None if colors else "No colors are listed for this product; do not guess.",
        "tags": json.loads(row["search_tags"] or "[]"),
        "stock": _stock_lines(stock),
        "sizes_in_stock": in_stock,
        "sizes_out_of_stock": out_of_stock,
        "total_in_stock": sum(stock.values()),
        "image_url": _image_url(row["image_file_path"]),
        "source": "campus_customs.db (catalogue + inventory)",
    }


def check_stock(product_id: str, size: str | None = None) -> dict:
    """Live stock for one product: one size (with a clear in/out-of-stock message) or every size."""
    raw = size
    size = _norm_size(size)
    if size and size not in SIZE_ORDER:
        return {"found": False, "error": f"Unknown size '{raw}'. Sizes are {', '.join(SIZE_ORDER)}."}
    with _db() as conn:
        row = conn.execute("SELECT name, price FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return _not_found(product_id)
        stock = _stock(conn, product_id)
    in_stock = [s for s, q in stock.items() if q > 0]
    base = {"found": True, "product_id": product_id, "name": row["name"], "price": row["price"],
            "sizes_in_stock": in_stock, "sizes_out_of_stock": [s for s, q in stock.items() if q == 0]}

    if size:
        q = stock.get(size, 0)
        status = _size_status(q)
        if status == "out_of_stock":
            others = f" Sizes in stock: {', '.join(in_stock)}." if in_stock else " No other sizes are in stock either."
            message = f"Size {size} of {row['name']} is OUT OF STOCK (0 available).{others}"
        elif status == "low_stock":
            message = f"Size {size} of {row['name']} is in stock, but only {q} left."
        else:
            message = f"Size {size} of {row['name']} is in stock ({q} available)."
        return {**base, "size": size, "quantity": q, "in_stock": q > 0, "status": status, "message": message}

    if not in_stock:
        message = f"{row['name']} is OUT OF STOCK in every size."
    else:
        message = f"{row['name']}: in stock in {', '.join(in_stock)}" + (
            f"; OUT OF STOCK in {', '.join(base['sizes_out_of_stock'])}." if base["sizes_out_of_stock"] else ".")
    return {**base, "stock": _stock_lines(stock), "total_in_stock": sum(stock.values()), "message": message}


def list_categories() -> dict:
    """What the shop carries: each category with product count and price range."""
    with _db() as conn:
        rows = conn.execute("SELECT garment_type, price FROM catalogue").fetchall()
    cats: dict[str, list[float]] = {}
    for r in rows:
        cats.setdefault(category_of(r["garment_type"]), []).append(r["price"])
    return {
        "categories": [
            {"category": c, "products": len(p), "min_price": min(p), "max_price": max(p)}
            for c, p in sorted(cats.items(), key=lambda kv: CATEGORIES.index(kv[0]))
        ],
        "sizes": SIZE_ORDER,
        "not_carried": ["shorts", "pants", "hats", "accessories", "kids/infant sizes"],
    }


def product_exists(product_id: str) -> bool:
    with _db() as conn:
        return conn.execute("SELECT 1 FROM catalogue WHERE product_id = ?", (product_id,)).fetchone() is not None


def product_cards(product_ids: list[str]) -> list[dict]:
    """Small card data for the chat widget, in the given order, unknown ids dropped."""
    if not product_ids:
        return []
    with _db() as conn:
        marks = ",".join("?" * len(product_ids))
        rows = {r["product_id"]: r for r in conn.execute(
            f"SELECT product_id, name, price, garment_type, image_file_path FROM catalogue WHERE product_id IN ({marks})",
            product_ids)}
    return [
        {"product_id": pid, "name": rows[pid]["name"], "price": rows[pid]["price"],
         "category": category_of(rows[pid]["garment_type"]), "image_url": _image_url(rows[pid]["image_file_path"])}
        for pid in dict.fromkeys(product_ids) if pid in rows
    ]


# ------------------------------------------------------------------ page results (Problem 7)
SEARCH_ARGS = ("query", "category", "color", "max_price", "min_price", "size", "sort")


def short_info(text: str, limit: int = 110) -> str:
    """First ~110 chars of the description, cut at a word boundary."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def page_matches(search_args: dict) -> dict:
    """Re-run a search the agent made (same filters) with a page-sized limit, as product-match cards.

    The agent decides *that* results should go on the page; the products always come from the DB.
    """
    args = {k: search_args.get(k) for k in SEARCH_ARGS if search_args.get(k) not in (None, "")}
    res = search_products(**args, limit=PAGE_MAX_RESULTS, max_results=PAGE_MAX_RESULTS)
    if res.get("found") is False:
        return {"query": args.get("query", ""), "filters": {}, "total_matches": 0, "products": []}
    return {
        "query": res["query"],
        "filters": res["filters"],
        "total_matches": res["total_matches"],
        "products": [
            {
                "product_id": r["product_id"],
                "name": r["name"],
                "category": r["category"],
                "price": r["price"],
                "image_url": r["image_url"],
                "short_description": short_info(r["description"]),
                "colors": r["colors"],
                "sizes_in_stock": r["sizes_in_stock"],
            }
            for r in res["results"]
        ],
    }


# ------------------------------------------------------------------ customer memory + page context (Problem 8)
def product_brief(product_id: str | None) -> dict | None:
    """Name, category, price and colors of one product (for the page context block). None if unknown."""
    if not product_id:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT product_id, name, garment_type, price, colors FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
    if row is None:
        return None
    colors = json.loads(row["colors"] or "[]")
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "category": category_of(row["garment_type"]),
        "price": row["price"],
        "colors": colors,
        "colors_note": None if colors else "No colors are listed for this product; do not guess.",
    }


def get_shopper_profile(user_id: int | None) -> dict:
    """The logged-in shopper's own profile and shopping memory.

    Privacy: only the session's user_id is ever passed in (the model cannot choose it), and only
    safe columns are selected. password_hash and sessions are never read.
    """
    if user_id is None:
        return {"logged_in": False, "note": "The shopper is a guest. Suggest logging in to save chat history."}
    with _db() as conn:
        u = conn.execute(
            "SELECT first_name, last_name, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if u is None:
            return {"logged_in": False, "note": "Unknown user."}
        stats = conn.execute(
            "SELECT COUNT(*) AS n, MIN(created_at) AS first_at, MAX(created_at) AS last_at "
            "FROM chat_messages WHERE user_id = ? AND role = 'user'", (user_id,)
        ).fetchone()
        rows = conn.execute(
            "SELECT products_json FROM chat_messages WHERE user_id = ? AND role = 'assistant' "
            "AND products_json IS NOT NULL ORDER BY id DESC LIMIT 30", (user_id,)
        ).fetchall()
        try:
            ctx_rows = conn.execute(
                "SELECT context_json FROM chat_messages WHERE user_id = ? AND role = 'user' "
                "AND context_json IS NOT NULL ORDER BY id DESC LIMIT 30", (user_id,)
            ).fetchall()
        except sqlite3.OperationalError:  # column not created yet
            ctx_rows = []

    def ids_from(rows, key: str) -> list[str]:
        out: list[str] = []
        for (raw,) in rows:
            try:
                data = json.loads(raw or "null")
            except ValueError:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get(key):
                    out.append(item[key])
        return list(dict.fromkeys(out))

    shown = ids_from(rows, "product_id")[:5]
    viewed = ids_from(ctx_rows, "product_id")[:5]
    return {
        "logged_in": True,
        "first_name": u["first_name"],
        "last_name": u["last_name"],
        "name": u["name"],
        "email": u["email"],
        "member_since": u["created_at"],
        "past_messages": stats["n"],
        "first_chat_at": stats["first_at"],
        "last_chat_at": stats["last_at"],
        "recently_recommended": product_cards(shown),
        "recently_asked_about_on_product_pages": product_cards(viewed),
    }
