"""Drift detectors: covariate axes, semantic shift, and drift-versus-manipulation interpretation."""

from __future__ import annotations

from collections import Counter

import numpy as np
from pydantic import Field
from scipy import stats as sps
from sklearn.decomposition import PCA

from ..contracts import (
    AssetType,
    AttackSupport,
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
from ..core.detector import Detector, DetectorResult, Params
from ..core.stats import MAD_SCALE, benjamini_hochberg, binomial_tail, fmt_p
from ..evidence.render import contact_sheet
from ..vision.encoders import normalise_embeddings
from ..vision.quality import AXIS_DESCRIPTIONS, image_statistics
from ..vision.residuals import residuals, window_energy
from .statistics import classifier_two_sample_auc, compare_axes, jsd_vec, mmd_permutation

DRIFT_ASSUMPTIONS = ["The reference set represents the conditions the model was validated for.",
                     "Incoming data are assessed as delivered; source/sensor attribution comes from metadata."]


def photometric_normalise(images: np.ndarray, target_mean: float = 118.0, target_std: float = 48.0) -> np.ndarray:
    """Per-image, per-channel standardisation to a fixed mean/spread (removes global illumination and colour cast)."""
    x = images.astype(np.float32)
    mu = x.mean(axis=(1, 2), keepdims=True)
    sd = x.std(axis=(1, 2), keepdims=True)
    return np.clip((x - mu) / np.maximum(sd, 1.0) * target_std + target_mean, 0, 255).astype(np.uint8)


def _reference(ctx: DetectorContext):
    ref = ctx.optional_asset("reference_analysis")
    return (ref, "trusted reference dataset") if ref is not None else (ctx.asset("dataset_analysis"), "training dataset")


def _stats(ctx: DetectorContext, key: str, analysis) -> dict[str, np.ndarray]:
    cache = ctx.shared.setdefault("image_statistics", {})
    if key not in cache:
        st = image_statistics(analysis.images)
        dims = [(s.width, s.height) for s in analysis.samples]
        if all(w and h for w, h in dims):
            st["resolution"] = np.log10(np.array([w * h for w, h in dims], float))
            st["aspect_ratio"] = np.array([w / h for w, h in dims], float)
        cache[key] = st
    return cache[key]


def _group_field(analysis) -> str | None:
    for field in ("contributor", "source", "sensor"):
        values = {getattr(s, field) for s in analysis.samples if getattr(s, field)}
        if len(values) >= 2:
            return field
    return None


def _table(ctx, title, summary, columns, rows, kind=EvidenceKind.TABLE, extra=None) -> Evidence:
    data = {"columns": columns, "rows": rows}
    if extra:
        data.update(extra)
    return Evidence(id=ctx.evidence_id(title), kind=kind, title=title, summary=summary, data=data)


# ---------------------------------------------------------------------------------------------- covariate

class CovariateParams(Params):
    alpha: float = Field(default=0.01, gt=0, lt=1)
    min_effect: float = Field(default=0.147, ge=0, le=1, description="|Cliff's δ| below this is negligible.")
    min_group: int = Field(default=15, ge=5)


class CovariateDrift(Detector):
    Params = CovariateParams
    spec = DetectorSpec(
        id="drift.covariate", version="1.0.0", title="Operational covariate drift", layer=Layer.DRIFT,
        summary="Compares incoming images with the reference on interpretable axes (brightness, contrast, saturation, "
                "sharpness, entropy, colour temperature, blur, noise, exposure, resolution, aspect) using KS tests with "
                "BH correction, PSI, Wasserstein distance and Cliff's δ; severity follows effect magnitude.",
        required=[Capability.OPERATIONAL_DATA],
        required_any=[[Capability.REFERENCE_DATASET, Capability.DATASET_IMAGES]],
        modes=[DetectorMode(name="reference", description="against the trusted reference dataset",
                            needs=[Capability.REFERENCE_DATASET]),
               DetectorMode(name="training-data", description="against the (untrusted) training dataset", degraded=True)],
        supports=[AttackSupport(attack_class="operational_drift", level=SupportLevel.FULL)],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.TABLE, EvidenceKind.DISTRIBUTION],
        limitations=["Axes are global image statistics; a shift confined to small objects may not move them.",
                     "A statistically detectable shift can be operationally harmless; magnitude and the interpretation "
                     "layer must be read together."],
        access_assumptions=DRIFT_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
        references=["Rabanser, Günnemann & Lipton (2019) Failing Loudly: An Empirical Study of Methods for Detecting "
                    "Dataset Shift. NeurIPS.", "Romano et al. (2006) Appropriate statistics for ordinal level data."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: CovariateParams = ctx.params  # type: ignore[assignment]
        ref, ref_name = _reference(ctx)
        cur = ctx.asset("operational_analysis")
        rs, cs = _stats(ctx, "reference", ref), _stats(ctx, "incoming", cur)
        axes = compare_axes({k: rs[k] for k in cs if k in rs}, cs, seed=ctx.seed)
        material = [a for a in axes if a.material(p.alpha, p.min_effect)]
        field = _group_field(cur)
        groups: dict[str, dict] = {}
        if field:
            values = np.array([getattr(s, field) or "unattributed" for s in cur.samples], dtype=object)
            for g in sorted(set(values)):
                m = values == g
                if m.sum() < p.min_group:
                    continue
                sub = compare_axes({k: rs[k] for k in cs if k in rs}, {k: v[m] for k, v in cs.items()}, seed=ctx.seed)
                top = max(sub, key=lambda a: abs(a.delta)) if sub else None
                groups[g] = {"n": int(m.sum()), "max_axis": top.axis if top else None,
                             "max_delta": float(top.delta) if top else 0.0,
                             "axes": {a.axis: round(a.delta, 3) for a in sub}}
        hist = {}
        for a in axes:
            lo = float(min(np.quantile(rs[a.axis], 0.01), np.quantile(cs[a.axis], 0.01)))
            hi = float(max(np.quantile(rs[a.axis], 0.99), np.quantile(cs[a.axis], 0.99)))
            edges = np.linspace(lo, hi if hi > lo else lo + 1e-6, 25)
            hist[a.axis] = {"edges": edges.round(5).tolist(),
                            "reference": (np.histogram(rs[a.axis], edges)[0] / len(rs[a.axis])).round(4).tolist(),
                            "incoming": (np.histogram(cs[a.axis], edges)[0] / len(cs[a.axis])).round(4).tolist()}
        res = DetectorResult(samples_processed=cur.n, artifacts={"axes": axes, "groups": groups, "field": field,
                                                                 "material": material})
        res.section = {"covariate": {"reference": ref_name, "axes": [a.to_dict() for a in axes], "histograms": hist,
                                     "group_field": field, "groups": groups,
                                     "descriptions": {k: AXIS_DESCRIPTIONS.get(k, k) for k in cs}}}
        table = _table(ctx, "Per-axis drift statistics", f"Incoming ({cur.n}) versus {ref_name} ({ref.n}); KS p-values "
                       "BH-adjusted; effect: Cliff's δ.", ["axis", "reference median", "incoming median", "shift (SD)",
                                                           "KS q", "PSI", "Cliff's δ", "magnitude"],
                       [[a.axis, f"{a.ref_median:.4g}", f"{a.cur_median:.4g}", f"{a.shift_sd:+.2f}", fmt_p(a.q),
                         f"{a.psi:.3f}", f"{a.delta:+.3f}", a.magnitude] for a in axes], extra={"histograms": hist})
        if not material:
            res.findings.append(ProposedFinding(
                attack_class="operational_drift", asset_type=AssetType.OPERATIONAL_DATA, asset_id=cur.dataset.name,
                subject="drift:covariate", severity=Severity.INFO, confidence=0.8,
                title="No material shift on interpretable image axes",
                reason=(f"On {len(axes)} axes the incoming batch differs from the {ref_name} by at most "
                        f"|δ| = {max((abs(a.delta) for a in axes), default=0):.3f}; no axis combines significance "
                        f"(BH q < {p.alpha}) with a non-negligible effect."),
                evidence=[table], access_assumptions=DRIFT_ASSUMPTIONS, limitations=self.spec.limitations,
                deterministic=False, calibrated=True, recommended_action="None."))
            return res
        large = [a for a in material if a.magnitude == "large"]
        severity = Severity.HIGH if len(large) >= 2 else (Severity.MEDIUM if large or len(material) >= 2 else Severity.LOW)
        top = sorted(material, key=lambda a: -abs(a.delta))
        order = np.argsort(-np.abs(cs[top[0].axis] - np.median(rs[top[0].axis])))[:12]
        sheet = Evidence(id=ctx.evidence_id("examples"), kind=EvidenceKind.CONTACT_SHEET,
                         title=f"Incoming images furthest from the reference on '{top[0].axis}'",
                         summary="Examples illustrating the dominant shift.",
                         blob=ctx.blobs.put_png(contact_sheet([cur.images[i] for i in order], borders=["warn"] * len(order))))
        desc = "; ".join(f"{a.axis} {a.magnitude} (median {a.ref_median:.3g} → {a.cur_median:.3g}, δ = {a.delta:+.2f}, "
                         f"PSI {a.psi:.2f})" for a in top[:4])
        res.findings.append(ProposedFinding(
            attack_class="operational_drift", asset_type=AssetType.OPERATIONAL_DATA, asset_id=cur.dataset.name,
            subject="drift:covariate", severity=severity, confidence=0.9 if ctx.mode == "reference" else 0.75,
            title=f"Distribution shift on {len(material)} image axis/axes ({', '.join(a.axis for a in top[:3])})",
            reason=f"Relative to the {ref_name}, the incoming batch of {cur.n} images shifts on: {desc}.",
            raw_score=round(abs(top[0].delta), 4), threshold=p.min_effect, score_semantics="max |Cliff's δ|",
            evidence=[table, sheet], access_assumptions=DRIFT_ASSUMPTIONS, limitations=self.spec.limitations,
            deterministic=False, calibrated=True, tags={"axes": ",".join(a.axis for a in top)},
            recommended_action="Confirm the operating conditions; re-validate the model under them before relying on it."))
        return res


# ---------------------------------------------------------------------------------------------- semantic

class SemanticParams(Params):
    permutations: int = Field(default=200, ge=20, le=5000)
    alpha: float = Field(default=0.01, gt=0, lt=1)
    auc_medium: float = Field(default=0.65, gt=0.5, lt=1)
    auc_high: float = Field(default=0.8, gt=0.5, lt=1)
    pca_dims: int = Field(default=32, ge=2)


class SemanticDrift(Detector):
    Params = SemanticParams
    spec = DetectorSpec(
        id="drift.semantic", version="1.0.0", title="Semantic distribution shift", layer=Layer.DRIFT,
        summary="Compares embedding distributions (MMD² with permutation test; classifier two-sample AUC as effect "
                "size) and, with model access, the predicted-class mix (χ², Jensen–Shannon).",
        required=[Capability.OPERATIONAL_DATA], required_any=[[Capability.REFERENCE_DATASET, Capability.DATASET_IMAGES]],
        optional=[Capability.SEMANTIC_ENCODER, Capability.MODEL_PREDICT],
        modes=[DetectorMode(name="semantic", description="learned embedding", needs=[Capability.SEMANTIC_ENCODER]),
               DetectorMode(name="descriptor", description="weight-free descriptor embedding", degraded=True)],
        supports=[AttackSupport(attack_class="semantic_drift", level=SupportLevel.FULL)],
        runtime=RuntimeClass.MODERATE, evidence_kinds=[EvidenceKind.STATISTIC, EvidenceKind.DISTRIBUTION],
        limitations=["The descriptor embedding reflects appearance more than content; semantic support is partial "
                     "without a learned encoder.",
                     "Predicted-class shift can reflect either a real change of content or model failure under drift."],
        access_assumptions=DRIFT_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
        references=["Gretton et al. (2012) A Kernel Two-Sample Test. JMLR.",
                    "Lopez-Paz & Oquab (2017) Revisiting Classifier Two-Sample Tests. ICLR."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: SemanticParams = ctx.params  # type: ignore[assignment]
        ref, ref_name = _reference(ctx)
        cur = ctx.asset("operational_analysis")
        # Content, not lighting: embeddings are computed on photometrically normalised images so that an
        # illumination or colour-cast change (the covariate detector's job) does not masquerade as semantic drift.
        raw_r = cur.encoder.encode(photometric_normalise(ref.images))
        raw_c = cur.encoder.encode(photometric_normalise(cur.images))
        er = normalise_embeddings(raw_r, raw_r)
        ec = normalise_embeddings(raw_c, raw_r)
        dims = min(p.pca_dims, er.shape[1], len(er) - 1)
        pca = PCA(n_components=dims, random_state=0).fit(er)
        zr, zc = pca.transform(er), pca.transform(ec)
        mmd, mmd_p = mmd_permutation(zr, zc, ctx.rng("mmd"), p.permutations)
        auc = classifier_two_sample_auc(zr, zc, ctx.seed)
        model = ctx.optional_asset("model")
        class_shift = None
        if model is not None and model.status.predict:
            K = len(model.class_names) or model.predict_proba(cur.images[:1]).shape[1]
            pr = np.bincount(model.predict_proba(ref.images).argmax(1), minlength=K)
            pc = np.bincount(model.predict_proba(cur.images).argmax(1), minlength=K)
            chi = sps.chi2_contingency(np.vstack([pr, pc]) + 0.5)
            fr, fc = pr / pr.sum(), pc / pc.sum()
            class_shift = {"classes": model.class_names, "reference": fr.round(4).tolist(), "incoming": fc.round(4).tolist(),
                           "chi2_p": float(chi.pvalue), "jsd": jsd_vec(fr, fc),
                           "largest_increase": model.class_names[int(np.argmax(fc - fr))] if model.class_names else int(np.argmax(fc - fr)),
                           "increase": float(np.max(fc - fr))}
        res = DetectorResult(samples_processed=cur.n,
                             artifacts={"auc": auc, "mmd_p": mmd_p, "class_shift": class_shift, "ref_z": zr, "cur_z": zc})
        res.section = {"semantic": {"reference": ref_name, "mmd2": mmd, "mmd_p": mmd_p, "c2st_auc": auc,
                                    "encoder": cur.encoder.id, "class_shift": class_shift,
                                    "projection": {"reference": zr[:300, :2].round(4).tolist(),
                                                   "incoming": zc[:300, :2].round(4).tolist()}}}
        significant = mmd_p < p.alpha
        severity = (Severity.HIGH if significant and auc >= p.auc_high else
                    Severity.MEDIUM if significant and auc >= p.auc_medium else None)
        ev = [Evidence(id=ctx.evidence_id("semantic"), kind=EvidenceKind.STATISTIC, title="Embedding two-sample tests",
                       summary=f"MMD² permutation test ({p.permutations} permutations) and cross-validated classifier AUC "
                               "(0.5 = indistinguishable).",
                       data={"mmd2": mmd, "p_value": mmd_p, "c2st_auc": auc, "encoder": cur.encoder.id,
                             "class_shift": class_shift})]
        common = dict(asset_type=AssetType.OPERATIONAL_DATA, asset_id=cur.dataset.name, subject="drift:semantic",
                      access_assumptions=DRIFT_ASSUMPTIONS, limitations=self.spec.limitations, deterministic=False,
                      calibrated=True, attack_class="semantic_drift", evidence=ev)
        cls_txt = ""
        if class_shift and class_shift["chi2_p"] < p.alpha and class_shift["increase"] >= 0.1:
            cls_txt = (f"; the model's predicted-class mix also changed (χ² p = {fmt_p(class_shift['chi2_p'])}), most for "
                       f"'{class_shift['largest_increase']}' (+{class_shift['increase']:.0%})")
            severity = severity or Severity.MEDIUM
        if severity is None:
            res.findings.append(ProposedFinding(
                severity=Severity.INFO, confidence=0.75, title="Semantic distribution comparatively stable",
                reason=(f"In the {cur.encoder.id} embedding a classifier separates incoming from reference data with AUC "
                        f"{auc:.2f} (0.5 = indistinguishable); MMD² permutation p = {fmt_p(mmd_p)}."),
                recommended_action="None.", **common))
            return res
        res.findings.append(ProposedFinding(
            severity=severity, confidence=round(min(0.95, 0.5 + (auc - 0.5)), 3),
            title=f"Semantic distribution shift (classifier AUC {auc:.2f})",
            reason=(f"Incoming embeddings are distinguishable from the {ref_name}: classifier two-sample AUC {auc:.2f}, "
                    f"MMD² = {mmd:.4f} (permutation p = {fmt_p(mmd_p)}){cls_txt}."),
            raw_score=round(auc, 4), threshold=p.auc_medium, score_semantics="classifier two-sample AUC",
            recommended_action="Determine whether the content of operations has changed (new theatre, new object types) "
                               "before trusting model outputs.", **common))
        return res


# ---------------------------------------------------------------------------------------------- interpretation

class InterpretationParams(Params):
    min_group: int = Field(default=15, ge=5)
    hot_z: float = Field(default=6.0, gt=0)
    artifact_ratio: float = Field(default=3.0, ge=1)
    min_artifact_rate: float = Field(default=0.1, ge=0, le=1)
    artifact_alpha: float = Field(default=1e-3, gt=0, lt=1, description="BH level across window positions.")
    group_auc: float = Field(default=0.7, gt=0.5, lt=1)
    spike: float = Field(default=0.15, gt=0, le=1)


class DriftInterpretation(Detector):
    Params = InterpretationParams
    spec = DetectorSpec(
        id="drift.interpretation", version="1.0.0", title="Drift versus manipulation reasoning", layer=Layer.DRIFT,
        summary="Examines every source separately as well as the whole batch, and weighs evidence for an "
                "operational/environmental explanation (global low-level shift, stable semantics, all sources affected) "
                "against manipulation (a position-persistent trigger-like artifact, a semantic shift or a target-class "
                "spike confined to one source).",
        required=[Capability.OPERATIONAL_DATA], required_any=[[Capability.REFERENCE_DATASET, Capability.DATASET_IMAGES]],
        optional=[Capability.MODEL_PREDICT, Capability.DATASET_METADATA],
        modes=[DetectorMode(name="evidence-rules", description="deterministic evidence rules over drift statistics")],
        supports=[AttackSupport(attack_class="drift_manipulation", level=SupportLevel.PARTIAL,
                                note="rule-based triage; capped at REVIEW without strong corroboration"),
                  AttackSupport(attack_class="operational_drift", level=SupportLevel.PARTIAL,
                                note="explains the likely cause of a shift")],
        depends_on=["drift.covariate"], runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.TABLE, EvidenceKind.TEXT],
        limitations=["An adversary who imitates an environmental change (e.g. darkening every source) would be "
                     "classified as operational.",
                     "Per-source analysis needs source/sensor/contributor metadata and at least ~15 images per source.",
                     "Interpretation is triage; it never replaces an operator's knowledge of the mission context."],
        access_assumptions=DRIFT_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
    )

    @staticmethod
    def _persistent_artifacts(ref, cur, groups: dict[str, np.ndarray], p: InterpretationParams) -> dict[str, dict]:
        """Per group: the window position whose hot-image rate most exceeds the reference rate at that position."""
        er, pos = window_energy(residuals(ref.images, 1.0), 8, 4)
        ec, _ = window_energy(residuals(cur.images, 1.0), 8, 4)
        lr, lc = np.log(er + 1e-6), np.log(ec + 1e-6)
        med = np.median(lr, axis=0)
        mad = np.maximum(np.median(np.abs(lr - med), axis=0) * MAD_SCALE, 1e-6)
        ref_rate = ((lr - med) / mad > p.hot_z).mean(axis=0)
        hot = (lc - med) / mad > p.hot_z
        floor = 0.5 / len(lr)
        out = {}
        for g, m in groups.items():
            n = int(m.sum())
            counts = hot[m].sum(axis=0)
            rate = counts / n
            base = np.maximum(ref_rate, floor)
            pvals = np.array([binomial_tail(int(c), n, float(b)) for c, b in zip(counts, base)])
            q = benjamini_hochberg(pvals)
            best = int(np.argmin(q)) if len(q) else 0
            ratio = float(rate[best] / base[best])
            out[g] = {"position": pos[best], "rate": float(rate[best]), "reference_rate": float(ref_rate[best]),
                      "ratio": ratio, "q": float(q[best]),
                      "present": bool(q[best] < p.artifact_alpha and rate[best] >= p.min_artifact_rate
                                      and ratio >= p.artifact_ratio)}
        return out

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: InterpretationParams = ctx.params  # type: ignore[assignment]
        cov = ctx.upstream["drift.covariate"].artifacts
        sem = ctx.upstream.get("drift.semantic")
        ref, ref_name = _reference(ctx)
        cur = ctx.asset("operational_analysis")
        material = cov["material"]
        field = cov["field"]
        low_level = max((abs(a.delta) for a in material), default=0.0)
        auc = sem.artifacts["auc"] if sem else None
        semantic = auc is not None and auc >= 0.65 and sem.artifacts["mmd_p"] < 0.01
        model = ctx.optional_asset("model")
        values = (np.array([getattr(s, field) or "unattributed" for s in cur.samples], dtype=object) if field
                  else np.array(["all"] * cur.n, dtype=object))
        groups = {g: values == g for g in sorted(set(values)) if (values == g).sum() >= p.min_group}
        groups_all = {**groups, "__all__": np.ones(cur.n, dtype=bool)}
        artifacts = self._persistent_artifacts(ref, cur, groups_all, p)
        pred_c = pred_r = None
        if model is not None and model.status.predict:
            pred_c = model.predict_proba(cur.images).argmax(1)
            pred_r = model.predict_proba(ref.images).argmax(1)
        per_group: dict[str, dict] = {}
        for g, m in groups.items():
            info = {"n": int(m.sum()), "artifact": artifacts[g], "low_level": abs(cov["groups"].get(g, {}).get("max_delta", 0.0))}
            if sem is not None and len(groups) >= 2:
                zr = sem.artifacts["ref_z"]
                rsub = zr[ctx.rng("group", g).choice(len(zr), size=min(len(zr), 2 * int(m.sum())), replace=False)]
                info["auc"] = classifier_two_sample_auc(rsub, sem.artifacts["cur_z"][m], ctx.seed)
            if pred_c is not None:
                K = int(max(pred_c.max(), pred_r.max()) + 1)
                fr = np.bincount(pred_r, minlength=K) / len(pred_r)
                fg = np.bincount(pred_c[m], minlength=K) / m.sum()
                k = int(np.argmax(fg - fr))
                info["spike"] = {"class": model.class_names[k] if model.class_names else str(k), "increase": float(fg[k] - fr[k])}
            per_group[g] = info
        rows = []
        suspicious: dict[str, list[str]] = {}
        for g, info in per_group.items():
            sig = []
            if info["artifact"]["present"]:
                a = info["artifact"]
                sig.append(f"position-persistent trigger-like artifact ({a['rate']:.0%} of images at window "
                           f"{a['position']} vs {a['reference_rate']:.0%} in the reference, q = {fmt_p(a['q'])})")
            if info.get("auc", 0.5) >= p.group_auc:
                sig.append(f"semantic shift within this source (AUC {info['auc']:.2f})")
            if info.get("spike") and info["spike"]["increase"] >= p.spike:
                sig.append(f"'{info['spike']['class']}' predictions +{info['spike']['increase']:.0%}")
            others_quiet = all(not per_group[o]["artifact"]["present"] and per_group[o].get("auc", 0.5) < p.group_auc
                               for o in per_group if o != g)
            if info["artifact"]["present"] or (len(sig) >= 2 and others_quiet and len(per_group) >= 2):
                suspicious[g] = sig
            rows.append([g, info["n"], f"{info['low_level']:.2f}", f"{info.get('auc', float('nan')):.2f}",
                         f"{info['artifact']['rate']:.0%} @ {info['artifact']['position']}",
                         f"{info['spike']['class']} +{info['spike']['increase']:.0%}" if info.get("spike") else "—",
                         "; ".join(sig) or "—"])
        all_affected = len(per_group) >= 2 and all(v["low_level"] >= 0.33 for v in per_group.values())
        ev = [_table(ctx, "Per-source evidence", f"Each {field or 'batch'} against the {ref_name}: low-level |δ|, "
                     "semantic classifier AUC, most persistent artifact position, predicted-class change.",
                     [field or "group", "images", "max |δ|", "AUC", "artifact", "class change", "signals"], rows,
                     extra={"global": {"max_low_level_delta": low_level, "c2st_auc": auc, "artifact": artifacts["__all__"]}})]
        res = DetectorResult(samples_processed=cur.n)
        common = dict(asset_type=AssetType.OPERATIONAL_DATA, asset_id=cur.dataset.name, evidence=ev,
                      access_assumptions=DRIFT_ASSUMPTIONS, limitations=self.spec.limitations, deterministic=False,
                      calibrated=False)
        if suspicious:
            g, sig = max(suspicious.items(), key=lambda kv: (len(kv[1]), -per_group[kv[0]]["artifact"]["q"]))
            m = groups[g]
            members = [SampleRef(sample_id=s.id, contributor=s.contributor, label=s.label)
                       for s, keep in zip(cur.samples, m) if keep][:200]
            verdict = "SUSPICIOUS SHIFT — REVIEW REQUIRED"
            res.section = {"interpretation": {"verdict": verdict, "group": g, "signals": sig, "per_group": per_group,
                                              "field": field}}
            target = per_group[g].get("spike", {}).get("class", "") if per_group[g].get("spike", {}).get("increase", 0) >= p.spike else ""
            res.findings.append(ProposedFinding(
                attack_class="drift_manipulation", subject=f"drift:suspicious:{g}", severity=Severity.HIGH,
                confidence=round(min(0.9, 0.45 + 0.15 * len(sig)), 3), title=verdict,
                reason=(f"Change confined to {field or 'the batch'} '{g}' ({per_group[g]['n']} of {cur.n} images): "
                        + "; ".join(sig) + ". The other sources do not show it. Automatic inference is capped at REVIEW "
                        "unless three independent signals agree."),
                affected_samples=members, affected_count=int(m.sum()), corroborating_signals=[s.split(" (")[0] for s in sig],
                recommended_action=f"Hold incoming data from {field} '{g}' and inspect it; do not use it for retraining "
                "until cleared.", tags={"verdict": "suspicious", "target_class": target}, **common))
            return res
        if material or semantic:
            content = semantic and low_level < 0.33
            operational = [("global low-level shift", low_level >= 0.33),
                           ("semantic distribution comparatively stable", auc is not None and not semantic),
                           ("every source affected", all_affected),
                           ("no persistent artifact in any source", True),
                           ("no source-confined change", True)]
            score = sum(v for _, v in operational) / len(operational)
            verdict = ("SEMANTIC SHIFT — CONTENT CHANGE, REVIEW MISSION CONTEXT" if content else
                       "LIKELY OPERATIONAL SHIFT" if score >= 0.6 else "DISTRIBUTION SHIFT — CAUSE UNDETERMINED")
            res.section = {"interpretation": {"verdict": verdict, "operational_score": score, "per_group": per_group,
                                              "criteria": operational, "field": field}}
            met = [n for n, v in operational if v]
            res.findings.append(ProposedFinding(
                attack_class="semantic_drift" if content else "operational_drift", subject="drift:interpretation",
                severity=Severity.MEDIUM, confidence=round(score, 3), title=verdict,
                reason=(f"{'; '.join(met).capitalize()}. "
                        + ("The content of the imagery changed while its low-level statistics stayed close to the reference; "
                           "this is consistent with a change of theatre or target mix rather than tampering."
                           if content else f"Likely interpretation: {'operational/environmental drift' if score >= 0.6 else 'undetermined'} "
                           f"(confidence {score:.2f}). No source shows a confined or trigger-like change.")),
                recommended_action="Review recommended: confirm the operational change and re-validate the model.",
                tags={"verdict": "content" if content else ("operational" if score >= 0.6 else "undetermined")}, **common))
            return res
        res.section = {"interpretation": {"verdict": "NO MATERIAL DRIFT", "per_group": per_group, "field": field}}
        res.findings.append(ProposedFinding(
            attack_class="operational_drift", subject="drift:interpretation", severity=Severity.INFO, confidence=0.8,
            title="No material drift",
            reason=(f"Neither low-level nor semantic statistics show a material shift, and none of the {len(per_group)} "
                    "sources shows a confined or trigger-like change."),
            recommended_action="None.", tags={"verdict": "none"}, **common))
        return res
