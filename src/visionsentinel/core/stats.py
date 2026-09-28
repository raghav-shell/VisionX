"""Statistical utilities shared by detectors, drift, risk and evaluation."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

MAD_SCALE = 1.4826  # consistency constant: MAD × 1.4826 estimates σ for Gaussian data


def benjamini_hochberg(pvalues: np.ndarray | list[float]) -> np.ndarray:
    """BH step-up adjusted p-values (q-values) controlling the false discovery rate."""
    p = np.asarray(pvalues, dtype=np.float64)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def wilson_interval(successes: int, trials: int, level: float = 0.95) -> tuple[float, float]:
    if trials <= 0:
        return 0.0, 1.0
    z = sps.norm.ppf(0.5 + level / 2)
    phat = successes / trials
    denom = 1 + z**2 / trials
    centre = (phat + z**2 / (2 * trials)) / denom
    half = z * math.sqrt(phat * (1 - phat) / trials + z**2 / (4 * trials**2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def robust_z(values: np.ndarray, reference: np.ndarray | None = None) -> np.ndarray:
    """Modified z-score (Iglewicz & Hoaglin): (x − median) / (1.4826 · MAD)."""
    ref = np.asarray(values if reference is None else reference, dtype=np.float64)
    med = np.median(ref)
    mad = np.median(np.abs(ref - med)) * MAD_SCALE
    if mad < 1e-12:
        mad = np.mean(np.abs(ref - med)) * 1.2533 or 1e-12
    return (np.asarray(values, dtype=np.float64) - med) / mad


def binomial_tail(k: int, n: int, p: float) -> float:
    """P(X ≥ k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    return float(sps.binom.sf(k - 1, n, min(max(p, 1e-12), 1 - 1e-12)))


def conformal_pvalues(calibration_scores: np.ndarray, test_scores: np.ndarray) -> np.ndarray:
    """Split-conformal p-values: (1 + #{calib ≥ s}) / (n + 1). Larger score = more anomalous."""
    cal = np.sort(np.asarray(calibration_scores, dtype=np.float64))
    n = len(cal)
    ge = n - np.searchsorted(cal, np.asarray(test_scores, dtype=np.float64), side="left")
    return (1.0 + ge) / (n + 1.0)


def tail_extrapolated_pvalues(calibration_scores: np.ndarray, test_scores: np.ndarray,
                              tail_fraction: float = 0.2, min_tail: int = 20) -> np.ndarray:
    """Conformal p-values whose resolution below 1/(n+1) is extended by a generalised-Pareto tail.

    Within the calibration range the ordinary split-conformal p-value is used. Beyond the tail
    threshold ``u`` (the (1 − tail_fraction) quantile of calibration scores) the exceedance
    probability is modelled as ``P(S > u) · GPD.sf(s − u)`` (Pickands–Balkema–de Haan), which lets a
    far-out sample obtain a p-value small enough to survive multiple-testing correction. The
    conformal value is kept whenever it is larger, so the extrapolation can only matter for scores in
    the extreme tail.
    """
    cal = np.sort(np.asarray(calibration_scores, dtype=np.float64))
    test = np.asarray(test_scores, dtype=np.float64)
    pv = conformal_pvalues(cal, test)
    n = len(cal)
    n_tail = max(min_tail, int(round(n * tail_fraction)))
    if n < 2 * min_tail or n_tail >= n:
        return pv
    u = cal[n - n_tail - 1]
    exceed = cal[n - n_tail:] - u
    if np.ptp(exceed) <= 1e-12:
        return pv
    shape, _, scale = sps.genpareto.fit(exceed, floc=0.0)
    shape = float(np.clip(shape, -0.5, 0.5))
    far = test > u
    tail_p = (n_tail / (n + 1.0)) * sps.genpareto.sf(test[far] - u, shape, loc=0.0, scale=scale)
    beyond = test[far] > cal[-1]
    pv_far = pv[far]
    pv_far[beyond] = np.maximum(tail_p[beyond], 1e-300)
    pv[far] = pv_far
    return pv


def cliffs_delta(a: np.ndarray, b: np.ndarray, max_n: int = 4000, seed: int = 0) -> float:
    """Cliff's δ = P(A > B) − P(A < B) via ranks (sub-sampled for very large inputs)."""
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if len(a) > max_n:
        a = rng.choice(a, max_n, replace=False)
    if len(b) > max_n:
        b = rng.choice(b, max_n, replace=False)
    if len(a) == 0 or len(b) == 0:
        return 0.0
    u = sps.mannwhitneyu(a, b, alternative="two-sided").statistic
    return float(2 * u / (len(a) * len(b)) - 1)


def effect_label(delta: float) -> str:
    """Romano et al. (2006) thresholds for |Cliff's δ|."""
    d = abs(delta)
    if d < 0.147:
        return "negligible"
    if d < 0.33:
        return "small"
    if d < 0.474:
        return "medium"
    return "large"


def auroc(scores_pos: np.ndarray, scores_neg: np.ndarray) -> float:
    pos, neg = np.asarray(scores_pos, float), np.asarray(scores_neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    u = sps.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def bootstrap_ci(fn, *arrays: np.ndarray, n_boot: int = 500, level: float = 0.95, seed: int = 0
                 ) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        resampled = [a[rng.integers(0, len(a), len(a))] for a in arrays]
        v = fn(*resampled)
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    lo, hi = np.percentile(vals, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def fmt_p(p: float) -> str:
    if p < 1e-12:
        return "< 1e-12"
    if p < 1e-3:
        return f"{p:.1e}"
    return f"{p:.3f}"
