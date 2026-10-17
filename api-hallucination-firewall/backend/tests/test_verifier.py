"""Tests for the deterministic verification engine (app.verifier).

Covers Cases A–K from the specification.
"""

import json
from pathlib import Path

import pytest

from app.knowledge_base import KnowledgeBase
from app.verifier import verify_code


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temp data directory with a requests 2.31.0 snapshot."""
    lib_dir = tmp_path / "requests"
    lib_dir.mkdir()

    snapshot = {
        "library": "requests",
        "version": "2.31.0",
        "source": {
            "name": "Official requests documentation",
            "url": "https://requests.readthedocs.io/en/v2.31.0/api/",
        },
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
            "requests.post": {
                "kind": "function",
                "module": "requests",
                "parameters": [
                    "url", "data", "json", "params", "headers",
                    "cookies", "files", "auth", "timeout",
                    "allow_redirects", "proxies", "hooks",
                    "stream", "verify", "cert",
                ],
                "parameterCompleteness": "verified",
                "positionalParameters": ["url", "data", "json"],
                "minPositionalArguments": 1,
                "maxPositionalArguments": 3,
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
# Case A: Supported call with valid keyword
# ---------------------------------------------------------------------------

class TestCaseA:
    def test_valid_keyword_passes(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "response = requests.get('https://example.com', timeout=5)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "passed"
        assert any(v.symbol == "requests.get" for v in result.verifiedItems)

    def test_multiple_valid_keywords(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "requests.get('url', timeout=5, verify=False, headers={})\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "passed"


# ---------------------------------------------------------------------------
# Case B: Unsupported keyword
# ---------------------------------------------------------------------------

class TestCaseB:
    def test_invalid_keyword_detected(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "response = requests.get('https://example.com', timeout_seconds=10)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "issues_found"
        assert any(
            i.type.value == "invalid_keyword" and i.argument == "timeout_seconds"
            for i in result.issues
        )

    def test_suggestion_generated(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "requests.get('url', timeout_seconds=10)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert any(
            s.original == "timeout_seconds" and s.suggested == "timeout"
            for s in result.suggestions
        )

    def test_evidence_attached(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "requests.get('url', timeout_seconds=10)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        kw_issues = [i for i in result.issues if i.argument == "timeout_seconds"]
        assert len(kw_issues) >= 1
        assert kw_issues[0].evidence is not None
        assert "timeout" in kw_issues[0].evidence.knownArguments


# ---------------------------------------------------------------------------
# Case C: Unknown symbol (partial snapshot)
# ---------------------------------------------------------------------------

class TestCaseC:
    def test_unknown_symbol_partial_snapshot(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "requests.this_function_does_not_exist()\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        # Snapshot is partial → cannot confirm invalid → unresolved
        assert any(
            i.type.value == "unresolved_symbol"
            for i in result.issues
        )
        assert result.overallStatus.value == "inconclusive"

    def test_unknown_symbol_complete_snapshot(self, data_dir: Path):
        """With a complete snapshot, unknown symbols are flagged as invalid."""
        lib_dir = data_dir / "requests"
        snap_data = json.loads((lib_dir / "2.31.0.json").read_text())
        snap_data["snapshotCompleteness"] = "complete"
        (lib_dir / "2.31.0.json").write_text(json.dumps(snap_data))

        kb = KnowledgeBase(data_dir=data_dir)
        code = (
            "import requests\n"
            "requests.this_function_does_not_exist()\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert any(i.type.value == "invalid_symbol" for i in result.issues)
        assert result.overallStatus.value == "issues_found"


# ---------------------------------------------------------------------------
# Case D: Invalid / unsupported import
# ---------------------------------------------------------------------------

class TestCaseD:
    def test_unsupported_library(self, kb: KnowledgeBase):
        code = (
            "import pandas\n"
            "df = pandas.read_csv('data.csv')\n"
        )
        result = verify_code(code, "pandas", "1.5.0", kb)
        assert result.overallStatus.value == "inconclusive"


# ---------------------------------------------------------------------------
# Case E: Unsupported version
# ---------------------------------------------------------------------------

class TestCaseE:
    def test_unsupported_version(self, kb: KnowledgeBase):
        code = "import requests\nrequests.get('url')\n"
        result = verify_code(code, "requests", "9.99.99", kb)
        assert result.overallStatus.value == "inconclusive"
        assert any(
            i.type.value == "unsupported_version" for i in result.issues
        )

    def test_available_versions_in_message(self, kb: KnowledgeBase):
        result = verify_code("import requests", "requests", "9.99.99", kb)
        messages = " ".join(i.message for i in result.issues)
        assert "2.31.0" in messages


# ---------------------------------------------------------------------------
# Case F: Syntax error
# ---------------------------------------------------------------------------

class TestCaseF:
    def test_syntax_error_returns_error_status(self, kb: KnowledgeBase):
        code = "import requests\nresponse = requests.get("
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "error"
        assert any(i.type.value == "syntax_error" for i in result.issues)

    def test_syntax_error_no_crash(self, kb: KnowledgeBase):
        """Malformed code must not raise an exception."""
        code = "def ::::"
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "error"


# ---------------------------------------------------------------------------
# Case G: Empty input
# ---------------------------------------------------------------------------

class TestCaseG:
    def test_empty_code_inconclusive(self, kb: KnowledgeBase):
        code = "# just a comment\n"
        result = verify_code(code, "requests", "2.31.0", kb)
        # No relevant calls → inconclusive
        assert result.overallStatus.value in ("passed", "inconclusive")

    def test_only_imports_no_calls(self, kb: KnowledgeBase):
        code = "import requests\n"
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value in ("passed", "inconclusive")


# ---------------------------------------------------------------------------
# Case H: Missing reference data
# ---------------------------------------------------------------------------

class TestCaseH:
    def test_missing_data_does_not_claim_valid(self, kb: KnowledgeBase):
        code = "import flask\nflask.run()\n"
        result = verify_code(code, "flask", "2.0.0", kb)
        assert result.overallStatus.value != "passed"


# ---------------------------------------------------------------------------
# Case I: Alias handling
# ---------------------------------------------------------------------------

class TestCaseI:
    def test_import_alias_resolution(self, kb: KnowledgeBase):
        code = (
            "import requests as req\n"
            "response = req.get('https://example.com')\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        # Should resolve req.get → requests.get and verify it
        assert any(v.symbol == "requests.get" for v in result.verifiedItems)

    def test_from_import_alias(self, kb: KnowledgeBase):
        code = (
            "from requests import get as fetch\n"
            "fetch('https://example.com')\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert any(v.symbol == "requests.get" for v in result.verifiedItems)


# ---------------------------------------------------------------------------
# Case J: Local function collision
# ---------------------------------------------------------------------------

class TestCaseJ:
    def test_local_function_not_treated_as_api(self, kb: KnowledgeBase):
        code = (
            "def get(value):\n"
            "    return value\n"
            "result = get('example')\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        # The local get() should NOT be flagged as a requests issue
        assert not any(
            i.symbol == "requests.get" for i in result.issues
        )


# ---------------------------------------------------------------------------
# Case K: Dynamic arguments
# ---------------------------------------------------------------------------

class TestCaseK:
    def test_kwargs_expansion_noted(self, kb: KnowledgeBase):
        code = (
            "import requests\n"
            "options = {}\n"
            "requests.get('url', **options)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        # Should have an INFO-level issue about **kwargs
        assert any(
            i.severity.value == "info" and "**kwargs" in i.message
            for i in result.issues
        )


# ---------------------------------------------------------------------------
# Positional Argument Validation (Regression Tests)
# ---------------------------------------------------------------------------

class TestCasePositionalValidation:
    """Regression tests for positional-argument validation."""

    def test_valid_single_positional_arg(self, kb: KnowledgeBase):
        """A valid requests.get() call with one positional URL argument."""
        code = "import requests\nresponse = requests.get('https://example.com')"
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "passed"
        assert any("positional_arguments_valid" in v.checksPassed for v in result.verifiedItems)

    def test_valid_multiple_supported_positional_args(self, kb: KnowledgeBase):
        """A valid call with supported positional arguments (url and params)."""
        code = "import requests\nresponse = requests.get('https://example.com', {'q': 'search'})"
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "passed"
        assert any("positional_arguments_valid" in v.checksPassed for v in result.verifiedItems)

    def test_excessive_positional_arguments(self, kb: KnowledgeBase):
        """A call with too many positional arguments (the 16-argument problem case)."""
        code = (
            "import requests\n"
            "response = requests.get(\n"
            "    'https://example.com',\n"
            "    None, None, None, None, None, None, None,\n"
            "    None, None, None, None, None, None, None, None\n"
            ")\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "issues_found"
        pos_issues = [
            i for i in result.issues
            if i.type.value in ("excessive_positional_arguments", "invalid_positional_argument")
        ]
        assert len(pos_issues) == 1
        issue = pos_issues[0]
        assert issue.severity.value == "error"
        assert issue.symbol == "requests.get"
        assert issue.line == 2
        assert issue.evidence is not None
        assert issue.evidence.maxPositionalArguments == 2
        assert "url" in issue.evidence.positionalParameters
        assert "params" in issue.evidence.positionalParameters

    def test_call_using_keyword_arguments(self, kb: KnowledgeBase):
        """A call using keyword arguments (positional url + valid keyword timeout)."""
        code = (
            "import requests\n"
            "response = requests.get('https://example.com', timeout=5, headers={'User-Agent': 'test'})\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "passed"
        assert any("positional_arguments_valid" in v.checksPassed for v in result.verifiedItems)
        assert any("all_keywords_valid" in v.checksPassed for v in result.verifiedItems)

    def test_incomplete_signature_metadata(self, tmp_path: Path):
        """Incomplete signature metadata results in inconclusive status rather than false error."""
        lib_dir = tmp_path / "customlib"
        lib_dir.mkdir()
        snapshot = {
            "library": "customlib",
            "version": "1.0.0",
            "source": {"name": "Test docs", "url": "https://example.com"},
            "snapshotCompleteness": "partial",
            "symbols": {
                "customlib.fetch": {
                    "kind": "function",
                    "module": "customlib",
                    "parameters": ["url", "timeout"],
                    "parameterCompleteness": "partial",
                    "signatureCompleteness": "incomplete",
                }
            },
        }
        (lib_dir / "1.0.0.json").write_text(json.dumps(snapshot))
        custom_kb = KnowledgeBase(data_dir=tmp_path)

        code = "import customlib\ncustomlib.fetch('https://example.com', 10)\n"
        result = verify_code(code, "customlib", "1.0.0", custom_kb)
        assert result.overallStatus.value == "inconclusive"
        warning_issues = [
            i for i in result.issues
            if i.type.value == "incomplete_reference_data" and i.severity.value == "warning"
        ]
        assert len(warning_issues) >= 1
        assert "Positional arguments" in warning_issues[0].message

    def test_excessive_positional_arguments_with_alias(self, kb: KnowledgeBase):
        """An import alias such as import requests as req correctly detects excessive positional args."""
        code = (
            "import requests as req\n"
            "response = req.get('https://example.com', None, None, None)\n"
        )
        result = verify_code(code, "requests", "2.31.0", kb)
        assert result.overallStatus.value == "issues_found"
        pos_issues = [
            i for i in result.issues
            if i.type.value in ("excessive_positional_arguments", "invalid_positional_argument")
        ]
        assert len(pos_issues) == 1
        assert pos_issues[0].symbol == "requests.get"
        assert pos_issues[0].severity.value == "error"

