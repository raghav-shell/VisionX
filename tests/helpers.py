"""Test doubles shared by several test modules."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from visionsentinel.contracts import (
    AssetType,
    AttackSupport,
    BudgetTier,
    CalibrationRequirement,
    Capability,
    DetectorMode,
    DetectorSpec,
    Evidence,
    EvidenceKind,
    Layer,
    ProposedFinding,
    RuntimeClass,
    Severity,
    SupportLevel,
)
from visionsentinel.core import Detector, DetectorContext, DetectorResult, DetectorRegistry, Params


def make_spec(id: str, *, required=(), optional=(), modes=None, supports=None, depends_on=(),
              min_budget=BudgetTier.TRIAGE, calibration=CalibrationRequirement.NOT_APPLICABLE,
              layer=Layer.DATA, deterministic=True) -> DetectorSpec:
    return DetectorSpec(
        id=id, version="1.0.0", title=f"Test {id}", layer=layer, summary="test detector",
        required=list(required), optional=list(optional),
        modes=modes or [DetectorMode(name="default", description="full")],
        supports=supports or [AttackSupport(attack_class="label_flip", level=SupportLevel.FULL)],
        depends_on=list(depends_on), runtime=RuntimeClass.FAST, min_budget=min_budget,
        evidence_kinds=[EvidenceKind.STATISTIC], limitations=["test only"], deterministic=deterministic,
        calibration=calibration,
    )


def finding(**over) -> ProposedFinding:
    base = dict(
        attack_class="label_flip", asset_type=AssetType.DATASET, asset_id="ds", subject="s1",
        title="Test finding title", reason="Sample s1 disagrees with 9 of 10 nearest neighbours.",
        severity=Severity.MEDIUM, confidence=0.7,
        evidence=[Evidence(id="EV-1", kind=EvidenceKind.STATISTIC, title="stat", summary="summary")],
    )
    base.update(over)
    return ProposedFinding(**base)


class ThresholdParams(Params):
    threshold: float = Field(default=0.5, ge=0, le=1)


class OkDetector(Detector):
    spec: ClassVar[DetectorSpec] = make_spec("test.ok", required=[Capability.DATASET_IMAGES])
    Params = ThresholdParams

    def run(self, ctx: DetectorContext) -> DetectorResult:
        return DetectorResult(findings=[finding()], samples_processed=3)


class LabelDetector(Detector):
    spec: ClassVar[DetectorSpec] = make_spec(
        "test.labels", required=[Capability.DATASET_IMAGES, Capability.DATASET_LABELS])

    def run(self, ctx: DetectorContext) -> DetectorResult:
        return DetectorResult()


class DegradableDetector(Detector):
    spec: ClassVar[DetectorSpec] = make_spec(
        "test.degradable", required=[Capability.MODEL_PREDICT],
        optional=[Capability.MODEL_GRADIENTS],
        modes=[DetectorMode(name="gradient", description="white-box", needs=[Capability.MODEL_GRADIENTS]),
               DetectorMode(name="query", description="query-based", degraded=True)],
        supports=[AttackSupport(attack_class="model_backdoor_patch", level=SupportLevel.FULL)],
        layer=Layer.MODEL)

    def run(self, ctx: DetectorContext) -> DetectorResult:
        return DetectorResult(samples_processed=1)


class CrashDetector(Detector):
    spec: ClassVar[DetectorSpec] = make_spec("test.crash", required=[Capability.DATASET_IMAGES])

    def run(self, ctx: DetectorContext) -> DetectorResult:
        raise RuntimeError("synthetic failure")


class DependentDetector(Detector):
    spec: ClassVar[DetectorSpec] = make_spec("test.dependent", required=[Capability.DATASET_IMAGES],
                                             depends_on=["test.crash"])

    def run(self, ctx: DetectorContext) -> DetectorResult:
        return DetectorResult()


class ExpensiveDetector(Detector):
    spec: ClassVar[DetectorSpec] = make_spec("test.expensive", required=[Capability.DATASET_IMAGES],
                                             min_budget=BudgetTier.FORENSIC)

    def run(self, ctx: DetectorContext) -> DetectorResult:
        return DetectorResult()


class AbstainDetector(Detector):
    spec: ClassVar[DetectorSpec] = make_spec("test.abstain", required=[Capability.DATASET_IMAGES])

    def run(self, ctx: DetectorContext) -> DetectorResult:
        return DetectorResult(abstained="every class has fewer than 30 samples")


def registry_of(*classes) -> DetectorRegistry:
    reg = DetectorRegistry()
    for c in classes:
        reg.register(c)
    reg.validate()
    return reg
