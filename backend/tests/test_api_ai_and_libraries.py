"""HTTP-level tests for /api/libraries and the optional ``ai`` field."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_libraries_endpoint():
    data = client.get("/api/libraries").json()
    assert data[0]["name"] == "requests"
    assert {"2.25.1", "2.31.0"} <= set(data[0]["versions"])


def test_verify_all_four_versions():
    for v in ("2.25.1", "2.28.2", "2.31.0", "2.32.3"):
        resp = client.post("/api/verify", json={"code": "import requests\nrequests.get('u')", "version": v})
        assert resp.status_code == 200 and resp.json()["overallStatus"] == "passed"


def test_ai_is_null_when_disabled_in_tests():
    resp = client.post("/api/verify", json={"code": "import requests\nrequests.fetch('u')"})
    body = resp.json()
    assert body["overallStatus"] == "issues_found"
    assert body["ai"] is None  # ENABLE_AI_EXPLANATION=false via tests/conftest.py


def test_explain_false_is_accepted():
    resp = client.post("/api/verify", json={"code": "import requests\nrequests.fetch('u')", "explain": False})
    assert resp.status_code == 200


def test_unknown_version_is_inconclusive_not_500():
    resp = client.post("/api/verify", json={"code": "import requests\nrequests.get('u')", "version": "9.9.9"})
    assert resp.status_code == 200 and resp.json()["overallStatus"] == "inconclusive"
