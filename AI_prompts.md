# AI Prompts Log — Homework 4

One section per problem. Each section lists the problem number and title, the prompt(s) I typed, and any follow-up prompt. The running site, database writes and screenshots are the evidence for each problem.

---

## Problem 1 — Vibe Coder Prompts

**Prompt:**
> Within AI foundations, we are now working in Homework 4 folder.

**Prompt:**
> Unzip the data.zip file. so you should have data/campus_customs.db and users and data/products/. Create AI_prompts.md and keep it updated as we work.

**Follow-up prompt:**
> We are on Problem 1. Put one section for each problem. Each section must include: 1) problem number and title, 2) at least one prompt I typed, and 3) one follow-up prompt if needed. The running site, database writes and screenshots are the evidence.

---

## Problem 2 — Analyze the database

**Prompt:**
> Problem 1 was just as I described previously. Only to ensure setup is correct. We are now onto Problem 2 - Analyze the database.

**Result:** Inspected `data/campus_customs.db` (schema, row counts, relationships, data quality, chat history) and wrote the findings to `DATABASE_ANALYSIS.md`.

**Follow-up prompt:**
> Please understand and review the fields of each table. Should understand catalogue, inventory and users. Start the file output/harness.md and write down each table and its fields - include one short line why the field matters. We will keep growing this harness file in later problems (models, tools, safety, specs).

**Result:** Created `output/harness.md` with a Data section listing every field of `catalogue`, `inventory`, `users` (plus `chat_messages` for reference), each with a one-line reason why it matters, and placeholder sections for Models, Tools, Safety and Specs.

---

## Problem 3 — Scaffold the React front end

**Prompt:**
> Now onto Problem 3. Scaffold a React + Vite + TypeScript front end for Campus Customs. Put a nav bar at the top that links to the main pages: Home, Products, About Us, Log In, Create Account. Can you pull Campus Customs-style wording from yalebulldogblue.com for Home and About Us but write in own words and not copying original site text.

**Result:** Created `frontend/` (React 19 + Vite + TypeScript + React Router) with a sticky Yale-blue nav bar and routes `/`, `/products`, `/about`, `/login`, `/register`. Home and About Us copy is original writing based on themes from yalebulldogblue.com (officially licensed Yale gear, students/alumni/fans, residential colleges and grad schools, 57 Broadway New Haven). Log In and Create Account forms are UI-only until the back end is added.

**Follow-up prompt:**
> On the Products page, show product images from the catalogue (use the image paths in the database) with basic product info (name, price, short description). Make each product open a single-item page (large image on one side, full product text on the other - description, size, sizes/stock). Clicking a card on Products should take the shopper there. Add a chat interface in the bottom right of the site (a floating chat panel works). It does not need to talk to an agent yet - a stub that will call your backend later is enough for this problem 3. Will need a small API soon to read the database. It is OK to start a simple FastAPI app in backend/main.py just to serve products and images, then grow it into the agent backend in Problem 5.

**Result:** Added `backend/main.py` (FastAPI): `GET /api/products`, `GET /api/products/{id}` (with per-size stock), `/images/*` served from `data/products/`, and a stub `POST /api/chat`. Products page now shows a card grid (image, name, price, short description); each card links to `/products/:productId` with a large image on the left and description, colors, sizes and stock on the right. Added a floating chat panel (bottom right) that posts to the stub endpoint. Vite proxies `/api` and `/images` to port 8000.

---

## Problem 4 — Create account and login

**Prompt:**
> Now onto Problem 4 - Create account and login. Build a normal create-account / login flow. Create account: first name, last name, email, password (confirm password), and log in: email and password. New accounts go into the users table. Make sure to store passwords securely so hackers (human or AI) cannot access them.

**Result:** Added `backend/auth.py` and auth endpoints in `backend/main.py` (`/api/auth/register`, `/login`, `/logout`, `/me`). New accounts are inserted into `users` (`name`, `email`, `first_name`, `last_name`, `password_hash`). Passwords are hashed with PBKDF2-SHA256 (600k iterations, random salt). Sessions use an HttpOnly cookie, and only a SHA-256 of the session token is stored in a new `sessions` table. Also added a generic login error, a dummy hash for unknown emails, rate limiting, and an upgrade of legacy seed hashes on login. Front end: Create Account (first, last, email, password, confirm) and Log In forms, auth context, and a nav bar that shows "Hi, <name> / Log Out" when logged in.

**Follow-up prompt:**
> The seed database already has a test user you can use while building. Email: test@campuscustoms.yale.edu and Password: password. Confirm that can log in as that user and that a brand new account you create also works. Update output/harness.md with how auth works (what you store for a user and how passwords are protected).

**Result:** Verified the test user logs in (and its legacy hash was upgraded to 600k iterations), and created a new account `bulldog.tester@yale.edu` (user id 4) that registers, logs out and logs back in; wrong passwords and duplicate emails are rejected. Added a "How auth works" section to `output/harness.md` (stored fields, hashing, flows, verification results).

---

## Problem 5 — PydanticAI agent backend

**Prompt:**
> Now onto Problem 5 - PydanticAI agent backend. Build the shop chatbot as a PydanticAI agent behind FastAPI, plugged into the front-end chat widget. Put the API app in backend/main.py - the file we run with Uvicorn. Keep the agent as these four files next to it (same idea as Homework 3). backend/prompts/prompt.md - system prompt (grow this same file later); backend/agent.py - agent entry / wiring; backend/tools.py - tools the agent can call; backend/models.py - Pydantic / PydanticAI structured types. In main.py expose a chat route so a message from the website returns a reply from the agent (and whatever else is needed for products / auth). Use AI model API key.

**Result:** Built the agent as four files: `backend/prompts/prompt.md`, `backend/agent.py` (PydanticAI `Agent`, `gpt-5.6-luna` via Portkey with `PORTKEY_API_KEY`, output type `ShopReply`), `backend/tools.py` (`search_products`, `get_product_details`, `check_stock`, `list_categories`, all read-only) and `backend/models.py`. `backend/main.py` now has `POST /api/chat` (runs the agent; saves both turns to `chat_messages` for logged-in users) and `GET /api/chat/history`. The chat widget shows formatted replies with clickable product cards, sends the current product page id, and restores saved chats after login.

**Follow-up prompt:**
> Put Campus Customs voice and safety basics into prompts/prompt.md (will expand tools and safety later). Start or update types in models.py for chat replies / product cards as needed. In output/harness.md, note how the front end talks to FastAPI and how the agent is loaded (prompt file + model). Make sure the backend runs from the backend/ folder like this: uvicorn main:app --reload --port 8000

**Result:** Added a "Voice" section (warm, upbeat-not-salesy, concise, light Yale spirit, honest) with an example and a numbered "Safety basics" section (on-topic, privacy, prompt-injection resistance, no harmful content, don't echo sensitive data, honest about being an AI) to `backend/prompts/prompt.md`. Consolidated types in `backend/models.py` (`ShopReply`, `ProductCard`, `ChatRequest`/`ChatResponse`, `ChatMessageOut`, `ShopperContext`, plus `RegisterRequest`/`LoginRequest`/`UserOut`). Switched backend imports to sibling imports so it runs with `cd backend && uvicorn main:app --reload --port 8000`. Documented the front end ↔ FastAPI flow and agent loading in `output/harness.md`.

---

## Problem 6 — Tools: product info and stock

**Prompt:**
> OK onto Problem 6 - Tools: product info and stock. Agent needs tools to look up real information from campus_customs.db : product description, price, how many are in stock (by size when the customer asks). Agent MUST use the database - should not invent prices or quantities. If a size is out of stock, say so clearly.

**Result:** Expanded `backend/tools.py`: new `find_product` (name → product_id), richer `get_product_details` (description, price, per-size `stock` with `in_stock` / `low_stock` / `out_of_stock` status, totals) and `check_stock` (per-size status plus a plain message like "Size XS … is OUT OF STOCK (0 available). Sizes in stock: …"). In `backend/agent.py`, every tool result feeds a facts ledger, and a `must_use_database` output validator rejects replies whose prices or quantities weren't returned by the DB this turn, or that don't say "out of stock" when a checked size is sold out (`ModelRetry`, then a DB-worded fallback). Updated the prompt's tool rules and documented everything, with offline test results, in `output/harness.md`.

**Follow-up prompt:**
> Expand prompts/prompt.md so the agent knows to call these tools for price and stock questions. Add or update return types in models.py . In output/harness.md, list each tool and explain which model fields you chose for lookup results and why.

**Result:** Added a "Price and stock questions: which tool to call" section to `backend/prompts/prompt.md` (the rule that every price, stock or size question requires a tool call this turn; a 3-step process to get the product_id, call the right lookup and answer from fields only; an intent → tool → fields table; size mapping; three worked examples, including out of stock). Added tool return types to `backend/models.py` (`ProductDetails`, `SizeStockCheck`, `ProductStock`, `FindProductResult`, `SearchResult`, `CategoriesResult`, `ToolError`, plus `SizeStock`, `ProductMatch`, `ProductSearchHit`, `CategorySummary`). `agent.py` now validates every tool result into these models. In `output/harness.md`, each tool is listed with its return type and the reason for every field; all 826 tool outputs from the real DB matched their models.

---

## Problem 7 — Chat search that updates the page

**Prompt:**
> Now onto Problem 7 - Chat search that updates the page. Let's add a new feature to the site - when a customer asks about a type of item - for example "what hoodies do you have?" The agent should search the catalogue and the website should dynamically show those matching items as product cards (image, name, price, short info). This is an API contract: the agent returns structured product matches and then the front end renders them on the website.

**Result:** Defined the contract in `backend/models.py`: the agent's `ShopReply.page_results` = `{heading}` (or null), and the API's `ChatResponse.page_results` = `PageResults {source, heading, query, filters, total_matches, products: ProductMatchCard[]}`, where each card has image, name, price, short description, colors and sizes in stock. `agent.py` remembers the agent's last `search_products` call and `build_page_results()` re-runs it against the DB (`tools.page_matches`, up to 60), so all 27 hoodies appear and every card is real. Front end: `ChatResultsContext`; the chat widget routes to `/products` and notes "Showing N results on the Products page"; the Products page shows a "From your chat" banner (heading, count, filters, "Show all products") and the match cards. Added prompt rules for when to set `page_results`, and documented the contract in `output/harness.md`.

**Follow-up prompt:**
> After the dynamic product cards are loaded by your new feature, make sure the same single-item page behavior that we built for Problem 3 still works - each product card - including the ones the chat just put on the page - should still open that detail view (large image + full info) when clicked. Update prompts/prompt.md and output/harness.md so it is clear how search results reach the page.

**Result:** All card types (catalogue grid, chat-search results on the Products page, cards in the chat bubble) link to the same `/products/:productId` → `ProductDetail` route from Problem 3. Verified offline that 120 page-result cards from 5 searches all resolve through the `GET /api/products/{id}` handler, with matching name, price and image and all 6 sizes. Fixed the round trip: the detail page opens at the top, the back link says "← Back to “<heading>” results", and the Products page restores the scroll position and keeps the chat results (React context). Rewrote the prompt's `page_results` section ("How your search reaches the page", when to set it, when to leave it null) and added an end-to-end step table plus a "single-item page still works" section to `output/harness.md`.

---

## Problem 8 — Customer memory

**Prompt:**
> Now onto Problem 8 - Customer memory. When a shopper is logged in, save their chat history in the database in an appropriate table and reload it when they return. The agent should know who is chatting (name, email) - put that in agent depts (or equivalent clear pattern) and/or tools the agent can call. Also pass enough page context that if someone is on a product page and asks "do you have this in pink?" the agent knows which item they mean. Can put code into the agent context.

**Result:** New `backend/memory.py` saves and reloads logged-in chats in `chat_messages`, adding a `context_json` column (which page each message came from) and a `(user_id, id)` index at startup. History reloads into the widget ("Welcome back, <name>!") and into the agent (last 20, with product-page prefixes); there is a Clear button / `DELETE /api/chat/history`. `ShopDeps` now carries `shopper: ShopperContext` (name, email, member since, past messages), `page: CurrentPage` (browser `PageContext` validated against the DB, with product name, price and colors) and a server-only `user_id`. A dynamic `@agent.instructions` block renders "who is chatting" and "what they are looking at", and the new `get_shopper_profile` tool returns the shopper's own profile and memory. So "do you have this in pink?" on the hoodie page is answered from that product's DB colors. Updated the prompt, models, front end and `output/harness.md`; tested offline on a DB copy.

**Follow-up prompt:**
> Guests can still chat but history only needs to persist for logged-in users. Document in output/harness.md : how user chat history is stored, what customer fields the agent sees and how page context is passed.

**Result:** Confirmed the behavior in code and in an offline test: guests get the full agent, with turns kept only in the browser (last 20 sent per message, nothing written to `chat_messages`), and only `if user:` turns are saved. Rewrote the Problem 8 section of `output/harness.md` into: a guest vs logged-in table; (1) how history is stored (`chat_messages` columns including the new `context_json`, index, write/read/delete lifecycle); (2) the customer fields the agent sees (`ShopperContext` fields with source and rendering, the `get_shopper_profile` extras, what is never shown, and an example context block); (3) how page context is passed (widget → `PageContext` → `resolve_page` validation → `CurrentPage` in deps → instructions, plus a field table and the "this in pink" walkthrough); and the offline test results.

---

## Problem 9 — Usability improvements

**Prompt:**
> Now onto Problem 9 - Usability improvements. Can you propose, decide and implement 2 front end usability improvements and 2 agent / backend usability improvements.

**Result:** Proposed 8 ideas and picked 4 (decision table in `output/harness.md`). **FE-1:** a filter and sort bar on Products (search box, category chips, "in stock in size", price sort), kept in the URL so it survives Back and refresh; cards show sizes in stock. **FE-2:** chat quick-reply chips (page-aware starters plus agent follow-ups) and an "Ask the assistant about this" button on product pages. **BE-1:** `ShopReply.suggestions` structured output, sanitized server-side (no prices or quantities, ≤ 60 characters, max 3, context-aware fallbacks), returned as `ChatResponse.suggestions`. **BE-2:** typo-tolerant `search_products` (difflib against the catalogue vocabulary; "hoddies" → 27 hoodies) reporting `corrections` so the agent says "Showing results for…". Updated the prompt, models, API and docs; checked offline.

**Follow-up prompt:**
> OK can you write output/usability.md as you build this. For each of the improvements, outline what you added and why it helps a Campus Customs shopper. Make sure all improvements actually show up in the running app. Make sure the write up is comprehensive.

**Result:** Wrote `output/usability.md`: the selection rationale (8 ideas → 4); for each improvement, what was added, why it helps a Campus Customs shopper, how it works, where to see it in the app, and its limits; offline test tables; a files-changed list; and a verification section. The front end passes a strict TypeScript check and the backend logic was checked against the real DB. A live in-browser check is pending: the app isn't running yet on this machine and the Chrome extension wasn't connected, so a step-by-step checklist with expected results is included.

---

## Problem 10 — Style the website

**Prompt:**
> Now onto Problem 10 - Style the website. Add creative design so the site feels like a real Campus Customs storefront - fonts, color, hierarchy, motion, product presentation, chat feel. Make it chic and sophisticated. Take your time to produce a unique and innovative style that stands out.

**Follow-up prompt:**
> At the same time write output/design.md - what you changed and why it should help customers stick around and keep buying. Keep it concrete and short.

**Result:** New "Elm City Editorial" design system. Ivory, Yale blue, midnight and brass palette; Fraunces, Manrope and IBM Plex Mono type; numbered editorial sections; hang-tag product cards (sizes with sold-out struck through, price tag, hover tilt and zoom); a home page with live hanging products, a stats strip, silhouette tiles that link to filtered lists, "The Game" band and editor's picks; a product page with cursor zoom, color swatches and a stock-status table; a restyled "Concierge" chat (crest launcher, spring-in panel, typing dots, brass chips); a ticker, scroll-reveal, page transitions and reduced-motion support; and an original CC crest and favicon. Found that 73 of 102 product photos were on black squares, so added `backend/make_cutouts.py` (transparent WebP cutouts in `data/products_cutout/`, originals untouched) and an `/images/{filename}` route that serves them. Wrote `output/design.md`. Type-checks under strict TypeScript; visually checked through static previews built from the real CSS.

---

## Problem 11 — Site testing (app check)

**Prompt:**
> Connect claude in chrome. Now onto Problem 11 - Site testing (app check). Test the live site and document it in output/app_check.html (a page you can double click open). Include clear screenshots and short captions for 1) Chat checking the inventory level of an item (honest stock/price from DB), 2) the dynamic search-result cards appearing after a category question (e.g. hoodies), 3) one of the usability features added in Problem 8. I need to make the HTML super easy to grade: heading for each check, screenshot, one or two sentences on what the screenshot proves. Put the screenshot image files in output/app_check_images/ and link them from app_check.html with relative paths (for example app_check_images/inventory.png).

**Clarification:** check 3 uses a Problem 9 usability feature (confirmed by the user).

**Follow-up prompts:**
> it says my organization does not include access to this feature

> done

**Result:**
- **Test method:** Claude in Chrome is blocked by the organization, so I wrote a Playwright test (headless Chromium, using the Playwright already installed for Homework 2) that drives the live site like a shopper and saves screenshots plus the agent's replies next to the database values.
- **First run:** it found a real bug. In the installed pydantic-ai version `result.usage` is a property, not a method, so every turn ended in a `model_error`. The audit trail showed it, and I fixed it in `agent.py`.
- **Second run:** all checks passed.
  - The L-size tee reply was "$32 … only 2 left" (DB: 2, $32).
  - XS of the baseball crewneck came back "out of stock" (DB: 0).
  - "What hoodies do you have?" put 25 hoodie cards on the Products page, and a card opened its product page.
  - "hoddies" still returned the 25 hoodies with follow-up chips, and tapping one narrowed the page to the 2 bulldog hoodies with correct sizes.
- **Report:** built `output/app_check.html` with a heading, screenshot and what-it-proves sentence per check; images are in `output/app_check_images/` and linked by relative paths.

---

## Problem 12 — Audit trail, safety, finish harness

**Prompt:**
> OK onto Problem 12 - Audit trail, safety, finish harness. Keep an append-only output/audit_trail.json of agent-loop activity (time, tool name, short args/result, stop reason). Do not wipe it between runs. Think of some sensible safety rules to give the agent and put them in prompts/prompt.md Finish output/harness.md so it is clear how the system works. Model fields in models.py and why you chose them, tools and abilities, safety rules and specs (loop limits, result caps, models, how to run front + back).

**Result:**
- **Audit trail:** new `backend/audit.py` writes an append-only `output/audit_trail.json` (atomic append under a lock, never wiped; an unreadable file is moved aside, not deleted). Each chat turn logs `run_start`, each `tool_call` (time, iteration, tool, args ≤ 60 chars, one-line result, status, duration), `validation_retry` / `safety_flag`, and `run_end` (stop reason, requests, tool calls, tokens, cards, page results). The `AuditEvent` model is in `models.py`.
- **Safety in code (`agent.py`, `main.py`):**
  - per-turn tool budget (10 soft / 12 hard) plus `request_limit` 8;
  - card, ID and password text redacted before the model, DB or log see it;
  - output checks: no other people's emails, no internals or secrets, no card numbers, ≤ 1,200 characters;
  - prompt-injection wording flagged in the audit trail;
  - chat rate limit of 20 messages per minute;
  - every run ends with an explicit stop reason, with fallbacks for retries or limits.
- **Prompt:** 13 numbered "Safety rules" in `backend/prompts/prompt.md`, covering honesty, privacy, scope, prompt injection and limits.
- **Harness:** `output/harness.md` now opens with an Overview (architecture, abilities, file map, how to run front and back, a specs-at-a-glance table of every limit and cap), and adds a full `models.py` field-by-field reference with reasons, a safety-rules table (prompt vs code enforcement) and an audit-trail section with an example and offline test results.

---

## Problem 13 — Push to GitHub and submit the URL

**Prompt:**
> Problem 13 - Push to GitHub and submit the URL. Put the code in a folder named hw4 and push it to a public GitHub repository. On the Yale Canvas portal, I need to submit the repo URL (such that link graders can open and clone). Do not put my real .env, campus_customs.db or product images in the GitHub repo. Use .gitignore Include .env.example with placeholders only. I will attach photo of expected file layout next. The agent itself is 4 files under backend/ : prompts/prompt.md, agent.py, tools.py and models.py Read.md should explain how to run the front and back end after placing the data pack.

**Follow-up:** the expected file layout (shared as a screenshot): `hw4/` with `AI_prompts.md`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `frontend/`, `backend/` (`main.py`, `agent.py`, `models.py`, `tools.py`, `prompts/prompt.md`), and `output/` (`harness.md`, `design.md`, `usability.md`, `app_check.html`, `app_check_images/`, `audit_trail.json`); the data pack `data/` (`campus_customs.db`, `products/`) stays local-only.

**Result:**
- **Folder:** moved the project into `hw4/` to match the layout. Merged the helper modules so `backend/` holds exactly the expected files: auth and chat-memory helpers now live in `main.py`, the audit trail in `agent.py`, and the image background cleanup is a lazy, cached step in `main.py`. Moved `requirements.txt` to the root.
- **New files:** `.gitignore` (excludes `.env`, `data/`, `*.db`, images, `node_modules`, `.venv`, caches), `.env.example` (placeholders only), and a grader-facing `README.md` (place the data pack in `hw4/data/`, add the key, run backend and front end).
- **Checks:** a dry-run `git add` lists 43 files, with no `.env`, database, images or `node_modules`, and the real API key string appears in none of them.
- **Push:** the sandbox cannot reach GitHub, so `Push hw4 to GitHub.command` (outside the repo) commits on the Mac, refuses to commit private files, creates or links a **public** repo (GitHub CLI or github.com/new), pushes, and copies the URL for Canvas.
