# Frontend ↔ Backend contract

The browser calls same-origin `/api/*`; `next.config.mjs` rewrites it to `BACKEND_URL` (default `http://127.0.0.1:8000`).
All mapping lives in `normalizeResponse()` in `src/lib/api.ts`.

| Backend (`POST /api/verify`) | UI |
|---|---|
| `overallStatus` `passed / issues_found / inconclusive / error` | `all_valid / issues_found or critical / inconclusive / error` |
| issue `severity` `error` on symbol/import/syntax | `critical` |
| issue `severity` `error` on argument | `warning` |
| issue `type` `invalid_symbol / invalid_import / invalid_keyword / excessive_positional_arguments` | `invalid_function / invalid_import / invalid_argument / invalid_argument` |
| top-level `suggestions[]` (line + symbol + original) | attached to the matching issue |
| `verifiedItems[]` | "Verified" list |
| `ai` (`aiStatus: ok`) | Gemma panel: `summary` + `explanation`, `correctedSnippet` |
| `ai` null or `aiStatus` ≠ `ok` | Panel shows "AI explanation temporarily unavailable"; deterministic results are still shown |

`GET /api/libraries` → `[{ "name": "requests", "versions": [...] }]` (sorted newest first in the UI).
Status codes: 400/422 → "couldn't process"; any other failure → "service unavailable".

Offline demo without a backend: `NEXT_PUBLIC_USE_MOCK=true` (only the three example snippets verify).
Never put API keys in `NEXT_PUBLIC_*` variables; the Gemini key belongs in `backend/.env`.
