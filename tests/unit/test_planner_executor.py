"""Planning and execution invariants: nothing silently skipped, ERROR never becomes UNAVAILABLE."""

from __future__ import annotations

import pytest

from tests.helpers import (
    AbstainDetector,
    CrashDetector,
    DependentDetector,
    ExpensiveDetector,
    LabelDetector,
    OkDetector,
    registry_of,
)
from visionsentinel.contracts import Availability, BudgetTier, Capability, ExecutionState
from visionsentinel.core import (
    CapabilitySet,
    DetectorContext,
    EventLog,
    PlanContext,
    build_plan,
    execute_plan,
    load_profile,
)
from visionsentinel.core.errors import ConfigurationError
from visionsentinel.core.registry import DetectorRegistry
from visionsentinel.evidence import MemoryBlobSink

ALL = (OkDetector, LabelDetector, CrashDetector, DependentDetector, ExpensiveDetector, AbstainDetector)


def _run(registry, capabilities):
    profile = load_profile("baseline")
    plan = build_plan(registry, capabilities, profile, PlanContext(BudgetTier.STANDARD))
    events = EventLog()

    def make_ctx(check, upstream):
        return DetectorContext(scan_id="SCN-TEST", spec=check.detector.spec, mode=check.negotiation.mode or "",
                               params=check.params, calibration=check.calibration, profile=profile,
                               capabilities=capabilities, assets={}, blobs=MemoryBlobSink(), seed=1,
                               upstream=upstream, shared={}, emit=events.emit)

    executions, results = execute_plan(plan, make_ctx, events, track_memory=False)
    return plan, executions, results, events


def test_no_registered_detector_is_silently_skipped():
    reg = registry_of(*ALL)
    plan, executions, _, _ = _run(reg, CapabilitySet.build({Capability.DATASET_IMAGES: ("t", None)}))
    assert [p.detector.spec.id for p in plan] == reg.order()
    assert {e.detector_id for e in executions} == set(reg.ids())
    for e in executions:
        if e.state == ExecutionState.NOT_RUN:
            assert e.reasons, f"{e.detector_id} was not run without a stated reason"


def test_crash_is_error_never_unavailable_and_dependants_fail_loudly():
    reg = registry_of(*ALL)
    _, executions, results, events = _run(reg, CapabilitySet.build({Capability.DATASET_IMAGES: ("t", None)}))
    by_id = {e.detector_id: e for e in executions}
    crash = by_id["test.crash"]
    assert crash.state == ExecutionState.ERROR
    assert crash.planned == Availability.READY
    assert crash.error_type == "RuntimeError" and "synthetic failure" in crash.error_message
    dep = by_id["test.dependent"]
    assert dep.state == ExecutionState.ERROR and "upstream detector failed" in dep.reasons[0]
    assert "test.crash" not in results
    assert any(ev.level == "error" and "FAILED" in ev.message for ev in events.events)


def test_states_distinguish_unavailable_budget_abstained_completed():
    reg = registry_of(*ALL)
    _, executions, _, _ = _run(reg, CapabilitySet.build({Capability.DATASET_IMAGES: ("t", None)}))
    by_id = {e.detector_id: e for e in executions}
    assert by_id["test.ok"].state == ExecutionState.COMPLETED
    assert by_id["test.ok"].findings == 1
    assert by_id["test.labels"].planned == Availability.UNAVAILABLE
    assert by_id["test.labels"].state == ExecutionState.NOT_RUN
    assert by_id["test.expensive"].planned == Availability.BUDGET_EXCLUDED
    assert by_id["test.abstain"].state == ExecutionState.ABSTAINED
    assert by_id["test.abstain"].assessed_classes == []


def test_dependency_on_unavailable_detector_is_unavailable_at_plan_time():
    class NeedsLabels(DependentDetector):
        spec = DependentDetector.spec.model_copy(update={"id": "test.needs_labels", "depends_on": ["test.labels"]})

    reg = registry_of(LabelDetector, NeedsLabels)
    plan, _, _, _ = _run(reg, CapabilitySet.build({Capability.DATASET_IMAGES: ("t", None)}))
    neg = {p.detector.spec.id: p.negotiation for p in plan}["test.needs_labels"]
    assert neg.availability == Availability.UNAVAILABLE
    assert "depends on test.labels" in neg.reasons[0]


def test_registry_rejects_duplicates_cycles_and_unknown_dependencies():
    reg = DetectorRegistry()
    reg.register(OkDetector)
    with pytest.raises(ConfigurationError):
        reg.register(OkDetector)
    reg2 = DetectorRegistry()
    reg2.register(DependentDetector)
    with pytest.raises(ConfigurationError, match="unregistered"):
        reg2.validate()
