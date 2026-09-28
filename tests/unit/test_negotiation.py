"""Capability negotiation invariants."""

from __future__ import annotations

from tests.helpers import DegradableDetector, ExpensiveDetector, LabelDetector, OkDetector
from visionsentinel.contracts import Availability, BudgetTier, Capability, SupportLevel
from visionsentinel.core import CapabilitySet, PlanContext

STANDARD = PlanContext(budget=BudgetTier.STANDARD)


def caps(*present: Capability, deny=()) -> CapabilitySet:
    return CapabilitySet.build({c: ("test", None) for c in present}, list(deny))


def test_detector_requiring_labels_is_never_ready_without_labels():
    neg = LabelDetector().negotiate(caps(Capability.DATASET_IMAGES), STANDARD)
    assert neg.availability == Availability.UNAVAILABLE
    assert Capability.DATASET_LABELS in neg.missing
    assert "Labels" in neg.reasons[0]


def test_ready_when_all_required_present():
    neg = LabelDetector().negotiate(caps(Capability.DATASET_IMAGES, Capability.DATASET_LABELS), STANDARD)
    assert neg.availability == Availability.READY
    assert neg.assessed_classes and all(a.level == SupportLevel.FULL for a in neg.assessed_classes)


def test_optional_capability_absent_degrades_and_downgrades_support():
    neg = DegradableDetector().negotiate(caps(Capability.MODEL_PREDICT), STANDARD)
    assert neg.availability == Availability.DEGRADED
    assert neg.mode == "query"
    assert all(a.level == SupportLevel.PARTIAL for a in neg.assessed_classes)
    full = DegradableDetector().negotiate(caps(Capability.MODEL_PREDICT, Capability.MODEL_GRADIENTS), STANDARD)
    assert full.availability == Availability.READY and full.mode == "gradient"


def test_withheld_capability_is_reported_as_policy_not_absence():
    neg = LabelDetector().negotiate(
        caps(Capability.DATASET_IMAGES, Capability.DATASET_LABELS, deny=[Capability.DATASET_LABELS]), STANDARD)
    assert neg.availability == Availability.UNAVAILABLE
    assert neg.withheld == [Capability.DATASET_LABELS]
    assert any("withheld by profile policy" in r for r in neg.reasons)


def test_blackbox_policy_prevents_whitebox_mode():
    neg = DegradableDetector().negotiate(
        caps(Capability.MODEL_PREDICT, Capability.MODEL_GRADIENTS, deny=[Capability.MODEL_GRADIENTS]), STANDARD)
    assert neg.mode == "query"
    assert neg.availability == Availability.DEGRADED


def test_budget_exclusion_is_distinct_from_unavailability():
    neg = ExpensiveDetector().negotiate(caps(Capability.DATASET_IMAGES), STANDARD)
    assert neg.availability == Availability.BUDGET_EXCLUDED
    assert ExpensiveDetector().negotiate(caps(Capability.DATASET_IMAGES),
                                         PlanContext(budget=BudgetTier.FORENSIC)).availability == Availability.READY


def test_missing_access_takes_precedence_over_budget():
    neg = ExpensiveDetector().negotiate(caps(), STANDARD)
    assert neg.availability == Availability.UNAVAILABLE


def test_precondition_blocks_with_scientific_reason():
    class Needy(OkDetector):
        def preconditions(self, caps, plan):
            return ["needs at least 5 classes (found 3)"] if plan.fact("classes", 0) < 5 else []

    neg = Needy().negotiate(caps(Capability.DATASET_IMAGES), PlanContext(BudgetTier.STANDARD, {"classes": 3}))
    assert neg.availability == Availability.UNAVAILABLE
    assert neg.reasons[0].startswith("precondition not met: needs at least 5 classes")
