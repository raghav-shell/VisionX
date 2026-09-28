"""Detector plugin contract and capability negotiation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict

from ..contracts import (
    AttackSupport,
    Availability,
    BudgetTier,
    Capability,
    DetectorSpec,
    Negotiation,
    ProposedFinding,
    Severity,
    SupportLevel,
)
from .capabilities import CapabilitySet

if TYPE_CHECKING:  # pragma: no cover
    from .context import DetectorContext


class EmptyParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Params(BaseModel):
    """Base class for detector parameter models (strict, immutable)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class PlanContext:
    budget: BudgetTier
    facts: dict[str, Any] = field(default_factory=dict)

    def fact(self, key: str, default: Any = None) -> Any:
        return self.facts.get(key, default)


@dataclass(frozen=True)
class SampleFlag:
    """One detector's statement that one sample is suspicious (feeds contributor risk)."""

    sample_id: str
    contributor: str | None
    attack_class: str
    signal: str
    confidence: float
    severity: Severity
    batch: str | None = None


@dataclass
class DetectorResult:
    findings: list[ProposedFinding] = field(default_factory=list)
    flags: list[SampleFlag] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    samples_processed: int = 0
    abstained: str | None = None
    notes: list[str] = field(default_factory=list)
    section: dict[str, Any] | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    assessed_override: list[AttackSupport] | None = None


class Detector(ABC):
    spec: ClassVar[DetectorSpec]
    Params: ClassVar[type[BaseModel]] = EmptyParams

    def preconditions(self, caps: CapabilitySet, plan: PlanContext) -> list[str]:
        """Scientific or structural prerequisites; any returned reason makes the detector UNAVAILABLE."""
        return []

    def negotiate(self, caps: CapabilitySet, plan: PlanContext) -> Negotiation:
        return negotiate_spec(self.spec, caps, plan, lambda: self.preconditions(caps, plan))

    @abstractmethod
    def run(self, ctx: "DetectorContext") -> DetectorResult:  # pragma: no cover - interface
        ...


def degrade(supports: list[AttackSupport], overrides: list[AttackSupport]) -> list[AttackSupport]:
    by_class = {o.attack_class: o for o in overrides}
    out = []
    for s in supports:
        if s.attack_class in by_class:
            out.append(by_class[s.attack_class])
        else:
            out.append(AttackSupport(attack_class=s.attack_class, level=SupportLevel.PARTIAL,
                                     note=(s.note + " " if s.note else "") + "(degraded mode)"))
    return out


def negotiate_spec(spec: DetectorSpec, caps: CapabilitySet, plan: PlanContext, preconditions) -> Negotiation:
    """Match a detector declaration against available capabilities, budget and prerequisites.

    Order of evaluation: required capabilities → any-of groups → preconditions → budget → mode.
    An access problem is reported in preference to a budget exclusion because it is the more
    fundamental statement ("could not run here at all" vs "was not run at this budget").
    """
    missing = [c for c in spec.required if not caps.has(c)]
    for group in spec.required_any:
        if not any(caps.has(c) for c in group):
            missing.extend(c for c in group if c not in missing)
    if missing:
        withheld = [c for c in missing if caps.withheld(c)]
        reasons = []
        absent = [c for c in missing if c not in withheld]
        if absent:
            reasons.append("required access not present: " + ", ".join(caps.describe(c) for c in absent))
        if withheld:
            reasons.append("required access withheld by profile policy: " + ", ".join(caps.describe(c) for c in withheld))
        return Negotiation(detector_id=spec.id, availability=Availability.UNAVAILABLE, missing=missing,
                           withheld=withheld, reasons=reasons)

    blocked = preconditions()
    if blocked:
        return Negotiation(detector_id=spec.id, availability=Availability.UNAVAILABLE,
                           reasons=["precondition not met: " + r for r in blocked])

    if spec.min_budget.rank > plan.budget.rank:
        return Negotiation(detector_id=spec.id, availability=Availability.BUDGET_EXCLUDED,
                           reasons=[f"requires budget {spec.min_budget.value} or higher; profile budget is "
                                    f"{plan.budget.value}"])

    skipped: list[str] = []
    for mode in spec.modes:
        lacking = [c for c in mode.needs if not caps.has(c)]
        if lacking:
            skipped.append(f"mode '{mode.name}' needs " + ", ".join(caps.describe(c) for c in lacking))
            continue
        if mode.min_budget and mode.min_budget.rank > plan.budget.rank:
            skipped.append(f"mode '{mode.name}' requires budget {mode.min_budget.value}")
            continue
        assessed = degrade(spec.supports, mode.support_override) if mode.degraded else list(spec.supports)
        reasons = [f"mode '{mode.name}': {mode.description}"]
        if mode.degraded:
            reasons = skipped + reasons
        return Negotiation(
            detector_id=spec.id,
            availability=Availability.DEGRADED if mode.degraded else Availability.READY,
            mode=mode.name,
            withheld=[c for c in spec.optional if caps.withheld(c)],
            reasons=reasons,
            assessed_classes=assessed,
        )

    lacking_caps = sorted({c for m in spec.modes for c in m.needs if not caps.has(c)}, key=lambda c: c.value)
    reasons = ["no execution mode is satisfiable: " + "; ".join(skipped)]
    budget_only = all("requires budget" in s for s in skipped)
    return Negotiation(
        detector_id=spec.id,
        availability=Availability.BUDGET_EXCLUDED if budget_only else Availability.UNAVAILABLE,
        missing=lacking_caps,
        withheld=[c for c in lacking_caps if caps.withheld(c)],
        reasons=reasons,
    )
