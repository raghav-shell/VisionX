"""Trigger reconstruction (Neural Cleanse, Wang et al., IEEE S&P 2019).

For every class *t*, optimise a mask *m* and pattern *p* so that ``(1 − m)·x + m·p`` is classified as *t*
for clean inputs of other classes, while penalising the mask's L1 size. A backdoored target class is
reachable with an anomalously small mask. Anomaly index on log sizes:
``(median(log L) − log L_t) / (1.4826 · MAD(log L))``.

Scientific guardrails implemented here:
* gradients are required — a gradient-free version would need on the order of 10⁵ queries per class
  at usable fidelity, so black-box access makes the detector UNAVAILABLE rather than silently weak;
* a minimum number of classes is required (MAD over a handful of norms is unstable);
* the decision threshold comes from the profile's calibration record; the literature value (2.0) is
  used only as a documented, *uncalibrated* default.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field

from ..contracts import (
    AssetType,
    AttackSupport,
    BudgetTier,
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
    UnsupportedAttack,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, Params, PlanContext
from ..core.stats import MAD_SCALE
from ..evidence.render import contact_sheet, heatmap
from .common import MODEL_ASSUMPTIONS, candidate, stat, table

LITERATURE_THRESHOLD = 2.0


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


class Adam:
    def __init__(self, shape: tuple[int, ...], lr: float) -> None:
        self.m = np.zeros(shape)
        self.v = np.zeros(shape)
        self.t = 0
        self.lr = lr

    def step(self, param: np.ndarray, grad: np.ndarray) -> np.ndarray:
        self.t += 1
        self.m = 0.9 * self.m + 0.1 * grad
        self.v = 0.999 * self.v + 0.001 * grad**2
        mh = self.m / (1 - 0.9**self.t)
        vh = self.v / (1 - 0.999**self.t)
        return param - self.lr * mh / (np.sqrt(vh) + 1e-8)


def reverse_engineer(model, clean: np.ndarray, target: int, *, steps: int, batch: int, lr: float, init_cost: float,
                     asr_goal: float, rng: np.random.Generator) -> dict:
    """Optimise (mask, pattern) for one target; returns the smallest successful mask found."""
    n, c, s, _ = clean.shape
    m_raw = rng.normal(-2.0, 0.1, (1, 1, s, s))
    p_raw = rng.normal(0.0, 0.1, (1, c, s, s))
    opt_m, opt_p = Adam(m_raw.shape, lr), Adam(p_raw.shape, lr)
    cost = init_cost
    best = {"l1": float(s * s), "asr": 0.0, "mask": None, "pattern": None, "reached": False}
    streak_up = streak_down = 0
    for step in range(steps):
        idx = rng.choice(n, size=min(batch, n), replace=False)
        x = clean[idx]
        mask, pattern = _sigmoid(m_raw), _sigmoid(p_raw)
        xp = (1 - mask) * x + mask * pattern
        _, g = model.loss_gradient(xp.astype(np.float32), target)
        g = g.astype(np.float64)
        grad_mask = (g * (pattern - x)).sum(axis=(0, 1), keepdims=True) + cost / (s * s)
        grad_pat = (g * mask).sum(axis=0, keepdims=True)
        m_raw = opt_m.step(m_raw, grad_mask * mask * (1 - mask))
        p_raw = opt_p.step(p_raw, grad_pat * pattern * (1 - pattern))
        if step % 10 == 9 or step == steps - 1:
            mask, pattern = _sigmoid(m_raw), _sigmoid(p_raw)
            logits = model.logits_from_pixels(((1 - mask) * x + mask * pattern).astype(np.float32))
            asr = float((logits.argmax(1) == target).mean())
            l1 = float(mask.sum())
            if asr >= asr_goal and l1 < best["l1"]:
                best = {"l1": l1, "asr": asr, "mask": mask[0, 0].copy(), "pattern": pattern[0].copy(), "reached": True}
            if asr >= asr_goal:
                streak_up, streak_down = streak_up + 1, 0
                if streak_up >= 2:
                    cost *= 1.5
                    streak_up = 0
            else:
                streak_down, streak_up = streak_down + 1, 0
                if streak_down >= 2:
                    cost /= 1.5 ** 1.5
                    streak_down = 0
    if best["mask"] is None:
        mask, pattern = _sigmoid(m_raw), _sigmoid(p_raw)
        best.update(mask=mask[0, 0], pattern=pattern[0], l1=float(mask.sum()))
    return best


class ReconstructionParams(Params):
    steps: int = Field(default=240, ge=20, le=5000)
    batch: int = Field(default=24, ge=4, le=256)
    clean_samples: int = Field(default=64, ge=8, le=1024)
    lr: float = Field(default=0.1, gt=0)
    init_cost: float = Field(default=0.5, gt=0)
    asr_goal: float = Field(default=0.9, gt=0, le=1)
    min_classes: int = Field(default=5, ge=3)


class TriggerReconstruction(Detector):
    Params = ReconstructionParams
    spec = DetectorSpec(
        id="model.trigger_reconstruction", version="1.0.0", title="Trigger reconstruction (Neural Cleanse)",
        layer=Layer.MODEL,
        summary="For every class, optimises the smallest mask-and-pattern that sends clean inputs of other classes to it; "
                "a class reachable with an anomalously small trigger (MAD anomaly index) is a backdoor indicator.",
        required=[Capability.MODEL_PREDICT, Capability.MODEL_GRADIENTS],
        required_any=[[Capability.PROBE_DATASET, Capability.REFERENCE_DATASET]],
        modes=[DetectorMode(name="gradient", description="white-box gradient optimisation")],
        supports=[AttackSupport(attack_class="model_backdoor_patch", level=SupportLevel.FULL,
                                note="static patch triggers"),
                  AttackSupport(attack_class="model_backdoor_blended", level=SupportLevel.PARTIAL,
                                note="large-area blended triggers inflate the reconstructed norm")],
        unsupported=[UnsupportedAttack(attack_class="sample_specific_trigger",
                                       reason="dynamic triggers have no single universal mask to recover")],
        min_budget=BudgetTier.DEEP, runtime=RuntimeClass.EXPENSIVE,
        evidence_kinds=[EvidenceKind.SERIES, EvidenceKind.HEATMAP, EvidenceKind.CONTACT_SHEET],
        limitations=["Needs enough classes for the median/MAD statistic to be meaningful.",
                     "Triggers that cover a large area, or all-to-all backdoors, do not yield an anomalously small mask.",
                     "A class that is naturally easy to reach (a 'sink' class) can produce an anomaly without a backdoor; "
                     "corroboration from data or activation analysis is required before concluding."],
        access_assumptions=MODEL_ASSUMPTIONS + ["Clean inputs (probe corpus or trusted reference) are available."],
        deterministic=True, calibration=CalibrationRequirement.REQUIRED,
        references=["Wang et al. (2019) Neural Cleanse: Identifying and Mitigating Backdoor Attacks in Neural Networks. "
                    "IEEE S&P."],
    )

    def preconditions(self, caps, plan: PlanContext) -> list[str]:
        k = plan.fact("model.num_classes", 0)
        return [] if k >= 5 else [f"the model has {k} output classes; the MAD anomaly statistic needs at least 5"]

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: ReconstructionParams = ctx.params  # type: ignore[assignment]
        model = candidate(ctx)
        K = model.num_classes or 0
        if K < p.min_classes:
            return DetectorResult(abstained=f"{K} classes (< {p.min_classes})")
        source = ctx.optional_asset("probe_analysis") or ctx.optional_asset("reference_analysis")
        rng = ctx.rng("clean")
        idx = rng.choice(source.n, size=min(p.clean_samples * 2, source.n), replace=False)
        images = source.images[idx]
        preds = model.predict_proba(images).argmax(1)
        size = model.cfg.input_size
        from PIL import Image
        x_all = np.stack([np.asarray(Image.fromarray(im).resize((size, size), Image.Resampling.BOX))
                          if im.shape[0] != size else im for im in images]).transpose(0, 3, 1, 2).astype(np.float64) / 255
        norms, results = [], []
        for t in range(K):
            clean = x_all[preds != t][: p.clean_samples]
            if len(clean) < 4:
                norms.append(float(size * size))
                results.append({"l1": float(size * size), "asr": 0.0, "reached": False, "mask": None, "pattern": None})
                continue
            ctx.emit(f"reverse-engineering trigger for class {model.class_names[t] if model.class_names else t}")
            r = reverse_engineer(model, clean, t, steps=p.steps, batch=p.batch, lr=p.lr, init_cost=p.init_cost,
                                 asr_goal=p.asr_goal, rng=ctx.rng("nc", t))
            norms.append(r["l1"])
            results.append(r)
        L = np.array(norms)
        # The statistic is computed on log L1: trigger sizes span orders of magnitude between easy and hard
        # classes, and on a linear scale a single hard class inflates the MAD (documented deviation from the paper).
        logL = np.log(np.maximum(L, 1e-3))
        med_log = float(np.median(logL))
        mad = float(np.median(np.abs(logL - med_log)) * MAD_SCALE) or 1e-9
        anomaly = (med_log - logL) / mad
        med = float(np.exp(med_log))
        threshold = (ctx.calibration.threshold if ctx.calibration and ctx.calibration.threshold is not None
                     else LITERATURE_THRESHOLD)
        names = model.class_names or [str(i) for i in range(K)]
        rows = [[names[t], f"{L[t]:.1f}", f"{results[t]['asr']:.0%}", f"{anomaly[t]:+.2f}",
                 "yes" if results[t]["reached"] else "no"] for t in range(K)]
        res = DetectorResult(samples_processed=K * p.steps)
        res.section = {"reconstruction": {"classes": names, "l1": L.tolist(), "anomaly_index": anomaly.tolist(),
                                          "threshold": threshold, "median": med, "mad": mad,
                                          "calibrated": ctx.calibrated,
                                          "threshold_origin": ctx.calibration.threshold_origin if ctx.calibration else ""}}
        series = table(ctx, "Reconstructed trigger size per class", "Mask L1 (pixels) of the smallest trigger reaching "
                       f"{p.asr_goal:.0%} attack success, and the MAD anomaly index.",
                       ["class", "mask L1 (px)", "success", "anomaly index", "goal reached"], rows, kind=EvidenceKind.SERIES,
                       extra={"threshold": threshold, "median": med})
        flagged = [t for t in range(K) if anomaly[t] > threshold and results[t]["reached"]]
        res.artifacts = {"flagged": [names[t] for t in flagged], "anomaly": anomaly.tolist()}
        common = dict(asset_type=AssetType.MODEL, asset_id=model.name, access_assumptions=self.spec.access_assumptions,
                      limitations=self.spec.limitations, deterministic=False, calibrated=ctx.calibrated)
        origin = ctx.calibration.threshold_origin if ctx.calibration else "literature default"
        if not flagged:
            res.findings.append(ProposedFinding(
                attack_class="model_backdoor_patch", subject="nc:none", severity=Severity.INFO, confidence=0.7,
                title="No class admits an anomalously small trigger",
                reason=(f"Across {K} classes the smallest reconstructed triggers range from {L.min():.0f} to {L.max():.0f} "
                        f"pixels (median {med:.0f}); the largest anomaly index is {anomaly.max():+.2f}, below the "
                        f"threshold {threshold:g} ({origin})."),
                evidence=[series], recommended_action="None from this detector; see its limitations.", **common))
            return res
        data_trigger = ctx.upstream.get("data.trigger_artifact")
        data_targets = {g.get("target") for g in (data_trigger.artifacts.get("groups", []) if data_trigger else [])}
        for t in flagged:
            r = results[t]
            corroboration = ["anomalously small universal trigger"]
            if names[t] in data_targets:
                corroboration.append("training-data trigger artifact correlated with the same class")
            mask_png = ctx.blobs.put_png(heatmap(r["mask"], cell=4, vmax=1.0))
            composite = (r["pattern"] * r["mask"][None]).transpose(1, 2, 0)
            comp_png = ctx.blobs.put_png(contact_sheet([np.clip(composite * 255, 0, 255).astype(np.uint8)], tile=192,
                                                       borders=["flag"], columns=1))
            ys, xs = np.nonzero(r["mask"] > 0.5)
            where = (f"rows {ys.min()}–{ys.max()}, columns {xs.min()}–{xs.max()}" if len(ys) else "diffuse")
            res.findings.append(ProposedFinding(
                attack_class="model_backdoor_patch", subject=f"nc:{names[t]}",
                severity=Severity.HIGH if len(corroboration) > 1 else Severity.MEDIUM,
                confidence=round(float(min(0.95, 0.55 + 0.08 * (anomaly[t] - threshold) + 0.15 * (len(corroboration) - 1))), 3),
                title=f"Backdoor indicator: class '{names[t]}' reachable with a {r['l1']:.0f}-pixel trigger",
                reason=(f"Stamping a reconstructed {r['l1']:.0f}-pixel mask ({where}) sends {r['asr']:.0%} of clean inputs of "
                        f"other classes to '{names[t]}', while the median class needs {med:.0f} pixels; anomaly index "
                        f"{anomaly[t]:.2f} exceeds the threshold {threshold:g} ({origin})"
                        + ("; the training data carries a trigger-like artifact correlated with the same class." if
                           len(corroboration) > 1 else ".")),
                raw_score=round(float(anomaly[t]), 3), threshold=threshold, score_semantics="MAD anomaly index",
                evidence=[series,
                          type(series)(id=ctx.evidence_id("mask"), kind=EvidenceKind.HEATMAP, title="Reconstructed mask",
                                       summary="Where the optimiser placed the trigger.", blob=mask_png),
                          type(series)(id=ctx.evidence_id("pattern"), kind=EvidenceKind.CONTACT_SHEET,
                                       title="Reconstructed trigger (mask × pattern)", summary="Enlarged.", blob=comp_png),
                          stat(ctx, "MAD statistic", "Anomaly index computation.",
                               {"median_l1": med, "mad_scaled": mad, "l1": float(L[t]), "anomaly_index": float(anomaly[t]),
                                "threshold": threshold, "calibration": origin})],
                corroborating_signals=corroboration, tags={"target_class": names[t]},
                recommended_action="Do not deploy; retrain from vetted data or apply unlearning, and confirm with the "
                                   "data-level trigger analysis.", **common))
        return res
