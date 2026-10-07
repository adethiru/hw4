# Campus Customs — Usability Improvements (Problem 9)

This write-up covers the four usability improvements added to the Campus Customs site: two on the **front end** and two on the **agent / backend**. For each one it covers what was added, why it helps a Campus Customs shopper, how it works, where to see it in the running app, and its limits.

| # | Improvement | Side | Shopper problem it solves |
|---|---|---|---|
| FE-1 | Filter, sort and search bar on the Products page | Front end | "There are 102 products; I just want hoodies in my size, cheapest first." |
| FE-2 | Chat quick replies and "Ask the assistant about this" | Front end | "I don't know what to ask the chatbot" / "typing on my phone is slow." |
| BE-1 | Agent-generated follow-up suggestions | Agent | "The bot answered… now what?" Conversations stall after one answer. |
| BE-2 | Typo-tolerant product search | Backend tool | "I typed *hoddie* and it said you don't sell hoodies." |

---

## 1. How the four were chosen

Eight ideas were considered, each judged on how much it helps a real shopper finish a task (find a product, check a size, decide to buy) against its cost and risk to the rules already in place, especially that **every price and stock number must come from the database**.

| Idea | Helps shoppers? | Cost / risk | Decision |
|---|---|---|---|
| Filter, sort and search on Products | High: browsing is the most common task, and works without the chat | Low (client-side) | ✅ FE-1 |
| Chat quick replies + product-page entry point | High: removes the "blank chat box" problem | Low | ✅ FE-2 |
| Agent follow-up suggestions | High: keeps the conversation going toward a decision | Low; sanitized server-side | ✅ BE-1 |
| Typo-tolerant search | High: a typo used to produce a wrong "we don't carry that" | Low (`difflib`, no new dependency) | ✅ BE-2 |
| Streaming replies | Medium (feels faster) | Conflicts with the grounding validator, which must see the whole reply before it's shown | ❌ Not now |
| Size recommendations from height and weight | Medium | No sizing data in the DB, so the agent would have to invent it | ❌ |
| Caching identical questions | Low for shoppers | Stock changes, so answers could go stale | ❌ |
| Dark mode | Low | Cosmetic | ❌ |

The two front-end improvements help shoppers **find** products and **start talking** to the assistant. The two backend improvements make the assistant **easier to keep talking to** and **harder to dead-end**.

---

## 2. FE-1: Filter, sort and search bar on the Products page

### What was added

At the top of **Products** (`/products`):

- **Search box:** "Search: e.g. bulldog, navy, Davenport…". Matches each word against the product name, full description, colors and category. Every word must match, so "navy bulldog" narrows rather than widens. A trailing "s" is ignored ("hoodies" = "hoodie").
- **Category chips:** All · t-shirt · long-sleeve shirt · crewneck · hoodie · full-zip hoodie · quarter-zip · jacket. These are the 7 normalized categories (the database has 22 different spellings of garment type; see `harness.md`). Clicking the active chip again turns it off.
- **"In stock in size" dropdown:** Any size / In stock in XS … XXL. Hides products whose chosen size is sold out.
- **Sort dropdown:** A–Z, Price: low to high, Price: high to low.
- **Result line:** "Showing 25 of 102 products · **Clear filters**".
- **Empty state:** "No products match these filters. Try clearing a filter, or ask the assistant (bottom right)."
- **Sizes on every card:** "In stock: S · M · L · XXL" (or "Currently sold out").
- **Filters in the URL**, e.g. `/products?cat=hoodie&size=M&sort=price_asc`.
- **Back keeps your filters:** "← Back to products" on a product page returns to the same filtered list, at the same scroll position.

### Why it helps a Campus Customs shopper

- **Finding things fast:** a student who wants "a hoodie, size M, cheapest first" gets there in three clicks instead of scrolling 102 cards. Campus Customs has a lot of near-identical items (29 crewnecks, 25 hoodies), so filtering matters more than for a small shop.
- **No dead ends on size:** stock is tracked per size and 145 size slots are sold out. The size filter and the "In stock:" line on each card stop shoppers from falling for an item only to find their size is gone.
- **Budget shoppers:** price sorting makes the $32 tees and the $45 hoodies easy to find, which matters to students.
- **Gift buyers and alumni** can search a residential college or school ("Davenport", "School of Art") directly.
- **Shareable:** a parent can text a link like `/products?cat=quarter-zip&size=L`, and it opens with the same filters.
- **Works without AI:** if the assistant is down (e.g. no API key, model outage), the shop is still fully browsable.

### How it works

| Piece | Detail |
|---|---|
| API | `GET /api/products` (`backend/main.py`) now also returns `category`, `description`, `colors` and `sizes_in_stock`, computed in the existing SQL query with `GROUP_CONCAT(CASE WHEN quantity > 0 THEN size END)`. One request, no extra calls. |
| Filtering | `applyFilters()` in `frontend/src/pages/Products.tsx`, client-side and instant (no request per keystroke). |
| State | `useSearchParams` keeps `q`, `cat`, `size` and `sort` in the URL (`replace: true`, so typing doesn't flood browser history). |
| Back navigation | `frontend/src/navMemory.ts` remembers the last Products query string; `ProductDetail` links back to it. Scroll position is restored per list (from Problem 7). |
| Chat results | When the chat has put results on the page (Problem 7), the chat-results view takes over; "Show all products" returns to the filterable catalogue. |

### Where to see it in the running app

1. Open `http://localhost:5173/products`. The search box, size and sort dropdowns, category chips and "Showing 102 of 102 products" appear above the grid.
2. Click **hoodie**, choose **In stock in M**, and sort **Price: low to high**. The count drops, the cheapest hoodies are first, and the URL changes to `?cat=hoodie&size=M&sort=price_asc`.
3. Type `bulldog`. Only bulldog designs remain.
4. Open a card, then click **← Back to products**. The same filters and scroll position are restored.
5. Click **Clear filters** to get all 102 again.

### Limits

- The search box is literal (no typo fixing). Typos are handled by the assistant's search (BE-2). The empty state points shoppers to the assistant for that reason.
- There's no color dropdown, because color names in the DB are free text ("heather gray", "dusty coral"); the search box covers colors instead.

---

## 3. FE-2: Chat quick replies and "Ask the assistant about this"

### What was added

- **Starter chips** before the first question, chosen for the page:
  - On a product page: *What sizes are in stock?* · *What colors does it come in?* · *Show me similar items*
  - On Products with chat results showing: *Which is the cheapest?* · *Only show ones in size M* · *Any in gray?*
  - Anywhere else: *What hoodies do you have?* · *Show me crewnecks under $60* · *Anything with a bulldog?*
- **Follow-up chips** under the latest assistant reply, written by the agent (BE-1). One tap sends the question.
- **"💬 Ask the assistant about this"** button on every product page, under the size table. It opens the chat and focuses the input. If you've already clicked a size (e.g. M), it pre-fills "Do you have this in M?".
- Chips only show under the **latest** reply and hide while the assistant is thinking, so old chips can't be tapped out of context.

### Why it helps a Campus Customs shopper

- **Removes the blank-box problem:** many shoppers don't know what an AI assistant can do. The starter chips show it: stock by size, colors, finding items, budget searches.
- **Faster on phones:** students shopping between classes can tap instead of typing.
- **Page-aware:** on the Basic Hoodie Big Yale page the chips are about *that* hoodie, and the agent already knows which product "this" is (page context, Problem 8), so the question just works.
- **Easy to find from a product page:** a shopper reading a product page has the most specific questions ("does this run big?", "is M in stock?"). A button right there beats hunting for the floating bubble.
- **Leads toward buying:** chips like "Only show ones in size M" narrow the choice step by step.

### How it works

| Piece | Detail |
|---|---|
| Sending | `ChatWidget.send(text)` is shared by the input box and the chips (`frontend/src/components/ChatWidget.tsx`). |
| Starter chips | `starterChips(onProduct, hasResults)`; mirrors the server's `default_suggestions` so wording is consistent. |
| Follow-up chips | From `ChatResponse.suggestions` (BE-1), stored on each assistant message; only the last message renders them. |
| Opening from other pages | `OPEN_CHAT_EVENT = "cc:open-chat"`; `ProductDetail` dispatches `new CustomEvent("cc:open-chat", {detail: {text}})`, and the widget listens, opens, pre-fills and focuses. |
| Page context | Unchanged from Problem 8: every message carries `{path, product_id, results_heading}`. |

### Where to see it in the running app

1. On the Home page, open the 💬 bubble. Three starter chips sit under the greeting.
2. Tap **What hoodies do you have?**. It sends straight away; the reply arrives with new follow-up chips (and the Products page switches to the hoodie results from Problem 7).
3. Open any product page, click size **M**, then **💬 Ask the assistant about this**. The chat opens with "Do you have this in M?" ready to send.
4. On a product page with an empty chat, the starter chips are the product ones (sizes, colors, similar items).

### Limits

- Chips are suggestions, not menus. Shoppers can always type anything.
- The pre-filled text is only set if a size is selected; otherwise the chat opens with the product chips.

---

## 4. BE-1: Agent-generated follow-up suggestions

### What was added

- The agent's structured output (`ShopReply`, `backend/models.py`) has a new field: **`suggestions: list[str]`**, 2–3 short follow-up questions written in the **shopper's** voice.
- The API response (`ChatResponse`) carries `suggestions`, and the front end renders them as chips (FE-2).
- **Server-side cleanup** in `agent.clean_suggestions()` before anything reaches the browser:
  - trims whitespace and bullet characters, and drops duplicates (case-insensitive);
  - drops anything over **60 characters**;
  - drops suggestions that **quote prices or stock numbers** ("Is it $55?", "Only 2 left?"), because a chip must never plant an ungrounded number. Price *filters* like "under $60" are allowed;
  - caps at **3**;
  - **fallback:** if the model returns none (or all are dropped), `default_suggestions()` supplies page-aware defaults (product page / results on page / general), so there is always a next step.
- **Prompt** (`backend/prompts/prompt.md`, "Quick-reply suggestions"): examples for each situation, e.g. after a list ("Which is the cheapest?"), about one product ("Do you have it in L?"), after an out-of-stock answer ("Any similar hoodies in XS?"), and after "we don't carry that" (a nearby thing we do carry). Empty list for refusals.

### Why it helps a Campus Customs shopper

- **Keeps momentum:** after "We have 27 hoodies…", the natural next steps ("Only ones in size M", "Which is the cheapest?") are one tap away. That is how a good shop assistant behaves.
- **Recovers from bad news:** when a size is out of stock, the suggestions point to alternatives ("Any similar hoodies in XS?") instead of leaving the shopper at a dead end.
- **Shows what the assistant can do** in context, without a help page.
- **Trustworthy:** because chips can't contain prices or quantities, the "every number comes from the database" promise (Problem 6) also holds for suggestions.

### How it works

```
model → ShopReply {reply, product_ids, suggestions, page_results}
      → agent.clean_suggestions(raw, deps, has_page_results)   (sanitize + fallback)
      → ChatResponse.suggestions                               (API contract)
      → ChatWidget chips → tap → send(text)                    (FE-2)
```

### Checked offline (against the real code)

| Input | Output |
|---|---|
| `["Do you have it in M?", "do you have it in M?", "Is it $55?", "Show crewnecks under $60", "Only 2 left?", <80-char string>, "  - Any in gray?  "]` | `["Do you have it in M?", "Show crewnecks under $60", "Any in gray?"]` (duplicate, price, quantity and too-long entries removed) |
| `[]` on the Basic Hoodie Big Yale page | `["What sizes are in stock?", "What colors does it come in?", "Show me similar items"]` |
| `[]` with page results showing | `["Which is the cheapest?", "Only show ones in size M", "Any in gray?"]` |
| `[]` elsewhere | `["What hoodies do you have?", "Show me crewnecks under $60", "Anything with a bulldog?"]` |

### Where to see it in the running app

Ask anything in the chat, e.g. "what hoodies do you have?". Under the reply there are 2–3 chips that fit the answer. Tap one to continue.

---

## 5. BE-2: Typo-tolerant product search ("did you mean")

### What was added

- `search_products` (`backend/tools.py`) now **auto-corrects misspelled words** before searching:
  - builds a **vocabulary** of every word in the catalogue (product names, ids, descriptions, colors, search tags, garment types) plus the synonym keys (e.g. "tee", "grey", "dan"). That's 282 words, cached once per server process;
  - for a query word that isn't in the vocabulary, picks the closest word with `difflib.get_close_matches(cutoff=0.8)`;
  - never changes words that are already valid, stopwords, words under 4 letters, or words containing digits, which keeps false corrections low.
- Search results include **`corrections`**, e.g. `{"hoddies": "hoodies"}` (typed in `models.SearchResult`).
- **Prompt** ("Misspellings"): when `corrections` isn't empty, the agent mentions it lightly ("Showing results for **hoodie**:") so the shopper knows what was searched, without making a fuss about spelling.
- Applies everywhere `search_products` is used: chat answers, `find_product` (which uses search), and the Products page results (Problem 7), which re-run the same search.

### Why it helps a Campus Customs shopper

- **Typos are common in chat**, especially on phones, and Yale names are hard to spell (Davenport, Berkeley, Pierson, Saybrook). Before, "hoddies" matched **0** products, and because the agent must be honest, it would tell the shopper Campus Customs doesn't sell hoodies. That's a wrong answer and a lost sale.
- **No extra round trip:** the shopper gets results immediately instead of being asked "did you mean…?".
- **Transparent:** "Showing results for hoodie" lets the shopper catch a wrong correction.
- **Still honest about what we don't carry:** "gym shorts" isn't corrected into something else and still correctly returns nothing.

### Checked offline (against the real database)

| Shopper typed | Corrected to | Matches | Top result |
|---|---|---|---|
| hoddies | hoodies | 27 | Basic Hoodie Big Yale |
| crewnek | crewneck | 29 | Baseball Left Chest Crewneck |
| davenprot college | davenport | 1 | Davenport College Crewneck |
| quater zip | quarter | 12 | Benjamin Franklin 1/4 Zip |
| fleese jacket | fleece | 7 | Benjamin Franklin Fleece Jacket |
| bulldgo | bulldog | 10 | District Vit Crewneck Vintage Bulldog |
| champian | champion | 4 | Champion Full Zip Hood |
| sweatshrit | sweatshirt | 67 | Baseball Left Chest Crewneck |
| berkley | berkeley | 2 | Berkeley 1/4 Zip |
| vintag | vintage | 6 | District Tri Blend T Shirt Vintage Shield |
| navy hoodie · hoodies · harvard · pierson tee | *(none needed)* | unchanged | — |
| gym shorts | *(none)* | 0 | correctly: we don't carry shorts |

### Where to see it in the running app

In the chat, type **"do you have any hoddies?"**. The reply says it's showing results for hoodies, the Products page fills with the 27 hoodies, and follow-up chips appear.

### Limits

- Only corrects single words (not run-together words like "quarterzip"); synonyms already cover the common ones.
- The Products page search box (FE-1) is literal; typos there are handled by asking the assistant.

---

## 6. Verification

### Done so far (2026-10-07)

| Check | Result |
|---|---|
| Backend logic against the real DB and code: `clean_suggestions`, `default_suggestions`, `search_products` corrections, `/api/products` new fields | ✅ Results in the tables above. `/api/products`: 102 products; categories crewneck 29, t-shirt 25, hoodie 25, quarter-zip 11, jacket 8, full-zip hoodie 2, long-sleeve shirt 2; Baseball Left Chest Crewneck sizes in stock = S, M, L, XXL (matches inventory) |
| Front-end type check: all of `frontend/src` compiled with `tsc --strict` (with stand-in type definitions for React and React Router, because packages can't be installed in the build sandbox) | ✅ No type errors in the app code: props, the API types (`ProductSummary`, `ChatReply.suggestions`, `PageContext`), hooks order and event wiring all check out |
| API ↔ UI contract | ✅ Fields the UI reads (`category`, `sizes_in_stock`, `colors`, `description`, `suggestions`, `corrections`) are produced by the backend code paths above |

### Still to confirm in the running app

The app hasn't been started on this machine yet (no `frontend/node_modules`, no `.venv`), and the Claude in Chrome extension wasn't connected, so these checks still need a live run. Start it with the commands in `README.md` (`cd backend && uvicorn main:app --reload --port 8000`, and `cd frontend && npm install && npm run dev`), then:

| # | Do this | Expected | ✓ |
|---|---|---|---|
| FE-1a | Open `localhost:5173/products` | Search box, size and sort dropdowns, category chips, "Showing 102 of 102 products"; every card has an "In stock: …" line | ☐ |
| FE-1b | Click **hoodie** → **In stock in M** → **Price: low to high** | Fewer cards, cheapest hoodies first, URL `?cat=hoodie&size=M&sort=price_asc` | ☐ |
| FE-1c | Open a card → **← Back to products** | Same filters and scroll position | ☐ |
| FE-1d | Type `zzz` in search | Empty state message + **Clear filters** | ☐ |
| FE-2a | Home → open 💬 | Greeting + 3 starter chips | ☐ |
| FE-2b | Product page → click size **M** → **💬 Ask the assistant about this** | Chat opens, input reads "Do you have this in M?" | ☐ |
| BE-1 | Tap **What hoodies do you have?** | Reply + 2–3 follow-up chips that fit the answer; tapping one sends it | ☐ |
| BE-2 | Type **do you have any hoddies?** | Reply says it's showing results for hoodies; Products page shows 27 hoodies | ☐ |

Screenshots of each row are the evidence for the homework.

## 7. Files changed

| File | Change |
|---|---|
| `backend/main.py` | `/api/products` adds category, description, colors, sizes_in_stock |
| `backend/tools.py` | `_vocabulary()`, `_correct()`, corrections in `_terms()` / `search_products()` |
| `backend/models.py` | `ShopReply.suggestions`, `ChatResponse.suggestions`, `SearchResult.corrections` |
| `backend/agent.py` | `clean_suggestions()`, `default_suggestions()`, suggestions in `run_chat` |
| `backend/prompts/prompt.md` | "Quick-reply suggestions" and "Misspellings" sections |
| `frontend/src/pages/Products.tsx` | Filter bar, category chips, size/sort, URL state, sizes on cards, empty state |
| `frontend/src/navMemory.ts` | Remembers the Products query for Back |
| `frontend/src/pages/ProductDetail.tsx` | "Ask the assistant about this" button; Back goes to the filtered list |
| `frontend/src/components/ChatWidget.tsx` | `send()`, starter and follow-up chips, `cc:open-chat` listener, input focus |
| `frontend/src/api.ts` | `ProductSummary` new fields; `ChatReply.suggestions` |
| `frontend/src/index.css` | Styles for the filter bar, chips and ask button |
