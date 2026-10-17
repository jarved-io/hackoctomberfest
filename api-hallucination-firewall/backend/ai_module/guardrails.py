"""Application-level guardrails applied to the model's output.

The prompt asks the model to behave; this code *enforces* it. Nothing here
executes user code (ast.parse only builds a syntax tree).
"""

from __future__ import annotations

import ast
import re
from typing import Any

from .schemas import Finding, ModelOutput

MAX_SNIPPET_CHARS = 2000

_NEGATION = re.compile(r"\b(not|no|never|cannot|can't|isn't|doesn't|don't|won't)\b|n't", re.IGNORECASE)
_OVERCLAIM = [
    re.compile(r"\b(entire|whole|rest of the) (program|code|script)\b.{0,40}\b(correct|valid|fine|safe|works?)\b", re.I),
    re.compile(r"\bbug[- ]?free\b", re.I),
    re.compile(r"\b(safe|guaranteed) to (run|execute|use)\b", re.I),
    re.compile(r"\bwill (run|work) (correctly|without|successfully)\b", re.I),
    re.compile(r"\bno (errors?|bugs?|problems?) (will|would) occur\b", re.I),
    re.compile(r"\bcode is (correct|valid|safe)\b", re.I),
]


class Rejected(Exception):
    """Model output is unusable as a whole. ``code`` explains why."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def severity_from_findings(findings: list[Finding]) -> str:
    if any(f.status == "invalid" for f in findings):
        return "error"
    if any(f.status == "unverified" for f in findings):
        return "warning"
    return "info"


def _dotted(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def known_symbols(findings: list[Finding], registry: dict[str, Any]) -> set[str]:
    """Names we are allowed to endorse: registry keys, validator suggestions and
    APIs the validator confirmed valid. Never APIs only found invalid."""
    valid_apis = {f.api for f in findings if f.status == "valid"}
    invalid_only = {f.api for f in findings if f.status == "invalid"} - valid_apis
    syms = set(registry) | valid_apis | {f.closestValid for f in findings if f.closestValid}
    return syms - invalid_only


def allowed_alternatives(findings: list[Finding], registry: dict[str, Any]) -> set[str]:
    allowed = {f.closestValid for f in findings if f.closestValid}
    allowed |= set(registry)
    for entry in registry.values():
        if isinstance(entry, dict):
            args = entry.get("arguments")
            if isinstance(args, (list, tuple)):
                allowed |= {a for a in args if isinstance(a, str)}
    return allowed


def _library_tokens(text: str, library: str) -> set[str]:
    return set(re.findall(rf"\b{re.escape(library)}(?:\.[A-Za-z_][A-Za-z0-9_]*)+", text))


def check_overclaims(text: str) -> bool:
    """True if the text claims the program is correct/safe (ignoring negated sentences)."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        if _NEGATION.search(sentence):
            continue
        if any(p.search(sentence) for p in _OVERCLAIM):
            return True
    return False


def check_prose_names(out: ModelOutput, library: str, symbols: set[str], findings: list[Finding]) -> None:
    """Reject if the prose mentions `library.something` that no supplied data contains."""
    supplied = symbols | {f.api for f in findings}
    for token in _library_tokens(f"{out.summary}\n{out.explanation}", library):
        if token not in supplied:
            raise Rejected("fabricated_api_name", "explanation mentions an API not in the supplied evidence")


def check_evidence_refs(out: ModelOutput, findings: list[Finding]) -> None:
    """Model-supplied evidence is only checked, never trusted or returned."""
    by_api: dict[str, list[Finding]] = {}
    for f in findings:
        by_api.setdefault(f.api, []).append(f)
    for ref in out.evidence:
        matches = by_api.get(ref.api)
        if not matches:
            raise Rejected("fabricated_evidence", "model cited an API that is not in the verified findings")
        if ref.status not in {m.status for m in matches}:
            raise Rejected("contradicts_validator", "model's evidence status disagrees with the validator")
        if ref.line is not None and ref.line not in {m.line for m in matches}:
            raise Rejected("fabricated_evidence", "model cited a line that does not match the findings")


def sanitize_alternative(
    alt: str | None, library: str, findings: list[Finding], registry: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Returns (alternative_or_None, note_if_dropped)."""
    if not alt or not alt.strip():
        return None, None
    alt = alt.strip()
    if not any(f.status == "invalid" for f in findings):
        return None, "Dropped suggested alternative: no invalid finding to correct."
    allowed = allowed_alternatives(findings, registry)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", alt)
    symbols = known_symbols(findings, registry)
    if any(t not in symbols for t in tokens if t.split(".")[0] == library):
        return None, "Dropped suggested alternative: it names an API not in the trusted evidence."
    if not any(t in allowed for t in tokens):
        return None, "Dropped suggested alternative: not supported by the supplied evidence."
    return alt, None


def sanitize_snippet(
    snippet: str | None, library: str, findings: list[Finding], registry: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Keep a corrected snippet only if every library API/keyword in it is grounded."""
    if not snippet or not snippet.strip():
        return None, None
    if len(snippet) > MAX_SNIPPET_CHARS:
        return None, "Dropped corrected snippet: too long."
    try:
        tree = ast.parse(snippet)  # parse only; never executed
    except SyntaxError:
        return None, "Dropped corrected snippet: it is not valid Python."
    symbols = known_symbols(findings, registry)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            name = _dotted(node)
            if name and name.split(".")[0] == library and name not in symbols:
                return None, "Dropped corrected snippet: it uses an API not in the trusted evidence."
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            entry = registry.get(name) if name else None
            args = entry.get("arguments") if isinstance(entry, dict) else None
            if isinstance(args, (list, tuple)):
                for kw in node.keywords:
                    if kw.arg is not None and kw.arg not in args:
                        return None, "Dropped corrected snippet: it passes an argument the trusted signature does not list."
    return snippet, None
