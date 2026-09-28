"""Out-of-distribution sample detection.

Reference mode (preferred): split-conformal p-values from the k-NN cosine distance to a trusted
reference set, with the threshold set by Benjamini–Hochberg FDR control rather than an arbitrary
distance cut-off; a Ledoit–Wolf Mahalanobis score provides independent corroboration.
Self-referential mode (degraded): leave-one-out k-NN distance within the dataset against a robust
(median/MAD) model of its own distribution — useful triage, but not calibrated.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field
from scipy import stats as sps
from sklearn.covariance import LedoitWolf
from sklearn.decomposition import PCA

from ..contracts import (
    AssetType,
    AttackSupport,
    CalibrationRequirement,
    Capability,
    DetectorMode,
    DetectorSpec,
    EvidenceKind,
    Layer,
    ProposedFinding,
    RuntimeClass,
    Severity,
    SupportLevel,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, Params, SampleFlag
from ..core.stats import benjamini_hochberg, fmt_p, robust_z, tail_extrapolated_pvalues
from .common import DATA_ASSUMPTIONS, analysis, ref, sheet_evidence, stat_evidence


def knn_distance(query: np.ndarray, base: np.ndarray, k: int, exclude_self: bool = False, chunk: int = 512
                 ) -> np.ndarray:
    """Mean Euclidean distance to the ``k`` nearest rows of ``base`` (features z-scored, magnitude kept)."""
    base_sq = (base.astype(np.float64) ** 2).sum(axis=1)
    kk = min(k, base.shape[0] - (1 if exclude_self else 0))
    out = np.empty(len(query))
    for start in range(0, len(query), chunk):
        q = query[start:start + chunk].astype(np.float64)
        d2 = (q**2).sum(axis=1)[:, None] + base_sq[None, :] - 2 * q @ base.T.astype(np.float64)
        if exclude_self:
            rows = np.arange(len(q))
            d2[rows, start + rows] = np.inf
        part = np.partition(np.maximum(d2, 0), kk - 1, axis=1)[:, :kk]
        out[start:start + chunk] = np.sqrt(part).mean(axis=1)
    return out


class OODParams(Params):
    k: int = Field(default=5, ge=1, le=50)
    alpha: float = Field(default=0.01, gt=0, lt=0.5, description="Benjamini–Hochberg FDR level.")
    calibration_fraction: float = Field(default=0.5, gt=0.1, lt=0.9)
    min_reference: int = Field(default=100, ge=20)
    pca_dims: int = Field(default=32, ge=2)
    max_findings: int = Field(default=100, ge=1)


class OutOfDistribution(Detector):
    Params = OODParams
    spec = DetectorSpec(
        id="data.ood", version="1.0.0", title="Out-of-distribution samples", layer=Layer.DATA,
        summary="Scores each sample's distance from a trusted reference distribution and converts it into a "
                "conformal p-value; flags samples at a controlled false-discovery rate.",
        required=[Capability.DATASET_IMAGES], optional=[Capability.REFERENCE_DATASET, Capability.SEMANTIC_ENCODER],
        modes=[DetectorMode(name="reference-semantic", description="conformal k-NN against the reference set in a "
                            "learned embedding", needs=[Capability.REFERENCE_DATASET, Capability.SEMANTIC_ENCODER]),
               DetectorMode(name="reference-descriptor", description="conformal k-NN against the reference set in the "
                            "classical descriptor space", needs=[Capability.REFERENCE_DATASET], degraded=True),
               DetectorMode(name="self-referential", description="leave-one-out k-NN against the dataset itself "
                            "(uncalibrated)", degraded=True)],
        supports=[AttackSupport(attack_class="ood_injection", level=SupportLevel.FULL)],
        runtime=RuntimeClass.MODERATE, evidence_kinds=[EvidenceKind.CONTACT_SHEET, EvidenceKind.STATISTIC],
        limitations=["Conformal guarantees assume the reference set is exchangeable with clean incoming data.",
                     "Semantic novelty is only visible in a learned embedding; the classical descriptor sees mostly "
                     "low-level appearance.",
                     "Self-referential mode cannot detect a large coherent OOD block (it becomes part of 'normal')."],
        access_assumptions=DATA_ASSUMPTIONS + ["The reference dataset is trusted and representative."],
        deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
        references=["Vovk, Gammerman & Shafer (2005) Algorithmic Learning in a Random World.",
                    "Sun et al. (2022) Out-of-Distribution Detection with Deep Nearest Neighbors. ICML.",
                    "Bates et al. (2023) Testing for outliers with conformal p-values. Ann. Statist.",
                    "Pickands (1975) Statistical inference using extreme order statistics. Ann. Statist."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: OODParams = ctx.params  # type: ignore[assignment]
        a = analysis(ctx)
        E = a.zscores
        res = DetectorResult(samples_processed=a.n)
        corroboration = None
        if ctx.mode.startswith("reference"):
            r = analysis(ctx, "reference_analysis")
            R = r.zscores
            if len(R) < p.min_reference:
                return DetectorResult(abstained=f"reference set has {len(R)} samples (< {p.min_reference})")
            rng = ctx.rng("split")
            perm = rng.permutation(len(R))
            n_cal = int(len(R) * p.calibration_fraction)
            cal, fit = R[perm[:n_cal]], R[perm[n_cal:]]
            cal_scores = knn_distance(cal, fit, p.k)
            scores = knn_distance(E, fit, p.k)
            pvals = tail_extrapolated_pvalues(cal_scores, scores)
            dims = min(p.pca_dims, fit.shape[1], len(fit) - 1)
            pca = PCA(n_components=dims, random_state=0).fit(fit)
            lw = LedoitWolf().fit(pca.transform(fit))
            maha_cal = lw.mahalanobis(pca.transform(cal))
            maha = lw.mahalanobis(pca.transform(E))
            corroboration = tail_extrapolated_pvalues(maha_cal, maha)
            calibrated = True
            method = (f"split-conformal k-NN (k={p.k}) against {len(fit)} reference samples, {n_cal} held out for "
                      "calibration, generalised-Pareto tail beyond the calibration range")
        else:
            scores = knn_distance(E, E, p.k, exclude_self=True)
            z = robust_z(np.log(np.maximum(scores, 1e-9)))
            pvals = sps.norm.sf(z)
            calibrated = False
            method = f"leave-one-out k-NN (k={p.k}) within the dataset, robust z of log distance"
        q = benjamini_hochberg(pvals)
        flagged = [int(i) for i in np.argsort(pvals) if q[i] <= p.alpha]
        res.metrics = {"flagged": len(flagged), "method": method, "encoder": a.encoder.id,
                       "median_score": float(np.median(scores))}
        res.section = {"ood": {"scores_hist": np.histogram(scores, bins=30)[0].tolist(),
                               "bin_edges": np.histogram(scores, bins=30)[1].round(5).tolist()}}
        base = analysis(ctx, "reference_analysis") if ctx.mode.startswith("reference") else a
        for rank, i in enumerate(flagged):
            s = a.samples[i]
            both = corroboration is not None and corroboration[i] <= p.alpha
            severity = Severity.HIGH if (both and q[i] < 1e-4) else Severity.MEDIUM
            conf = float(min(0.99, 1 - q[i])) * (1.0 if both or corroboration is None else 0.85)
            res.flags.append(SampleFlag(s.id, s.contributor, "ood_injection", self.spec.id, conf, severity, s.batch))
            if rank >= p.max_findings:
                continue
            nn = np.argsort(((base.zscores - E[i]) ** 2).sum(axis=1))[:5]
            ev = [sheet_evidence(ctx, [a.images[i]] + [base.images[j] for j in nn], ["flag"] + ["neutral"] * len(nn),
                                 f"{s.id} and its nearest {'reference' if base is not a else 'dataset'} samples",
                                 "Even the closest trusted samples differ markedly from the flagged image.", columns=6),
                  stat_evidence(ctx, "Distance evidence", method, {
                      "knn_distance": round(float(scores[i]), 5), "p_value": float(pvals[i]), "q_value": float(q[i]),
                      "mahalanobis_p": float(corroboration[i]) if corroboration is not None else None,
                      "fdr_level": p.alpha})]
            res.findings.append(ProposedFinding(
                attack_class="ood_injection", asset_type=AssetType.SAMPLE, asset_id=s.id, subject=f"ood:{s.id}",
                title=f"Possible out-of-distribution sample {s.id}",
                reason=(f"Sample {s.id}{f' from {s.contributor}' if s.contributor else ''} is farther from the "
                        f"{'trusted reference' if calibrated else 'rest of the dataset'} than "
                        f"{'held-out reference samples (p = ' + fmt_p(float(pvals[i])) + ')' if calibrated else 'expected under the dataset distribution'}"
                        f" (k-NN distance {scores[i]:.3f}; BH q = {fmt_p(float(q[i]))})"
                        + ("; an independent Mahalanobis score agrees." if both else ".")),
                severity=severity, confidence=round(conf, 4), raw_score=round(float(scores[i]), 5),
                threshold=p.alpha, score_semantics="mean z-scored Euclidean k-NN distance (flag when BH q ≤ threshold)", evidence=ev,
                access_assumptions=self.spec.access_assumptions, limitations=self.spec.limitations,
                affected_samples=[ref(s)], affected_contributors=[s.contributor] if s.contributor else [],
                corroborating_signals=["conformal k-NN distance"] + (["Mahalanobis distance"] if both else []),
                deterministic=False, calibrated=calibrated,
                recommended_action="Inspect the sample; remove it if it is not operational imagery."))
        return res
