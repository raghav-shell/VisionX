from __future__ import annotations

import numpy as np
import pytest

from visionsentinel.core.stats import (
    auroc,
    benjamini_hochberg,
    binomial_tail,
    cliffs_delta,
    conformal_pvalues,
    effect_label,
    robust_z,
    tail_extrapolated_pvalues,
    wilson_interval,
)


def test_benjamini_hochberg_matches_hand_computation():
    q = benjamini_hochberg([0.01, 0.04, 0.03, 0.2])
    assert q == pytest.approx([0.04, 0.0533333, 0.0533333, 0.2], rel=1e-5)
    assert np.all(q >= np.array([0.01, 0.04, 0.03, 0.2]))


def test_wilson_interval_contains_estimate_and_is_bounded():
    lo, hi = wilson_interval(8, 10)
    assert 0 <= lo < 0.8 < hi <= 1
    assert wilson_interval(0, 50)[0] == pytest.approx(0.0, abs=1e-12)


def test_robust_z_ignores_outliers():
    x = np.r_[np.random.default_rng(0).normal(0, 1, 500), [50.0] * 20]
    z = robust_z(x)
    assert abs(np.median(z)) < 0.2 and z[-1] > 20


def test_binomial_tail():
    assert binomial_tail(0, 10, 0.5) == 1.0
    assert binomial_tail(10, 10, 0.5) == pytest.approx(0.5**10)


def test_conformal_pvalues_are_valid_under_exchangeability():
    rng = np.random.default_rng(1)
    cal, test = rng.normal(size=2000), rng.normal(size=20000)
    p = conformal_pvalues(cal, test)
    assert abs((p <= 0.05).mean() - 0.05) < 0.01
    assert p.min() >= 1 / 2001


def test_tail_extrapolation_resolves_extremes_but_preserves_bulk():
    rng = np.random.default_rng(2)
    cal = rng.exponential(size=300)
    test = np.r_[rng.exponential(size=1000), [30.0, 40.0]]
    base = conformal_pvalues(cal, test)
    ext = tail_extrapolated_pvalues(cal, test)
    assert ext[-1] < 1e-5 < base[-1]
    assert np.allclose(ext[test <= cal.max()], base[test <= cal.max()])
    assert abs((ext[:1000] <= 0.05).mean() - 0.05) < 0.03


def test_effect_sizes():
    a, b = np.arange(100.0), np.arange(100.0) + 200
    assert cliffs_delta(a, b) == pytest.approx(-1.0)
    assert effect_label(0.1) == "negligible" and effect_label(0.5) == "large"
    assert auroc(b, a) == pytest.approx(1.0)
