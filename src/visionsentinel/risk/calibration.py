"""Score calibration and calibration artifacts.

Detectors that emit continuous scores are calibrated on *calibration* attack families and reported on
held-out *evaluation* families. A calibration artifact records the method, the families and sizes it was fitted
on, the resulting threshold for a target false-positive rate, and reliability statistics (Brier score,
reliability bins, expected calibration error). Cryptographic checks need no calibration: they are exact.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


@dataclass
class Calibrator:
    method: str
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    coef: float = 0.0
    intercept: float = 0.0

    def predict(self, scores: np.ndarray) -> np.ndarray:
        s = np.asarray(scores, dtype=np.float64)
        if self.method == "isotonic":
            return np.interp(s, self.x, self.y, left=self.y[0], right=self.y[-1])
        return 1.0 / (1.0 + np.exp(-(self.coef * s + self.intercept)))


def fit_calibrator(scores: np.ndarray, labels: np.ndarray, method: str = "isotonic") -> Calibrator:
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    if method == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(s, y)
        xs = np.unique(s)
        return Calibrator("isotonic", x=xs.tolist(), y=iso.predict(xs).tolist())
    lr = LogisticRegression(C=1e6, max_iter=5000).fit(s[:, None], y)
    return Calibrator("platt", coef=float(lr.coef_[0, 0]), intercept=float(lr.intercept_[0]))


def brier(prob: np.ndarray, labels: np.ndarray) -> float:
    return float(np.mean((np.asarray(prob) - np.asarray(labels)) ** 2))


def reliability(prob: np.ndarray, labels: np.ndarray, bins: int = 10) -> tuple[list[dict], float]:
    prob, labels = np.asarray(prob, float), np.asarray(labels, float)
    edges = np.linspace(0, 1, bins + 1)
    out, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (prob >= lo) & (prob < hi if hi < 1 else prob <= hi)
        if m.any():
            conf, acc = float(prob[m].mean()), float(labels[m].mean())
            ece += m.mean() * abs(conf - acc)
            out.append({"lower": float(lo), "upper": float(hi), "n": int(m.sum()), "mean_predicted": conf,
                        "observed_rate": acc})
    return out, float(ece)


def threshold_for_fpr(neg_scores: np.ndarray, target_fpr: float) -> float:
    """Smallest threshold whose false-positive rate on negatives is ≤ target (flag when score ≥ threshold)."""
    neg = np.sort(np.asarray(neg_scores, float))
    if len(neg) == 0:
        return float("inf")
    k = int(np.floor(target_fpr * len(neg)))
    idx = len(neg) - k
    return float(neg[idx] + 1e-9) if idx < len(neg) else float(neg[-1] + 1e-9)


@dataclass
class CalibrationArtifact:
    detector: str
    score: str
    method: str
    calibration_families: list[str]
    evaluation_families: list[str]
    n_positive: int
    n_negative: int
    target_fpr: float
    threshold: float
    brier: float
    ece: float
    reliability: list[dict]
    calibrator: dict
    seeds: list[int]
    created_with: str
    notes: str = ""

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=1))
        return path


def calibrate(detector: str, score: str, pos: np.ndarray, neg: np.ndarray, *, target_fpr: float,
              calibration_families: list[str], evaluation_families: list[str], seeds: list[int], created_with: str,
              method: str = "isotonic", notes: str = "") -> CalibrationArtifact:
    scores = np.r_[pos, neg]
    labels = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    cal = fit_calibrator(scores, labels, method)
    prob = cal.predict(scores)
    bins, ece = reliability(prob, labels)
    return CalibrationArtifact(detector=detector, score=score, method=method, calibration_families=calibration_families,
                               evaluation_families=evaluation_families, n_positive=len(pos), n_negative=len(neg),
                               target_fpr=target_fpr, threshold=threshold_for_fpr(neg, target_fpr),
                               brier=brier(prob, labels), ece=ece, reliability=bins, calibrator=asdict(cal),
                               seeds=seeds, created_with=created_with, notes=notes)
