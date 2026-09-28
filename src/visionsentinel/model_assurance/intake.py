"""Model artifact intake: report artifacts rejected at the security boundary as evidenced findings."""

from __future__ import annotations

from ..contracts import (
    AssetType,
    AttackSupport,
    CalibrationRequirement,
    DetectorMode,
    DetectorSpec,
    EvidenceKind,
    Layer,
    ProposedFinding,
    RuntimeClass,
    Severity,
    SupportLevel,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, PlanContext
from .common import MODEL_ASSUMPTIONS, stat


class ModelIntake(Detector):
    spec = DetectorSpec(
        id="model.intake", version="1.0.0", title="Model artifact intake", layer=Layer.MODEL,
        summary="Reports every supplied model artifact that the loaders or the sandbox refused (unsafe pickle payloads, "
                "external data references, oversize tensors, malformed graphs) together with the isolation in force.",
        modes=[DetectorMode(name="deterministic", description="loader and sandbox verdicts")],
        supports=[AttackSupport(attack_class="malicious_artifact", level=SupportLevel.FULL,
                                note="payloads that the loaders or sandbox refuse")],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.TEXT, EvidenceKind.STATISTIC],
        limitations=["A payload that exploits a native runtime without triggering a refusal is contained by the sandbox "
                     "but not necessarily detected."],
        access_assumptions=MODEL_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
    )

    def preconditions(self, caps, plan: PlanContext) -> list[str]:
        return [] if plan.fact("model.supplied") else ["no model artifact was supplied"]

    def run(self, ctx: DetectorContext) -> DetectorResult:
        rejected = ctx.optional_asset("rejected_models") or []
        res = DetectorResult(samples_processed=int(ctx.optional_asset("models_supplied") or 0))
        for item in rejected:
            res.findings.append(ProposedFinding(
                attack_class="malicious_artifact", asset_type=AssetType.MODEL, asset_id=item["name"],
                subject=f"intake:{item['role']}", severity=Severity.HIGH, confidence=1.0,
                title=f"{item['role'].replace('_', ' ').capitalize()} rejected at the security boundary",
                reason=(f"Loading {item['name']} ({item['role'].replace('_', ' ')}) was refused: {item['error']}. The "
                        "artifact was never executed outside the sandbox; nothing about its behaviour can be assessed."),
                evidence=[stat(ctx, "Intake verdict", "Loader / sandbox refusal.",
                               {"artifact": item["name"], "role": item["role"], "error": item["error"],
                                "error_type": item["type"], "sha256": item.get("digest")})],
                access_assumptions=MODEL_ASSUMPTIONS, limitations=self.spec.limitations, deterministic=True,
                calibrated=True, recommended_action="Quarantine the file and establish its origin; do not attempt to load it "
                "outside the sandbox."))
        return res
