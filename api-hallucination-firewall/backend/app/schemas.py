"""
Pydantic models for API request validation and response serialization.

These schemas define the stable contract between the backend and frontend.
All field names, types, and meanings are documented for integration.

Top-level response fields:
  overallStatus  — Summary verification result.
  issues         — Problems or uncertainties detected.
  verifiedItems  — Usages that passed applicable checks.
  suggestions    — Deterministic correction suggestions.
  metadata       — Information about the verification process.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class OverallStatus(str, Enum):
    """Top-level verification result.

    Values:
      passed        — All applicable checks completed with no errors.
      issues_found  — At least one confirmed issue was detected.
      inconclusive  — Reference data is insufficient for a reliable result.
      error         — The verification request could not be processed.
    """
    PASSED = "passed"
    ISSUES_FOUND = "issues_found"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"


class IssueType(str, Enum):
    """Classification of a detected issue."""
    INVALID_IMPORT = "invalid_import"
    INVALID_SYMBOL = "invalid_symbol"
    INVALID_KEYWORD = "invalid_keyword"
    INVALID_ARGUMENT = "invalid_argument"
    INVALID_POSITIONAL_ARGUMENT = "invalid_positional_argument"
    EXCESSIVE_POSITIONAL_ARGUMENTS = "excessive_positional_arguments"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNRESOLVED_SYMBOL = "unresolved_symbol"
    INCOMPLETE_REFERENCE_DATA = "incomplete_reference_data"
    SYNTAX_ERROR = "syntax_error"


class Severity(str, Enum):
    """Issue severity level.

    error   — Confirmed problem backed by reference data.
    warning — Potential problem; reference data is incomplete.
    info    — Informational note (e.g. dynamic args cannot be checked).
    """
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    """Request body for POST /api/verify.

    Attributes:
        code:             Python source code to analyze (1–50 000 chars).
        library:          Target library to verify against.
        version:          Target library version string (e.g. "2.31.0").
        requirementsText: Optional requirements.txt content for version hints.
    """
    code: str = Field(
        ...,
        min_length=1,
        max_length=50_000,
        description="Python source code to analyze",
    )
    library: str = Field(
        default="requests",
        min_length=1,
        max_length=100,
        description="Target library name",
    )
    version: str = Field(
        default="2.31.0",
        min_length=1,
        max_length=50,
        description="Target library version (e.g. '2.31.0')",
    )
    requirementsText: str | None = Field(
        default=None,
        description="Optional requirements.txt content",
    )
    explain: bool = Field(
        default=True,
        description="Ask the Gemma explanation layer to explain confirmed/unverified findings",
    )


# ---------------------------------------------------------------------------
# Response — nested models
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """Reference-data evidence supporting an issue finding."""
    library: str = Field(description="Library name")
    version: str = Field(description="Version checked")
    knownArguments: list[str] = Field(
        default_factory=list,
        description="Valid arguments from reference data",
    )
    referenceSource: str = Field(
        default="",
        description="Provenance (e.g. documentation URL)",
    )
    parameterCompleteness: str = Field(
        default="unknown",
        description="verified | partial | unknown",
    )
    positionalParameters: list[str] = Field(
        default_factory=list,
        description="Parameters accepted positionally",
    )
    maxPositionalArguments: int | None = Field(
        default=None,
        description="Maximum positional arguments accepted",
    )
    signatureCompleteness: str = Field(
        default="unknown",
        description="verified | partial | unknown",
    )


class Issue(BaseModel):
    """A single verification finding."""
    type: IssueType
    severity: Severity
    message: str
    line: int | None = Field(default=None, description="1-based line number")
    column: int | None = Field(default=None, description="0-based column offset")
    symbol: str = Field(default="", description="API symbol involved")
    argument: str | None = Field(default=None, description="Keyword argument involved")
    evidence: Evidence | None = Field(default=None)


class Suggestion(BaseModel):
    """A deterministic correction suggestion backed by reference data."""
    line: int | None = None
    symbol: str
    original: str
    suggested: str
    reason: str


class VerifiedItem(BaseModel):
    """An API usage that passed applicable checks."""
    symbol: str
    line: int | None = None
    checksPassed: list[str] = Field(default_factory=list)


class Metadata(BaseModel):
    """Verification process metadata."""
    library: str
    version: str
    checksPerformed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    snapshotCompleteness: str = Field(default="unknown")


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class VerifyResponse(BaseModel):
    """Response from POST /api/verify."""
    overallStatus: OverallStatus
    issues: list[Issue] = Field(default_factory=list)
    verifiedItems: list[VerifiedItem] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    metadata: Metadata
    ai: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Gemma explanation of the deterministic findings (see ai_module.schemas."
            "ExplanationResult). Null when there was nothing to explain or explain=false. "
            "Never affects overallStatus."
        ),
    )