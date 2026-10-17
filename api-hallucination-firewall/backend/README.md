# Backend

FastAPI service: deterministic verification + guardrailed Gemma explanations.

```
app/
  main.py            routes: GET /health, GET /api/libraries, POST /api/verify
  parser.py          ast-based extraction of imports, calls, attribute references (no execution)
  knowledge_base.py  loads data/<library>/<version>.json
  verifier.py        symbol / keyword / positional / import / attribute checks
  suggestions.py     curated hints (curated/<library>.json) + same-namespace similarity
  explain_bridge.py  verifier result -> ai_module findings -> `ai` field
  schemas.py         request/response contract
ai_module/           Gemma 4 client, prompt, guardrails (see ../docs/gemma-integration.md)
data/requests/*.json generated snapshots (do not edit; run scripts/import_truth_db.py)
curated/             hint-only mappings (e.g. requests.fetch -> requests.get), never decide existence
scripts/             import_truth_db.py, diagnose_gemma.py
```

Status semantics: `issues_found` = at least one *proven* problem; `inconclusive` = something could not be
verified (unknown version/library, unresolved symbol, nothing to check); `passed` = every applicable check
passed; `error` = unparsable code. The `ai` field never influences these.

Run: `uvicorn app.main:app --reload` · Test: `python -m pytest -q` (offline).
Env vars: see `.env.example`.
