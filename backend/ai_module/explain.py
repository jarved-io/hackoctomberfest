"""generate_explanation(): turns deterministic findings into a validated explanation.

Deterministic findings are always preserved. If Gemma is unavailable, returns
unusable output, or breaks a guardrail, the result carries a deterministic
explanation and an explicit ``aiStatus`` so nothing is ever presented as an
AI-verified fact.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from . import guardrails
from .config import AIConfig
from .gemma_client import AIUnavailableError, GemmaClient, ModelClient
from .prompt import REPAIR_SUFFIX, SYSTEM_PROMPT, build_user_prompt
from .schemas import EvidenceItem, ExplanationResult, Finding, ModelOutput

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # one initial call + at most one repair retry (invalid output only)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_ALIASES = {"symbol": "api", "lineNumber": "line", "message": "reason",
            "closest_valid": "closestValid", "suggestion": "closestValid"}


# ------------------------------------------------------------------ parsing
def parse_model_text(text: str) -> ModelOutput:
    """Strip markdown fences, extract the JSON object, validate against the schema.
    Raises ValueError (bad JSON) or pydantic.ValidationError (bad shape)."""
    cleaned = _FENCE.sub("", text.strip())
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    try:
        data, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc.msg}") from None
    if not isinstance(data, dict):
        raise ValueError("JSON is not an object")
    return ModelOutput.model_validate(data)


# ------------------------------------------------------- deterministic text
def _normalise_findings(raw: list[dict[str, Any]]) -> list[Finding]:
    out = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each verified finding must be a dict")
        data = dict(item)
        for old, new in _ALIASES.items():
            if old in data and new not in data:
                data[new] = data[old]
        out.append(Finding.model_validate(data))
    return out


def _label(f: Finding) -> str:
    where = f"Line {f.line}: " if f.line is not None else ""
    what = f"argument `{f.argument}` of `{f.api}`" if f.argument else f"`{f.api}`"
    return f"{where}{what}"


def _deterministic_text(findings: list[Finding], library: str, version: str) -> tuple[str, str]:
    bad = [f for f in findings if f.status == "invalid"]
    unv = [f for f in findings if f.status == "unverified"]
    ok = [f for f in findings if f.status == "valid"]
    if not findings:
        return (
            "No API references were checked.",
            f"No {library} API references were found to check. This is not a validation of the code.",
        )
    parts = []
    if bad:
        parts.append(f"{len(bad)} confirmed problem(s)")
    if unv:
        parts.append(f"{len(unv)} could not be verified")
    if ok:
        parts.append(f"{len(ok)} confirmed valid")
    summary = ", ".join(parts).capitalize() + f" against {library} {version}."
    lines = []
    for f in bad:
        extra = f" Closest valid option from the validator: `{f.closestValid}`." if f.closestValid else ""
        lines.append(f"- {_label(f)} was NOT found in the trusted API data. {f.reason}{extra}".strip())
    for f in unv:
        lines.append(f"- {_label(f)} could not be verified. {f.reason}".strip())
    for f in ok:
        lines.append(f"- {_label(f)} exists in the trusted API data.")
    lines.append("Only the API references listed above were checked; this does not show the program as a whole is correct.")
    return summary, "\n".join(lines)


def _build_result(
    *,
    findings: list[Finding],
    raw_findings: list[dict[str, Any]],
    registry: dict[str, Any],
    library: str,
    version: str,
    ai_status: str,
    ai_error: str | None,
    notes: list[str],
    model_out: ModelOutput | None = None,
    alternative: str | None = None,
    snippet: str | None = None,
) -> ExplanationResult:
    if model_out is not None:
        summary, explanation = model_out.summary.strip(), model_out.explanation.strip()
    else:
        summary, explanation = _deterministic_text(findings, library, version)
        if ai_status == "unavailable":
            notes = notes + ["AI explanation unavailable; showing deterministic findings only."]
    evidence = [
        EvidenceItem(
            line=f.line, api=f.api, kind=f.kind, argument=f.argument, status=f.status,
            detail=f.reason, registry=registry.get(f.api) if isinstance(registry.get(f.api), dict) else None,
        )
        for f in findings
    ]
    if snippet:
        notes = notes + ["Corrected snippet is a partial fix for the flagged line(s) only, not a verified replacement for the whole program."]
    return ExplanationResult(
        summary=summary, severity=guardrails.severity_from_findings(findings),
        explanation=explanation, evidence=evidence,
        suggestedAlternative=alternative, correctedSnippet=snippet,
        correctionIsPartial=bool(snippet), aiStatus=ai_status, aiError=ai_error,
        notes=notes, findings=copy.deepcopy(raw_findings),
    )


# --------------------------------------------------------------- main entry
def generate_explanation(
    code: str,
    library: str,
    version: str,
    verified_findings: list[dict[str, Any]],
    verified_api_evidence: dict[str, Any] | None = None,
    *,
    client: ModelClient | None = None,
    config: AIConfig | None = None,
) -> ExplanationResult:
    """Explain deterministic verification results with Gemma.

    ``verified_findings``: list of finding dicts (see schemas.Finding).
    ``verified_api_evidence``: trusted registry entries keyed by API name, e.g.
    {"requests.get": {"kind": "function", "arguments": ["url", "params", "timeout"]}}.
    ``client``: optional ``(system_prompt, user_prompt) -> str`` for tests.

    Never raises for AI problems; raises ValueError only for malformed findings input.
    """
    registry = verified_api_evidence or {}
    findings = _normalise_findings(verified_findings)
    common = dict(findings=findings, raw_findings=verified_findings, registry=registry,
                  library=library, version=version)

    if not findings:
        return _build_result(**common, ai_status="skipped", ai_error=None, notes=[])

    cfg = config or AIConfig.from_env()
    notes: list[str] = []
    try:
        model_client = client or GemmaClient(cfg)
        user_prompt = build_user_prompt(
            code, library, version, [f.model_dump(exclude_none=True) for f in findings],
            registry, cfg.max_code_chars,
        )
        out, last_problem = None, ""
        for attempt in range(MAX_ATTEMPTS):
            prompt = user_prompt + (REPAIR_SUFFIX.format(reason=last_problem) if attempt else "")
            text = model_client(SYSTEM_PROMPT, prompt)
            try:
                out = parse_model_text(text)
                break
            except (ValueError, ValidationError) as exc:
                last_problem = "schema mismatch" if isinstance(exc, ValidationError) else str(exc)
                log.info("Gemma output rejected (attempt %d): %s", attempt + 1, last_problem)
        if out is None:
            return _build_result(**common, ai_status="invalid_response", ai_error="invalid_json",
                                 notes=["AI output was not valid structured JSON and was discarded."])
    except AIUnavailableError as exc:
        if str(exc) != exc.code:
            notes.append(f"AI call failed: {exc}")
        return _build_result(**common, ai_status="unavailable", ai_error=exc.code, notes=notes)
    except Exception as exc:  # noqa: BLE001 - an injected client must not crash the pipeline
        log.warning("Unexpected AI failure: %s", type(exc).__name__)
        return _build_result(**common, ai_status="unavailable", ai_error="api_error", notes=notes)

    # ---- guardrails: enforce, don't trust ----
    symbols = guardrails.known_symbols(findings, registry)
    try:
        guardrails.check_evidence_refs(out, findings)
        guardrails.check_prose_names(out, library, symbols, findings)
        if guardrails.check_overclaims(f"{out.summary}\n{out.explanation}"):
            raise guardrails.Rejected("overclaim", "model claimed the program is correct or safe")
    except guardrails.Rejected as rej:
        return _build_result(**common, ai_status="invalid_response", ai_error=rej.code,
                             notes=[f"AI explanation discarded ({rej.code}); deterministic findings are unchanged."])

    det_severity = guardrails.severity_from_findings(findings)
    used_model = getattr(model_client, "last_model", None)
    if used_model and used_model != cfg.model:
        notes.append(f"Primary model was unavailable; answered by fallback model {used_model}.")
    if out.severity != det_severity:
        notes.append(f"Model severity '{out.severity}' disagreed with validator; using '{det_severity}'.")

    alternative, note = guardrails.sanitize_alternative(out.suggestedAlternative, library, findings, registry)
    if note:
        notes.append(note)
    snippet = None
    if alternative:
        snippet, note = guardrails.sanitize_snippet(out.correctedSnippet, library, findings, registry)
        if note:
            notes.append(note)
    elif out.correctedSnippet:
        notes.append("Dropped corrected snippet: no supported alternative.")

    return _build_result(**common, ai_status="ok", ai_error=None, notes=notes,
                         model_out=out, alternative=alternative, snippet=snippet)
