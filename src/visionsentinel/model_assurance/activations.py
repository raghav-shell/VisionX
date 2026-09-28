"""Activation analysis of a model on the data it was trained with.

Per declared class, penultimate activations are examined two ways:

* **Activation clustering** (Chen et al., 2018): PCA to a few components, 2-means; a poisoned class tends to
  split into a large clean cluster and a small, well-separated poisoned cluster (silhouette score).
* **Spectral signature** (Tran et al., 2018): outlier score along the top singular vector of the centred
  representations; poisoned samples concentrate in the tail.

Clean classes also split (backgrounds, sub-types), so a split alone is weak evidence. The detector reports a
class only when the split is well separated, the minority cluster has a plausible poisoning size, and — where
available — the minority coincides with independently flagged samples (trigger artifacts, label conflicts).
"""

from __future__ import annotations

import numpy as np
from pydantic import Field
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from ..contracts import (
    AssetType,
    AttackSupport,
    BudgetTier,
    CalibrationRequirement,
    Capability,
    DetectorMode,
    DetectorSpec,
    Evidence,
    EvidenceKind,
    Layer,
    ProposedFinding,
    RuntimeClass,
    SampleRef,
    Severity,
    SupportLevel,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, Params, SampleFlag
from ..evidence.render import contact_sheet
from .common import MODEL_ASSUMPTIONS, candidate, table


class ActivationParams(Params):
    min_class: int = Field(default=30, ge=10)
    components: int = Field(default=10, ge=2, le=64)
    min_fraction: float = Field(default=0.04, gt=0, lt=0.5)
    max_fraction: float = Field(default=0.35, gt=0, lt=0.5)
    silhouette: float = Field(default=0.25, gt=0, lt=1, description="Minimum silhouette for a separated split.")
    min_overlap: float = Field(default=0.5, gt=0, le=1,
                               description="Share of the minority cluster that must be independently flagged.")


class ActivationAnalysis(Detector):
    Params = ActivationParams
    spec = DetectorSpec(
        id="model.activation_analysis", version="1.0.0", title="Activation clustering & spectral signatures",
        layer=Layer.MODEL,
        summary="Examines the model's penultimate activations on its training data per class for a small, well-separated "
                "sub-population (activation clustering) and spectral-signature outliers, and cross-checks them against "
                "independently flagged samples.",
        required=[Capability.MODEL_ACTIVATIONS, Capability.DATASET_IMAGES, Capability.DATASET_LABELS],
        modes=[DetectorMode(name="white-box", description="penultimate activations on the training data")],
        supports=[AttackSupport(attack_class="model_backdoor_patch", level=SupportLevel.PARTIAL,
                                note="needs the poisoned training data"),
                  AttackSupport(attack_class="model_backdoor_blended", level=SupportLevel.PARTIAL,
                                note="needs the poisoned training data"),
                  AttackSupport(attack_class="localized_trigger", level=SupportLevel.PARTIAL,
                                note="identifies which training samples the model represents differently")],
        depends_on=[], min_budget=BudgetTier.DEEP, runtime=RuntimeClass.MODERATE,
        evidence_kinds=[EvidenceKind.TABLE, EvidenceKind.CONTACT_SHEET, EvidenceKind.DISTRIBUTION],
        limitations=["Only meaningful when the model was trained on (a superset of) the analysed data.",
                     "Clean classes with distinct sub-types or backgrounds also split; splits are reported only with "
                     "independent corroboration.",
                     "Requires at least ~30 samples per class."],
        access_assumptions=MODEL_ASSUMPTIONS + ["The supplied dataset is the model's training data (or a superset)."],
        deterministic=True, calibration=CalibrationRequirement.REQUIRED,
        references=["Chen et al. (2018) Detecting Backdoor Attacks on Deep Neural Networks by Activation Clustering. "
                    "arXiv:1811.03728.",
                    "Tran, Li & Madry (2018) Spectral Signatures in Backdoor Attacks. NeurIPS."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: ActivationParams = ctx.params  # type: ignore[assignment]
        model = candidate(ctx)
        a = ctx.asset("dataset_analysis")
        labels = a.labels
        feats = model.features(a.images)
        independent: set[str] = set()
        for det in ("data.trigger_artifact", "data.label_consistency", "data.duplicate_label_conflict"):
            up = ctx.upstream.get(det)
            if up is not None:
                independent.update(f.sample_id for f in up.flags)
        res = DetectorResult(samples_processed=a.n)
        rows, per_class = [], []
        for c in sorted(set(int(v) for v in labels if v >= 0)):
            idx = np.nonzero(labels == c)[0]
            name = a.dataset.classes[c]
            if len(idx) < p.min_class:
                rows.append([name, len(idx), "—", "—", "—", "—", "too few samples"])
                continue
            F = feats[idx] - feats[idx].mean(axis=0)
            comps = min(p.components, F.shape[1], len(idx) - 1)
            Z = PCA(n_components=comps, random_state=0).fit_transform(F)
            km = KMeans(n_clusters=2, n_init=10, random_state=int(ctx.seed % (2**31))).fit(Z)
            sizes = np.bincount(km.labels_, minlength=2)
            minority = int(np.argmin(sizes))
            frac = float(sizes[minority] / len(idx))
            sil = float(silhouette_score(Z, km.labels_)) if len(set(km.labels_)) > 1 else 0.0
            _, _, vt = np.linalg.svd(F, full_matrices=False)
            spectral = (F @ vt[0]) ** 2
            members = idx[km.labels_ == minority]
            overlap = (sum(1 for i in members if a.ids[i] in independent) / len(members)) if len(members) else 0.0
            top = idx[np.argsort(-spectral)[: max(1, int(1.5 * len(members)))]]
            spec_overlap = len(set(top) & set(members)) / max(len(members), 1)
            status = "clean"
            if p.min_fraction <= frac <= p.max_fraction and sil >= p.silhouette:
                status = "separated split" + (" (corroborated)" if overlap >= p.min_overlap else " (uncorroborated)")
            rows.append([name, len(idx), f"{frac:.1%}", f"{sil:.2f}", f"{overlap:.0%}", f"{spec_overlap:.0%}", status])
            per_class.append({"class": name, "n": int(len(idx)), "minority_fraction": frac, "silhouette": sil,
                              "independent_overlap": overlap, "spectral_overlap": spec_overlap, "status": status})
            if status.endswith("(corroborated)"):
                ev = [table(ctx, "Per-class activation analysis", "Minority-cluster size, silhouette and overlap with "
                            "independently flagged samples.", ["class", "samples", "minority", "silhouette",
                                                               "independently flagged", "spectral overlap", "status"], rows),
                      Evidence(
                          id=ctx.evidence_id("minority", name), kind=EvidenceKind.CONTACT_SHEET,
                          title=f"Minority activation cluster of '{name}' ({len(members)})",
                          summary="Samples the model represents apart from the rest of their class.",
                          data={"sample_ids": [a.ids[i] for i in members[:200]]},
                          blob=ctx.blobs.put_png(contact_sheet([a.images[i] for i in members[:24]],
                                                               borders=["flag"] * min(24, len(members)))))]
                res.findings.append(ProposedFinding(
                    attack_class="model_backdoor_patch", asset_type=AssetType.MODEL, asset_id=model.name,
                    subject=f"ac:{name}", severity=Severity.HIGH, confidence=round(min(0.9, 0.5 + sil / 2), 3),
                    title=f"Class '{name}' contains a separate sub-population in the model's representation",
                    reason=(f"The model's penultimate activations for the {len(idx)} samples labelled '{name}' split into "
                            f"clusters of {sizes.max()} and {sizes.min()} ({frac:.0%} minority, silhouette {sil:.2f}); "
                            f"{overlap:.0%} of the minority were independently flagged by data-level detectors and "
                            f"{spec_overlap:.0%} fall in the spectral-signature tail. This is the representation signature "
                            "of samples the model learned through a different feature, as poisoned samples are."),
                    raw_score=round(sil, 4), threshold=p.silhouette, score_semantics="silhouette of the 2-means split",
                    evidence=ev, access_assumptions=self.spec.access_assumptions, limitations=self.spec.limitations,
                    affected_samples=[SampleRef(sample_id=a.ids[i], contributor=a.samples[i].contributor,
                                                label=a.samples[i].label) for i in members[:200]],
                    affected_count=len(members),
                    affected_contributors=sorted({a.samples[i].contributor for i in members if a.samples[i].contributor}),
                    corroborating_signals=["separated activation cluster", "independent data-level flags"]
                    + (["spectral-signature tail"] if spec_overlap >= 0.5 else []),
                    deterministic=False, calibrated=ctx.calibrated, tags={"target_class": name},
                    recommended_action="Remove the minority samples and retrain; treat the class as a backdoor target."))
                for i in members:
                    res.flags.append(SampleFlag(a.ids[i], a.samples[i].contributor, "localized_trigger", self.spec.id,
                                                0.7, Severity.MEDIUM, a.samples[i].batch))
        res.section = {"activations": {"classes": per_class}}
        if not res.findings:
            res.findings.append(ProposedFinding(
                attack_class="model_backdoor_patch", asset_type=AssetType.MODEL, asset_id=model.name, subject="ac:none",
                severity=Severity.INFO, confidence=0.6, title="No corroborated activation split",
                reason=(f"Across {len(per_class)} analysable classes no class shows a well-separated minority activation "
                        "cluster that coincides with independently flagged samples."),
                evidence=[table(ctx, "Per-class activation analysis", "Minority-cluster size and separation per class.",
                                ["class", "samples", "minority", "silhouette", "independently flagged", "spectral overlap",
                                 "status"], rows)],
                access_assumptions=self.spec.access_assumptions, limitations=self.spec.limitations,
                deterministic=False, calibrated=ctx.calibrated, recommended_action="None from this detector."))
        return res
