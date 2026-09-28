"""Backdoor indicators on a genuinely data-poisoned model versus its clean counterpart."""

from __future__ import annotations

import pytest

from visionsentinel.attacklab.corpus import load_truth
from visionsentinel.contracts import Availability, Severity
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan


def _by(result, detector):
    return [f for f in result.findings if f.detector_id == detector]


@pytest.fixture(scope="module")
def strip_scans(model_zoo, tmp_path_factory):
    out = {}
    for name in ("backdoor", "approved"):
        ws = Workspace(tmp_path_factory.mktemp(f"strip-{name}")).ensure()
        out[name] = run_scan(ScanRequest(model=model_zoo[name], probe_dataset=model_zoo["probe"],
                                         suspect_inputs=model_zoo["suspect"], profile="selftest"), workspace=ws)
    return out


def test_strip_flags_trigger_carrying_inputs_on_the_backdoored_model(strip_scans, model_zoo):
    truth = load_truth(model_zoo["suspect"])
    triggered = {k for k, v in truth.items() if v["attacks"]}
    f = [x for x in _by(strip_scans["backdoor"], "model.strip") if x.subject == "strip:flagged"]
    assert f, "no trigger-dominated inputs found on the backdoored model"
    flagged = {s.sample_id for s in f[0].affected_samples}
    assert len(flagged & triggered) >= 0.7 * len(triggered)
    assert len(flagged - triggered) <= 3
    assert f[0].tags.get("target_class") == "civilian_vehicle"
    assert f[0].calibrated, "STRIP is calibrated on held-out clean inputs every scan"


def test_strip_on_the_clean_model_flags_far_fewer_inputs(strip_scans):
    def count(r):
        f = [x for x in _by(r, "model.strip") if x.subject == "strip:flagged"]
        return f[0].affected_count if f else 0
    assert count(strip_scans["approved"]) < count(strip_scans["backdoor"]) / 2


def test_strip_is_unavailable_without_suspect_inputs(model_zoo, tmp_path):
    r = run_scan(ScanRequest(model=model_zoo["backdoor"], probe_dataset=model_zoo["probe"], profile="selftest"),
                 workspace=Workspace(tmp_path / "ws").ensure())
    ex = {e.detector_id: e for e in r.executions}["model.strip"]
    assert ex.planned == Availability.UNAVAILABLE
    assert "Suspect inputs" in ex.reasons[0]
    row = {c.attack_class: c for c in r.coverage.rows}["runtime_trigger_input"]
    assert row.state.value == "NOT_ASSESSED" and any("suspected of carrying a trigger" in e for e in row.recommended_evidence)


def test_blackbox_stress_reports_anomalies_not_a_verdict(model_zoo, tmp_path):
    r = run_scan(ScanRequest(model=model_zoo["backdoor"], reference_model=model_zoo["approved"],
                             probe_dataset=model_zoo["probe"], profile="selftest"),
                 workspace=Workspace(tmp_path / "ws").ensure())
    f = _by(r, "model.blackbox_stress")[0]
    assert f.title == "Behavioural anomalies observed under black-box stress testing"
    assert "backdoor" not in f.title.lower().replace("black-box", "")
    assert "patch-triggered class redirection" in f.corroborating_signals
    assert f.tags["target_class"] == "civilian_vehicle"


def test_blackbox_stress_is_quiet_for_the_approved_model_itself(model_zoo, tmp_path):
    r = run_scan(ScanRequest(model=model_zoo["copy"], reference_model=model_zoo["approved"],
                             probe_dataset=model_zoo["probe"], profile="selftest"),
                 workspace=Workspace(tmp_path / "ws").ensure())
    f = _by(r, "model.blackbox_stress")[0]
    assert f.severity == Severity.INFO


@pytest.fixture(scope="module")
def poisoned_scan(model_zoo, tmp_path_factory):
    ws = Workspace(tmp_path_factory.mktemp("poisoned")).ensure()
    return run_scan(ScanRequest(dataset=model_zoo["poisoned"], model=model_zoo["backdoor"],
                                probe_dataset=model_zoo["probe"], profile="selftest"), workspace=ws)


def test_data_trigger_gains_model_dependence_with_model_access(poisoned_scan):
    trig = [f for f in _by(poisoned_scan, "data.trigger_artifact") if f.attack_class == "localized_trigger"]
    assert trig and "model dependence" in trig[0].corroborating_signals
    assert trig[0].affected_contributors == ["Delta"]


def test_activation_analysis_isolates_the_poisoned_subpopulation(poisoned_scan, model_zoo):
    truth = load_truth(model_zoo["poisoned"])
    poisoned = {k for k, v in truth.items() if v["attacks"]}
    ac = [f for f in _by(poisoned_scan, "model.activation_analysis") if f.subject.startswith("ac:") and f.subject != "ac:none"]
    assert ac, "no corroborated activation split for the poisoned class"
    f = ac[0]
    assert f.tags["target_class"] == "civilian_vehicle"
    members = {s.sample_id for s in f.affected_samples}
    assert len(members & poisoned) / len(members) >= 0.7


def test_trigger_reconstruction_runs_with_gradients_and_reports_every_class(poisoned_scan):
    ex = {e.detector_id: e for e in poisoned_scan.executions}["model.trigger_reconstruction"]
    assert ex.planned == Availability.READY and ex.mode == "gradient"
    section = poisoned_scan.sections["model.trigger_reconstruction"]["reconstruction"]
    assert len(section["classes"]) == 6 and len(section["l1"]) == 6
    assert section["calibrated"] is False and "NOT validated" in section["threshold_origin"]
    for f in _by(poisoned_scan, "model.trigger_reconstruction"):
        assert f.recommended_disposition.value != "QUARANTINE", "uncalibrated NC must never auto-quarantine"


def test_trigger_reconstruction_budget_and_access_gating(model_zoo, tmp_path):
    for profile, expected in (("baseline", Availability.BUDGET_EXCLUDED), ("blackbox", Availability.UNAVAILABLE)):
        r = run_scan(ScanRequest(model=model_zoo["backdoor"], probe_dataset=model_zoo["probe"], profile=profile),
                     workspace=Workspace(tmp_path / profile).ensure())
        assert {e.detector_id: e for e in r.executions}["model.trigger_reconstruction"].planned == expected
