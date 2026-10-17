"""Intentionally hallucinated / valid AI-style snippets with the findings the *whole*
pipeline should produce. Person 2 can import SNIPPETS to drive end-to-end tests;
test_truth_db.py already exercises the truth layer part of each expectation."""

SNIPPETS = [
    dict(id="valid_get", version="2.31.0", expect="ok",
         code='import requests\nr = requests.get("https://example.com", params={"q": 1}, timeout=10)\nprint(r.status_code, r.json())\n'),
    dict(id="fake_function", version="2.31.0", expect="missing", symbol="requests.fetch", suggest="requests.get",
         code='import requests\ndata = requests.fetch("https://example.com")\n'),
    dict(id="fake_argument", version="2.31.0", expect="invalid_arguments", symbol="requests.get",
         bad_args=["timeout_seconds"], suggest_arg="timeout",
         code='import requests\nrequests.get("https://example.com", timeout_seconds=10)\n'),
    dict(id="httpx_style_arg", version="2.31.0", expect="invalid_arguments", symbol="requests.post",
         bad_args=["follow_redirects"], suggest_arg="allow_redirects",
         code='import requests\nrequests.post(url, json=x, follow_redirects=True)\n'),
    dict(id="fake_method", version="2.31.0", expect="missing", symbol="requests.Response.json_data",
         suggest="requests.Response.json",
         code='import requests\nrequests.get(u).json_data\n'),
    dict(id="fake_class", version="2.31.0", expect="missing", symbol="requests.Client", suggest="requests.Session",
         code='import requests\nc = requests.Client()\n'),
    dict(id="wrong_import", version="2.31.0", expect="missing", symbol="requests.exceptions.TimeoutError",
         suggest="requests.exceptions.Timeout",
         code='from requests.exceptions import TimeoutError\n'),
    # version-related: JSONDecodeError was added in requests 2.27
    dict(id="wrong_version_old", version="2.25.1", expect="wrong_version", symbol="requests.exceptions.JSONDecodeError",
         code='import requests\ntry:\n    requests.get(u).json()\nexcept requests.exceptions.JSONDecodeError:\n    pass\n'),
    dict(id="right_version_new", version="2.31.0", expect="exists", symbol="requests.exceptions.JSONDecodeError",
         code='import requests\ntry:\n    requests.get(u).json()\nexcept requests.exceptions.JSONDecodeError:\n    pass\n'),
    # edge cases the API layer must survive (truth layer is not involved)
    dict(id="malformed_python", version="2.31.0", expect="parse_error", code='import requests\nrequests.get(\n'),
    dict(id="empty_input", version="2.31.0", expect="empty", code=''),
    dict(id="ambiguous_symbol", version="2.31.0", expect="ambiguous",
         code='from mylib import get\nget("x", timeout_seconds=3)\n',
         note="`get` is not provably requests.get - validator must NOT flag it."),
]
