# API Hallucination Firewall — Backend Service

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-orange.svg)](https://docs.pydantic.dev/)
[![Tests](https://img.shields.io/badge/Tests-97%20passed-brightgreen.svg)](tests/)

Deterministic verification engine and HTTP backend for the **API Hallucination Firewall** hackathon project.

---

## 1. Project Overview

### What the Backend Does
The **API Hallucination Firewall** detects hallucinated, obsolete, or incorrect Python API usage in AI-generated code. It parses Python source code into an Abstract Syntax Tree (AST), extracts imports, function calls, keyword arguments, and positional arguments, and compares them against trusted, versioned reference data.

For example, when an AI model generates:
```python
import requests
response = requests.get("https://example.com", timeout_seconds=10)
```
The backend parses the code safely, flags that `timeout_seconds` is not a valid parameter for `requests.get()`, cites the verified reference documentation as evidence, and suggests `timeout`.

Similarly, when code supplies excessive positional arguments:
```python
import requests
response = requests.get('https://example.com', None, None, None)
```
The verifier flags that `requests.get` accepts at most 2 positional arguments (`url`, `params`), reports an error with `excessive_positional_arguments`, and provides reference evidence.

### Why the Project Exists
LLM code generators frequently invent ("hallucinate") plausible-sounding parameter names (such as `timeout_seconds`, `retry_count`, or `auth_token`) or pass invalid positional arguments. Because the code is syntactically valid Python, static syntax checkers will not catch the error—it fails only at runtime. This service provides a fast, deterministic guardrail before code execution.

### Team Role: Member 2 — Backend & Verification Lead
As **Member 2**, this repository contains the complete backend and verification system:
- Safe Python AST parser (no dynamic execution).
- Versioned API reference database loader with explicit completeness semantics and signature metadata.
- Deterministic verification engine for symbols, keyword arguments, and positional arguments.
- Evidence-backed string-similarity suggestion engine.
- FastAPI REST service exposing `GET /health` and `POST /api/verify`.
- Automated test suite (97 unit, integration, and regression tests).
- Frontend integration contract and documentation.

*Note: Member 1 handles the Gemma LLM explanation layer, and Member 3 handles the Next.js frontend.*

---

## 2. Architecture & Technology Stack

### Technology Stack
- **Language**: Python 3.11+ (tested on Python 3.13)
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/)
- **AST Parsing**: Python standard library `ast` module (zero code execution)
- **Similarity Matching**: Python standard library `difflib.SequenceMatcher`
- **Testing**: [Pytest](https://docs.pytest.org/) and `httpx` / Starlette `TestClient`

### Architecture Diagram
```
                     ┌───────────────────────────────┐
                     │   Next.js Frontend (Member 3) │
                     └───────────────┬───────────────┘
                                     │ POST /api/verify
                                     ▼
                     ┌───────────────────────────────┐
                     │         FastAPI Server        │
                     │          (app/main.py)        │
                     └───────┬───────────────┬───────┘
                             │               │
        ┌────────────────────▼──┐         ┌──▼────────────────────┐
        │    Safe AST Parser    │         │     Knowledge Base    │
        │    (app/parser.py)    │         │(app/knowledge_base.py)│
        │  • Imports & aliases  │         │  • Versioned snapshots│
        │  • Dotted calls       │         │  • Completeness state │
        │  • Keyword args       │         │  • Provenance URLs    │
        │  • Positional counts  │         └───────────┬───────────┘
        │  • *args / **kwargs   │                     │
        └────────────────────┬──┘                     │
                             │                        │
                             └───────────┬────────────┘
                                         ▼
                     ┌───────────────────────────────┐
                     │  Deterministic Verifier Engine│
                     │       (app/verifier.py)       │
                     │  • Symbol existence check     │
                     │  • Parameter validation       │
                     │  • Dynamic argument warnings  │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │       Suggestion Engine       │
                     │     (app/suggestions.py)      │
                     │  • difflib similarity scoring │
                     │  • Reference-backed evidence  │
                     └───────────────────────────────┘
```

---

## 3. Directory Structure

```
backend/
├── app/
│   ├── __init__.py           # Package marker
│   ├── config.py             # Settings, CORS, limits, metadata
│   ├── schemas.py            # Pydantic request/response models & enums
│   ├── parser.py             # Safe AST parsing & alias resolution
│   ├── knowledge_base.py     # Versioned JSON reference data loader
│   ├── verifier.py           # Deterministic verification engine
│   ├── suggestions.py        # Evidence-backed string similarity suggestions
│   └── main.py               # FastAPI app, endpoints, error handlers, CORS
├── data/
│   └── requests/
│       └── 2.31.0.json       # Reference API snapshot for requests 2.31.0
├── tests/
│   ├── __init__.py           # Test package marker
│   ├── test_health.py        # Health endpoint & security tests
│   ├── test_parser.py        # AST parser unit tests (13 test cases)
│   ├── test_knowledge_base.py# Snapshot loader & caching tests
│   ├── test_verifier.py      # Core verification test suite (Cases A–K)
│   ├── test_api.py           # HTTP contract & size limit tests (Cases M, N, O)
│   └── test_edge_cases.py    # Side-effect prevention & safety tests (Case L)
├── .env.example              # Configurable environment variable template
├── .gitignore                # Excludes .venv, __pycache__, .env, test caches
├── pytest.ini                # Pytest discovery and output flags
├── requirements.txt          # Direct backend dependencies
├── IMPLEMENTATION_TASKS.md   # Implementation checklist and verification audit
├── GITHUB_COMMIT_GUIDE.md    # Step-by-step Git feature branch commit guide
├── TECHNICAL_DOCUMENTATION.md# In-depth architectural and design document
└── README.md                 # This primary documentation file
```

---

## 4. Setup and Installation (macOS / zsh)

### Step 1: Check Python Version
Ensure you have Python 3.11 or later installed:
```bash
python3 --version
```

### Step 2: Navigate to Backend Directory
```bash
cd "/Users/manojmhegde/Coding/Hactober Fest/api-hallucination-firewall/backend"
```

### Step 3: Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables (Optional)
```bash
cp .env.example .env
```
Default values allow local frontend communication at `http://localhost:3000` and `http://127.0.0.1:3000`.

---

## 5. Running the Service

### Start the Development Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Interactive API Documentation
Once running, open your browser to:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 6. Running the Automated Test Suite

Execute the full suite of **97 tests**:
```bash
pytest
```
Or with verbose output:
```bash
python -m pytest tests/ -v
```

All 97 tests pass without errors or failures, verifying:
- **`test_health.py`** (5 tests): Health check responses, headers, and secret leakage prevention.
- **`test_parser.py`** (25 tests): Imports, aliases (`import ... as`, `from ... import ... as`), calls, keywords, positional counts, `*args`, `**kwargs`, syntax errors, and whitespace.
- **`test_knowledge_base.py`** (17 tests): Snapshot loading, caching, version fallback, malformed JSON handling, and signature/parameter completeness metadata.
- **`test_verifier.py`** (25 tests): Valid calls, invalid keywords, suggestions, missing symbols, local collisions, version checks, and positional argument validation (single arg, multiple args, excessive positional args, keyword args, incomplete signature metadata, and aliased imports).
- **`test_api.py`** (14 tests): Request validation, size limits (max 50,000 characters), excessive positional arguments endpoint verification, 422 handlers, and state isolation between requests.
- **`test_edge_cases.py`** (11 tests): Prevention of code execution (dangerous code containing `os.system` or `exec` is parsed safely without execution).

---

## 7. API Reference & Contract

### 1. Health Check
`GET /health`

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "service": "api-hallucination-firewall",
  "version": "1.0.0"
}
```

---

### 2. Verify Python Code
`POST /api/verify`

**Request Body**:
```json
{
  "code": "import requests\nresponse = requests.get('https://example.com', timeout_seconds=10)",
  "library": "requests",
  "version": "2.31.0",
  "requirementsText": null
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `code` | `string` | Yes | — | Python source code (1 to 50,000 characters) |
| `library` | `string` | No | `"requests"` | Target package name to verify against |
| `version` | `string` | No | `"2.31.0"` | Target package version |
| `requirementsText` | `string` | No | `null` | Optional requirements.txt file contents |

**Example Response (`200 OK`)**:
```json
{
  "overallStatus": "issues_found",
  "issues": [
    {
      "type": "invalid_keyword",
      "severity": "error",
      "message": "The keyword argument 'timeout_seconds' is not listed in the verified API reference for 'requests.get'.",
      "line": 2,
      "column": 11,
      "symbol": "requests.get",
      "argument": "timeout_seconds",
      "evidence": {
        "library": "requests",
        "version": "2.31.0",
        "knownArguments": [
          "url", "params", "data", "json", "headers", "cookies",
          "files", "auth", "timeout", "allow_redirects", "proxies",
          "hooks", "stream", "verify", "cert"
        ],
        "referenceSource": "https://requests.readthedocs.io/en/v2.31.0/api/",
        "parameterCompleteness": "verified"
      }
    }
  ],
  "verifiedItems": [],
  "suggestions": [
    {
      "line": 2,
      "symbol": "requests.get",
      "original": "timeout_seconds",
      "suggested": "timeout",
      "reason": "The verified API reference lists 'timeout' as a supported parameter (similarity: 64%)."
    }
  ],
  "metadata": {
    "library": "requests",
    "version": "2.31.0",
    "checksPerformed": [
      "import_analysis",
      "symbol_validation",
      "keyword_validation"
    ],
    "warnings": [],
    "snapshotCompleteness": "partial"
  }
}
```

---

## 8. Status & Completeness Semantics

The firewall strictly avoids binary oversimplification:
- **`overallStatus`**:
  - `passed`: All inspected calls matched verified reference data with no errors.
  - `issues_found`: Confirmed errors detected (e.g. invalid keyword argument on a verified function).
  - `inconclusive`: Code uses symbols or libraries outside the verified reference dataset, or reference data is partial.
  - `error`: Code contains syntax errors or empty submissions.
- **Absence $\neq$ Invalidity**:
  If reference data has `snapshotCompleteness: "partial"`, a symbol not found in the snapshot produces an `unresolved_symbol` warning (`inconclusive`), **not** a false `invalid_symbol` error.

---

## 9. Security Design

1. **No Code Execution**: Submitted code is processed strictly via `ast.parse()`. Neither `eval()`, `exec()`, `importlib`, nor `subprocess` is ever called on user code.
2. **Leakage Prevention**: Exception handlers catch unexpected errors and return uniform 500 JSON payloads without stack traces or internal filesystem paths.
3. **CORS Boundary**: Defaults to restricting origins to `http://localhost:3000` and `http://127.0.0.1:3000`. Configurable via `CORS_ORIGINS`.
4. **Denial-of-Service Protection**: Request source code is limited to 50,000 characters by Pydantic validators.

---

## 10. Current Limitations & Scope

- **Supported Reference Library**: `requests` version `2.31.0`.
- **API Surface**: Top-level convenience functions (`requests.get`, `post`, `put`, `patch`, `delete`, `head`, `options`, `request`). Session objects and adapters are not covered in this initial snapshot.
- **Dynamic Usage**: Usages like `**kwargs` or `*args` cannot be evaluated statically and trigger informational warnings.
- **Language**: Python only.

---

## 11. Companion Documents

- [TECHNICAL_DOCUMENTATION.md](file:///Users/manojmhegde/Coding/Hactober%20Fest/api-hallucination-firewall/backend/TECHNICAL_DOCUMENTATION.md): Deep-dive into AST traversal, symbol resolution, and verification rules.
- [GITHUB_COMMIT_GUIDE.md](file:///Users/manojmhegde/Coding/Hactober%20Fest/api-hallucination-firewall/backend/GITHUB_COMMIT_GUIDE.md): Git commit-by-commit instructions for pushing to `feature/backend` in a shared hackathon repository.
- [IMPLEMENTATION_TASKS.md](file:///Users/manojmhegde/Coding/Hactober%20Fest/api-hallucination-firewall/backend/IMPLEMENTATION_TASKS.md): Task tracking checklist and verification records.
