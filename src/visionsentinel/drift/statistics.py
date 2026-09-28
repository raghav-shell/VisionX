"""Two-sample statistics for drift: significance *and* magnitude, never one without the other.

A very large batch makes any difference "significant". Every axis therefore reports a p-value (KS,
Benjamini–Hochberg adjusted across axes) together with effect sizes that do not grow with sample size:
Cliff's δ (Romano et al. thresholds), the Population Stability Index, and the Wasserstein-1 distance and
median shift expressed in reference standard deviations. Severity is driven by magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as sps
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from ..core.stats import benjamini_hochberg, cliffs_delta, effect_label


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10, eps: float = 1e-4) -> float:
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(reference, edges)[0] / len(reference) + eps
    c = np.histogram(current, edges)[0] / len(current) + eps
    return float(((c - r) * np.log(c / r)).sum())


def jsd_vec(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen–Shannon divergence (nats) between two discrete distributions."""
    p = np.clip(np.asarray(p, float), 1e-12, 1)
    q = np.clip(np.asarray(q, float), 1e-12, 1)
    p, q = p / p.sum(), q / q.sum()
    m = 0.5 * (p + q)
    return float(0.5 * (p * np.log(p / m)).sum() + 0.5 * (q * np.log(q / m)).sum())


def psi_label(value: float) -> str:
    return "none" if value < 0.1 else ("moderate" if value < 0.25 else "significant")


@dataclass
class AxisResult:
    axis: str
    n_ref: int
    n_cur: int
    ref_median: float
    cur_median: float
    shift_sd: float
    ks: float
    p: float
    q: float = 1.0
    psi: float = 0.0
    wasserstein_sd: float = 0.0
    delta: float = 0.0

    @property
    def magnitude(self) -> str:
        return effect_label(self.delta)

    def material(self, alpha: float, min_effect: float) -> bool:
        return self.q < alpha and abs(self.delta) >= min_effect

    def to_dict(self) -> dict:
        return {"axis": self.axis, "n_reference": self.n_ref, "n_incoming": self.n_cur,
                "reference_median": self.ref_median, "incoming_median": self.cur_median,
                "median_shift_sd": self.shift_sd, "ks": self.ks, "p": self.p, "q": self.q, "psi": self.psi,
                "psi_band": psi_label(self.psi), "wasserstein_sd": self.wasserstein_sd, "cliffs_delta": self.delta,
                "magnitude": self.magnitude}


def compare_axes(reference: dict[str, np.ndarray], current: dict[str, np.ndarray], seed: int = 0) -> list[AxisResult]:
    out: list[AxisResult] = []
    for axis in reference:
        r, c = np.asarray(reference[axis], float), np.asarray(current[axis], float)
        r, c = r[np.isfinite(r)], c[np.isfinite(c)]
        if len(r) < 5 or len(c) < 5:
            continue
        sd = float(r.std()) or 1e-9
        ks = sps.ks_2samp(r, c)
        out.append(AxisResult(axis=axis, n_ref=len(r), n_cur=len(c), ref_median=float(np.median(r)),
                              cur_median=float(np.median(c)), shift_sd=float((np.median(c) - np.median(r)) / sd),
                              ks=float(ks.statistic), p=float(ks.pvalue), psi=psi(r, c),
                              wasserstein_sd=float(sps.wasserstein_distance(r, c) / sd),
                              delta=cliffs_delta(c, r, seed=seed)))
    qs = benjamini_hochberg([a.p for a in out])
    for a, q in zip(out, qs):
        a.q = float(q)
    return out


def mmd_permutation(x: np.ndarray, y: np.ndarray, rng: np.random.Generator, permutations: int = 200,
                    max_n: int = 300) -> tuple[float, float]:
    """Unbiased MMD² with an RBF kernel (median heuristic) and a permutation p-value."""
    if len(x) > max_n:
        x = x[rng.choice(len(x), max_n, replace=False)]
    if len(y) > max_n:
        y = y[rng.choice(len(y), max_n, replace=False)]
    z = np.vstack([x, y]).astype(np.float64)
    sq = (z**2).sum(1)
    d2 = np.maximum(sq[:, None] + sq[None, :] - 2 * z @ z.T, 0)
    bandwidth = np.median(d2[np.triu_indices(len(z), 1)]) or 1.0
    k = np.exp(-d2 / bandwidth)
    n = len(x)

    def stat(idx: np.ndarray) -> float:
        a, b = idx[:n], idx[n:]
        kxx = k[np.ix_(a, a)]
        kyy = k[np.ix_(b, b)]
        kxy = k[np.ix_(a, b)]
        m = len(a)
        mm = len(b)
        return float((kxx.sum() - np.trace(kxx)) / (m * (m - 1)) + (kyy.sum() - np.trace(kyy)) / (mm * (mm - 1))
                     - 2 * kxy.mean())

    base = np.arange(len(z))
    observed = stat(base)
    null = np.array([stat(rng.permutation(len(z))) for _ in range(permutations)])
    return observed, float((1 + (null >= observed).sum()) / (permutations + 1))


def classifier_two_sample_auc(x: np.ndarray, y: np.ndarray, seed: int, max_n: int = 600) -> float:
    """Cross-validated AUC of a classifier separating reference from incoming (0.5 = indistinguishable)."""
    rng = np.random.default_rng(seed)
    if len(x) > max_n:
        x = x[rng.choice(len(x), max_n, replace=False)]
    if len(y) > max_n:
        y = y[rng.choice(len(y), max_n, replace=False)]
    z = np.vstack([x, y])
    lab = np.r_[np.zeros(len(x)), np.ones(len(y))]
    folds = min(5, int(min(len(x), len(y))))
    if folds < 2:
        return 0.5
    proba = cross_val_predict(LogisticRegression(C=0.5, max_iter=2000), z, lab,
                              cv=StratifiedKFold(folds, shuffle=True, random_state=seed % (2**32)),
                              method="predict_proba")[:, 1]
    from ..core.stats import auroc
    return float(auroc(proba[lab == 1], proba[lab == 0]))
