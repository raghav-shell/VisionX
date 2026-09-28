from __future__ import annotations

import numpy as np

from visionsentinel.risk.calibration import brier, calibrate, fit_calibrator, reliability, threshold_for_fpr


def test_threshold_respects_target_false_positive_rate():
    rng = np.random.default_rng(0)
    neg = rng.normal(0, 1, 5000)
    t = threshold_for_fpr(neg, 0.01)
    assert (neg >= t).mean() <= 0.01
    assert (neg >= t).mean() >= 0.005


def test_isotonic_and_platt_calibrators_are_monotone_and_improve_brier():
    rng = np.random.default_rng(1)
    scores = np.r_[rng.normal(2, 1, 400), rng.normal(0, 1, 400)]
    labels = np.r_[np.ones(400), np.zeros(400)]
    raw = 1 / (1 + np.exp(-scores * 5))  # badly over-confident scores
    for method in ("isotonic", "platt"):
        cal = fit_calibrator(scores, labels, method)
        p = cal.predict(np.sort(scores))
        assert np.all(np.diff(p) >= -1e-12)
        assert brier(cal.predict(scores), labels) < brier(raw, labels)
    bins, ece = reliability(fit_calibrator(scores, labels).predict(scores), labels)
    assert ece < 0.05 and sum(b["n"] for b in bins) == 800


def test_calibration_artifact_records_its_provenance(tmp_path):
    rng = np.random.default_rng(2)
    art = calibrate("data.x", "score", rng.normal(2, 1, 100), rng.normal(0, 1, 300), target_fpr=0.02,
                    calibration_families=["patch-checker"], evaluation_families=["patch-glyph"], seeds=[1, 2],
                    created_with="test")
    p = art.write(tmp_path / "cal.json")
    assert p.exists() and art.n_positive == 100 and art.n_negative == 300
    assert "patch-glyph" not in art.calibration_families
