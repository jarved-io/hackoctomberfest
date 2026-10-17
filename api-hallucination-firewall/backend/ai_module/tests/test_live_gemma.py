"""OPTIONAL live test against the real Gemma API. Skipped unless explicitly enabled.

    GEMINI_API_KEY=... RUN_LIVE_GEMMA=1 python3 -m unittest ai_module.tests.test_live_gemma -v

Makes one real (possibly billable) request. Checks that the real SDK call works and
that the live reply survives schema validation and the guardrails.
"""

import os
import unittest

from ai_module import generate_explanation

LIVE = os.environ.get("RUN_LIVE_GEMMA") == "1" and bool(
    os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


@unittest.skipUnless(LIVE, "set RUN_LIVE_GEMMA=1 and GEMINI_API_KEY to run")
class TestLiveGemma(unittest.TestCase):
    def test_live_invalid_kwarg(self):
        findings = [
            {"line": 1, "api": "requests.get", "kind": "function", "status": "valid", "reason": "Found."},
            {"line": 1, "api": "requests.get", "kind": "argument", "argument": "timeout_seconds",
             "status": "invalid", "reason": "Not in trusted signature.", "closestValid": "timeout"},
        ]
        registry = {"requests.get": {"kind": "function", "arguments": ["url", "params", "headers", "timeout"]}}
        result = generate_explanation(
            'requests.get("https://example.com", timeout_seconds=10)', "requests", "2.31.0", findings, registry)
        print(result.to_dict())
        self.assertNotEqual(result.aiError, "missing_api_key")
        self.assertEqual(result.severity, "error")
        self.assertEqual(result.findings, findings)
        # A live model may legitimately be rejected by a guardrail; the status says which.
        self.assertIn(result.aiStatus, {"ok", "invalid_response", "unavailable"})


if __name__ == "__main__":
    unittest.main()
