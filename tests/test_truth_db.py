import json
import pytest
from tests.fixtures import SNIPPETS
import truth_db as t


def test_snapshots_present_and_versioned():
    v = t.available_versions("requests")
    assert {"2.25.1", "2.31.0"} <= set(v) and len(v) >= 3
    assert v == sorted(v, key=t._vkey)


def test_valid_function_and_kwargs():
    assert t.verify_symbol("requests", "2.31.0", "requests.get")["status"] == "exists"
    r = t.verify_kwargs("requests", "2.31.0", "requests.get", ["params", "timeout", "headers"], n_positional=1)
    assert r["status"] == "ok"


def test_fake_argument_prd_example():
    r = t.verify_kwargs("requests", "2.31.0", "requests.get", ["timeout_seconds"], n_positional=1)
    assert r["status"] == "invalid_arguments"
    assert r["invalid"][0]["argument"] == "timeout_seconds"
    assert r["invalid"][0]["suggestions"][0]["argument"] == "timeout"


def test_session_methods_resolve_forwarded_kwargs():
    assert t.verify_kwargs("requests", "2.31.0", "requests.Session.get", ["verify"])["status"] == "ok"
    assert t.verify_kwargs("requests", "2.31.0", "requests.Session.get", ["bogus"])["status"] == "invalid_arguments"


def test_too_many_positionals():
    assert t.verify_kwargs("requests", "2.31.0", "requests.get", [], n_positional=5)["status"] == "invalid_arguments"


def test_var_kwargs_not_overclaimed():
    # Response.json(**kwargs) forwards to json.loads - we must not claim an arg is invalid
    r = t.verify_kwargs("requests", "2.31.0", "requests.Response.json", ["parse_float"])
    assert r["status"] == "unverifiable_var_kwargs"


def test_unknown_library_and_version_degrade_gracefully():
    assert t.verify_symbol("flask", "3.0", "flask.Flask")["status"] == "unknown_library"
    r = t.verify_symbol("requests", "9.9.9", "requests.get")
    assert r["status"] == "unsupported_version" and "2.31.0" in r["known_versions"]


def test_similarity_fallback_without_curation():
    s = t.suggest("requests", "2.31.0", "requests.sesion")
    assert any(x["symbol"].lower().endswith("session") for x in s)


def test_version_difference_json_decode_error():
    assert t.verify_symbol("requests", "2.25.1", "requests.exceptions.JSONDecodeError")["status"] == "wrong_version"
    assert t.verify_symbol("requests", "2.31.0", "requests.exceptions.JSONDecodeError")["status"] == "exists"


@pytest.mark.parametrize("s", [s for s in SNIPPETS if "symbol" in s], ids=lambda s: s["id"])
def test_fixture_expectations(s):
    if s["expect"] == "invalid_arguments":
        r = t.verify_kwargs("requests", s["version"], s["symbol"], s["bad_args"], n_positional=1)
        assert r["status"] == "invalid_arguments"
        assert r["invalid"][0]["suggestions"][0]["argument"] == s["suggest_arg"]
    else:
        r = t.verify_symbol("requests", s["version"], s["symbol"])
        assert r["status"] == s["expect"]
        if "suggest" in s:
            assert r["suggestions"][0]["symbol"] == s["suggest"]


def test_curated_hints_are_honest():
    """Every 'wrong' name must truly not exist; every 'use' target must truly exist (all versions)."""
    cur = json.loads((t.DATA_DIR / "curated" / "requests.json").read_text())
    for v in t.available_versions("requests"):
        apis = t.load("requests", v)["apis"]
        for wrong, c in cur["symbol_corrections"].items():
            assert wrong not in apis, f"{wrong} exists in {v}; remove from curated"
            assert c["use"] in apis, f"{c['use']} missing in {v}"
        accepted = set()
        for q in ("requests.get", "requests.post"):
            accepted |= set(apis[q]["accepted_arguments"])
        for wrong, c in cur["argument_corrections"].items():
            assert wrong not in accepted, f"{wrong} is a real kwarg in {v}"
            assert c["use"] in accepted
