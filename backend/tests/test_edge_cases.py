"""Edge-case tests (Cases L and additional scenarios)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.verifier import verify_code
from app.knowledge_base import KnowledgeBase


client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    lib_dir = tmp_path / "requests"
    lib_dir.mkdir()
    snapshot = {
        "library": "requests",
        "version": "2.31.0",
        "source": {"name": "Official docs", "url": "https://requests.readthedocs.io/en/v2.31.0/api/"},
        "snapshotCompleteness": "partial",
        "symbols": {
            "requests.get": {
                "kind": "function",
                "module": "requests",
                "parameters": [
                    "url", "params", "data", "json", "headers",
                    "cookies", "files", "auth", "timeout",
                    "allow_redirects", "proxies", "hooks",
                    "stream", "verify", "cert",
                ],
                "parameterCompleteness": "verified",
                "positionalParameters": ["url", "params"],
                "minPositionalArguments": 1,
                "maxPositionalArguments": 2,
                "signatureCompleteness": "verified",
            },
        },
    }
    (lib_dir / "2.31.0.json").write_text(json.dumps(snapshot))
    return tmp_path


@pytest.fixture
def kb(data_dir: Path) -> KnowledgeBase:
    return KnowledgeBase(data_dir=data_dir)


# ---------------------------------------------------------------------------
# Case L: No execution — code with side effects
# ---------------------------------------------------------------------------

class TestNoExecution:
    """Verify that submitted code is parsed, never executed."""

    def test_dangerous_code_not_executed(self, kb: KnowledgeBase):
        """Code that would create a file if executed must not do so."""
        dangerous_code = (
            "import os\n"
            "os.system('touch /tmp/hacked_by_test')\n"
        )
        # This should parse without executing
        result = verify_code(dangerous_code, "os", "0.0.0", kb)
        # The library "os" is not supported → inconclusive
        assert result.overallStatus.value in ("inconclusive", "error")
        # The file should NOT exist
        import os as real_os
        assert not real_os.path.exists("/tmp/hacked_by_test")

    def test_import_side_effect_not_triggered(self, kb: KnowledgeBase):
        """Importing a module in the submitted code must not actually import it."""
        code = "import this_module_does_not_exist_12345"
        # If the parser tried to import this, it would raise ImportError
        result = verify_code(code, "this_module_does_not_exist_12345", "1.0", kb)
        assert result is not None  # No crash

    def test_exec_in_submitted_code_not_run(self):
        """Submitted code containing exec() should not be executed."""
        code = 'exec("raise RuntimeError(\'boom\')")'
        resp = client.post("/api/verify", json={
            "code": code,
            "library": "requests",
            "version": "2.31.0",
        })
        assert resp.status_code == 200  # No crash


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

class TestMultipleCallsInOneFile:
    def test_mix_valid_and_invalid(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "requests.get('url', timeout=5)\n"
            "requests.get('url', timeout_seconds=10)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "issues_found"
        # Should have both verified items and issues
        assert len(result.verifiedItems) >= 1
        assert len(result.issues) >= 1


class TestSuggestionQuality:
    def test_similar_keyword_suggested(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "requests.get('url', timeot=5)\n"  # typo
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        suggestions = [s for s in result.suggestions if s.original == "timeot"]
        assert len(suggestions) >= 1
        assert suggestions[0].suggested == "timeout"

    def test_no_suggestion_for_unrelated_keyword(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "requests.get('url', zzzzz_totally_unrelated=1)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        suggestions = [
            s for s in result.suggestions
            if s.original == "zzzzz_totally_unrelated"
        ]
        # Very dissimilar → should not suggest anything
        assert len(suggestions) == 0


class TestUnicodeAndSpecialInput:
    def test_unicode_in_strings(self):
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('https://例え.jp')",
        })
        assert resp.status_code == 200

    def test_non_string_code_rejected(self):
        resp = client.post("/api/verify", json={
            "code": 12345,
        })
        assert resp.status_code == 422


class TestDecoratorAndClassUsage:
    def test_method_call_inside_class(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "class Fetcher:\n"
            "    def fetch(self):\n"
            "        return requests.get('url', timeout=5)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert any(v.symbol == "requests.get" for v in result.verifiedItems)


class TestDefaultParameterValues:
    def test_default_library_and_version(self):
        """When library/version omitted, defaults should work."""
        resp = client.post("/api/verify", json={
            "code": "import requests\nrequests.get('url')",
        })
        data = resp.json()
        assert data["metadata"]["library"] == "requests"
        assert data["metadata"]["version"] == "2.31.0"
