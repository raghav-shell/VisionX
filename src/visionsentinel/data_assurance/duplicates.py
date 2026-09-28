"""Near-duplicate flooding and duplicate-label conflicts.

Two-stage matching: (A) pHash *and* dHash Hamming distance, mirror-aware; (B) embedding cosine
confirmation. Small clusters (pairs, triples) are what ordinary augmentation produces and are not
flagged; flooding is established by cluster size and by a contributor-level binomial test of
redundancy against the other contributors' redundancy rate.
"""

from __future__ import annotations

from collections import Counter, defaultdict

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
from ..vision.hashing import to_hex
from .common import DATA_ASSUMPTIONS, analysis, contributor_counts, join_ids, pct, ref, sheet_evidence, stat_evidence, table_evidence


def _clusters(comp: np.ndarray) -> list[np.ndarray]:
    groups: dict[int, list[int]] = defaultdict(list)
    for i, c in enumerate(comp):
        groups[int(c)].append(i)
    return [np.array(v) for v in groups.values() if len(v) >= 2]


class NearDuplicateParams(Params):
    max_phash: int = Field(default=8, ge=0, le=32)
    max_dhash: int = Field(default=10, ge=0, le=32)
    min_cosine: float = Field(default=0.9, ge=0, le=1)
    min_cluster: int = Field(default=5, ge=3, description="Clusters smaller than this are treated as augmentation.")
    alpha: float = Field(default=0.01, gt=0, lt=1)
    min_ratio: float = Field(default=3.0, ge=1)


class NearDuplicateFlooding(Detector):
    Params = NearDuplicateParams
    spec = DetectorSpec(
        id="data.near_duplicate", version="1.0.0", title="Near-duplicate flooding", layer=Layer.DATA,
        summary="Finds clusters of near-identical samples (perceptual hash + embedding confirmation), measures the "
                "class imbalance they introduce and tests contributor redundancy against the rest of the population.",
        required=[Capability.DATASET_IMAGES], optional=[Capability.CONTRIBUTOR_METADATA, Capability.DATASET_LABELS],
        modes=[DetectorMode(name="hash+embedding", description="pHash/dHash candidates confirmed by embedding cosine")],
        supports=[AttackSupport(attack_class="duplicate_flood", level=SupportLevel.FULL)],
        runtime=RuntimeClass.FAST,
        evidence_kinds=[EvidenceKind.CONTACT_SHEET, EvidenceKind.GRAPH, EvidenceKind.HASH_LIST, EvidenceKind.DISTRIBUTION],
        limitations=["Heavily transformed copies (large crops, strong colour changes) can fall outside the hash bounds.",
                     "Legitimate burst photography of a static scene produces genuine near-duplicates; clusters are "
                     "evidence for review, not proof of intent."],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
        references=["Zauner, C. (2010) Implementation and benchmarking of perceptual image hash functions.",
                    "Krawetz, N. (2013) Kind of like that (dHash)."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: NearDuplicateParams = ctx.params  # type: ignore[assignment]
        a = analysis(ctx)
        comp = a.duplicate_components(p.max_phash, p.max_dhash, p.min_cosine)
        pairs = a.duplicate_pairs(p.max_phash, p.max_dhash, p.min_cosine)
        clusters = _clusters(comp)
        res = DetectorResult(samples_processed=a.n)
        stamps = [a.samples[i].timestamp or "" for i in range(a.n)]
        redundant = np.zeros(a.n, dtype=bool)
        for cl in clusters:
            order = sorted(cl, key=lambda i: (stamps[i], a.ids[i]))
            redundant[order[1:]] = True
        res.metrics = {"clusters": len(clusters), "samples_in_clusters": int(sum(len(c) for c in clusters)),
                       "redundant": int(redundant.sum()), "candidate_pairs": len(pairs),
                       "largest_cluster": int(max((len(c) for c in clusters), default=0))}
        pair_lookup = {(i, j): (pd, dd, m, cos) for i, j, pd, dd, m, cos in pairs}
        labels = a.labels
        class_counts = Counter(int(x) for x in labels if x >= 0)
        total_labelled = sum(class_counts.values())

        # --- cluster-level findings
        for cl in sorted(clusters, key=len, reverse=True):
            if len(cl) < p.min_cluster:
                continue
            members = [a.samples[i] for i in cl]
            contrib = contributor_counts([s.contributor for s in members])
            dominant, dom_n = next(iter(contrib.items()))
            dists = [pair_lookup[(min(i, j), max(i, j))][0] for i in cl for j in cl
                     if i < j and (min(i, j), max(i, j)) in pair_lookup]
            mean_pd = float(np.mean(dists)) if dists else float(p.max_phash)
            cl_labels = Counter(int(labels[i]) for i in cl if labels[i] >= 0)
            imbalance_pp = 0.0
            cls_name = None
            if cl_labels and total_labelled:
                top, top_n = cl_labels.most_common(1)[0]
                cls_name = a.dataset.classes[top]
                share_with = class_counts[top] / total_labelled
                share_without = (class_counts[top] - top_n + 1) / (total_labelled - len(cl) + 1)
                imbalance_pp = (share_with - share_without) * 100
            severity = Severity.HIGH if (len(cl) >= 2 * p.min_cluster or imbalance_pp >= 1.0) else Severity.MEDIUM
            ordered = sorted(cl, key=lambda i: (stamps[i], a.ids[i]))
            sheet = sheet_evidence(ctx, [a.images[i] for i in ordered], ["ok"] + ["flag"] * (len(ordered) - 1),
                                   f"Near-duplicate cluster ({len(cl)} samples)",
                                   "Green frame: earliest sample (treated as the source); red frames: redundant copies.",
                                   {"sample_ids": [a.ids[i] for i in ordered][:24]})
            graph = stat_evidence(ctx, "Cluster graph", "Pairwise perceptual-hash distances within the cluster.", {
                "nodes": [{"id": a.ids[i], "contributor": a.samples[i].contributor} for i in ordered[:60]],
                "edges": [{"source": a.ids[i], "target": a.ids[j], "phash": v[0], "dhash": v[1], "mirrored": v[2],
                           "cosine": round(v[3], 4)} for (i, j), v in pair_lookup.items()
                          if comp[i] == comp[cl[0]]][:200]}, kind=EvidenceKind.GRAPH)
            hashes = table_evidence(ctx, "Perceptual hashes", "64-bit pHash and dHash per member.",
                                    ["sample", "contributor", "phash", "dhash"],
                                    [[a.ids[i], a.samples[i].contributor, to_hex(a.hashes["phash"][i]),
                                      to_hex(a.hashes["dhash"][i])] for i in ordered], kind=EvidenceKind.HASH_LIST)
            dist = stat_evidence(ctx, "Contributor distribution", "Members per contributor.", {"counts": contrib},
                                 kind=EvidenceKind.DISTRIBUTION)
            cross = len(contrib) > 1
            reason = (f"{len(cl)} samples are near-identical (mean pHash distance {mean_pd:.1f}/64, embedding-confirmed); "
                      f"{dom_n} of them come from contributor {dominant}"
                      + (f" and the cluster spans {len(contrib)} contributors" if cross else "")
                      + (f". All carry label '{cls_name}', inflating that class by {imbalance_pp:.2f} percentage points"
                         if cls_name and len(cl_labels) == 1 else "") + ".")
            res.findings.append(ProposedFinding(
                attack_class="duplicate_flood", asset_type=AssetType.DATASET, asset_id=a.dataset.name,
                subject="dupcluster:" + ",".join(sorted(a.ids[i] for i in cl))[:200],
                title=f"Near-duplicate cluster of {len(cl)} samples ({dominant})", reason=reason, severity=severity,
                confidence=0.95 if mean_pd <= 4 else 0.85, raw_score=float(len(cl)), threshold=float(p.min_cluster),
                score_semantics="cluster size (samples)", evidence=[sheet, graph, hashes, dist],
                access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                affected_samples=[ref(a.samples[i], "redundant copy" if redundant[i] else "earliest member")
                                  for i in ordered], affected_contributors=list(contrib),
                corroborating_signals=["perceptual-hash match", "embedding cosine confirmation"],
                deterministic=True, calibrated=bool(ctx.calibrated),
                recommended_action="Keep one representative, remove redundant copies and ask the contributor to "
                                   "explain the submission.",
                tags={"cluster_size": str(len(cl))}))
            for i in cl:
                if redundant[i]:
                    res.flags.append(SampleFlag(a.ids[i], a.samples[i].contributor, "duplicate_flood", self.spec.id,
                                                0.9, severity, a.samples[i].batch))

        # --- contributor-level redundancy test (leave-one-out baseline)
        contributors = sorted({c for c in a.contributors if c})
        if len(contributors) >= 2:
            tests = []
            for c in contributors:
                mine = a.contributors == c
                n_c, r_c = int(mine.sum()), int(redundant[mine].sum())
                n_o, r_o = int((~mine).sum()), int(redundant[~mine].sum())
                p0 = (r_o + 0.5) / (n_o + 1.0)
                tests.append((c, n_c, r_c, p0, binomial_tail(r_c, n_c, p0)))
            qs = benjamini_hochberg([t[4] for t in tests])
            res.metrics["contributor_tests"] = [{"contributor": c, "samples": n, "redundant": r, "baseline": round(p0, 5),
                                                 "q": float(q)} for (c, n, r, p0, _), q in zip(tests, qs)]
            for (c, n_c, r_c, p0, _pv), q in zip(tests, qs):
                rate = r_c / max(n_c, 1)
                if q < p.alpha and r_c >= p.min_cluster and rate / max(p0, 1e-9) >= p.min_ratio:
                    idx = [i for i in range(a.n) if a.contributors[i] == c and redundant[i]]
                    ev = sheet_evidence(ctx, [a.images[i] for i in idx], ["flag"] * len(idx),
                                        f"Redundant copies from {c}", f"{r_c} redundant near-duplicates.")
                    st = stat_evidence(ctx, "Redundancy test", "One-sided binomial test against the other "
                                       "contributors' redundancy rate, Benjamini–Hochberg adjusted.",
                                       {"contributor": c, "samples": n_c, "redundant": r_c, "rate": rate,
                                        "baseline_rate": p0, "q_value": float(q)})
                    res.findings.append(ProposedFinding(
                        attack_class="duplicate_flood", asset_type=AssetType.CONTRIBUTOR, asset_id=c,
                        subject=f"dupflood-contributor:{c}", title=f"Contributor {c} floods the dataset with near-duplicates",
                        reason=(f"{r_c} of contributor {c}'s {n_c} samples ({pct(rate)}) are redundant near-duplicate "
                                f"copies, {rate / max(p0, 1e-9):.1f}× the {pct(p0)} redundancy rate of the other "
                                f"contributors (binomial q = {fmt_p(float(q))})."),
                        severity=Severity.HIGH if q < 1e-6 else Severity.MEDIUM,
                        confidence=float(min(0.99, 1 - q)), raw_score=float(rate), threshold=float(p0 * p.min_ratio),
                        score_semantics="redundant-sample rate", evidence=[ev, st],
                        access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                        affected_samples=[ref(a.samples[i], "redundant copy") for i in idx[:200]],
                        affected_count=len(idx), affected_contributors=[c],
                        corroborating_signals=["near-duplicate clusters", "contributor-level binomial test"],
                        deterministic=False, calibrated=bool(ctx.calibrated),
                        recommended_action=f"Deduplicate {c}'s submission and review the batches involved."))
        return res


class ConflictParams(Params):
    max_phash: int = Field(default=6, ge=0, le=32)
    max_dhash: int = Field(default=8, ge=0, le=32)
    min_cosine: float = Field(default=0.95, ge=0, le=1)


class DuplicateLabelConflict(Detector):
    Params = ConflictParams
    spec = DetectorSpec(
        id="data.duplicate_label_conflict", version="1.0.0", title="Duplicate-label conflict", layer=Layer.DATA,
        summary="Finds visually near-identical samples that carry different labels and attributes the conflict to "
                "the minority label, using the out-of-fold label model to break ties.",
        required=[Capability.DATASET_IMAGES, Capability.DATASET_LABELS],
        optional=[Capability.CONTRIBUTOR_METADATA],
        modes=[DetectorMode(name="tight-hash", description="tight perceptual-hash bound with embedding confirmation")],
        supports=[AttackSupport(attack_class="duplicate_label_conflict", level=SupportLevel.FULL),
                  AttackSupport(attack_class="label_flip", level=SupportLevel.PARTIAL,
                                note="only flips applied to duplicated content")],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.PAIR_COMPARISON, EvidenceKind.TABLE],
        limitations=["Only conflicts between near-identical images are visible; a flip on unique content is left "
                     "to label-consistency analysis.",
                     "When a conflict is an even split and the label model is uncertain, both sides are reported."],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: ConflictParams = ctx.params  # type: ignore[assignment]
        a = analysis(ctx)
        comp = a.duplicate_components(p.max_phash, p.max_dhash, p.min_cosine)
        labels = a.labels
        lm = a.label_model()
        oof_pred = {}
        if lm is not None:
            for k, i in enumerate(lm.index):
                oof_pred[int(i)] = lm.classes_modelled[int(lm.predicted[k])]
        res = DetectorResult(samples_processed=a.n)
        conflicts = 0
        for cl in _clusters(comp):
            labs = Counter(int(labels[i]) for i in cl if labels[i] >= 0)
            if len(labs) < 2:
                continue
            conflicts += 1
            ranked = labs.most_common()
            majority = ranked[0][0]
            if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
                votes = Counter(oof_pred.get(int(i)) for i in cl if int(i) in oof_pred)
                tied = [lab for lab, n in ranked if n == ranked[0][1]]
                best = [lab for lab in tied if votes.get(lab, 0) == max(votes.get(t, 0) for t in tied)]
                majority = best[0] if len(best) == 1 else None
            minority = [i for i in cl if labels[i] >= 0 and (majority is None or labels[i] != majority)]
            members = [a.samples[i] for i in cl]
            contribs = sorted({a.samples[i].contributor or "unattributed" for i in minority})
            desc = ", ".join(f"'{a.dataset.classes[lab]}' ×{n}" for lab, n in ranked)
            reason = (f"{len(cl)} near-identical samples (pHash ≤ {p.max_phash}, embedding cosine ≥ {p.min_cosine}) "
                      f"carry conflicting labels: {desc}."
                      + (f" The minority label comes from {', '.join(contribs)}." if majority is not None
                         else " The split is even and unresolved by the label model; all members need review."))
            ev = sheet_evidence(ctx, [a.images[i] for i in cl],
                                ["flag" if i in minority else "ok" for i in cl], "Conflicting duplicates",
                                "Red frames carry the minority (suspect) label.",
                                {"members": [{"sample": s.id, "contributor": s.contributor, "label": s.label}
                                             for s in members]}, columns=4)
            res.findings.append(ProposedFinding(
                attack_class="duplicate_label_conflict", asset_type=AssetType.DATASET, asset_id=a.dataset.name,
                subject="conflict:" + ",".join(sorted(s.id for s in members))[:200],
                title=f"Same content labelled {' / '.join(a.dataset.classes[lab] for lab, _ in ranked)}",
                reason=reason, severity=Severity.HIGH, confidence=0.9, evidence=[ev],
                access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                affected_samples=[ref(a.samples[i], "minority label" if i in minority else "majority label") for i in cl],
                affected_contributors=contribs, corroborating_signals=["perceptual-hash identity", "label disagreement"],
                deterministic=True, calibrated=bool(ctx.calibrated),
                recommended_action="Adjudicate the correct label and ask the minority contributor for justification."))
            for i in minority:
                res.flags.append(SampleFlag(a.ids[i], a.samples[i].contributor, "duplicate_label_conflict",
                                            self.spec.id, 0.9, Severity.HIGH, a.samples[i].batch))
        res.metrics = {"conflicting_clusters": conflicts}
        return res
