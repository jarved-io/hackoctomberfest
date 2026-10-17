# Technical Documentation — API Hallucination Firewall Backend

## 1. Problem Statement

AI code generators (LLMs) sometimes produce Python code that uses incorrect API function names, invalid keyword arguments, or nonexistent library symbols. These errors look syntactically valid but are semantically wrong — the functions or parameters do not exist in the actual library.

Example:

```python
import requests
response = requests.get("https://example.com", timeout_seconds=10)
```

The parameter `timeout_seconds` does not exist in `requests.get()`. The correct parameter is `timeout`. This type of error is difficult to detect by syntax checking alone because it is valid Python — it will only fail at runtime.

## 2. Backend Responsibility

The backend (Member 2's contribution) provides:

- A **safe Python AST parser** that extracts API usage from source code without executing it.
- A **trusted, versioned API reference database** stored as JSON snapshots.
- A **deterministic verification engine** that compares parsed API usage against reference data.
- A **suggestion engine** that proposes corrections using string similarity.
- A **FastAPI HTTP service** exposing the verification logic to the frontend.

The backend does **not**:

- Execute submitted code.
- Use AI models for verification decisions.
- Provide explanations (that is Member 1's Gemma integration).
- Build the frontend (that is Member 3's responsibility).

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                  │
│                     (Member 3)                          │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /api/verify
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Backend                       │
│                   (app/main.py)                         │
│                                                         │
│  ┌─────────────┐  ┌───────────────┐  ┌───────────────┐ │
│  │   Parser     │  │ Knowledge     │  │  Verifier     │ │
│  │ (parser.py)  │→ │ Base          │→ │ (verifier.py) │ │
│  │              │  │ (knowledge_   │  │               │ │
│  │ AST extract  │  │  base.py)     │  │ Deterministic │ │
│  │ No execution │  │               │  │ checks        │ │
│  └─────────────┘  │ JSON snapshots│  └───────┬───────┘ │
│                    └───────────────┘          │         │
│                                      ┌───────▼───────┐ │
│                                      │ Suggestions   │ │
│                                      │(suggestions.py│ │
│                                      │ difflib-based)│ │
│                                      └───────────────┘ │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Reference Data (data/)                     │
│              JSON snapshots per library/version          │
└─────────────────────────────────────────────────────────┘
```

## 4. Request Lifecycle

1. **Frontend** sends `POST /api/verify` with Python source code, library name, and version.
2. **Input validation** — Pydantic validates the request body (size, types, required fields).
3. **Whitespace check** — Empty/whitespace-only code returns an `error` status immediately.
4. **AST Parsing** — `parser.py` builds an AST from the source code (no execution). If the code has syntax errors, returns an `error` status.
5. **Alias map** — The parser builds a mapping from import aliases to canonical module paths.
6. **Snapshot loading** — `knowledge_base.py` loads the versioned JSON snapshot for the requested library/version. If unavailable, returns `inconclusive`.
7. **Call matching** — The verifier identifies which calls in the parsed code are relevant to the target library.
8. **Symbol validation** — Each relevant call is checked against the snapshot's symbol list.
9. **Keyword validation** — Each keyword argument is checked against the symbol's known parameters.
10. **Suggestion generation** — For invalid keywords/symbols, `suggestions.py` finds similar valid alternatives using string similarity.
11. **Status calculation** — The overall status is computed based on the severity of findings.
12. **Response** — A JSON response is returned with issues, verified items, suggestions, and metadata.

## 5. AST Parsing Approach

### Parsing vs. Executing

The parser uses Python's built-in `ast.parse()` function, which converts source code into an Abstract Syntax Tree without executing it. This is fundamentally different from `exec()` or `eval()`, which run the code.

- `ast.parse(code)` — Builds a tree data structure. **Safe.**
- `exec(code)` — Runs the code. **Dangerous.** Never used.

### What the Parser Extracts

| Data | Example | AST Node |
|---|---|---|
| Module imports | `import requests` | `ast.Import` |
| From-imports | `from requests import get` | `ast.ImportFrom` |
| Import aliases | `import requests as req` | `alias.asname` |
| Function calls | `requests.get(url)` | `ast.Call` |
| Keyword arguments | `timeout=5` | `ast.keyword` |
| Positional arg count | 2 args | `len(node.args)` |
| *args usage | `*args` | `ast.Starred` |
| **kwargs usage | `**kwargs` | `keyword.arg is None` |
| Line numbers | Line 3 | `node.lineno` |
| Column offsets | Column 4 | `node.col_offset` |

## 6. Import and Alias Resolution

The parser builds an alias map from import statements:

| Import Statement | Local Name | Canonical Name |
|---|---|---|
| `import requests` | `requests` | `requests` |
| `import requests as req` | `req` | `requests` |
| `from requests import get` | `get` | `requests.get` |
| `from requests import get as fetch` | `fetch` | `requests.get` |

When a call like `req.get(url)` is found, the parser resolves `req` → `requests` using the alias map, producing the canonical name `requests.get`.

**Limitation:** If a call cannot be confidently resolved (e.g., a variable assigned dynamically), it is marked as unresolved rather than guessed.

## 7. Function-Call Extraction

The parser walks the AST looking for `ast.Call` nodes. For each call:

1. Extract the dotted name (e.g., `requests.get`).
2. If the name contains only `ast.Name` and `ast.Attribute` nodes, it can be represented as a string.
3. Complex expressions like `get_client().fetch()` are skipped because the base is a function call, not a name.

## 8. Keyword Argument Extraction

For each `ast.Call` node, the parser iterates over `node.keywords`:

- If `keyword.arg` is a string (e.g., `timeout`), it is a named keyword argument.
- If `keyword.arg` is `None`, it represents `**kwargs` expansion.

The parser also detects `*args` by checking for `ast.Starred` in `node.args`.

## 9. API Reference Data Schema

Reference data is stored as JSON files at `data/<library>/<version>.json`.

```json
{
  "library": "requests",
  "version": "2.31.0",
  "source": {
    "name": "requests official documentation",
    "url": "https://requests.readthedocs.io/en/v2.31.0/api/"
  },
  "snapshotCompleteness": "partial",
  "symbols": {
    "requests.get": {
      "kind": "function",
      "module": "requests",
      "parameters": ["url", "params", "timeout", "...more..."],
      "parameterCompleteness": "verified"
    }
  }
}
```

### Completeness Model

| Value | Meaning |
|---|---|
| `complete` | The snapshot comprehensively covers the API surface. |
| `partial` | Only selected symbols or parameters are represented. |
| `unknown` | The completeness has not been established. |

**Why this matters:** Absence from the JSON file does NOT prove that an API symbol is invalid. If the snapshot is `partial` and a symbol is missing, the verifier reports it as `unresolved` (unknown) — not `invalid`.

## 10. Version Resolution

The knowledge base looks for a file at `data/<library>/<version>.json`. If the file does not exist:

- The verifier checks if any data exists for the library.
- If the library has data but not the requested version, the response lists available versions.
- If the library has no data at all, the response says the library is unsupported.
- No version guessing or fallback is performed.

## 11. Deterministic Verification Rules

### Check 1: Symbol Validation

For each call resolved to the target library:

- If the symbol exists in the snapshot → proceed to keyword validation.
- If the symbol is missing AND the snapshot is `complete` → report `invalid_symbol` (ERROR).
- If the symbol is missing AND the snapshot is `partial` → report `unresolved_symbol` (WARNING).

### Check 2: Keyword Argument Validation

For each keyword argument on a found symbol:

- If the keyword is in the symbol's parameter list → mark as valid.
- If the keyword is NOT in the list AND `parameterCompleteness` is `verified` → report `invalid_keyword` (ERROR).
- If the keyword is NOT in the list AND completeness is `partial`/`unknown` → report `incomplete_reference_data` (WARNING).

### Check 3: Positional Argument Validation

For each call to a recognized symbol:

- If `signatureCompleteness` is `verified` or `complete` and `maxPositionalArguments` is defined:
  - If `call.positional_arg_count > maxPositionalArguments` → report `excessive_positional_arguments` (ERROR).
  - Else → mark positional arguments as valid (`positional_arguments_valid`).
- If `signatureCompleteness` is `partial` or `unknown` and positional arguments are supplied:
  - Report `incomplete_reference_data` (WARNING) so the call results in `inconclusive` rather than a false positive or false negative.

### Check 4: Dynamic Argument Detection

- If `**kwargs` is used → report INFO that dynamic keywords cannot be checked.
- If `*args` is used → report INFO that dynamic positional args cannot be checked.

## 12. Valid, Invalid, and Unknown Result Semantics

| Status | Meaning |
|---|---|
| `passed` | All applicable checks passed. No errors. At most INFO-level notes. |
| `issues_found` | At least one ERROR-severity issue detected. |
| `inconclusive` | WARNING-severity issues exist, or nothing could be verified. |
| `error` | The request could not be processed (syntax error, empty input). |

### Issue Types

| Type | Severity | When |
|---|---|---|
| `invalid_keyword` | error | Keyword not in verified parameter list |
| `excessive_positional_arguments` | error | Positional argument count exceeds verified signature limit |
| `invalid_symbol` | error | Symbol not in complete snapshot |
| `invalid_import` | error | Import contradicts reference data |
| `unsupported_version` | warning | No snapshot for requested version |
| `unresolved_symbol` | warning | Symbol missing from partial snapshot |
| `incomplete_reference_data` | warning/info | Partial data, incomplete signature, or dynamic args |
| `syntax_error` | error | Code cannot be parsed |

## 13. Confidence Limitations

The system cannot:

- Verify libraries without reference data.
- Verify dynamically constructed function calls.
- Resolve aliases assigned through variables (only import aliases).
- Detect semantic errors (e.g., passing the wrong type to a valid parameter).
- Guarantee completeness for partial snapshots.

When the system cannot make a determination, it reports `inconclusive` or `unknown` — never a false `passed` or false `invalid`.

## 14. Suggestion Generation

The suggestion engine uses `difflib.SequenceMatcher` to compare invalid keywords/symbols against known valid alternatives.

- **Threshold:** 60% similarity (configurable).
- **Maximum suggestions:** 3 per item.
- **Symbol comparison:** Compares the function name portion (after the last dot) to keep scores meaningful.
- **All suggestions are backed by evidence** from the reference data.
- **No AI model** is involved.

Example: `timeout_seconds` vs `timeout` → 73% similarity → suggestion generated.

## 15. HTTP API Contract

### GET /health

**Response:** `200 OK`

```json
{"status": "ok", "service": "api-hallucination-firewall", "version": "1.0.0"}
```

### POST /api/verify

**Request body:**

```json
{
  "code": "import requests\nrequests.get('url', timeout_seconds=10)",
  "library": "requests",
  "version": "2.31.0",
  "requirementsText": null
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `code` | string | Yes | — | Python source code (1–50,000 chars) |
| `library` | string | No | `"requests"` | Library to verify against |
| `version` | string | No | `"2.31.0"` | Library version |
| `requirementsText` | string | No | `null` | Optional requirements.txt content |

**Response body:**

```json
{
  "overallStatus": "issues_found",
  "issues": [{"type": "invalid_keyword", "severity": "error", "...": "..."}],
  "verifiedItems": [{"symbol": "requests.get", "checksPassed": ["..."]}],
  "suggestions": [{"original": "timeout_seconds", "suggested": "timeout", "...": "..."}],
  "metadata": {"library": "requests", "version": "2.31.0", "...": "..."}
}
```

## 16. Input Validation

- **Missing code** → 422.
- **Empty code** → 422.
- **Whitespace-only code** → `error` status.
- **Code > 50,000 chars** → 422.
- **Non-string code** → 422.
- **Invalid library** → `inconclusive` (no reference data).
- **Unsupported version** → `inconclusive` with available versions listed.

## 17. Error Handling

- Syntax errors → `error` status with line/column info.
- Missing snapshots → `inconclusive` with warning.
- Malformed JSON data → Logged; returns `None` from knowledge base.
- Unhandled exceptions → Caught by global handler; returns 500 without stack traces.
- Request validation errors → 422 with field-level messages.

## 18. Security Design

- **No code execution.** The parser uses `ast.parse()` only.
- **No eval/exec.** Never used anywhere in the codebase.
- **No subprocess calls** for submitted code.
- **No dynamic imports** of user code.
- **No secrets in responses.** The health endpoint and error handlers do not expose env vars or file paths.
- **CORS is restricted** to configured origins (default: `localhost:3000`).
- **Input size limits** prevent abuse.
- **Error isolation.** A failing request does not corrupt shared state.

## 19. Test Strategy

The test suite contains **97 tests** across 6 files:

| File | Tests | Coverage |
|---|---|---|
| `test_health.py` | 5 | Health endpoint, no-secrets check |
| `test_parser.py` | 25 | Imports, aliases, calls, kwargs, positional counts, errors, empty input |
| `test_knowledge_base.py` | 17 | Loading, missing, malformed, completeness, signatures, caching |
| `test_verifier.py` | 25 | Cases A–K plus 6 positional argument validation regression tests |
| `test_api.py` | 14 | Endpoint contract, size limits, excessive positional args, request independence |
| `test_edge_cases.py` | 11 | No-execution, suggestions, unicode, defaults |

## 20. Known Limitations

1. **Only the `requests` library** has reference data (version 2.31.0).
2. **Snapshot is partial** — `requests.Session` methods and internal classes are not covered.
3. **Import aliases only** — Aliases assigned through variables (`client = requests`) are not resolved.
4. **No semantic type checking** — Valid parameter names are checked but not their expected types.
5. **No cross-module analysis** — Each file is analyzed independently.
6. **No pip install verification** — The system does not check what is actually installed.
7. **String similarity has limits** — Very short or very different strings may not produce useful suggestions.

## 21. Frontend Integration

The backend runs at `http://127.0.0.1:8000` by default.

The frontend should:

1. Send `POST http://127.0.0.1:8000/api/verify` with the JSON body.
2. Parse the JSON response.
3. Display `overallStatus` as the main result.
4. List `issues` with their severity and messages.
5. Show `suggestions` as actionable corrections.
6. Show `verifiedItems` as confirmed-good usages.
7. Display `metadata.warnings` for any caveats.

The backend requires no API key, no authentication, and no Gemma model.

## 22. Future Improvements

- Add reference data for more libraries (e.g., `flask`, `pandas`, `numpy`).
- Support multiple library versions simultaneously.
- Add `requests.Session` method coverage.
- Integrate Gemma model (Member 1) for natural-language explanations.
- Add positional argument count validation.
- Support return-type checking.
- Add a web-based reference data editor.
- Support requirements.txt parsing for automatic version detection.
