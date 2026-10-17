# Gemma integration (AI module)

**Location:** `backend/ai_module/`. **Job:** take the *deterministic* verification results and
produce a short, beginner-friendly, validated explanation with Gemma 4. It never decides what is
valid. The validator and trusted API registry are the source of truth.

> **Assumption:** the repo had no backend when this was written, so the module is plain Python
> (needs only `pydantic`). If the backend is TypeScript, use the CLI bridge below.

**Transport:** the client uses the official `google-genai` SDK if it can be imported, otherwise it calls
Google's REST endpoint (`models/{model}:generateContent`, key in the `x-goog-api-key` header) with the
standard library. So `pip install google-genai` is optional. On Windows ARM it often fails to build
`cryptography`; just skip it.

## Call it (already wired in `backend/app/explain_bridge.py`: after deterministic checks, before the response is returned)

```python
from ai_module import generate_explanation

result = generate_explanation(
    code,                      # str: submitted code (treated as untrusted data)
    library,                   # str: "requests"
    version,                   # str: "2.31.0"
    verified_findings,         # list[dict]: one per checked API reference (below)
    verified_api_evidence,     # dict | None: trusted registry entries (below)
)
payload = result.to_dict()     # JSON-ready; put it in your response, e.g. metadata.ai / suggestions
```

It never raises for AI problems (missing key, timeout, bad output). It raises `ValueError` only if
`verified_findings` entries are not dicts or have an invalid `status`.

**TypeScript / other backends:** `echo '{"code","library","version","findings","apiEvidence"}' | python -m ai_module`
prints the result JSON (exit 2 + `{"error":"bad_input"}` on bad input).

## Input

`verified_findings` items (extra keys are ignored; aliases `symbol`, `lineNumber`, `message`,
`closest_valid`/`suggestion` are accepted):

| field | type | notes |
|---|---|---|
| `api` | str, required | e.g. `"requests.get"` |
| `status` | `"valid"` \| `"invalid"` \| `"unverified"`, required | from the deterministic validator |
| `line` | int \| null | 1-based line in `code` |
| `kind` | str \| null | `import`, `function`, `class`, `argument`... |
| `argument` | str \| null | keyword name when `kind == "argument"` |
| `reason` | str | the validator's own explanation |
| `closestValid` | str \| null | validator's closest valid symbol/argument (the only source of suggestions besides the registry) |

`verified_api_evidence`: trusted registry entries keyed by API name, e.g.
`{"requests.get": {"kind": "function", "arguments": ["url", "params", "headers", "timeout"]}}`.
Only the `arguments` list is interpreted by the guardrails; other keys are passed to Gemma and
echoed in `evidence[].registry`.

Example: `requests.get("https://example.com", timeout_seconds=10)` gives two findings, `requests.get`
(valid, function) and `requests.get` (invalid, argument `timeout_seconds`, `closestValid: "timeout"`).

## Output (`ExplanationResult`)

| field | type | notes |
|---|---|---|
| `summary` | str | short result |
| `severity` | `info` \| `warning` \| `error` | **always derived from findings**: any invalid → `error`, any unverified → `warning`, else `info` |
| `explanation` | str | Gemma text if accepted, otherwise generated deterministically |
| `evidence` | list | one item per input finding: `{line, api, kind, argument, status, source: "deterministic_validator", detail, registry}`. Never taken from model text |
| `suggestedAlternative` | str \| null | only if grounded in `closestValid`/registry and an invalid finding exists |
| `correctedSnippet` | str \| null | only if the alternative survived and every `library.*` name and keyword in the snippet is in the registry |
| `correctionIsPartial` | bool | `true` whenever a snippet is returned: it fixes flagged lines only |
| `aiStatus` | `ok` \| `unavailable` \| `invalid_response` \| `skipped` | show an "AI explanation unavailable" state in the UI unless `ok` |
| `aiError` | str \| null | see below |
| `notes` | list[str] | disagreements, dropped suggestions, partial-fix warning |
| `findings` | list | your original findings, unchanged |

## Failure handling

| situation | `aiStatus` / `aiError` | what the caller gets |
|---|---|---|
| no `GEMINI_API_KEY` / `GOOGLE_API_KEY` | `unavailable` / `missing_api_key` | deterministic text + all evidence |
| timeout / 429 / 5xx on the primary model | retried once on the fallback model | if that also fails: `unavailable` / `timeout`, `rate_limited`, `api_error` + deterministic result |
| 400 / 403 / 404 / empty reply | `unavailable` / `api_error`, `empty_response` | not retried (a second model cannot fix these) |
| malformed JSON, wrong types, bad enum | `invalid_response` / `invalid_json` | one repair retry, then deterministic fallback |
| model cites an API/line not in findings | `invalid_response` / `fabricated_evidence` | model text discarded |
| model's status contradicts validator | `invalid_response` / `contradicts_validator` | model text discarded |
| prose mentions unsupplied `library.name` | `invalid_response` / `fabricated_api_name` | model text discarded |
| claims program is correct/safe/bug-free | `invalid_response` / `overclaim` | model text discarded |
| no findings supplied | `skipped` | "No API references were checked", Gemma not called |

Model severity can never lower the deterministic severity (a note records the disagreement).
Known limit: the prose check is conservative, so a model that mentions a real `requests.*` name
missing from the registry is discarded; the deterministic text is still returned.

## Guardrails in code

Untrusted code goes in a delimited `<untrusted_code>` block with closing tags neutralised. The system
prompt is fixed and never includes user text. Snippets are parsed with `ast.parse` only. Submitted
code is never executed. The key is read from the environment, hidden from `repr`, never logged or returned.

## Environment variables

See `.env.example`: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), optional `GEMMA_MODEL`
(default `gemma-4-26b-a4b-it`), `GEMMA_FALLBACK_MODEL` (default: the other Gemma 4 model; `none` disables),
`GEMMA_TIMEOUT_SECONDS` (20, per attempt), `GEMMA_MAX_CODE_CHARS` (20000).
Worst case a request takes about two timeouts. In testing, Google's Gemma 4 endpoints returned intermittent
HTTP 500s and timeouts on both models, which is why the fallback exists. `notes` says when it was used.
`python scripts/diagnose_gemma.py` (run from `backend/`) lists the models your key can use and tests them.
Install: `pip install -r requirements.txt` in `backend/` (`google-genai` is optional).
On failure, the `notes` field includes the HTTP status, e.g. `AI call failed: api_error (HTTP 503)`.

## Tests

```bash
python3 -m unittest discover -s ai_module/tests -t . -v   # run from backend/      # offline, mocked, no key (pytest also works)
```

## Optional live test (one real API call)

```bash
GEMINI_API_KEY=your-key RUN_LIVE_GEMMA=1 python3 -m unittest ai_module.tests.test_live_gemma -v
```

Skipped unless both variables are set. This is the only check of the real SDK call; the offline
tests use a stand-in SDK and a mocked REST call, so run it once before the demo.
