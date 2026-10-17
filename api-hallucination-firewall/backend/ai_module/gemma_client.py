"""Server-side client for Gemma 4 through the Gemini API.

Two transports, chosen automatically:
  1. The official ``google-genai`` SDK, when it can be imported.
  2. Google's REST endpoint over the standard library (``urllib``), when it cannot
     (for example on Windows ARM, where the SDK's ``cryptography`` dependency often
     fails to install). No extra packages are needed for this path.

Resilience: if the primary model fails with a transient error (HTTP 5xx, timeout,
rate limit), the same request is tried once on the fallback model. Errors that a
second model cannot fix (bad key, bad request, empty reply) are not retried.

Everything is imported/used lazily so the rest of the module and the unit tests
work without the SDK or without an API key.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from .config import AIConfig

log = logging.getLogger(__name__)

REST_BASE = "https://generativelanguage.googleapis.com/v1beta"

# A "model client" is any callable (system_prompt, user_prompt) -> raw text.
# generate_explanation() accepts one so tests and teammates can inject their own.
ModelClient = Callable[[str, str], str]


class AIUnavailableError(Exception):
    """The AI service could not produce a response. ``code`` is machine-readable.

    Codes: missing_api_key, sdk_not_installed, timeout, rate_limited,
    api_error, empty_response. ``status`` is the HTTP status when known.
    """

    def __init__(self, code: str, message: str = "", status: int | None = None):
        super().__init__(message or code)
        self.code = code
        self.status = status

    @property
    def transient(self) -> bool:
        """True if trying a different model could plausibly succeed."""
        if self.code in ("timeout", "rate_limited"):
            return True
        return self.code == "api_error" and isinstance(self.status, int) and self.status >= 500


def _classify(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status == 429 or "ratelimit" in name or "resourceexhausted" in name:
        return "rate_limited"
    if isinstance(exc, TimeoutError) or "timeout" in name or status == 408 or status == 504:
        return "timeout"
    return "api_error"


class GemmaClient:
    """Calls Gemma 4 through the Gemini API. Construct cheaply; connects on first call."""

    def __init__(self, config: AIConfig | None = None):
        self.config = config or AIConfig.from_env()
        self._client = None
        self._types = None
        self._use_rest = False
        self.last_model: str | None = None  # model that produced the last successful reply

    # ------------------------------------------------------------ SDK path
    def _connect(self) -> None:
        if not self.config.api_key:
            raise AIUnavailableError("missing_api_key", "GEMINI_API_KEY is not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIUnavailableError("sdk_not_installed", "pip install google-genai") from exc
        self._types = types
        # HttpOptions.timeout is in milliseconds.
        self._client = genai.Client(
            api_key=self.config.api_key,
            http_options=types.HttpOptions(timeout=int(self.config.timeout_seconds * 1000)),
        )

    def _sdk_call(self, model: str, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=self._types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0,
                    max_output_tokens=1500,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a safe error code below
            code = _classify(exc)
            # Log only the exception type, never its message (may echo request details).
            log.warning("Gemma call failed: %s (%s)", code, type(exc).__name__)
            http = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            http = http if isinstance(http, int) else None
            detail = f"{code} ({type(exc).__name__}" + (f", HTTP {http}" if http else "") + ")"
            raise AIUnavailableError(code, detail, status=http) from None
        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise AIUnavailableError("empty_response", "model returned no text")
        return text

    # ----------------------------------------------------------- REST path
    def _rest_call(self, model: str, system_prompt: str, user_prompt: str) -> str:
        """POST models/{model}:generateContent. The key goes in the x-goog-api-key
        header (never in the URL) and is never logged."""
        model_path = urllib.parse.quote(model, safe="-._")
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1500},
        }
        request = urllib.request.Request(
            f"{REST_BASE}/models/{model_path}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.config.api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status = exc.code
            code = "rate_limited" if status == 429 else "timeout" if status in (408, 504) else "api_error"
            log.warning("Gemma REST call failed: %s (HTTP %s)", code, status)
            raise AIUnavailableError(code, f"{code} (HTTP {status})", status=status) from None
        except (TimeoutError, socket.timeout):
            raise AIUnavailableError("timeout", "timeout") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise AIUnavailableError("timeout", "timeout") from None
            raise AIUnavailableError("api_error", "api_error (network error)") from None
        except ValueError:
            raise AIUnavailableError("api_error", "api_error (unreadable response)") from None

        try:
            parts = data["candidates"][0]["content"]["parts"]
            # Skip "thought" parts if the model returns its reasoning separately.
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought"))
        except (KeyError, IndexError, TypeError):
            raise AIUnavailableError("empty_response", "model returned no text") from None
        if not text.strip():
            raise AIUnavailableError("empty_response", "model returned no text")
        return text

    # -------------------------------------------------------------- entry
    def _call_model(self, model: str, system_prompt: str, user_prompt: str) -> str:
        if self._client is None and not self._use_rest:
            try:
                self._connect()
            except AIUnavailableError as exc:
                if exc.code != "sdk_not_installed":
                    raise
                self._use_rest = True  # SDK missing or unimportable: use REST
        if self._use_rest:
            return self._rest_call(model, system_prompt, user_prompt)
        return self._sdk_call(model, system_prompt, user_prompt)

    def __call__(self, system_prompt: str, user_prompt: str) -> str:
        models = [self.config.model]
        fallback = self.config.fallback_model
        if fallback and fallback != self.config.model:
            models.append(fallback)
        for i, model in enumerate(models):
            try:
                text = self._call_model(model, system_prompt, user_prompt)
            except AIUnavailableError as exc:
                if not exc.transient or i == len(models) - 1:
                    raise
                log.warning("Gemma model %s failed (%s); trying fallback model", model, exc.code)
                continue
            self.last_model = model
            return text
        raise AIUnavailableError("api_error")  # unreachable; keeps type checkers happy
