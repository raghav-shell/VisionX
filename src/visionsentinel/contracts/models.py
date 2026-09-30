"""Pydantic domain objects.

Every model forbids unknown fields so that a typo in a profile, a scenario manifest or an API
payload fails loudly instead of being ignored.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .catalog import ATTACK_CLASSES
from .enums import (
    AssetType,
    Availability,
    BudgetTier,
    CalibrationRequirement,
    Capability,
    CoverageState,
    Disposition,
    EvidenceKind,
    ExecutionState,
    Layer,
    RuntimeClass,
    ScanStatus,
    Severity,
    SupportLevel,
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=False, ser_json_inf_nan="strings")


# --------------------------------------------------------------------------- detector declaration


class AttackSupport(Contract):
    attack_class: str
    level: SupportLevel
    note: str = ""

    @field_validator("attack_class")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in ATTACK_CLASSES:
            raise ValueError(f"unknown attack class {v!r}")
        return v


class UnsupportedAttack(Contract):
    attack_class: str
    reason: str

    @field_validator("attack_class")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in ATTACK_CLASSES:
            raise ValueError(f"unknown attack class {v!r}")
        return v


class DetectorMode(Contract):
    """A named execution mode and the capabilities it needs beyond ``required``."""

    name: str
    description: str
    needs: list[Capability] = Field(default_factory=list)
    degraded: bool = False
    min_budget: BudgetTier | None = None
    # Attack-class support is downgraded to PARTIAL in degraded modes unless listed here.
    support_override: list[AttackSupport] = Field(default_factory=list)


class DetectorSpec(Contract):
    id: str = Field(pattern=r"^[a-z]+\.[a-z0-9_]+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    title: str
    layer: Layer
    summary: str
    required: list[Capability] = Field(default_factory=list)
    required_any: list[list[Capability]] = Field(
        default_factory=list, description="Each inner list must have at least one capability present."
    )
    optional: list[Capability] = Field(default_factory=list)
    modes: list[DetectorMode] = Field(min_length=1)
    supports: list[AttackSupport] = Field(min_length=1)
    unsupported: list[UnsupportedAttack] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    runtime: RuntimeClass
    min_budget: BudgetTier = BudgetTier.TRIAGE
    evidence_kinds: list[EvidenceKind] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    access_assumptions: list[str] = Field(default_factory=list)
    deterministic: bool
    calibration: CalibrationRequirement
    references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "DetectorSpec":
        supported = {s.attack_class for s in self.supports}
        overlap = supported & {u.attack_class for u in self.unsupported}
        if overlap:
            raise ValueError(f"attack classes both supported and unsupported: {sorted(overlap)}")
        names = [m.name for m in self.modes]
        if len(names) != len(set(names)):
            raise ValueError("duplicate mode names")
        return self


class Negotiation(Contract):
    detector_id: str
    availability: Availability
    mode: str | None = None
    missing: list[Capability] = Field(default_factory=list)
    withheld: list[Capability] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    assessed_classes: list[AttackSupport] = Field(default_factory=list)


class DetectorExecution(Contract):
    detector_id: str
    detector_version: str
    title: str
    layer: Layer
    planned: Availability
    mode: str | None
    state: ExecutionState
    reasons: list[str] = Field(default_factory=list)
    assessed_classes: list[AttackSupport] = Field(default_factory=list)
    runtime_ms: float = 0.0
    samples_processed: int = 0
    peak_memory_bytes: int = 0
    findings: int = 0
    error_type: str | None = None
    error_message: str | None = None
    calibrated: bool | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- evidence


class BlobRef(Contract):
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_type: Literal["image/png", "application/json"]
    size_bytes: int = Field(ge=0)


class Evidence(Contract):
    id: str
    kind: EvidenceKind
    title: str
    summary: str
    data: dict[str, Any] | None = None
    blob: BlobRef | None = None


class SampleRef(Contract):
    sample_id: str
    contributor: str | None = None
    label: str | None = None
    note: str | None = None


# --------------------------------------------------------------------------- findings


class ProposedFinding(Contract):
    """What a detector reports. Disposition is assigned later by the risk engine."""

    attack_class: str
    asset_type: AssetType
    asset_id: str
    subject: str = Field(description="Stable key of what the finding is about, used to match findings across scans.")
    title: str = Field(min_length=8)
    reason: str = Field(min_length=24)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    raw_score: float | None = None
    threshold: float | None = None
    score_semantics: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    evidence_unavailable_reason: str | None = None
    access_assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    affected_samples: list[SampleRef] = Field(default_factory=list)
    affected_count: int = 0
    affected_contributors: list[str] = Field(default_factory=list)
    corroborating_signals: list[str] = Field(default_factory=list)
    deterministic: bool = False
    calibrated: bool = False
    recommended_action: str = ""
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("attack_class")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in ATTACK_CLASSES:
            raise ValueError(f"unknown attack class {v!r}")
        return v

    @model_validator(mode="after")
    def _evidence_or_reason(self) -> "ProposedFinding":
        if not self.evidence and not self.evidence_unavailable_reason:
            raise ValueError("a finding must carry evidence or state why evidence is unavailable")
        if self.affected_count < len(self.affected_samples):
            self.affected_count = len(self.affected_samples)
        return self


class Finding(ProposedFinding):
    id: str
    scan_id: str
    detector_id: str
    detector_version: str
    proposed_severity: Severity
    recommended_disposition: Disposition
    availability: Availability
    policy_rule: str
    policy_digest: str
    guardrails: list[str] = Field(default_factory=list)
    created_at: datetime


# --------------------------------------------------------------------------- coverage


class CoverageRow(Contract):
    attack_class: str
    layer: Layer
    title: str
    state: CoverageState
    detectors: list[str] = Field(default_factory=list)
    failed_detectors: list[str] = Field(default_factory=list)
    reason: str
    required_access: list[Capability] = Field(default_factory=list)
    recommended_evidence: list[str] = Field(default_factory=list)


class CoverageStatement(Contract):
    rows: list[CoverageRow]
    total: int
    assessed: int
    partial: int
    not_assessed: int
    failed: int
    unsupported: int

    @model_validator(mode="after")
    def _validate_aggregates(self) -> "CoverageStatement":
        """Keep exported coverage mathematically tied to its authoritative rows."""
        attack_classes = [row.attack_class for row in self.rows]
        if len(attack_classes) != len(set(attack_classes)):
            raise ValueError("coverage rows contain duplicate attack_class values")
        if self.total != len(self.rows):
            raise ValueError("coverage total must equal the number of rows")
        counts = {state: sum(row.state is state for row in self.rows) for state in CoverageState}
        supplied = {
            CoverageState.ASSESSED: self.assessed,
            CoverageState.PARTIALLY_ASSESSED: self.partial,
            CoverageState.NOT_ASSESSED: self.not_assessed,
            CoverageState.FAILED_TO_EXECUTE: self.failed,
            CoverageState.UNSUPPORTED: self.unsupported,
        }
        for state in CoverageState:
            if supplied[state] != counts[state]:
                raise ValueError(f"coverage {state.value} count disagrees with row states")
        if sum(supplied.values()) != self.total:
            raise ValueError("coverage aggregate counts must sum to total")
        return self

    @property
    def fraction_assessed(self) -> float:
        return self.assessed / self.total if self.total else 0.0


# --------------------------------------------------------------------------- scans


class AssetDescriptor(Contract):
    role: AssetType
    asset_id: str
    name: str
    path: str
    digest: str | None = None
    format: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CapabilityRecord(Contract):
    capability: Capability
    present: bool
    withheld: bool = False
    source: str | None = None
    note: str | None = None


class ScanEvent(Contract):
    seq: int
    t_ms: int
    level: Literal["info", "warn", "error", "stage"]
    message: str
    detector_id: str | None = None


class ContributorAssessment(Contract):
    contributor: str
    samples: int
    flagged: int
    flagged_weighted: float
    baseline_rate: float
    expected_low: int
    expected_high: int
    posterior_mean: float
    credible_low: float
    credible_high: float
    posterior_anomaly: float = Field(description="P(flag rate > excess_factor × baseline | data)")
    evidence_strength: Literal["NONE", "LOW", "MEDIUM", "HIGH"]
    risk_tier: Literal["LOW", "ELEVATED", "HIGH", "CRITICAL"]
    dominant_signals: list[str] = Field(default_factory=list)
    signal_breakdown: dict[str, float] = Field(default_factory=dict)
    campaign_findings: list[str] = Field(default_factory=list)
    batches: dict[str, dict[str, int]] = Field(default_factory=dict)
    recommended_action: Disposition
    rationale: list[str] = Field(default_factory=list)


class GraphNode(Contract):
    id: str
    type: Literal[
        "Asset", "Dataset", "Sample", "Contributor", "Model", "Detector", "Finding",
        "InferenceRecord", "Decision", "Evidence", "Signal", "Class",
    ]
    label: str
    attrs: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(Contract):
    source: str
    target: str
    type: Literal[
        "SUPPLIED_BY", "FLAGGED_BY", "SUPPORTED_BY", "GENERATED_BY", "DECIDED_BY", "DERIVED_FROM",
        "USES_MODEL", "USES_INPUT", "CORRELATES_WITH", "ABOUT", "EXECUTED",
    ]
    attrs: dict[str, Any] = Field(default_factory=dict)


class EvidenceGraph(Contract):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class ReproductionInfo(Contract):
    seed: int
    profile: str
    profile_digest: str
    software_version: str
    git_commit: str | None
    python: str
    platform: str
    libraries: dict[str, str]
    runtime_settings: dict[str, Any]
    encoder: str | None = None
    scan_time: datetime
    determinism_note: str


class ScanSummary(Contract):
    findings: int
    by_severity: dict[Severity, int]
    by_disposition: dict[Disposition, int]
    asset_dispositions: dict[str, Disposition]
    coverage_assessed: int
    coverage_partial: int
    coverage_total: int
    detectors_completed: int
    detectors_degraded: int
    detectors_unavailable: int
    detectors_error: int
    detectors_abstained: int
    detectors_budget_excluded: int
    overall_disposition: Disposition


class ScanResult(Contract):
    scan_id: str
    name: str
    status: ScanStatus
    profile: str
    budget: BudgetTier
    created_at: datetime
    completed_at: datetime | None = None
    assets: list[AssetDescriptor]
    capabilities: list[CapabilityRecord]
    plan: list[Negotiation]
    executions: list[DetectorExecution]
    findings: list[Finding]
    coverage: CoverageStatement
    contributors: list[ContributorAssessment] = Field(default_factory=list)
    graph: EvidenceGraph = Field(default_factory=EvidenceGraph)
    sections: dict[str, Any] = Field(default_factory=dict, description="Layer-specific result panels (model, drift, provenance, data).")
    events: list[ScanEvent] = Field(default_factory=list)
    summary: ScanSummary | None = None
    reproduction: ReproductionInfo | None = None
    report_digest: str | None = None
