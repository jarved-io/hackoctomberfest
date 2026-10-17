"""Schemas: deterministic input findings, raw model output, and final result."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["info", "warning", "error"]
FindingStatus = Literal["valid", "invalid", "unverified"]
AIStatus = Literal["ok", "unavailable", "invalid_response", "skipped"]


# ----------------------------------------------------------------- input side
class Finding(BaseModel):
    """One deterministic verification finding supplied by the backend."""

    model_config = ConfigDict(extra="ignore")

    line: int | None = None
    api: str                      # e.g. "requests.get"
    kind: str | None = None       # "import" | "function" | "class" | "argument" ...
    argument: str | None = None   # keyword name when kind == "argument"
    status: FindingStatus
    reason: str = ""              # validator's own explanation of the result
    closestValid: str | None = None  # validator's closest valid symbol/argument, if any


# ---------------------------------------------------------- raw model output
class ModelEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    line: int | None = None
    api: str
    status: FindingStatus
    note: str = ""


class ModelOutput(BaseModel):
    """What we ask Gemma to return. Anything else is rejected or ignored."""

    model_config = ConfigDict(extra="ignore")

    summary: str
    severity: Severity
    explanation: str
    evidence: list[ModelEvidenceRef] = Field(default_factory=list)
    suggestedAlternative: str | None = None
    correctedSnippet: str | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def _norm_severity(cls, v: Any) -> Any:
        return v.strip().lower() if isinstance(v, str) else v


# ------------------------------------------------------------- final result
class EvidenceItem(BaseModel):
    """Evidence always comes from the deterministic validator / trusted registry,
    never from model text."""

    line: int | None = None
    api: str
    kind: str | None = None
    argument: str | None = None
    status: FindingStatus
    source: Literal["deterministic_validator"] = "deterministic_validator"
    detail: str = ""
    registry: dict[str, Any] | None = None  # trusted registry entry for `api`, if supplied


class ExplanationResult(BaseModel):
    summary: str
    severity: Severity
    explanation: str
    evidence: list[EvidenceItem]
    suggestedAlternative: str | None = None
    correctedSnippet: str | None = None
    correctionIsPartial: bool = False
    aiStatus: AIStatus
    aiError: str | None = None     # machine-readable code when aiStatus != "ok"
    notes: list[str] = Field(default_factory=list)
    findings: list[dict[str, Any]]  # original deterministic findings, unchanged

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
