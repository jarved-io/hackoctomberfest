"""
Deterministic suggestion engine.

Suggests corrections for invalid API symbols and keyword arguments
using string-similarity matching against known valid values from the
reference data.

No AI model is used.  Every suggestion is backed by reference-data evidence.
"""

from __future__ import annotations

import difflib


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

def suggest_keyword_correction(
    invalid_keyword: str,
    known_parameters: list[str],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict[str, str]]:
    """Suggest valid keywords that resemble *invalid_keyword*.

    Returns:
        List of ``{"suggested": ..., "reason": ...}`` dicts.
    """
    matches = find_similar_strings(invalid_keyword, known_parameters, threshold)
    return [
        {
            "suggested": candidate,
            "reason": (
                f"The verified API reference lists '{candidate}' as a "
                f"supported parameter (similarity: {score:.0%})."
            ),
        }
        for candidate, score in matches
    ]


def suggest_symbol_correction(
    invalid_symbol: str,
    known_symbols: list[str],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict[str, str]]:
    """Suggest valid symbols that resemble *invalid_symbol*.

    Compares the function-name portion (after the last dot) to keep
    similarity scores meaningful (e.g. ``gett`` vs ``get`` rather than
    ``requests.gett`` vs ``requests.get``).

    Returns:
        List of ``{"suggested": ..., "reason": ...}`` dicts.
    """
    # Extract the short function name from the invalid symbol
    invalid_short = invalid_symbol.rsplit(".", 1)[-1]

    # Build short-name → full-name mapping
    short_to_full: dict[str, str] = {}
    for sym in known_symbols:
        short = sym.rsplit(".", 1)[-1]
        short_to_full[short] = sym

    matches = find_similar_strings(
        invalid_short, list(short_to_full.keys()), threshold
    )

    return [
        {
            "suggested": short_to_full[short_name],
            "reason": (
                f"The verified API reference lists '{short_to_full[short_name]}' "
                f"as a known symbol (similarity: {score:.0%})."
            ),
        }
        for short_name, score in matches
    ]
