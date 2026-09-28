"""Layer-wise weight statistics: corruption checks and reference comparison.

Useful for reference comparison, corruption detection and triage of unusual layers. It is explicitly
*not* a backdoor detector: nothing here infers a trojan from weight statistics alone.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field
from scipy import stats as sps

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
    UnsupportedAttack,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, Params
from .common import MODEL_ASSUMPTIONS, candidate, reference, table


def layer_stats(name: str, w: np.ndarray) -> dict:
    a = np.asarray(w, dtype=np.float64).reshape(-1)
    finite = np.isfinite(a)
    af = a[finite]
    if len(af) == 0:
        return {"layer": name, "size": int(a.size), "nonfinite": int((~finite).sum())}
    std = float(af.std())
    q = np.quantile(af, [0.001, 0.01, 0.5, 0.99, 0.999])
    return {
        "layer": name, "shape": list(np.shape(w)), "size": int(a.size), "mean": float(af.mean()), "std": std,
        "sparsity": float((np.abs(af) < 1e-8).mean()), "l1": float(np.abs(af).sum()), "l2": float(np.sqrt((af**2).sum())),
        "kurtosis": float(sps.kurtosis(af)) if len(af) > 3 and std > 0 else 0.0,
        "extreme_fraction": float((np.abs(af - af.mean()) > 6 * std).mean()) if std > 0 else 0.0,
        "max_abs": float(np.abs(af).max()), "quantiles": [float(v) for v in q], "nonfinite": int((~finite).sum()),
    }


class WeightParams(Params):
    exploding_abs: float = Field(default=1e4, gt=0)
    change_tolerance: float = Field(default=1e-7, ge=0, description="Relative L2 change treated as identical.")


class WeightStatistics(Detector):
    Params = WeightParams
    spec = DetectorSpec(
        id="model.weight_statistics", version="1.0.0", title="Weight statistics", layer=Layer.MODEL,
        summary="Computes per-layer mean, spread, sparsity, norms, kurtosis, extreme-value share and quantiles; flags "
                "corrupted tensors and, against a reference, which layers changed and by how much.",
        required=[Capability.MODEL_PARAMETERS], optional=[Capability.REFERENCE_MODEL],
        modes=[DetectorMode(name="reference-comparison", description="per-layer comparison with the approved weights",
                            needs=[Capability.REFERENCE_MODEL]),
               DetectorMode(name="standalone", description="corruption checks and statistics only", degraded=True,
                            support_override=[AttackSupport(attack_class="model_corruption", level=SupportLevel.FULL)])],
        supports=[AttackSupport(attack_class="model_corruption", level=SupportLevel.FULL),
                  AttackSupport(attack_class="model_weight_tampering", level=SupportLevel.FULL,
                                note="which layers changed relative to the approved weights")],
        unsupported=[UnsupportedAttack(attack_class="model_backdoor_patch",
                                       reason="weight statistics alone cannot establish a backdoor")],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.TABLE, EvidenceKind.SERIES],
        limitations=["Statistics describe weights, not behaviour; a small targeted change can be behaviourally large.",
                     "Without a reference, only corruption (non-finite, exploding, degenerate tensors) is judged."],
        access_assumptions=MODEL_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: WeightParams = ctx.params  # type: ignore[assignment]
        cand = candidate(ctx)
        params = cand.parameters() or {}
        stats = [layer_stats(k, v) for k, v in sorted(params.items())]
        res = DetectorResult(samples_processed=len(stats))
        res.section = {"weights": {"layers": stats}}
        common = dict(asset_type=AssetType.MODEL, asset_id=cand.name, access_assumptions=MODEL_ASSUMPTIONS,
                      limitations=self.spec.limitations, calibrated=True)
        bad = [s for s in stats if s.get("nonfinite")]
        exploding = [s for s in stats if s.get("max_abs", 0) > p.exploding_abs]
        dead = [s for s in stats if s.get("std", 1) == 0 and s.get("size", 0) > 1 and not s["layer"].endswith("bias")]
        if bad or exploding or dead:
            rows = [[s["layer"], s.get("nonfinite", 0), f"{s.get('max_abs', float('nan')):.3g}", f"{s.get('std', 0):.3g}"]
                    for s in bad + exploding + dead]
            res.findings.append(ProposedFinding(
                attack_class="model_corruption", subject="weights:corruption", severity=Severity.HIGH,
                title=f"{len(bad) + len(exploding) + len(dead)} corrupted parameter tensor(s)",
                reason=(f"{len(bad)} tensors contain non-finite values, {len(exploding)} exceed |w| > {p.exploding_abs:g} "
                        f"and {len(dead)} weight tensors are constant."),
                confidence=1.0, deterministic=True,
                evidence=[table(ctx, "Corrupted tensors", "Layers failing corruption checks.",
                                ["layer", "non-finite", "max |w|", "std"], rows)],
                recommended_action="Reject the artifact and obtain a clean copy.", **common))
        ref = reference(ctx) if ctx.mode == "reference-comparison" else None
        rparams = ref.parameters() if ref is not None else None
        if rparams:
            rows, changed = [], []
            for name in sorted(set(params) | set(rparams)):
                a, b = params.get(name), rparams.get(name)
                if a is None or b is None or np.shape(a) != np.shape(b):
                    rows.append([name, "added" if b is None else "removed" if a is None else "shape changed", "—", "—"])
                    changed.append((name, float("inf")))
                    continue
                a64, b64 = np.asarray(a, np.float64), np.asarray(b, np.float64)
                rel = float(np.linalg.norm(a64 - b64) / max(np.linalg.norm(b64), 1e-12))
                cos = float((a64.ravel() @ b64.ravel()) / max(np.linalg.norm(a64) * np.linalg.norm(b64), 1e-12))
                rows.append([name, "changed" if rel > p.change_tolerance else "identical", f"{rel:.3e}", f"{cos:.6f}"])
                if rel > p.change_tolerance:
                    changed.append((name, rel))
            res.section["weights"]["comparison"] = rows
            if changed:
                total = len(set(params) | set(rparams))
                top = sorted(changed, key=lambda x: -x[1])[:5]
                pattern = ("only the final classification layer changed" if all(n.startswith(("fc", "classifier",
                           "head")) for n, _ in changed) else f"{len(changed)} of {total} tensors changed")
                res.findings.append(ProposedFinding(
                    attack_class="model_weight_tampering", subject="weights:changed",
                    severity=Severity.HIGH if len(changed) < total else Severity.MEDIUM,
                    title=f"Parameters differ from the approved model ({pattern})",
                    reason=(f"Relative to the approved weights, {pattern}; largest relative L2 changes: "
                            + ", ".join(f"{n} {r:.2e}" for n, r in top) + "."
                            + (" A change confined to a few layers is characteristic of targeted fine-tuning." if
                               len(changed) < total else " A change across every layer is characteristic of "
                               "retraining or re-initialisation.")),
                    confidence=1.0, deterministic=True,
                    evidence=[table(ctx, "Per-layer comparison", "Relative L2 change and cosine similarity to the "
                                    "approved weights.", ["tensor", "status", "relative L2 change", "cosine"], rows,
                                    kind=EvidenceKind.DIFF)],
                    recommended_action="Establish who changed the weights and why; run behavioural and backdoor checks.",
                    **common))
        return res
