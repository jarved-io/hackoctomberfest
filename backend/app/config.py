"""
Application configuration.

Centralizes settings for CORS, input limits, paths, and app metadata.
Configurable values can be overridden via environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# --- Application metadata ---
APP_NAME = "api-hallucination-firewall"
APP_VERSION = "1.0.0"

# --- Input validation ---
MAX_CODE_SIZE = 50_000  # Maximum characters of submitted Python code

# --- CORS ---
# Comma-separated list of allowed origins; defaults to local Next.js dev server.
_cors_env = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS: list[str] = (
    [origin.strip() for origin in _cors_env.split(",") if origin.strip()]
    if _cors_env
    else [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)

# --- Supported libraries ---
SUPPORTED_LIBRARIES = ["requests"]
