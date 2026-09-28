"""Label-flip and systematic-mislabel detection.

Label consistency combines two signals conservatively — similarity-weighted neighbour agreement in
embedding space (the sample's own near-duplicate component is excluded so copies cannot vouch for
each other) and an out-of-fold classifier with confident-learning per-class thresholds — and flags
a sample only when both disagree with the declared label.

Systematic mislabelling aggregates the resulting declared → inferred transitions per contributor
and tests each against the other contributors' rate for the same transition.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from pydantic import Field

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
from ..core.stats import benjamini_hochberg, binomial_tail, fmt_p
from .common import DATA_ASSUMPTIONS, analysis, pct, ref, sheet_evidence, stat_evidence, table_evidence

_SEMANTIC_NOTE = ("Neighbour and classifier signals are computed in the embedding space of the selected encoder; "
                  "without a learned (semantic) encoder the weight-free descriptor is used and support is partial.")


class LabelParams(Params):
    k: int = Field(default=10, ge=3, le=50)
    folds: int = Field(default=5, ge=3, le=10)
    C: float = Field(default=0.3, gt=0)
    min_class: int = Field(default=10, ge=5)
    max_agreement: float = Field(default=0.3, ge=0, le=1)
    min_predicted_prob: float = Field(default=0.6, ge=0, le=1)
    degraded_max_agreement: float = Field(default=0.1, ge=0, le=1,
                                          description="Stricter bound used in the non-semantic descriptor mode.")
    degraded_min_predicted_prob: float = Field(default=0.85, ge=0, le=1)
    confident_learning: bool = True
    max_findings: int = Field(default=250, ge=1)


class LabelConsistency(Detector):
    Params = LabelParams
    spec = DetectorSpec(
        id="data.label_consistency", version="1.0.0", title="Label consistency (label flips)", layer=Layer.DATA,
        summary="Flags samples whose declared label is contradicted both by their visual neighbours and by an "
                "out-of-fold classifier (confident-learning thresholds).",
        required=[Capability.DATASET_IMAGES, Capability.DATASET_LABELS],
        optional=[Capability.SEMANTIC_ENCODER, Capability.CONTRIBUTOR_METADATA],
        modes=[DetectorMode(name="semantic", description="learned encoder embedding space",
                            needs=[Capability.SEMANTIC_ENCODER]),
               DetectorMode(name="descriptor", description="weight-free classical descriptor space", degraded=True)],
        supports=[AttackSupport(attack_class="label_flip", level=SupportLevel.FULL),
                  AttackSupport(attack_class="localized_trigger", level=SupportLevel.PARTIAL,
                                note="dirty-label poisons are label flips of visually intact content")],
        runtime=RuntimeClass.MODERATE, evidence_kinds=[EvidenceKind.CONTACT_SHEET, EvidenceKind.STATISTIC],
        limitations=["A flip into a visually similar class is harder to detect than a flip into a distinct class.",
                     "When a large share of one class is flipped, the classifier learns the flip and agreement rises.",
                     _SEMANTIC_NOTE],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
        references=["Northcutt, Jiang & Chuang (2021) Confident Learning: Estimating Uncertainty in Dataset Labels. JAIR.",
                    "Bahri, Jiang & Gupta (2020) Deep k-NN for Noisy Labels. ICML."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: LabelParams = ctx.params  # type: ignore[assignment]
        a = analysis(ctx)
        lm = a.label_model(k=p.k, folds=p.folds, C=p.C, min_class=p.min_class)
        if lm is None:
            return DetectorResult(abstained=f"fewer than two classes have at least {p.min_class} labelled samples")
        p_decl, p_pred = lm.p_declared(), lm.p_predicted()
        thresholds = lm.per_class_threshold[lm.declared]
        degraded = ctx.mode == "descriptor"
        max_agree = p.degraded_max_agreement if degraded else p.max_agreement
        min_prob = p.degraded_min_predicted_prob if degraded else p.min_predicted_prob
        cand = (lm.predicted != lm.declared) & (p_pred >= min_prob) & (lm.agreement <= max_agree)
        if p.confident_learning:
            cand &= p_decl < thresholds
        score = 1.0 - 0.5 * (lm.agreement + p_decl)
        if ctx.calibration and ctx.calibration.threshold is not None:
            cand &= score >= ctx.calibration.threshold
        order = np.argsort(-score)
        flagged = [int(k) for k in order if cand[k]]
        res = DetectorResult(samples_processed=len(lm.index), artifacts={"label_model": lm, "flagged": flagged})
        per_contrib: dict[str, int] = defaultdict(int)
        for k in flagged:
            per_contrib[a.samples[int(lm.index[k])].contributor or "unattributed"] += 1
        res.metrics = {"oof_accuracy": round(lm.oof_accuracy, 4), "scheme": lm.scheme, "flagged": len(flagged),
                       "modelled": len(lm.index),
                       "flagged_by_contributor": dict(per_contrib), "encoder": a.encoder.id}
        res.section = {"label_model": {"oof_accuracy": lm.oof_accuracy, "encoder": a.encoder.id, "scheme": lm.scheme,
                                       "classes": [a.class_name(lm, c) for c in range(len(lm.classes_modelled))],
                                       "thresholds": [round(float(t), 4) for t in lm.per_class_threshold]}}
        for rank, k in enumerate(flagged):
            i = int(lm.index[k])
            s = a.samples[i]
            declared, predicted = a.class_name(lm, int(lm.declared[k])), a.class_name(lm, int(lm.predicted[k]))
            nbrs = [int(j) for j in lm.neighbours[k]]
            same = sum(1 for j in nbrs if a.labels[j] == a.labels[i])
            conf = float(min(p_pred[k], 1.0 - lm.agreement[k]))
            severity = Severity.HIGH if (score[k] >= 0.9 and same == 0 and not degraded) else Severity.MEDIUM
            res.flags.append(SampleFlag(s.id, s.contributor, "label_flip", self.spec.id, conf, severity, s.batch))
            if rank >= p.max_findings:
                continue
            sheet = sheet_evidence(ctx, [a.images[i]] + [a.images[j] for j in nbrs[:7]],
                                   ["flag"] + ["ok" if a.labels[j] == a.labels[i] else "neutral" for j in nbrs[:7]],
                                   f"{s.id} and its nearest neighbours",
                                   "First tile: flagged sample. Green: neighbours sharing the declared label; grey: "
                                   "neighbours with other labels.",
                                   {"neighbours": [{"sample": a.ids[j], "label": a.samples[j].label} for j in nbrs]},
                                   columns=8)
            stats = stat_evidence(ctx, "Label evidence", "Out-of-fold classifier and neighbourhood statistics.", {
                "declared": declared, "predicted": predicted, "p_predicted": round(float(p_pred[k]), 4),
                "p_declared": round(float(p_decl[k]), 4), "cl_threshold": round(float(thresholds[k]), 4),
                "neighbour_agreement": round(float(lm.agreement[k]), 4), "neighbours_same_label": same, "k": len(nbrs),
                "neighbour_majority": a.class_name(lm, int(lm.neighbour_class[k]))})
            res.findings.append(ProposedFinding(
                attack_class="label_flip", asset_type=AssetType.SAMPLE, asset_id=s.id, subject=f"labelflip:{s.id}",
                title=f"Label '{declared}' contradicted by content ({s.id})",
                reason=(f"Sample {s.id}{f' from {s.contributor}' if s.contributor else ''} is declared '{declared}', but "
                        f"only {same} of its {len(nbrs)} nearest visual neighbours carry that label "
                        f"({pct(float(lm.agreement[k]))} similarity-weighted) and a {lm.scheme} classifier predicts "
                        f"'{predicted}' with {pct(float(p_pred[k]))} probability (declared class {pct(float(p_decl[k]))})."),
                severity=severity, confidence=round(conf, 4), raw_score=round(float(score[k]), 4),
                threshold=ctx.calibration.threshold if ctx.calibration else None,
                score_semantics="1 − mean(neighbour agreement, declared-class probability)",
                evidence=[sheet, stats], access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                affected_samples=[ref(s, f"inferred '{predicted}'")],
                affected_contributors=[s.contributor] if s.contributor else [],
                corroborating_signals=["neighbour label disagreement", "out-of-fold classifier disagreement"],
                deterministic=False, calibrated=bool(ctx.calibrated),
                recommended_action=f"Verify the label; if the content is '{predicted}', correct it and review the "
                                   "contributor's other submissions.",
                tags={"declared": declared, "inferred": predicted}))
        return res


class SystematicParams(Params):
    min_count: int = Field(default=5, ge=2)
    min_ratio: float = Field(default=3.0, ge=1)
    degraded_min_ratio: float = Field(default=5.0, ge=1, description="Stricter ratio in the descriptor mode.")
    alpha: float = Field(default=0.01, gt=0, lt=1)
    min_inferred_prob: float = Field(default=0.5, ge=0, le=1)


class SystematicMislabel(Detector):
    Params = SystematicParams
    spec = DetectorSpec(
        id="data.systematic_mislabel", version="1.0.0", title="Systematic contributor mislabelling", layer=Layer.DATA,
        summary="Builds a declared → inferred confusion matrix per contributor (contributor-held-out inference) and "
                "tests every off-diagonal transition against the other contributors' rate, scaled by the "
                "contributor's general difficulty (binomial test, Benjamini–Hochberg).",
        required=[Capability.DATASET_IMAGES, Capability.DATASET_LABELS, Capability.CONTRIBUTOR_METADATA],
        optional=[Capability.SEMANTIC_ENCODER],
        modes=[DetectorMode(name="semantic", description="inference from a learned encoder",
                            needs=[Capability.SEMANTIC_ENCODER]),
               DetectorMode(name="descriptor", description="inference from the classical descriptor", degraded=True)],
        supports=[AttackSupport(attack_class="systematic_mislabel", level=SupportLevel.FULL),
                  AttackSupport(attack_class="label_flip", level=SupportLevel.PARTIAL,
                                note="targeted flips concentrated in one contributor")],
        depends_on=["data.label_consistency"], runtime=RuntimeClass.FAST,
        evidence_kinds=[EvidenceKind.CONFUSION_MATRIX, EvidenceKind.CONTACT_SHEET, EvidenceKind.STATISTIC],
        limitations=["Needs enough samples per contributor and class for the binomial test to have power: with about "
                     "100 samples per contributor and the weight-free descriptor, campaigns of fewer than ~20 relabelled "
                     "samples are typically not significant.",
                     "A pattern shared by every contributor (e.g. an ambiguous class definition) is, correctly, not "
                     "attributed to any one contributor.",
                     "In the descriptor mode, contributor-specific imaging conditions (terrain, sensor noise) can make "
                     "genuine samples of one class resemble another class across contributors; such findings are "
                     "reported at MEDIUM severity and require review.", _SEMANTIC_NOTE],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
        references=["Benjamini & Hochberg (1995) Controlling the false discovery rate. JRSS-B."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: SystematicParams = ctx.params  # type: ignore[assignment]
        a = analysis(ctx)
        lm = ctx.upstream["data.label_consistency"].artifacts["label_model"]
        K = len(lm.classes_modelled)
        contribs = np.array([a.samples[int(i)].contributor or "" for i in lm.index], dtype=object)
        degraded = ctx.mode == "descriptor"
        min_ratio = p.degraded_min_ratio if degraded else p.min_ratio
        confident = lm.p_predicted() >= p.min_inferred_prob
        if degraded:
            # Without a semantic encoder, cross-contributor domain shift can masquerade as relabelling; a
            # transition then also needs the cross-contributor neighbour majority to agree.
            confident &= lm.neighbour_class == lm.predicted
        # Samples already flagged as out-of-distribution are foreign content, not relabelled content: they are
        # excluded from the transition counts when the OOD detector ran (soft dependency).
        ood = ctx.upstream.get("data.ood")
        ood_ids = {f.sample_id for f in ood.flags} if ood is not None else set()
        foreign = np.array([a.ids[int(i)] in ood_ids for i in lm.index], dtype=bool)
        inferred = np.where(confident & ~foreign, lm.predicted, -1)

        def error_rate(mask: np.ndarray) -> float:
            decided = mask & (inferred >= 0)
            return float(((inferred != lm.declared) & decided).sum() / max(int(decided.sum()), 1))
        names = sorted({c for c in contribs if c})
        tests = []
        matrices: dict[str, list[list[int]]] = {}
        for c in names:
            mine = contribs == c
            mat = np.zeros((K, K + 1), dtype=int)  # last column: uncertain
            for d, inf in zip(lm.declared[mine], inferred[mine]):
                mat[d, inf if inf >= 0 else K] += 1
            matrices[c] = mat.tolist()
            for d in range(K):
                n_cd = int((mine & (lm.declared == d)).sum())
                if n_cd == 0:
                    continue
                other = (~mine) & (lm.declared == d)
                n_od = int(other.sum())
                # Contributor difficulty: how much more often the held-out model errs on this contributor's
                # *other* classes than on everyone else's. A contributor imaging in unusual conditions is harder
                # to classify everywhere; a relabelling campaign is an excess beyond that.
                e_c = error_rate(mine & (lm.declared != d))
                e_o = error_rate((~mine) & (lm.declared != d))
                difficulty = max(1.0, e_c / max(e_o, 1e-3))
                for b in range(K):
                    if b == d:
                        continue
                    k_cdb = int(mat[d, b])
                    if k_cdb == 0:
                        continue
                    k_odb = int((other & (inferred == b)).sum())
                    p0 = min(0.95, (k_odb + 0.5) / (n_od + 1.0) * difficulty)
                    tests.append((c, d, b, k_cdb, n_cd, k_odb, n_od, p0, difficulty,
                                  binomial_tail(k_cdb, n_cd, p0)))
        res = DetectorResult(samples_processed=len(lm.index))
        qs = benjamini_hochberg([t[-1] for t in tests]) if tests else np.array([])
        res.metrics = {"tests": len(tests), "contributors": names, "excluded_as_ood": int(foreign.sum())}
        res.section = {"confusion": {"classes": [a.class_name(lm, i) for i in range(K)] + ["uncertain"],
                                     "matrices": matrices}}
        for (c, d, b, k, n, k_o, n_o, p0, difficulty, _pv), q in zip(tests, qs):
            rate = k / n
            if not (q < p.alpha and k >= p.min_count and rate / p0 >= min_ratio):
                continue
            dn, bn = a.class_name(lm, d), a.class_name(lm, b)
            sel = [int(lm.index[j]) for j in range(len(lm.index))
                   if contribs[j] == c and lm.declared[j] == d and inferred[j] == b]
            conf = float(min(0.99, (1 - q) * min(1.0, lm.oof_accuracy / 0.8)))
            sheet = sheet_evidence(ctx, [a.images[i] for i in sel], ["flag"] * len(sel),
                                   f"{c}: declared '{dn}', inferred '{bn}'", f"{len(sel)} affected samples.")
            cm = table_evidence(ctx, f"Confusion matrix for {c}", "Rows: declared class; columns: class inferred by "
                                "the out-of-fold model ('uncertain' when its probability is below the threshold).",
                                ["declared \\ inferred"] + [a.class_name(lm, i) for i in range(K)] + ["uncertain"],
                                [[a.class_name(lm, r)] + matrices[c][r] for r in range(K)],
                                kind=EvidenceKind.CONFUSION_MATRIX)
            st = stat_evidence(ctx, "Transition test", "One-sided binomial test against other contributors, BH-adjusted.",
                               {"contributor": c, "declared": dn, "inferred": bn, "count": k, "declared_total": n,
                                "rate": rate, "other_count": k_o, "other_declared_total": n_o,
                                "contributor_difficulty": round(difficulty, 3), "baseline_rate": p0,
                                "q_value": float(q), "held_out_accuracy": lm.oof_accuracy, "scheme": lm.scheme})
            res.findings.append(ProposedFinding(
                attack_class="systematic_mislabel", asset_type=AssetType.CONTRIBUTOR, asset_id=c,
                subject=f"systematic:{c}:{dn}->{bn}", title=f"{c} systematically labels '{bn}' content as '{dn}'",
                reason=(f"Contributor {c}: {k} of {n} samples declared '{dn}' ({pct(rate)}) are visually inferred as "
                        f"'{bn}', versus {k_o} of {n_o} ({pct(k_o / max(n_o, 1))}) for the other contributors "
                        f"(baseline adjusted ×{difficulty:.2f} for this contributor's overall difficulty; binomial "
                        f"q = {fmt_p(float(q))}). The pattern is concentrated, not random."),
                severity=Severity.MEDIUM if degraded else Severity.HIGH, confidence=round(conf, 4),
                raw_score=round(rate / p0, 3),
                threshold=min_ratio, score_semantics="rate ratio versus other contributors",
                evidence=[cm, sheet, st], access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                affected_samples=[ref(a.samples[i], f"inferred '{bn}'") for i in sel], affected_contributors=[c],
                corroborating_signals=["contributor-specific transition (BH)", "out-of-fold classifier inference"],
                deterministic=False, calibrated=bool(ctx.calibrated),
                recommended_action=f"Suspend {c}'s '{dn}' labels pending re-annotation and investigate the source.",
                tags={"declared": dn, "inferred": bn}))
            for i in sel:
                res.flags.append(SampleFlag(a.ids[i], c, "systematic_mislabel", self.spec.id, conf, Severity.HIGH,
                                            a.samples[i].batch))
        return res
