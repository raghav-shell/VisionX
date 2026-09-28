"""STRIP: STRong Intentional Perturbation (Gao et al., ACSAC 2019) — an *input-level* detector.

Each suspect input is superimposed with many clean images; a trigger-carrying input keeps predicting the
target class regardless of the overlay, so the entropy of its predictions stays abnormally low. The decision
threshold is calibrated on held-out clean inputs (false-rejection-rate quantile), exactly as the method
prescribes.

STRIP is never run over clean probes to make a model-level claim: without suspect inputs it is UNAVAILABLE,
with the reason stated.
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
    SampleRef,
    Severity,
    SupportLevel,
    UnsupportedAttack,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, Params, SampleFlag
from ..evidence.render import contact_sheet
from .common import MODEL_ASSUMPTIONS, candidate, stat, table


def superimposition_entropy(model, inputs: np.ndarray, overlays: np.ndarray, n: int, rng: np.random.Generator
                            ) -> tuple[np.ndarray, np.ndarray]:
    """→ (label entropy, mean softmax entropy) per input, in bits.

    Decision statistic: the entropy of the *predicted-label histogram* over the n superimpositions — how
    consistently the decision survives the overlays. It is invariant to the softmax temperature, unlike the
    softmax entropy of the original paper, which a poorly calibrated model keeps high even when a trigger wins
    every overlay (observed on the demonstration models). The softmax entropy is kept as secondary evidence.
    """
    label_h = np.empty(len(inputs))
    soft_h = np.empty(len(inputs))
    for i, x in enumerate(inputs):
        picks = overlays[rng.choice(len(overlays), size=n, replace=len(overlays) < n)]
        blended = np.clip(0.5 * x.astype(np.float32) + 0.5 * picks.astype(np.float32), 0, 255).astype(np.uint8)
        p = np.clip(model.predict_proba(blended), 1e-12, 1)
        soft_h[i] = float((-(p * np.log2(p)).sum(axis=1)).mean())
        freq = np.bincount(p.argmax(1), minlength=p.shape[1]) / len(p)
        nz = freq[freq > 0]
        label_h[i] = float(-(nz * np.log2(nz)).sum())
    return label_h, soft_h


class StripParams(Params):
    overlays: int = Field(default=32, ge=8, le=256)
    frr: float = Field(default=0.01, gt=0, lt=0.5, description="False-rejection rate on clean inputs.")
    calibration_inputs: int = Field(default=120, ge=20)


class Strip(Detector):
    Params = StripParams
    spec = DetectorSpec(
        id="model.strip", version="1.0.0", title="STRIP runtime-trigger screening", layer=Layer.MODEL,
        summary="Superimposes each suspect input with clean images; inputs whose prediction entropy stays below the "
                "clean-calibrated threshold are trigger-dominated.",
        required=[Capability.MODEL_PREDICT, Capability.SUSPECT_INPUTS, Capability.PROBE_DATASET],
        modes=[DetectorMode(name="input-level", description="per suspect input, clean-calibrated threshold")],
        supports=[AttackSupport(attack_class="runtime_trigger_input", level=SupportLevel.FULL,
                                note="inputs carrying a strong, input-agnostic trigger"),
                  AttackSupport(attack_class="model_backdoor_patch", level=SupportLevel.PARTIAL,
                                note="only as evidence that a supplied input activates a backdoor")],
        unsupported=[UnsupportedAttack(attack_class="sample_specific_trigger",
                                       reason="input-specific triggers do not dominate under superimposition")],
        min_budget=BudgetTier.STANDARD, runtime=RuntimeClass.MODERATE,
        evidence_kinds=[EvidenceKind.DISTRIBUTION, EvidenceKind.CONTACT_SHEET, EvidenceKind.TABLE],
        limitations=["STRIP requires candidate inputs that may contain the trigger; it says nothing about a model "
                     "when only clean inputs are available.",
                     "Blending weakens small or low-contrast triggers; adaptive triggers can be designed to raise entropy.",
                     "Classes the model predicts with very high confidence can also yield low entropy."],
        access_assumptions=MODEL_ASSUMPTIONS + ["The probe corpus contains only clean inputs."],
        deterministic=True, calibration=CalibrationRequirement.REQUIRED,
        references=["Gao et al. (2019) STRIP: A Defence Against Trojan Attacks on Deep Neural Networks. ACSAC."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: StripParams = ctx.params  # type: ignore[assignment]
        model = candidate(ctx)
        suspect = ctx.asset("suspect_analysis")
        clean = ctx.asset("probe_analysis")
        rng = ctx.rng("split")
        perm = rng.permutation(clean.n)
        n_cal = min(p.calibration_inputs, clean.n // 2)
        cal_idx, overlay_idx = perm[:n_cal], perm[n_cal:]
        overlays = clean.images[overlay_idx]
        h_clean, soft_clean = superimposition_entropy(model, clean.images[cal_idx], overlays, p.overlays, ctx.rng("cal"))
        threshold = float(np.quantile(h_clean, p.frr))
        h, soft = superimposition_entropy(model, suspect.images, overlays, p.overlays, ctx.rng("suspect"))
        pvals = (1 + (h_clean[None, :] <= h[:, None]).sum(1)) / (len(h_clean) + 1)
        flagged = np.nonzero(h < threshold)[0]
        preds = model.predict_proba(suspect.images).argmax(1)
        names = model.class_names or [str(i) for i in range(int(preds.max()) + 1)]
        res = DetectorResult(samples_processed=suspect.n)
        res.section = {"strip": {"clean_entropy": np.round(h_clean, 4).tolist(), "suspect_entropy": np.round(h, 4).tolist(),
                                 "clean_softmax_entropy": np.round(soft_clean, 4).tolist(),
                                 "suspect_softmax_entropy": np.round(soft, 4).tolist(),
                                 "threshold": threshold, "frr": p.frr, "suspect_ids": suspect.ids[:500]}}
        dist = stat(ctx, "Entropy distributions", f"Entropy of the predicted-label histogram over {p.overlays} "
                    f"superimpositions; threshold = {p.frr:.0%} quantile of {len(h_clean)} held-out clean inputs.",
                    {"clean": np.round(h_clean, 4).tolist(), "suspect": np.round(h, 4).tolist(), "threshold": threshold},
                    kind=EvidenceKind.DISTRIBUTION)
        common = dict(asset_type=AssetType.SUSPECT_INPUTS, asset_id=suspect.dataset.name,
                      access_assumptions=self.spec.access_assumptions, limitations=self.spec.limitations,
                      deterministic=False, calibrated=ctx.calibrated)
        if len(flagged) == 0:
            res.findings.append(ProposedFinding(
                attack_class="runtime_trigger_input", subject="strip:none", severity=Severity.INFO, confidence=0.7,
                title=f"No trigger-dominated input among {suspect.n} suspect inputs",
                reason=(f"Every suspect input's superimposition entropy is at or above {threshold:.3f} bits, the "
                        f"{p.frr:.0%} false-rejection quantile of {len(h_clean)} clean inputs."),
                evidence=[dist], recommended_action="None from this detector.", **common))
            return res
        targets = {names[int(preds[i])] for i in flagged}
        rows = [[suspect.ids[i], f"{h[i]:.3f}", f"{soft[i]:.3f}", f"{pvals[i]:.3f}", names[int(preds[i])]]
                for i in flagged]
        sheet = ctx.blobs.put_png(contact_sheet([suspect.images[i] for i in flagged[:24]], borders=["flag"] * min(24, len(flagged))))
        res.findings.append(ProposedFinding(
            attack_class="runtime_trigger_input", subject="strip:flagged",
            severity=Severity.HIGH if len(flagged) >= 3 and len(targets) == 1 else Severity.MEDIUM,
            confidence=round(float(1 - np.median(pvals[flagged])), 3),
            title=f"{len(flagged)} suspect input(s) behave as trigger-dominated",
            reason=(f"{len(flagged)} of {suspect.n} suspect inputs keep the same prediction under superimposition with "
                    f"clean images (entropy {np.median(h[flagged]):.3f} bits median versus a clean {p.frr:.0%}-quantile of "
                    f"{threshold:.3f}); they are predicted as {', '.join(sorted(targets))}."),
            raw_score=round(float(np.median(h[flagged])), 4), threshold=round(threshold, 4),
            score_semantics="superimposition entropy (bits; low = trigger-dominated)",
            evidence=[dist, table(ctx, "Flagged inputs", "Label entropy, softmax entropy, conformal p-value against "
                                  "clean inputs, and prediction.",
                                  ["input", "label entropy", "softmax entropy", "p-value", "prediction"], rows),
                      type(dist)(id=ctx.evidence_id("inputs"), kind=EvidenceKind.CONTACT_SHEET, title="Flagged inputs",
                                 summary="Suspect inputs identified as trigger-dominated.", blob=sheet)],
            affected_samples=[SampleRef(sample_id=suspect.ids[i], note=f"entropy {h[i]:.3f}") for i in flagged[:200]],
            affected_count=len(flagged), corroborating_signals=["low superimposition entropy"],
            tags={"target_class": next(iter(targets)) if len(targets) == 1 else ""},
            recommended_action="Block the flagged inputs and investigate their source; test the model for a backdoor.",
            **common))
        for i in flagged:
            res.flags.append(SampleFlag(suspect.ids[i], None, "runtime_trigger_input", self.spec.id, 0.8, Severity.HIGH))
        return res
