"""Tests for the POST /api/verify endpoint contract (Cases M, N, O)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Case M: API endpoint contract
# ---------------------------------------------------------------------------

class TestEndpointContract:
    """Verify that /api/verify returns the expected structure and HTTP codes."""

    def test_returns_200_for_valid_request(self):
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url', timeout=5)",
            "library": "requests",
            "version": "2.31.0",
        })
        assert resp.status_code == 200

    def test_response_has_required_fields(self):
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url')",
        })
        data = resp.json()
        assert "overallStatus" in data
        assert "issues" in data
        assert "verifiedItems" in data
        assert "suggestions" in data
        assert "metadata" in data

    def test_metadata_structure(self):
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url')",
        })
        meta = resp.json()["metadata"]
        assert "library" in meta
        assert "version" in meta
        assert "checksPerformed" in meta
        assert "warnings" in meta

    def test_issue_structure_when_present(self):
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url', timeout_seconds=10)",
        })
        data = resp.json()
        issues = data["issues"]
        kw_issues = [i for i in issues if i["type"] == "invalid_keyword"]
        assert len(kw_issues) >= 1
        issue = kw_issues[0]
        assert "severity" in issue
        assert "message" in issue
        assert "symbol" in issue
        assert "line" in issue

    def test_missing_code_returns_422(self):
        resp = client.post("/api/verify", json={
            "library": "requests",
        })
        assert resp.status_code == 422

    def test_empty_code_returns_422(self):
        resp = client.post("/api/verify", json={
            "code": "",
        })
        assert resp.status_code == 422

    def test_whitespace_only_code_returns_error(self):
        resp = client.post("/api/verify", json={
            "code": "   \n\n  ",
        })
        data = resp.json()
        assert data["overallStatus"] == "error"

    def test_valid_status_values(self):
        """Status must be one of the defined enum values."""
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url')",
        })
        status = resp.json()["overallStatus"]
        assert status in ("passed", "issues_found", "inconclusive", "error")


# ---------------------------------------------------------------------------
# Case N: Request size limit
# ---------------------------------------------------------------------------

class TestSizeLimit:
    def test_oversized_code_rejected(self):
        """Code exceeding max_length should be rejected with 422."""
        huge_code = "x = 1\n" * 100_000  # Way over 50k chars
        resp = client.post("/api/verify", json={
            "code": huge_code,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Case O: Independent requests
# ---------------------------------------------------------------------------

class TestIndependentRequests:
    def test_bad_request_does_not_corrupt_later_requests(self):
        """A failing request must not affect subsequent valid requests."""
        # Send a bad request first
        client.post("/api/verify", json={
            "code": "def ::::",
        })

        # Then a valid one
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url', timeout=5)",
            "library": "requests",
            "version": "2.31.0",
        })
        assert resp.status_code == 200
        assert resp.json()["overallStatus"] == "passed"

    def test_multiple_valid_requests_independent(self):
        """Two valid requests should produce consistent results."""
        payload = {
            "code": "import requests\nrequests.get('url', timeout=5)",
            "library": "requests",
            "version": "2.31.0",
        }
        r1 = client.post("/api/verify", json=payload).json()
        r2 = client.post("/api/verify", json=payload).json()
        assert r1["overallStatus"] == r2["overallStatus"]

    def test_invalid_then_valid_keywords(self):
        """Invalid-keyword request followed by valid-keyword request."""
        bad = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url', timeout_seconds=10)",
        })
        assert bad.json()["overallStatus"] == "issues_found"

        good = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url', timeout=10)",
        })
        assert good.json()["overallStatus"] == "passed"

    def test_excessive_positional_arguments_endpoint(self):
        """Endpoint detects excessive positional arguments and returns issues_found."""
        resp = client.post("/api/verify", json={
            "code": (
                "import requests\n"
                "response = requests.get(\n"
                "    'https://example.com',\n"
                "    None, None, None, None, None, None, None,\n"
                "    None, None, None, None, None, None, None, None\n"
                ")"
            ),
            "library": "requests",
            "version": "2.31.0",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["overallStatus"] == "issues_found"
        assert any(
            i["type"] == "excessive_positional_arguments" and i["severity"] == "error"
            for i in data["issues"]
        )
        assert "positional_argument_validation" in data["metadata"]["checksPerformed"]

