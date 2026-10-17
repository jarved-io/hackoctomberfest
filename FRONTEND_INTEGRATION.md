# Frontend Integration

All backend calls live in `src/lib/api.ts`. Types: `src/types/verification.ts`. Demo data: `src/lib/demo.ts` (temporary).

## 1. Call
`POST /api/verify` with `Content-Type: application/json`.

## 2. Request
```json
{ "code": "import requests\n...", "library": "requests", "version": "2.31.0" }
```

## 3. Response (what the UI reads)
```json
{
  "overallStatus": "all_valid | issues_found | critical",
  "issues": [{
    "id": "1", "severity": "critical | warning | info",
    "type": "invalid_function | invalid_argument | invalid_import | invalid_class | other",
    "symbol": "requests.get()", "argument": "timeout_seconds", "line": 5,
    "message": "...", "suggestion": { "original": "timeout_seconds", "replacement": "timeout", "description": "Valid argument" },
    "version": "2.31.0", "evidence": "..."
  }],
  "verifiedItems": [{ "symbol": "requests.get()", "kind": "function", "message": "Function exists", "line": 3 }],
  "suggestions": [],
  "checkedCount": 3,
  "explanation": { "text": "...", "correctedCode": "..." },
  "aiAvailable": true
}
```

## 4. Required vs optional
- Required: `issues` (array), `verifiedItems` (array). Per issue: `message`, `symbol`.
- Optional: everything else. `overallStatus` and `checkedCount` are derived if missing. `line` is only displayed if present (never faked).
- If Gemma fails: return the deterministic results with `"aiAvailable": false` (or an `aiError` field). The UI still shows all issues.

## 5. Status codes
`400/422` → "couldn't process" message; any other non-2xx or network failure → "service unavailable".

## 6. Optional: `GET /api/libraries`
Returns `[{ "name": "requests", "versions": ["2.31.0"] }]` (or `{ "libraries": [...] }`). Falls back to requests/2.31.0.

## 7. Connecting the real endpoint (Person 1)
1. Implement `POST /api/verify`. If your field names differ, edit only `normalizeResponse()` in `src/lib/api.ts`.
2. Make sure `NEXT_PUBLIC_USE_MOCK` is unset (or `false`). Keep API keys server-side only; never prefix them with `NEXT_PUBLIC_`.
3. Replacing mock data: set `NEXT_PUBLIC_USE_MOCK=true` for offline demos (it only answers the three example snippets, anything else shows "unavailable"). The example *buttons* only fill the editor with code; delete `src/lib/demo.ts` mock responses when no longer needed.
