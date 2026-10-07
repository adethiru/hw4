# Campus Customs — HW4 (AI Foundations)

A Campus Customs storefront (React + Vite + TypeScript) with a FastAPI backend and a **PydanticAI shopping agent** ("the Concierge") that answers only from the store database. It checks stock per size, puts search results on the Products page, remembers logged-in shoppers, and writes an append-only audit trail.

```
hw4/
├── AI_prompts.md            # every prompt used, one section per problem
├── requirements.txt         # backend Python packages
├── .env.example             # copy to .env and add your key
├── .gitignore               # keeps .env, data/, images, node_modules out of git
├── README.md
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app: run with  uvicorn main:app --reload --port 8000
│   ├── agent.py             # agent wiring, limits, grounding/safety checks, audit trail
│   ├── models.py            # Pydantic / PydanticAI types
│   ├── tools.py             # read-only database tools the agent can call
│   └── prompts/prompt.md    # system prompt
└── output/
    ├── harness.md           # how the whole system works (start here)
    ├── design.md · usability.md
    ├── app_check.html       # live-site test with screenshots (app_check_images/)
    └── audit_trail.json     # append-only agent-loop log
```

## 1. Place the data pack (not in git)

The database and product photos are **not** in this repo. Unzip the course data pack so that you have:

```
hw4/
└── data/
    ├── campus_customs.db
    └── products/            # the product images referenced by the catalogue
```

If your zip unpacks to `data/…`, unzip it **inside `hw4/`**:

```bash
cd hw4
unzip /path/to/data.zip          # creates hw4/data/campus_customs.db and hw4/data/products/
```

On first start the backend adds two small things to the database: a `sessions` table (logins) and a `context_json` column + index on `chat_messages` (chat memory). It also caches cleaned-up product photos in `data/products_cutout/`.

## 2. Add your API key

```bash
cp .env.example .env
# edit .env and set PORTKEY_API_KEY=...
```

Browsing, product pages and log in / create account work without a key; only the chat needs it.

## 3. Run the backend (terminal 1)

Requires Python 3.10+.

```bash
cd hw4
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd backend
uvicorn main:app --reload --port 8000
```

Check: http://127.0.0.1:8000/api/health returns `{"status": "ok", "db": true}`.

## 4. Run the front end (terminal 2)

Requires Node 18+.

```bash
cd hw4/frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` and `/images` to the backend on port 8000, so both must be running.

## 5. Try it

- **Log in:** test account `test@campuscustoms.yale.edu` / `password`, or create your own account.
- **Products:** filter by category, size in stock and price; click any card for the product page.
- **Chat (bottom right, "Ask the Concierge"):**
  - "What hoodies do you have?" → the Products page fills with hoodie cards.
  - On a product page: "Do you have this in XS?" → honest stock from the database ("out of stock" when it is).
  - "do you have any hoddies?" → typo corrected.
  - Log out and back in → your chat history comes back.
- Agent activity is appended to `output/audit_trail.json`.

## Model and limits (summary)

`gpt-5.6-luna` via Portkey (`PORTKEY_API_KEY`). Per message: ≤ 8 model calls, ≤ 10 tool calls, ≤ 12 search results to the model, ≤ 60 products on the page, replies ≤ 1,200 characters, 20 messages a minute. All details, model fields, tools, safety rules and the audit format are in **`output/harness.md`**.
