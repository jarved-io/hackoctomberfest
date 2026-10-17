"""Tests for the Truth-DB-backed snapshots, import/attribute checks, curated hints and AI bridge."""

import json

import pytest

from app.explain_bridge import build_findings, build_registry
from app.knowledge_base import KnowledgeBase
from app.verifier import verify_code

KB = KnowledgeBase()
VERSIONS = ["2.25.1", "2.28.2", "2.31.0", "2.32.3"]


def run(code: str, version: str = "2.31.0"):
    return verify_code(code, "requests", version, KB)


def symbols(resp):
    return {(i.type.value, i.symbol) for i in resp.issues}


# --- data ------------------------------------------------------------------

def test_all_four_versions_available():
    assert KB.list_available_versions("requests") == VERSIONS
    assert KB.list_libraries() == ["requests"]


@pytest.mark.parametrize("version", VERSIONS)
def test_snapshot_loads_and_is_complete(version):
    snap = KB.get_snapshot("requests", version)
    assert snap is not None and snap.snapshot_completeness == "complete"
    assert snap.has_symbol("requests.get") and len(snap.symbols) > 400


def test_curated_dir_is_not_mistaken_for_a_library():
    assert not KB.is_library_supported("curated")


def test_wrong_version_symbol():
    old = run("import requests\nrequests.exceptions.JSONDecodeError\n", "2.25.1")
    new = run("import requests\nrequests.exceptions.JSONDecodeError\n", "2.31.0")
    assert ("invalid_symbol", "requests.exceptions.JSONDecodeError") in symbols(old)
    assert not new.issues


# --- core hallucination scenarios (PRD) -------------------------------------

def test_fake_function_gets_curated_suggestion():
    r = run('import requests\nrequests.fetch("u")\n')
    assert r.overallStatus.value == "issues_found"
    assert ("invalid_symbol", "requests.fetch") in symbols(r)
    assert r.suggestions[0].suggested == "requests.get"


def test_fake_class_suggests_session_not_junk():
    r = run("import requests\nrequests.Client()\n")
    assert [s.suggested for s in r.suggestions][0] == "requests.Session"
    assert all(s.suggested.count(".") == 1 for s in r.suggestions)  # same namespace only


@pytest.mark.parametrize("bad,good", [("timeout_seconds", "timeout"), ("follow_redirects", "allow_redirects")])
def test_fake_argument_suggestions(bad, good):
    r = run(f'import requests\nrequests.get("u", {bad}=1)\n')
    assert r.suggestions[0].original == bad and r.suggestions[0].suggested == good


def test_valid_code_passes():
    r = run('import requests\nr = requests.get("u", params={"q": 1}, timeout=5)\n')
    assert r.overallStatus.value == "passed" and not r.issues


# --- imports & attribute references -----------------------------------------

def test_invalid_from_import():
    r = run("from requests.exceptions import TimeoutError\n")
    assert ("invalid_import", "requests.exceptions.TimeoutError") in symbols(r)
    assert r.suggestions[0].suggested == "requests.exceptions.Timeout"


def test_invalid_attribute_in_except_clause():
    r = run("import requests\ntry:\n    pass\nexcept requests.exceptions.TimeoutError:\n    pass\n")
    assert ("invalid_symbol", "requests.exceptions.TimeoutError") in symbols(r)


@pytest.mark.parametrize("code", [
    "import requests\nrequests.packages.urllib3.disable_warnings()\n",
    "from requests.packages.urllib3.util.retry import Retry\n",
    "import requests.packages.urllib3\n",
    "from requests.adapters import HTTPAdapter\n",
    "import requests\nprint(requests.__version__, requests.codes.ok)\n",
    "from requests import *\n",
])
def test_no_false_invalid_on_real_patterns(code):
    r = run(code)
    assert not [i for i in r.issues if i.severity.value == "error"], r.issues


def test_exception_with_message_is_not_flagged():
    r = run('import requests\nraise requests.RequestException("boom")\n')
    assert not r.issues


# --- AI bridge --------------------------------------------------------------

def test_bridge_builds_findings_and_registry():
    r = run('import requests\nrequests.get("u", timeout_seconds=3)\n')
    findings = build_findings(r)
    assert {"api": "requests.get", "status": "valid"}.items() <= next(f for f in findings if f["status"] == "valid").items()
    bad = next(f for f in findings if f["status"] == "invalid")
    assert bad["argument"] == "timeout_seconds" and bad["closestValid"] == "timeout" and bad["kind"] == "argument"
    reg = build_registry(findings, r, KB)
    assert "timeout" in reg["requests.get"]["arguments"]


def test_pipeline_with_stub_model():
    from ai_module import generate_explanation

    r = run('import requests\nrequests.get("u", timeout_seconds=3)\n')
    findings = build_findings(r)
    reg = build_registry(findings, r, KB)
    reply = json.dumps({
        "summary": "One argument is not valid.", "severity": "error",
        "explanation": "The validator found that timeout_seconds is not accepted; timeout is.",
        "evidence": [{"line": 2, "api": "requests.get", "status": "invalid", "note": ""}],
        "suggestedAlternative": "timeout",
        "correctedSnippet": 'requests.get("u", timeout=3)',
    })
    out = generate_explanation("code", "requests", "2.31.0", findings, reg, client=lambda s, u: reply)
    assert out.aiStatus == "ok" and out.severity == "error" and out.suggestedAlternative == "timeout"


def test_pipeline_degrades_without_api_key(monkeypatch):
    from app.explain_bridge import explain

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    r = run('import requests\nrequests.fetch("u")\n')
    ai = explain("import requests\nrequests.fetch('u')\n", r, KB)
    assert ai["aiStatus"] == "unavailable" and ai["aiError"] == "missing_api_key"
    assert ai["severity"] == "error" and "requests.fetch" in ai["explanation"]


def test_explain_skipped_for_valid_code():
    from app.explain_bridge import explain

    r = run('import requests\nrequests.get("u")\n')
    assert explain("x", r, KB) is None
