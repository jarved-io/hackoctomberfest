# API Hallucination Firewall

Verify AI-generated Python code against the **real** API surface of a library version, then explain and fix
the problems in plain English with **Gemma 4**. Verification is deterministic (AST + versioned truth data);
Gemma only *explains* verified evidence and can never change a verdict.

```
Code ─▶ Frontend (Next.js) ─▶ /api/verify ─▶ Backend (FastAPI)
                                              1. parse (ast, never executes code)
                                              2. look up symbols/arguments in Truth DB snapshots
                                              3. verdict: passed | issues_found | inconclusive | error
                                              4. Gemma explanation (guardrailed, optional) ─▶ `ai` field
```

| Folder | What it is |
|---|---|
| `backend/` | FastAPI app (`app/`), Gemma layer (`ai_module/`), snapshots (`data/`), curated hints (`curated/`), tests |
| `frontend/` | Next.js 14 UI; proxies `/api/*` to the backend |
| `truth_db_project/` | Truth DB generator + tests (introspects real `requests` releases with `inspect.signature`) |
| `docs/` | Gemma integration notes, backend technical notes |

Supported today: **Python · `requests` 2.25.1, 2.28.2, 2.31.0, 2.32.3**.

## Run locally

```bash
# 1. backend  (http://127.0.0.1:8000, docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add GEMINI_API_KEY for AI explanations (optional)
uvicorn app.main:app --reload

# 2. frontend (http://localhost:3000)
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

No Gemini key? Everything still works: findings are deterministic and `ai.aiStatus` is `"unavailable"`
with a deterministic explanation. Set `ENABLE_AI_EXPLANATION=false` to skip model calls entirely.

Docker: `docker compose up --build` (frontend :3000, backend :8000).

## API

`POST /api/verify` `{ "code", "library": "requests", "version": "2.31.0", "explain": true }`
returns `overallStatus`, `issues[]`, `verifiedItems[]`, `suggestions[]`, `metadata` and optional `ai`.
`GET /api/libraries` lists libraries and versions. `GET /health` for probes.
Details: `frontend/FRONTEND_INTEGRATION.md`, `docs/gemma-integration.md`.

What is checked: called symbols, keyword arguments, positional-argument counts, `from x import y`
imports, and non-call references such as `except requests.exceptions.TimeoutError`.

## Tests

```bash
cd backend && python -m pytest -q            # backend + ai_module (offline; live Gemma test is skipped)
cd truth_db_project && python -m pytest -q   # truth DB
cd frontend && npm run typecheck && npm run lint && npm run build
```

Live Gemma check (uses your key): `RUN_LIVE_GEMMA=1 GEMINI_API_KEY=... python -m pytest ai_module/tests/test_live_gemma.py -s`.
Refresh snapshots: `cd truth_db_project && python scripts/generate_snapshots.py 2.25.1 2.28.2 2.31.0 2.32.3`
then `cd backend && python scripts/import_truth_db.py`.

## Known limits

* One language/library (Python `requests`). Other libraries need snapshots first.
* Static only: no type inference, so `requests.get(u).json_data` (attribute of a call result) and calls on
  variables (`session.get(...)`) are not resolved. Names that cannot be tied to the library are not flagged.
* Re-export shims (`requests.packages`, `requests.compat`) are treated as opaque, never as "missing".
* Gemma's corrected snippet is a partial fix of the flagged lines, not a verified replacement program.
