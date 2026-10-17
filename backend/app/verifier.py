"""
Deterministic verification engine.

Compares parsed Python API usage against trusted, versioned API reference
data.  All findings are backed by reference-data evidence — no AI model
is involved.

Result semantics:
  valid   — The usage was checked and matches the reference data.
  invalid — The usage contradicts the reference data.
  unknown — The reference data is insufficient for a determination.
"""

from __future__ import annotations

from app.knowledge_base import KnowledgeBase, Snapshot, SymbolInfo
from app.parser import ParseResult, CallInfo, parse_python_code
from app.schemas import (
    Evidence,
    Issue,
    IssueType,
    Metadata,
    OverallStatus,
    Severity,
    Suggestion,
    VerifiedItem,
    VerifyResponse,
)
from app.suggestions import suggest_keyword_correction, suggest_symbol_correction


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def verify_code(
    code: str,
    library: str,
    version: str,
    knowledge_base: KnowledgeBase,
) -> VerifyResponse:
    """Verify *code* against the trusted API snapshot for *library*/*version*.

    Steps:
      1. Parse code into an AST (safe, no execution).
      2. Load the reference snapshot.
      3. Match calls to the target library.
      4. Validate symbols and keyword arguments.
      5. Generate suggestions where applicable.
      6. Compute overall status.

    Returns a fully populated ``VerifyResponse``.
    """
    issues: list[Issue] = []
    verified_items: list[VerifiedItem] = []
    suggestions: list[Suggestion] = []
    warnings: list[str] = []
    checks_performed: list[str] = []

    # ── 1. Parse ──────────────────────────────────────────────────────────
    parse_result = parse_python_code(code)

    if parse_result.error:
        return _syntax_error_response(parse_result, library, version)

    # ── 2. Load snapshot ──────────────────────────────────────────────────
    snapshot = knowledge_base.get_snapshot(library, version)

    if snapshot is None:
        if not knowledge_base.is_library_supported(library):
            return _unsupported_library_response(library, version)
        available = knowledge_base.list_available_versions(library)
        return _unsupported_version_response(library, version, available)

    checks_performed.extend([
        "import_analysis",
        "symbol_validation",
        "keyword_validation",
        "positional_argument_validation",
    ])

    # ── 3. Check for relevant imports ─────────────────────────────────────
    library_imports = [
        imp for imp in parse_result.imports
        if imp.module == library or imp.module.startswith(f"{library}.")
    ]
    if not library_imports:
        warnings.append(
            f"No imports of '{library}' found in the submitted code. "
            f"Verification is limited to resolved calls."
        )

    # ── 4. Validate each relevant call ────────────────────────────────────
    for call in parse_result.calls:
        if not _is_relevant_call(call, library, parse_result):
            continue

        resolved = call.resolved_function or call.function
        symbol_info = snapshot.lookup_symbol(resolved)

        if symbol_info is not None:
            _validate_keywords(
                call, symbol_info, snapshot,
                issues, verified_items, suggestions,
            )
        else:
            _handle_unknown_symbol(
                call, resolved, snapshot, issues, suggestions,
            )

    # ── 5. Overall status ─────────────────────────────────────────────────
    overall = _calculate_status(issues, verified_items)

    return VerifyResponse(
        overallStatus=overall,
        issues=issues,
        verifiedItems=verified_items,
        suggestions=suggestions,
        metadata=Metadata(
            library=library,
            version=version,
            checksPerformed=checks_performed,
            warnings=warnings,
            snapshotCompleteness=snapshot.snapshot_completeness,
        ),
    )


# ---------------------------------------------------------------------------
# Call relevance
# ---------------------------------------------------------------------------

def _is_relevant_call(
    call: CallInfo,
    library: str,
    parse_result: ParseResult,
) -> bool:
    """Return True if *call* relates to *library*.

    A call is relevant when:
      - Its resolved name starts with the library prefix, OR
      - Its raw name starts with the library prefix, OR
      - It was imported from the library (from-import).
    """
    resolved = call.resolved_function or ""
    raw = call.function

    if resolved == library or resolved.startswith(f"{library}."):
        return True
    if raw.startswith(f"{library}."):
        return True

    # Bare name that was from-imported from the library
    for imp in parse_result.imports:
        if imp.is_from_import and imp.module == library:
            local_name = imp.alias or imp.name
            if raw == local_name:
                return True

    return False


# ---------------------------------------------------------------------------
# Keyword validation
# ---------------------------------------------------------------------------

def _validate_keywords(
    call: CallInfo,
    symbol_info: SymbolInfo,
    snapshot: Snapshot,
    issues: list[Issue],
    verified_items: list[VerifiedItem],
    suggestions: list[Suggestion],
) -> None:
    """Validate positional and keyword arguments against the reference symbol."""
    resolved = call.resolved_function or call.function
    checks_passed: list[str] = ["symbol_exists"]

    evidence = Evidence(
        library=snapshot.library,
        version=snapshot.version,
        knownArguments=symbol_info.parameters,
        referenceSource=snapshot.source_url or snapshot.source_name,
        parameterCompleteness=symbol_info.parameter_completeness,
        positionalParameters=symbol_info.positional_parameters,
        maxPositionalArguments=symbol_info.max_positional_arguments,
        signatureCompleteness=symbol_info.signature_completeness,
    )

    # -- Dynamic argument warnings --
    if call.has_kwargs:
        issues.append(Issue(
            type=IssueType.INCOMPLETE_REFERENCE_DATA,
            severity=Severity.INFO,
            message=(
                f"Call to '{resolved}' uses **kwargs; dynamically supplied "
                f"keyword arguments cannot be fully verified statically."
            ),
            line=call.line,
            column=call.column,
            symbol=resolved,
        ))

    if call.has_starargs:
        issues.append(Issue(
            type=IssueType.INCOMPLETE_REFERENCE_DATA,
            severity=Severity.INFO,
            message=(
                f"Call to '{resolved}' uses *args; dynamically supplied "
                f"positional arguments cannot be fully verified statically."
            ),
            line=call.line,
            column=call.column,
            symbol=resolved,
        ))

    # -- Positional argument validation --
    has_positional_error = False
    if (
        symbol_info.signature_completeness in ("verified", "complete")
        and symbol_info.max_positional_arguments is not None
    ):
        if call.positional_arg_count > symbol_info.max_positional_arguments:
            has_positional_error = True
            pos_names = (
                ", ".join(f"'{p}'" for p in symbol_info.positional_parameters)
                or "none"
            )
            issues.append(Issue(
                type=IssueType.EXCESSIVE_POSITIONAL_ARGUMENTS,
                severity=Severity.ERROR,
                message=(
                    f"Call to '{resolved}' accepts at most "
                    f"{symbol_info.max_positional_arguments} positional argument(s) "
                    f"({pos_names}), but {call.positional_arg_count} were given."
                ),
                line=call.line,
                column=call.column,
                symbol=resolved,
                evidence=evidence,
            ))
        else:
            checks_passed.append("positional_arguments_valid")
    elif call.positional_arg_count > 0:
        # Signature information is incomplete/unknown, and positional arguments were supplied
        issues.append(Issue(
            type=IssueType.INCOMPLETE_REFERENCE_DATA,
            severity=Severity.WARNING,
            message=(
                f"Call to '{resolved}' supplies {call.positional_arg_count} positional argument(s), "
                f"but signature reference data is marked as '{symbol_info.signature_completeness}'. "
                f"Positional arguments cannot be definitively verified."
            ),
            line=call.line,
            column=call.column,
            symbol=resolved,
            evidence=evidence,
        ))

    # -- Check each keyword argument --
    has_invalid = False
    for kw in call.keyword_arguments:
        if kw in symbol_info.parameters:
            checks_passed.append(f"keyword_{kw}_valid")
            continue

        if symbol_info.parameter_completeness in ("verified", "complete"):
            # Reference data is authoritative → report error
            has_invalid = True
            issues.append(Issue(
                type=IssueType.INVALID_KEYWORD,
                severity=Severity.ERROR,
                message=(
                    f"The keyword argument '{kw}' is not listed in the "
                    f"verified API reference for '{resolved}'."
                ),
                line=call.line,
                column=call.column,
                symbol=resolved,
                argument=kw,
                evidence=evidence,
            ))
            for sug in suggest_keyword_correction(kw, symbol_info.parameters):
                suggestions.append(Suggestion(
                    line=call.line,
                    symbol=resolved,
                    original=kw,
                    suggested=sug["suggested"],
                    reason=sug["reason"],
                ))
        else:
            # Parameter list is partial/unknown → uncertain
            issues.append(Issue(
                type=IssueType.INCOMPLETE_REFERENCE_DATA,
                severity=Severity.WARNING,
                message=(
                    f"The keyword argument '{kw}' is not in the reference "
                    f"data for '{resolved}', but the parameter list is "
                    f"marked as '{symbol_info.parameter_completeness}'. "
                    f"This keyword may or may not be valid."
                ),
                line=call.line,
                column=call.column,
                symbol=resolved,
                argument=kw,
                evidence=evidence,
            ))

    if not has_invalid:
        checks_passed.append("all_keywords_valid")

    verified_items.append(VerifiedItem(
        symbol=resolved,
        line=call.line,
        checksPassed=checks_passed,
    ))


# ---------------------------------------------------------------------------
# Unknown symbol handling
# ---------------------------------------------------------------------------

def _handle_unknown_symbol(
    call: CallInfo,
    resolved: str,
    snapshot: Snapshot,
    issues: list[Issue],
    suggestions: list[Suggestion],
) -> None:
    """Handle a symbol absent from the snapshot."""
    if snapshot.snapshot_completeness == "complete":
        # Snapshot claims completeness → symbol is likely invalid
        issues.append(Issue(
            type=IssueType.INVALID_SYMBOL,
            severity=Severity.ERROR,
            message=(
                f"The symbol '{resolved}' is not found in the verified "
                f"API reference for {snapshot.library} {snapshot.version}."
            ),
            line=call.line,
            column=call.column,
            symbol=resolved,
            evidence=Evidence(
                library=snapshot.library,
                version=snapshot.version,
                referenceSource=snapshot.source_url or snapshot.source_name,
                parameterCompleteness="n/a",
            ),
        ))
        for sug in suggest_symbol_correction(resolved, snapshot.list_symbols()):
            suggestions.append(Suggestion(
                line=call.line,
                symbol=resolved,
                original=resolved,
                suggested=sug["suggested"],
                reason=sug["reason"],
            ))
    else:
        # Snapshot is partial → cannot confirm invalidity
        issues.append(Issue(
            type=IssueType.UNRESOLVED_SYMBOL,
            severity=Severity.WARNING,
            message=(
                f"The symbol '{resolved}' is not in the reference data for "
                f"{snapshot.library} {snapshot.version}, but the snapshot "
                f"is marked as '{snapshot.snapshot_completeness}'. "
                f"This symbol may exist in the full API."
            ),
            line=call.line,
            column=call.column,
            symbol=resolved,
        ))


# ---------------------------------------------------------------------------
# Special responses
# ---------------------------------------------------------------------------

def _syntax_error_response(
    parse_result: ParseResult,
    library: str,
    version: str,
) -> VerifyResponse:
    err = parse_result.error or {}
    return VerifyResponse(
        overallStatus=OverallStatus.ERROR,
        issues=[Issue(
            type=IssueType.SYNTAX_ERROR,
            severity=Severity.ERROR,
            message=f"Syntax error: {err.get('message', 'Unknown')}",
            line=err.get("line"),
            column=err.get("column"),
            symbol="",
        )],
        metadata=Metadata(
            library=library,
            version=version,
            checksPerformed=["syntax_check"],
            warnings=["Code has syntax errors; verification was not performed."],
            snapshotCompleteness="n/a",
        ),
    )


def _unsupported_library_response(
    library: str, version: str,
) -> VerifyResponse:
    return VerifyResponse(
        overallStatus=OverallStatus.INCONCLUSIVE,
        issues=[Issue(
            type=IssueType.UNSUPPORTED_VERSION,
            severity=Severity.WARNING,
            message=(
                f"No reference data is available for library '{library}'."
            ),
            symbol=library,
        )],
        metadata=Metadata(
            library=library,
            version=version,
            warnings=[f"Library '{library}' has no reference data."],
            snapshotCompleteness="n/a",
        ),
    )


def _unsupported_version_response(
    library: str, version: str, available: list[str],
) -> VerifyResponse:
    avail_str = ", ".join(available) or "none"
    return VerifyResponse(
        overallStatus=OverallStatus.INCONCLUSIVE,
        issues=[Issue(
            type=IssueType.UNSUPPORTED_VERSION,
            severity=Severity.WARNING,
            message=(
                f"Version '{version}' of '{library}' has no reference data. "
                f"Available versions: {avail_str}."
            ),
            symbol=library,
        )],
        metadata=Metadata(
            library=library,
            version=version,
            warnings=[
                f"Version '{version}' unavailable. Available: {avail_str}."
            ],
            snapshotCompleteness="n/a",
        ),
    )


# ---------------------------------------------------------------------------
# Status calculation
# ---------------------------------------------------------------------------

def _calculate_status(
    issues: list[Issue],
    verified_items: list[VerifiedItem],
) -> OverallStatus:
    """Determine overall verification status.

    Rules:
      ERROR-severity issue present         → issues_found
      WARNING-severity issue present       → inconclusive
      Verified items with at most INFO     → passed
      Nothing verified, no issues          → inconclusive
    """
    has_errors = any(i.severity == Severity.ERROR for i in issues)
    has_warnings = any(i.severity == Severity.WARNING for i in issues)

    if has_errors:
        return OverallStatus.ISSUES_FOUND
    if has_warnings:
        return OverallStatus.INCONCLUSIVE
    if verified_items:
        return OverallStatus.PASSED
    return OverallStatus.INCONCLUSIVE
