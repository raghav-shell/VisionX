"""Drift: significance with magnitude, and operational shift distinguished from a manipulated stream."""

from __future__ import annotations

import numpy as np
import pytest

from visionsentinel.attacklab.corpus import generate_clean_set, write_corpus
from visionsentinel.attacklab.drift_attacks import manipulated_stream, operational_batch
from visionsentinel.contracts import Disposition, Severity
from visionsentinel.core.workspace import Workspace
from visionsentinel.drift.statistics import compare_axes, jsd_vec, mmd_permutation, psi
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan

SCENARIOS = {
    "same": lambda: operational_batch(160, 9),
    "low_light": lambda: operational_batch(160, 9, shift="low_light"),
    "blur": lambda: operational_batch(160, 9, shift="blur"),
    "manipulated": lambda: manipulated_stream(160, 9),
}


@pytest.fixture(scope="module")
def drift_scans(tmp_path_factory):
    root = tmp_path_factory.mktemp("drift")
    write_corpus(generate_clean_set(300, 5, "reference"), root / "ref", name="ref")
    out = {}
    for name, make in SCENARIOS.items():
        write_corpus(make(), root / name, name=name)
        out[name] = run_scan(ScanRequest(reference_dataset=root / "ref", operational_data=root / name, profile="selftest"),
                             workspace=Workspace(root / f"ws-{name}").ensure())
    return out


def _f(result, detector):
    return next(f for f in result.findings if f.detector_id == detector)


def test_same_distribution_is_not_drift(drift_scans):
    r = drift_scans["same"]
    for det in ("drift.covariate", "drift.semantic", "drift.interpretation"):
        assert _f(r, det).severity == Severity.INFO, det


@pytest.mark.parametrize("scenario,axis", [("low_light", "brightness"), ("blur", "sharpness")])
def test_environmental_shift_is_detected_and_called_operational(drift_scans, scenario, axis):
    r = drift_scans[scenario]
    cov = _f(r, "drift.covariate")
    assert cov.severity.rank >= Severity.MEDIUM.rank and axis in cov.tags["axes"]
    axes = {a["axis"]: a for a in r.sections["drift.covariate"]["covariate"]["axes"]}
    assert axes[axis]["magnitude"] == "large" and axes[axis]["q"] < 0.01
    interp = _f(r, "drift.interpretation")
    assert interp.title == "LIKELY OPERATIONAL SHIFT" and interp.attack_class == "operational_drift"
    assert interp.recommended_disposition == Disposition.REVIEW


def test_manipulated_source_is_isolated_and_capped_at_review(drift_scans):
    r = drift_scans["manipulated"]
    interp = _f(r, "drift.interpretation")
    assert interp.attack_class == "drift_manipulation"
    assert interp.title.startswith("SUSPICIOUS SHIFT")
    assert "uav-patrol-3" in interp.reason
    assert interp.recommended_disposition == Disposition.REVIEW
    assert "G4" in " ".join(interp.guardrails) or interp.recommended_disposition != Disposition.QUARANTINE
    # the global statistics alone would not have raised it
    assert _f(r, "drift.covariate").severity == Severity.INFO


def test_significance_without_magnitude_is_not_material():
    rng = np.random.default_rng(0)
    ref = {"x": rng.normal(0, 1, 50000)}
    cur = {"x": rng.normal(0.03, 1, 50000)}  # tiny effect, enormous sample
    (a,) = compare_axes(ref, cur)
    assert a.p < 1e-3 and a.magnitude == "negligible"
    assert not a.material(0.01, 0.147)


def test_statistics_primitives():
    rng = np.random.default_rng(1)
    same = rng.normal(size=4000)
    assert psi(same, rng.normal(size=4000)) < 0.1
    assert psi(same, rng.normal(1.5, 1, 4000)) > 0.25
    x, y = rng.normal(size=(120, 4)), rng.normal(size=(120, 4))
    assert mmd_permutation(x, y, rng, 100)[1] > 0.05
    assert mmd_permutation(x, y + 1.0, rng, 100)[1] < 0.05
    assert jsd_vec(np.array([0.5, 0.5]), np.array([0.5, 0.5])) == pytest.approx(0, abs=1e-9)
