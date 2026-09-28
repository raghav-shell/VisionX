"""Scan planning: negotiate every registered detector before anything runs."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from ..contracts import Availability, CalibrationRequirement, Negotiation
from .capabilities import CapabilitySet
from .detector import Detector, PlanContext
from .errors import ProfileError
from .profiles import CalibrationConfig, Profile
from .registry import DetectorRegistry

RUNNABLE = (Availability.READY, Availability.DEGRADED)


@dataclass
class PlannedCheck:
    detector: Detector
    negotiation: Negotiation
    params: BaseModel
    calibration: CalibrationConfig | None

    @property
    def runnable(self) -> bool:
        return self.negotiation.availability in RUNNABLE


def _calibration(detector: Detector, profile: Profile) -> CalibrationConfig | None:
    cfg = profile.detector_config(detector.spec.id)
    if cfg.calibration is not None:
        return cfg.calibration
    if detector.spec.calibration == CalibrationRequirement.NOT_APPLICABLE:
        return None
    return CalibrationConfig(source="uncalibrated", threshold=None,
                             threshold_origin="no calibration configured in the active profile")


def build_plan(registry: DetectorRegistry, caps: CapabilitySet, profile: Profile, plan_ctx: PlanContext
               ) -> list[PlannedCheck]:
    """Return one PlannedCheck per registered detector, in execution order. Nothing is dropped."""
    checks: dict[str, PlannedCheck] = {}
    for det_id in registry.order():
        det = registry.get(det_id)
        try:
            params = det.Params.model_validate(profile.detector_config(det_id).params)
        except ValidationError as exc:
            raise ProfileError(f"invalid parameters for {det_id}: {exc}") from exc
        neg = det.negotiate(caps, plan_ctx)
        if neg.availability in RUNNABLE and det.spec.depends_on:
            blocked = [(d, checks[d].negotiation.availability) for d in det.spec.depends_on
                       if checks[d].negotiation.availability not in RUNNABLE]
            if blocked:
                all_budget = all(a == Availability.BUDGET_EXCLUDED for _, a in blocked)
                neg = Negotiation(
                    detector_id=det_id,
                    availability=Availability.BUDGET_EXCLUDED if all_budget else Availability.UNAVAILABLE,
                    reasons=[f"depends on {d}, which is {a.value}" for d, a in blocked],
                )
        checks[det_id] = PlannedCheck(det, neg, params, _calibration(det, profile))
    if len(checks) != len(registry):  # pragma: no cover - defensive invariant
        raise AssertionError("planner dropped a registered detector")
    return list(checks.values())


def plan_counts(plan: list[PlannedCheck]) -> dict[str, int]:
    counts = {a.value: 0 for a in Availability}
    for check in plan:
        counts[check.negotiation.availability.value] += 1
    return counts
