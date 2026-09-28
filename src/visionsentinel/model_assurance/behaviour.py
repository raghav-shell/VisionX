"""Behavioural fingerprint: does the candidate behave like the approved model on a fixed probe battery?

Black-box compatible (predictions only; per-class scores when available). Divergence is measured with
robust statistics: top-1 agreement with a Wilson interval, median and mean Jensen–Shannon divergence,
and mean Kendall τ of class rankings, per probe group. Identity is declared only within numerical
tolerance; any real difference is reported with its magnitude and the probes that show it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, Params
from ..core.errors import LoaderError
from ..core.stats import wilson_interval
from ..evidence.render import contact_sheet
from ..loaders.models import ModelHandle
from .common import MODEL_ASSUMPTIONS, candidate, reference, stat, table
from .probes import BATTERY_VERSION, battery

IDENTITY_JSD = 1e-6


def jsd(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1)
    q = np.clip(q, 1e-12, 1)
    m = 0.5 * (p + q)
    return 0.5 * (p * np.log(p / m)).sum(1) + 0.5 * (q * np.log(q / m)).sum(1)


def probe_set(model: ModelHandle, ctx: DetectorContext | None, max_natural: int) -> list[tuple[str, np.ndarray, str]]:
    probe = ctx.optional_asset("probe_analysis") if ctx is not None else None
    if probe is not None:
        return battery(model.cfg.input_size, probe.images, probe.ids, max_natural)
    return battery(model.cfg.input_size)


def fingerprint(model: ModelHandle, probes: list[tuple[str, np.ndarray, str]]) -> np.ndarray:
    return model.predict_proba(np.stack([p[1] for p in probes]))


def fingerprint_document(model: ModelHandle, probes: list[tuple[str, np.ndarray, str]]) -> dict[str, Any]:
    probs = fingerprint(model, probes)
    return {"version": 1, "battery": BATTERY_VERSION, "input_size": model.cfg.input_size,
            "model_artifact_digest": model.artifact_digest, "classes": model.class_names,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "probes": [{"id": pid, "group": g} for pid, _, g in probes],
            "probabilities": [[int(round(v * 1_000_000)) for v in row] for row in probs]}


def load_fingerprint(path: Path) -> dict[str, Any]:
    data = Path(path).read_bytes()
    if len(data) > 64 * 1024 * 1024:
        raise LoaderError("fingerprint file too large")
    doc = json.loads(data)
    if doc.get("version") != 1 or doc.get("battery") != BATTERY_VERSION:
        raise LoaderError(f"fingerprint battery {doc.get('battery')!r} is not {BATTERY_VERSION}")
    return doc


class BehaviourParams(Params):
    max_natural: int = Field(default=64, ge=0, le=512)
    divergent_agreement: float = Field(default=0.9, gt=0, le=1)
    divergent_jsd: float = Field(default=0.05, gt=0)


class BehaviouralFingerprint(Detector):
    Params = BehaviourParams
    spec = DetectorSpec(
        id="model.behaviour_fingerprint", version="1.0.0", title="Behavioural fingerprint", layer=Layer.MODEL,
        summary="Runs a deterministic probe battery (structured patterns, noise, gradients, primitives, natural probes "
                "and their colour/corruption transforms) and compares the candidate's outputs with the approved model.",
        required=[Capability.MODEL_PREDICT], required_any=[[Capability.REFERENCE_MODEL, Capability.REFERENCE_FINGERPRINT]],
        optional=[Capability.MODEL_LOGITS, Capability.PROBE_DATASET],
        modes=[DetectorMode(name="full-battery", description="synthetic and natural probes",
                            needs=[Capability.PROBE_DATASET]),
               DetectorMode(name="synthetic-battery", description="synthetic probes only (no probe corpus)",
                            degraded=True)],
        supports=[AttackSupport(attack_class="behavioural_divergence", level=SupportLevel.FULL),
                  AttackSupport(attack_class="model_substitution", level=SupportLevel.PARTIAL,
                                note="functional substitution without digest access"),
                  AttackSupport(attack_class="model_weight_tampering", level=SupportLevel.PARTIAL,
                                note="tampering that changes behaviour on the battery")],
        depends_on=[], runtime=RuntimeClass.MODERATE,
        evidence_kinds=[EvidenceKind.TABLE, EvidenceKind.CONTACT_SHEET, EvidenceKind.SERIES],
        limitations=["A backdoored model can agree with the approved model on every probe that does not contain its "
                     "trigger; agreement is evidence of functional equivalence on the battery only.",
                     "Without a probe corpus only synthetic probes are used, which exercise the model off-distribution."],
        access_assumptions=MODEL_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
        references=["Cao, Jia & Gong (2021) IPGuard: Protecting IP of DNN classifiers by fingerprinting the "
                    "classification boundary. AsiaCCS.",
                    "Lukas, Zhang & Kerschbaum (2021) Deep Neural Network Fingerprinting by Conferrable Adversarial "
                    "Examples. ICLR."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: BehaviourParams = ctx.params  # type: ignore[assignment]
        cand = candidate(ctx)
        ref = reference(ctx)
        probes = probe_set(cand, ctx if ctx.mode == "full-battery" else None, p.max_natural)
        if ref is not None and ref.status.predict:
            ref_probs = fingerprint(ref, probes)
            ref_source = f"reference model {ref.name}"
        else:
            doc = ctx.asset("reference_fingerprint")
            by_id = {pr["id"]: i for i, pr in enumerate(doc["probes"])}
            keep = [k for k, pr in enumerate(probes) if pr[0] in by_id]
            probes = [probes[k] for k in keep]
            ref_probs = np.array([doc["probabilities"][by_id[pr[0]]] for pr in probes], dtype=np.float64) / 1_000_000
            ref_source = f"stored fingerprint of {doc.get('model_artifact_digest', '?')[:19]}"
        cand_probs = fingerprint(cand, probes)
        if cand_probs.shape != ref_probs.shape:
            return DetectorResult(abstained=f"output shapes differ ({cand_probs.shape} vs {ref_probs.shape}); the "
                                            "models do not share a label space")
        groups = np.array([g for _, _, g in probes])
        d = jsd(cand_probs, ref_probs)
        agree = cand_probs.argmax(1) == ref_probs.argmax(1)
        tau = np.array([sps.kendalltau(a, b).statistic if np.ptp(a) > 0 and np.ptp(b) > 0 else 1.0
                        for a, b in zip(cand_probs, ref_probs)])
        tau = np.nan_to_num(tau, nan=1.0)
        rows = []
        per_group: dict[str, dict[str, float]] = {}
        for g in sorted(set(groups)):
            m = groups == g
            lo, hi = wilson_interval(int(agree[m].sum()), int(m.sum()))
            per_group[g] = {"n": int(m.sum()), "agreement": float(agree[m].mean()), "agreement_ci": [lo, hi],
                            "jsd_median": float(np.median(d[m])), "jsd_mean": float(d[m].mean()),
                            "kendall_tau": float(tau[m].mean())}
            rows.append([g, int(m.sum()), f"{agree[m].mean():.1%}", f"[{lo:.1%}, {hi:.1%}]", f"{np.median(d[m]):.2e}",
                         f"{d[m].mean():.2e}", f"{tau[m].mean():.3f}"])
        overall = {"probes": len(probes), "agreement": float(agree.mean()), "jsd_median": float(np.median(d)),
                   "jsd_mean": float(d.mean()), "jsd_max": float(d.max()), "kendall_tau": float(tau.mean())}
        natural = groups != "synthetic"
        nat_agree = float(agree[natural].mean()) if natural.any() else None
        res = DetectorResult(samples_processed=len(probes))
        worst = np.argsort(-d)[:12]
        res.section = {"behaviour": {"overall": overall, "groups": per_group, "reference": ref_source,
                                     "scatter": [[float(cand_probs[i].max()), float(ref_probs[i].max()),
                                                  bool(agree[i]), str(groups[i])] for i in range(0, len(probes),
                                                                                                max(1, len(probes) // 400))],
                                     "worst": [{"probe": probes[i][0], "group": str(groups[i]), "jsd": float(d[i]),
                                                "candidate": cand.class_names[int(cand_probs[i].argmax())] if cand.class_names else int(cand_probs[i].argmax()),
                                                "reference": cand.class_names[int(ref_probs[i].argmax())] if cand.class_names else int(ref_probs[i].argmax())}
                                               for i in worst]}}
        digest = ctx.upstream.get("model.artifact_digest")
        corroboration = []
        if digest is not None and not digest.artifacts.get("artifact_match", True):
            corroboration.append("artifact digest mismatch")
        ev = [table(ctx, "Agreement by probe group", f"Candidate versus {ref_source}.",
                    ["group", "probes", "top-1 agreement", "95% CI", "median JSD", "mean JSD", "Kendall τ"], rows,
                    kind=EvidenceKind.SERIES, extra={"overall": overall})]
        common = dict(asset_type=AssetType.MODEL, asset_id=cand.name, access_assumptions=MODEL_ASSUMPTIONS,
                      limitations=self.spec.limitations, deterministic=True, calibrated=True,
                      attack_class="behavioural_divergence", subject="behaviour")
        if overall["jsd_max"] <= IDENTITY_JSD and overall["agreement"] == 1.0:
            res.findings.append(ProposedFinding(
                severity=Severity.INFO, confidence=1.0, title="Behaviour identical to the approved model on the battery",
                reason=(f"On all {len(probes)} probes the candidate's class distributions match {ref_source} within "
                        f"numerical tolerance (max JSD {overall['jsd_max']:.1e})."),
                evidence=ev, recommended_action="None.", **common))
            return res
        sheet = contact_sheet([probes[i][1] for i in worst], borders=["flag"] * len(worst), tile=64, columns=6)
        ev.append(type(ev[0])(id=ctx.evidence_id("worst"), kind=EvidenceKind.CONTACT_SHEET,
                              title="Most divergent probes", summary="Probes with the largest Jensen–Shannon divergence.",
                              data={"probes": res.section["behaviour"]["worst"]}, blob=ctx.blobs.put_png(sheet)))
        strong = (overall["agreement"] < p.divergent_agreement or overall["jsd_mean"] > p.divergent_jsd
                  or (nat_agree is not None and nat_agree < p.divergent_agreement))
        res.findings.append(ProposedFinding(
            severity=Severity.HIGH if strong else Severity.MEDIUM, confidence=0.97 if strong else 0.8,
            title="Behaviour diverges from the approved model",
            reason=(f"Across {len(probes)} probes the candidate agrees with {ref_source} on {overall['agreement']:.1%} of "
                    f"top-1 decisions"
                    + (f" ({nat_agree:.1%} on natural probes)" if nat_agree is not None else "")
                    + f"; median Jensen–Shannon divergence {overall['jsd_median']:.2e}, mean {overall['jsd_mean']:.2e}, "
                    f"mean Kendall τ {overall['kendall_tau']:.3f}. The largest divergence is on "
                    f"'{probes[int(worst[0])][0]}'."),
            raw_score=round(overall["jsd_mean"], 6), threshold=p.divergent_jsd, score_semantics="mean JSD",
            evidence=ev, corroborating_signals=corroboration,
            recommended_action="Treat the candidate as a different model; do not deploy without re-approval.", **common))
        return res
