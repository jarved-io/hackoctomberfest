"""
Deterministic suggestion engine.

Suggests corrections for invalid API symbols and keyword arguments
using string-similarity matching against known valid values from the
reference data.

No AI model is used.  Every suggestion is backed by reference-data evidence.
"""

from __future__ import annotations

import difflib
import json
from functools import lru_cache

from app.config import CURATED_DIR


# Minimum similarity ratio (0.0–1.0) to consider a match
DEFAULT_THRESHOLD: float = 0.6

# Maximum suggestions returned per item
MAX_SUGGESTIONS: int = 3


# ---------------------------------------------------------------------------
# Generic similarity helper
# ---------------------------------------------------------------------------

def find_similar_strings(
    target: str,
    candidates: list[str],
    threshold: float = DEFAULT_THRESHOLD,
    max_results: int = MAX_SUGGESTIONS,
) -> list[tuple[str, float]]:
    """Return candidates similar to *target*, scored by SequenceMatcher.

    Args:
        target:      The string to match against.
        candidates:  Valid strings to compare.
        threshold:   Minimum similarity ratio.
        max_results: Maximum results to return.

    Returns:
        ``[(candidate, score), ...]`` sorted by score descending.
    """
    if not target or not candidates:
        return []

    target_lower = target.lower()
    scored: list[tuple[str, float]] = []

    for candidate in candidates:
        ratio = difflib.SequenceMatcher(
            None, target_lower, candidate.lower()
        ).ratio()
        if ratio >= threshold:
            scored.append((candidate, ratio))

    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:max_results]


# ---------------------------------------------------------------------------
# Domain-specific suggestion helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _curated(library: str) -> dict:
    """Curated hints (common AI mistakes). Hints only: never used to decide existence."""
    path = CURATED_DIR / f"{library}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        return {}


def suggest_keyword_correction(
    invalid_keyword: str,
    known_parameters: list[str],
    threshold: float = DEFAULT_THRESHOLD,
    library: str | None = None,
) -> list[dict[str, str]]:
    """Suggest valid keywords that resemble *invalid_keyword*.

    Returns:
        List of ``{"suggested": ..., "reason": ...}`` dicts.
    """
    out: list[dict[str, str]] = []
    cur = _curated(library).get("argument_corrections", {}).get(invalid_keyword) if library else None
    if cur and cur.get("use") in known_parameters:
        out.append({
            "suggested": cur["use"],
            "reason": (
                f"The verified API reference lists '{cur['use']}' as a supported parameter. "
                + cur.get("note", "")
            ).strip(),
        })
    matches = find_similar_strings(invalid_keyword, known_parameters, threshold)
    for candidate, score in matches:
        if all(o["suggested"] != candidate for o in out):
            out.append({
                "suggested": candidate,
                "reason": (
                    f"The verified API reference lists '{candidate}' as a "
                    f"supported parameter (similarity: {score:.0%})."
                ),
            })
    return out[:MAX_SUGGESTIONS]


def suggest_symbol_correction(
    invalid_symbol: str,
    known_symbols: list[str],
    threshold: float = DEFAULT_THRESHOLD,
    library: str | None = None,
) -> list[dict[str, str]]:
    """Suggest valid symbols that resemble *invalid_symbol*.

    Compares the function-name portion (after the last dot) to keep
    similarity scores meaningful (e.g. ``gett`` vs ``get`` rather than
    ``requests.gett`` vs ``requests.get``).

    Returns:
        List of ``{"suggested": ..., "reason": ...}`` dicts.
    """
    out: list[dict[str, str]] = []
    known = set(known_symbols)

    # Curated hints first (e.g. requests.fetch -> requests.get), only if the target is real.
    cur = _curated(library).get("symbol_corrections", {}).get(invalid_symbol) if library else None
    if cur and cur.get("use") in known:
        out.append({
            "suggested": cur["use"],
            "reason": (
                f"The verified API reference lists '{cur['use']}' as a known symbol. "
                + cur.get("note", "")
            ).strip(),
        })

    # Similarity only among siblings in the same namespace (same parent path),
    # so 'requests.Clent' is compared with 'requests.X', not with every method.
    parent = invalid_symbol.rsplit(".", 1)[0] if "." in invalid_symbol else ""
    invalid_short = invalid_symbol.rsplit(".", 1)[-1]
    short_to_full: dict[str, str] = {}
    for sym in known_symbols:
        if (sym.rsplit(".", 1)[0] if "." in sym else "") == parent:
            short_to_full.setdefault(sym.rsplit(".", 1)[-1], sym)

    for short_name, score in find_similar_strings(
        invalid_short, list(short_to_full.keys()), threshold
    ):
        full = short_to_full[short_name]
        if all(o["suggested"] != full for o in out):
            out.append({
                "suggested": full,
                "reason": (
                    f"The verified API reference lists '{full}' "
                    f"as a known symbol (similarity: {score:.0%})."
                ),
            })
    return out[:MAX_SUGGESTIONS]
