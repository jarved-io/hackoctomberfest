"""Bridge between the deterministic verifier and the Gemma explanation layer.

The verifier decides what is valid / invalid / unverified. This module only
translates that result into the ``ai_module`` input format and attaches the
explanation. It can never change ``overallStatus``, and any AI failure degrades
to deterministic text (see ``ai_module.explain``).
"""

from __future__ import annotations

import logging
from typing import Any

from app.knowledge_base import KnowledgeBase
from app.schemas import IssueType, Severity, VerifyResponse

logger = logging.getLogger(__name__)

_KIND_BY_ISSUE = {
    IssueType.INVALID_KEYWORD: "argument",
    IssueType.INVALID_ARGUMENT: "argument",
    IssueType.INVALID_POSITIONAL_ARGUMENT: "argument",
    IssueType.EXCESSIVE_POSITIONAL_ARGUMENTS: "argument",
    IssueType.INVALID_IMPORT: "import",
    IssueType.INVALID_SYMBOL: "function",
    IssueType.UNRESOLVED_SYMBOL: "function",
}


def build_findings(response: VerifyResponse) -> list[dict[str, Any]]:
    """Deterministic findings in the ``ai_module.schemas.Finding`` shape."""
    findings: list[dict[str, Any]] = []

    for item in response.verifiedItems:
        findings.append({
            "line": item.line, "api": item.symbol, "kind": "function",
            "status": "valid", "reason": "Found in the trusted API data.",
        })

    for issue in response.issues:
        if issue.severity == Severity.INFO:
            continue  # caveats such as **kwargs; not a verdict on an API
        if issue.severity == Severity.ERROR:
            status = "invalid"
        else:
            status = "unverified"
        closest = None
        for sug in response.suggestions:
            same_place = sug.line == issue.line and sug.symbol == issue.symbol
            same_item = sug.original == (issue.argument or issue.symbol)
            if same_place and same_item:
                closest = sug.suggested
                break
        finding: dict[str, Any] = {
            "line": issue.line,
            "api": issue.symbol,
            "kind": _KIND_BY_ISSUE.get(issue.type, "function"),
            "status": status,
            "reason": issue.message,
        }
        if issue.argument:
            finding["argument"] = issue.argument
        if closest:
            finding["closestValid"] = closest
        findings.append(finding)

    return findings


def build_registry(
    findings: list[dict[str, Any]],
    response: VerifyResponse,
    knowledge_base: KnowledgeBase,
) -> dict[str, Any]:
    """Trusted registry entries (from the snapshot) for every API the model may mention."""
    snapshot = knowledge_base.get_snapshot(response.metadata.library, response.metadata.version)
    if snapshot is None:
        return {}
    names = {f["api"] for f in findings if f["status"] == "valid"}
    names |= {f["closestValid"] for f in findings if f.get("closestValid")}
    names |= {s.suggested for s in response.suggestions}
    registry: dict[str, Any] = {}
    for name in names:
        info = snapshot.lookup_symbol(name)
        if info is None:
            continue
        entry: dict[str, Any] = {"kind": info.kind}
        if info.parameters:
            entry["arguments"] = list(info.parameters)
        registry[name] = entry
    return registry


def explain(
    code: str,
    response: VerifyResponse,
    knowledge_base: KnowledgeBase,
) -> dict[str, Any] | None:
    """Return the Gemma explanation dict, or ``None`` when there is nothing to explain.

    Never raises: the verification result is always returned to the caller.
    """
    if response.overallStatus.value in ("error",):
        return None
    findings = build_findings(response)
    if not any(f["status"] in ("invalid", "unverified") for f in findings):
        return None  # all-valid or nothing checked: no model call needed
    try:
        from ai_module import generate_explanation

        result = generate_explanation(
            code,
            response.metadata.library,
            response.metadata.version,
            findings,
            build_registry(findings, response, knowledge_base),
        )
        return result.to_dict()
    except Exception as exc:  # noqa: BLE001 - AI problems must never break verification
        logger.warning("Explanation layer failed: %s", type(exc).__name__)
        return None
