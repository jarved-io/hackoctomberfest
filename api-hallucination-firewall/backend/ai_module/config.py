"""Environment-based configuration for the Gemma AI module.

The API key is read from the server environment only. It is never logged,
never part of any returned result, and hidden from ``repr``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Gemma 4 model IDs listed on https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api
# (gemma-4-31b-it and gemma-4-26b-a4b-it). Override with GEMMA_MODEL.
DEFAULT_MODEL = "gemma-4-26b-a4b-it"
DEFAULT_FALLBACK_MODEL = "gemma-4-31b-it"  # tried when the primary fails transiently
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_CODE_CHARS = 20_000


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value > 0 else default


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class AIConfig:
    api_key: str | None = field(default=None, repr=False)
    model: str = DEFAULT_MODEL
    fallback_model: str | None = DEFAULT_FALLBACK_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_code_chars: int = DEFAULT_MAX_CODE_CHARS

    @classmethod
    def from_env(cls) -> "AIConfig":
        key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
        model = (os.environ.get("GEMMA_MODEL") or "").strip() or DEFAULT_MODEL
        other = DEFAULT_FALLBACK_MODEL if model != DEFAULT_FALLBACK_MODEL else DEFAULT_MODEL
        fallback = (os.environ.get("GEMMA_FALLBACK_MODEL") or "").strip() or other
        if fallback.lower() == "none" or fallback == model:
            fallback = None  # set GEMMA_FALLBACK_MODEL=none to disable
        return cls(
            api_key=key or None,
            model=model,
            fallback_model=fallback,
            timeout_seconds=_float_env("GEMMA_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
            max_code_chars=_int_env("GEMMA_MAX_CODE_CHARS", DEFAULT_MAX_CODE_CHARS),
        )
