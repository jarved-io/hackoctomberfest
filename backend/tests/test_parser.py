"""Tests for the Python AST parser (app.parser)."""

from app.parser import parse_python_code


# ── 1. Ordinary imports ───────────────────────────────────────────────────

def test_ordinary_import():
    result = parse_python_code("import requests")
    assert len(result.imports) == 1
    imp = result.imports[0]
    assert imp.module == "requests"
    assert imp.alias is None
    assert imp.is_from_import is False


def test_multiple_imports():
    code = "import requests\nimport json"
    result = parse_python_code(code)
    modules = [i.module for i in result.imports]
    assert "requests" in modules
    assert "json" in modules


# ── 2. From-imports ───────────────────────────────────────────────────────

def test_from_import():
    result = parse_python_code("from requests import get")
    assert len(result.imports) == 1
    imp = result.imports[0]
    assert imp.module == "requests"
    assert imp.name == "get"
    assert imp.is_from_import is True


def test_from_import_multiple():
    result = parse_python_code("from requests import get, post")
    assert len(result.imports) == 2
    names = {i.name for i in result.imports}
    assert names == {"get", "post"}


# ── 3. Import aliases ────────────────────────────────────────────────────

def test_import_alias():
    result = parse_python_code("import requests as req")
    imp = result.imports[0]
    assert imp.module == "requests"
    assert imp.alias == "req"


def test_from_import_alias():
    result = parse_python_code("from requests import get as fetch")
    imp = result.imports[0]
    assert imp.module == "requests"
    assert imp.name == "get"
    assert imp.alias == "fetch"


# ── 4. Function calls ────────────────────────────────────────────────────

def test_simple_function_call():
    code = "import requests\nrequests.get('https://example.com')"
    result = parse_python_code(code)
    assert len(result.calls) == 1
    assert result.calls[0].function == "requests.get"


def test_method_call_on_alias():
    code = "import requests as req\nreq.get('https://example.com')"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.function == "req.get"
    assert call.resolved_function == "requests.get"


def test_bare_function_from_import():
    code = "from requests import get\nget('https://example.com')"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.function == "get"
    assert call.resolved_function == "requests.get"


def test_bare_aliased_function():
    code = "from requests import get as fetch\nfetch('https://example.com')"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.function == "fetch"
    assert call.resolved_function == "requests.get"


# ── 5. Keyword arguments ─────────────────────────────────────────────────

def test_keyword_arguments_extracted():
    code = "import requests\nrequests.get('url', timeout=5, verify=False)"
    result = parse_python_code(code)
    call = result.calls[0]
    assert "timeout" in call.keyword_arguments
    assert "verify" in call.keyword_arguments


# ── 6. Line and column extraction ─────────────────────────────────────────

def test_line_number():
    code = "import requests\nrequests.get('url')"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.line == 2


def test_column_offset():
    code = "import requests\nrequests.get('url')"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.column == 0


def test_import_line_number():
    code = "import json\nimport requests"
    result = parse_python_code(code)
    req_import = [i for i in result.imports if i.module == "requests"][0]
    assert req_import.line == 2


# ── 7. Nested calls ──────────────────────────────────────────────────────

def test_nested_calls():
    code = "import requests\nprint(requests.get('url'))"
    result = parse_python_code(code)
    functions = {c.function for c in result.calls}
    assert "print" in functions
    assert "requests.get" in functions


# ── 8. Positional arguments ──────────────────────────────────────────────

def test_positional_arg_count():
    code = "import requests\nrequests.get('url', 'extra')"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.positional_arg_count == 2


# ── 9. *args and **kwargs ────────────────────────────────────────────────

def test_starargs_detected():
    code = "import requests\nrequests.get(*args)"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.has_starargs is True


def test_kwargs_detected():
    code = "import requests\nrequests.get(**kwargs)"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.has_kwargs is True


def test_both_star_and_kwargs():
    code = "import requests\nrequests.get('url', *a, **kw)"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.has_starargs is True
    assert call.has_kwargs is True


# ── 10. Malformed Python ─────────────────────────────────────────────────

def test_syntax_error_returns_error():
    result = parse_python_code("def foo(")
    assert result.error is not None
    assert "message" in result.error


def test_syntax_error_includes_line():
    result = parse_python_code("def foo(\n  pass")
    assert result.error is not None
    assert result.error.get("line") is not None


def test_syntax_error_no_calls():
    result = parse_python_code("import requests\nrequests.get(")
    assert result.error is not None
    assert result.calls == []
    assert result.imports == []


# ── 11. Empty source ─────────────────────────────────────────────────────

def test_empty_string():
    result = parse_python_code("")
    assert result.error is None
    assert result.imports == []
    assert result.calls == []


def test_whitespace_only():
    result = parse_python_code("   \n\n  ")
    assert result.error is None
    assert result.imports == []
    assert result.calls == []


# ── 12. Unresolvable calls ───────────────────────────────────────────────

def test_unresolved_call():
    """A call to an unknown name should have resolved_function == None."""
    code = "unknown_module.do_thing()"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.resolved_function is None


def test_complex_expression_call_skipped():
    """Calls like f().method() can't become a dotted name; they are skipped."""
    code = "get_client().fetch('url')"
    result = parse_python_code(code)
    # The outer call (get_client().fetch) cannot be represented;
    # only the inner call (get_client) is captured.
    functions = [c.function for c in result.calls]
    assert "get_client" in functions


# ── 13. Local function collision ──────────────────────────────────────────

def test_local_function_not_resolved_to_library():
    """A local 'get' should NOT resolve to 'requests.get' if not imported."""
    code = "def get(x): return x\nresult = get('hello')"
    result = parse_python_code(code)
    call = result.calls[0]
    assert call.function == "get"
    assert call.resolved_function is None  # Not imported → not resolved
