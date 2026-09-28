"""Model identity: digests, architecture, weights and behaviour on genuinely trained models."""

from __future__ import annotations

import pytest

from visionsentinel.contracts import Availability, Disposition, ExecutionState, Severity
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan


def _scan(zoo, tmp_path, model, profile="selftest", **extra):
    ws = Workspace(tmp_path / "ws").ensure()
    return run_scan(ScanRequest(model=zoo[model], reference_model=zoo["approved"], probe_dataset=zoo["probe"],
                                profile=profile, **extra), workspace=ws)


def _by(result, detector):
    return [f for f in result.findings if f.detector_id == detector]


def test_identical_copy_is_accepted_on_every_identity_axis(model_zoo, tmp_path):
    r = _scan(model_zoo, tmp_path, "copy")
    digest = _by(r, "model.artifact_digest")
    assert len(digest) == 1 and digest[0].severity == Severity.INFO
    assert digest[0].recommended_disposition == Disposition.ACCEPT
    assert _by(r, "model.architecture")[0].severity == Severity.INFO
    assert not [f for f in _by(r, "model.weight_statistics") if f.attack_class == "model_weight_tampering"]
    behaviour = _by(r, "model.behaviour_fingerprint")
    assert behaviour[0].severity == Severity.INFO and "identical" in behaviour[0].title
    assert r.summary.overall_disposition == Disposition.ACCEPT


def test_reserialised_model_is_distinguished_from_substitution(model_zoo, tmp_path):
    r = _scan(model_zoo, tmp_path, "reserialised")
    d = _by(r, "model.artifact_digest")[0]
    assert d.tags["parameters"] == "identical" and d.recommended_disposition == Disposition.REVIEW
    assert _by(r, "model.behaviour_fingerprint")[0].severity == Severity.INFO


def test_substituted_model_is_critical_when_behaviour_also_diverges(model_zoo, tmp_path):
    r = _scan(model_zoo, tmp_path, "modified")
    d = _by(r, "model.artifact_digest")[0]
    assert d.severity.rank >= Severity.HIGH.rank and d.recommended_disposition == Disposition.QUARANTINE
    b = _by(r, "model.behaviour_fingerprint")[0]
    assert b.attack_class == "behavioural_divergence" and "artifact digest mismatch" in b.corroborating_signals
    assert (b.severity, b.recommended_disposition) == (Severity.CRITICAL, Disposition.QUARANTINE)
    tamper = [f for f in _by(r, "model.weight_statistics") if f.attack_class == "model_weight_tampering"]
    assert tamper and "fc.weight" in tamper[0].reason
    assert _by(r, "model.architecture")[0].severity == Severity.INFO


def test_grafted_branch_is_explained_by_architecture_diff(model_zoo, tmp_path):
    r = _scan(model_zoo, tmp_path, "grafted")
    a = _by(r, "model.architecture")[0]
    assert a.severity == Severity.HIGH and a.recommended_disposition == Disposition.QUARANTINE
    for op in ("Sigmoid", "GlobalMaxPool", "Conv"):
        assert op in a.reason
    diff = r.sections["model.architecture"]["architecture"]["diff"]
    assert diff["added"].get("Mul") == 2 and diff["candidate_nodes"] > diff["reference_nodes"]


def test_blackbox_profile_never_claims_whitebox_checks(model_zoo, tmp_path):
    r = _scan(model_zoo, tmp_path, "modified", profile="blackbox")
    ex = {e.detector_id: e for e in r.executions}
    assert ex["model.weight_statistics"].planned == Availability.UNAVAILABLE
    assert "withheld by profile policy" in " ".join(ex["model.weight_statistics"].reasons)
    assert ex["model.architecture"].planned == Availability.UNAVAILABLE
    assert ex["model.artifact_digest"].mode == "artifact-only"
    assert ex["model.behaviour_fingerprint"].state in (ExecutionState.COMPLETED, ExecutionState.COMPLETED_DEGRADED)
    caps = {c.capability.value: c for c in r.capabilities}
    assert caps["MODEL_GRADIENTS"].withheld and caps["MODEL_PARAMETERS"].withheld
    rows = {row.attack_class: row for row in r.coverage.rows}
    assert rows["model_graph_modification"].state.value == "NOT_ASSESSED"


def test_stored_fingerprint_replaces_reference_model(model_zoo, tmp_path):
    import json

    from visionsentinel.loaders.models import open_model
    from visionsentinel.model_assurance.behaviour import fingerprint_document
    from visionsentinel.model_assurance.probes import battery

    ref = open_model(model_zoo["approved"])
    try:
        fp = tmp_path / "approved.fingerprint.json"
        fp.write_text(json.dumps(fingerprint_document(ref, battery(ref.cfg.input_size))))
    finally:
        ref.close()
    ws = Workspace(tmp_path / "ws2").ensure()
    r = run_scan(ScanRequest(model=model_zoo["modified"], reference_fingerprint=fp, profile="selftest"), workspace=ws)
    b = _by(r, "model.behaviour_fingerprint")[0]
    assert b.attack_class == "behavioural_divergence" and b.severity.rank >= Severity.MEDIUM.rank
    ex = {e.detector_id: e for e in r.executions}
    assert ex["model.artifact_digest"].planned == Availability.UNAVAILABLE  # no approved digest supplied


@pytest.mark.parametrize("variant", ["copy", "modified"])
def test_model_sections_expose_isolation(model_zoo, tmp_path, variant):
    r = _scan(model_zoo, tmp_path, variant)
    iso = r.sections["model.artifact_digest"]["identity"]["isolation"]
    assert iso["rlimit_fsize"] == 0 and "audit_hook" in iso
