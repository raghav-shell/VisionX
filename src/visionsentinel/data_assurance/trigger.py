"""Trigger / poisoning artifact analysis.

This detector does not claim to find backdoors. It reports *trigger-like artifacts* and grades them
by how many independent signals agree:

1. **Frequency anomaly + spatial persistence** — high-pass residual energy in sliding windows,
   robust-z scored per window position; a position where anomalously many images are "hot" is
   tested against the typical hot rate (binomial, Benjamini–Hochberg).
2. **Pattern repetition** — natural texture does not repeat pixel-for-pixel across images; the
   normalised residual patches at a persistent position are compared, a consensus template is built
   and every image is scanned for it (normalised correlation, ±2 px).
3. **Contributor concentration** — Fisher exact test of the template-bearing set against the
   dataset's contributor mix.
4. **Class correlation** — Fisher exact test of the set's labels (dirty-label poisoning concentrates
   in a target class).
5. **Model dependence** (optional, needs model predictions) — occluding the artifact region changes
   predictions far more often than occluding the same region in control images.

A global variant looks for a shared additive residual component across many images (blended
triggers): after removing the dataset-wide mean residual (which absorbs compression grids), images
whose residuals correlate strongly with each other — excluding near-duplicates — form a group.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from pydantic import Field
from scipy import ndimage
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
from ..core.detector import Detector, DetectorResult, Params, SampleFlag
from ..core.stats import MAD_SCALE, benjamini_hochberg, binomial_tail, fmt_p
from ..evidence.render import heatmap, overlay_region
from .analysis import DatasetAnalysis, UnionFind
from .common import DATA_ASSUMPTIONS, analysis, pct, ref, sheet_evidence, stat_evidence, table_evidence


def _residuals(images: np.ndarray, sigma: float) -> np.ndarray:
    """Luma high-pass residual (image − Gaussian blur), float32 N×H×W."""
    y = images.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = np.empty_like(y)
    for i in range(len(y)):
        out[i] = y[i] - ndimage.gaussian_filter(y[i], sigma)
    return out


def _window_energy(res: np.ndarray, win: int, stride: int) -> tuple[np.ndarray, list[tuple[int, int]]]:
    sq = res.astype(np.float64) ** 2
    integ = np.zeros((sq.shape[0], sq.shape[1] + 1, sq.shape[2] + 1))
    integ[:, 1:, 1:] = sq.cumsum(1).cumsum(2)
    H, W = res.shape[1:]
    pos = [(y, x) for y in range(0, H - win + 1, stride) for x in range(0, W - win + 1, stride)]
    e = np.stack([integ[:, y + win, x + win] - integ[:, y, x + win] - integ[:, y + win, x] + integ[:, y, x]
                  for y, x in pos], axis=1)
    return e, pos


def _patches(res: np.ndarray, y: int, x: int, win: int, shift: int = 0) -> np.ndarray:
    H, W = res.shape[1:]
    y0, x0 = int(np.clip(y + shift, 0, H - win)), int(np.clip(x, 0, W - win))
    p = res[:, y0:y0 + win, x0:x0 + win].reshape(len(res), -1).astype(np.float64)
    p = p - p.mean(axis=1, keepdims=True)
    return p / np.maximum(np.linalg.norm(p, axis=1, keepdims=True), 1e-9)


def _best_match(res: np.ndarray, template: np.ndarray, y: int, x: int, win: int, radius: int = 2
                ) -> tuple[np.ndarray, np.ndarray]:
    """Best normalised correlation with ``template`` within ±radius px, and the aligned patch per image."""
    H, W = res.shape[1:]
    best = np.full(len(res), -np.inf)
    aligned = np.zeros((len(res), win * win))
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            yy, xx = int(np.clip(y + dy, 0, H - win)), int(np.clip(x + dx, 0, W - win))
            p = res[:, yy:yy + win, xx:xx + win].reshape(len(res), -1).astype(np.float64)
            p = p - p.mean(axis=1, keepdims=True)
            p /= np.maximum(np.linalg.norm(p, axis=1, keepdims=True), 1e-9)
            score = p @ template
            better = score > best
            best[better] = score[better]
            aligned[better] = p[better]
    return best, aligned


def _where(y: int, x: int, win: int, H: int, W: int) -> str:
    vert = "top" if y + win / 2 < H / 3 else ("bottom" if y + win / 2 > 2 * H / 3 else "middle")
    horz = "left" if x + win / 2 < W / 3 else ("right" if x + win / 2 > 2 * W / 3 else "centre")
    return "centre" if (vert, horz) == ("middle", "centre") else f"{vert}-{horz}"


def _fisher_enrichment(member: np.ndarray, values: np.ndarray) -> tuple[str | None, float, float, int]:
    """Most over-represented value among members: (value, enrichment, p, count)."""
    if member.sum() == 0:
        return None, 0.0, 1.0, 0
    counts = Counter(v for v in values[member] if v not in ("", None, -1))
    if not counts:
        return None, 0.0, 1.0, 0
    best, n_in = counts.most_common(1)[0]
    total_in = int(member.sum())
    n_all = int((values == best).sum())
    n_out = n_all - n_in
    table = [[n_in, total_in - n_in], [n_out, int((~member).sum()) - n_out]]
    _, p = sps.fisher_exact(table, alternative="greater")
    rest_rate = n_out / max(int((~member).sum()), 1)
    enrich = (n_in / total_in) / max(rest_rate, 1.0 / max(len(values), 1))
    return best, float(enrich), float(p), int(n_in)


class TriggerParams(Params):
    sigma: float = Field(default=1.0, gt=0)
    window: int = Field(default=8, ge=4, le=32)
    stride: int = Field(default=4, ge=1, le=16)
    hot_z: float = Field(default=6.0, gt=0, description="Robust z of log window energy to count as 'hot'.")
    persistence_alpha: float = Field(default=1e-4, gt=0, lt=1)
    min_members: int = Field(default=6, ge=3)
    template_similarity: float = Field(default=0.8, gt=0, le=1)
    min_consensus: float = Field(default=0.6, gt=0, le=1, description="Mean pairwise patch correlation required.")
    enrichment_alpha: float = Field(default=1e-3, gt=0, lt=1)
    blend_similarity: float = Field(default=0.3, gt=0, lt=1)
    blend_max_fraction: float = Field(default=0.4, gt=0, lt=1)
    occlusion_samples: int = Field(default=48, ge=4)
    occlusion_min_ratio: float = Field(default=3.0, ge=1)


class TriggerArtifactAnalysis(Detector):
    Params = TriggerParams
    spec = DetectorSpec(
        id="data.trigger_artifact", version="1.0.0", title="Trigger / poisoning artifact analysis", layer=Layer.DATA,
        summary="Looks for repeated high-frequency artifacts that persist in one image region (patch triggers) or "
                "form a shared additive residual (blended triggers), then grades them by contributor concentration, "
                "class correlation and — with model access — whether occluding them changes predictions.",
        required=[Capability.DATASET_IMAGES],
        optional=[Capability.DATASET_LABELS, Capability.CONTRIBUTOR_METADATA, Capability.MODEL_PREDICT],
        modes=[DetectorMode(name="artifact+model", description="artifact statistics with model occlusion test",
                            needs=[Capability.MODEL_PREDICT]),
               DetectorMode(name="artifact", description="artifact statistics only (no model dependence test)",
                            support_override=[AttackSupport(attack_class="localized_trigger", level=SupportLevel.PARTIAL),
                                              AttackSupport(attack_class="blended_trigger", level=SupportLevel.PARTIAL)],
                            degraded=True)],
        supports=[AttackSupport(attack_class="localized_trigger", level=SupportLevel.FULL,
                                note="fixed-position patch triggers"),
                  AttackSupport(attack_class="blended_trigger", level=SupportLevel.PARTIAL,
                                note="fixed additive patterns; not validated for low-amplitude blends")],
        unsupported=[UnsupportedAttack(attack_class="sample_specific_trigger",
                                       reason="no repeated pixel pattern exists to correlate"),
                     UnsupportedAttack(attack_class="clean_label_poisoning",
                                       reason="perturbations are sample-specific and labels remain consistent")],
        runtime=RuntimeClass.MODERATE,
        evidence_kinds=[EvidenceKind.HEATMAP, EvidenceKind.CONTACT_SHEET, EvidenceKind.DISTRIBUTION, EvidenceKind.TABLE],
        limitations=["Triggers placed at random positions, smooth (low-frequency) triggers and physical-object triggers "
                     "do not produce a spatially persistent high-frequency artifact.",
                     "Legitimate overlays (watermarks, timestamps, sensor graticules) also repeat; they are reported "
                     "as artifacts and are distinguished only by concentration and class correlation.",
                     "Without model access the detector cannot say whether a model learned the artifact."],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
        references=["Gu, Dolan-Gavitt & Garg (2017) BadNets. arXiv:1708.06733.",
                    "Chen et al. (2017) Targeted backdoor attacks … using data poisoning (blended). arXiv:1712.05526.",
                    "Tran, Li & Madry (2018) Spectral Signatures in Backdoor Attacks. NeurIPS."],
    )

    # ------------------------------------------------------------------ localized
    def _localized(self, ctx: DetectorContext, a: DatasetAnalysis, res: np.ndarray, p: TriggerParams,
                   out: DetectorResult) -> set[int]:
        N, H, W = res.shape
        energy, pos = _window_energy(res, p.window, p.stride)
        loge = np.log(energy + 1e-6)
        med = np.median(loge, axis=0)
        mad = np.median(np.abs(loge - med), axis=0) * MAD_SCALE
        z = (loge - med) / np.maximum(mad, 1e-6)
        hot = z > p.hot_z
        counts = hot.sum(axis=0)
        base = max(float(np.median(counts)) / N, 1.0 / N)
        pvals = np.array([binomial_tail(int(c), N, base) for c in counts])
        q = benjamini_hochberg(pvals)
        grid = int(round(np.sqrt(len(pos))))
        out.section = {"persistence": {"grid": counts.reshape(grid, -1).tolist() if grid * grid == len(pos) else [],
                                       "window": p.window, "stride": p.stride}}
        claimed: set[int] = set()
        order = np.argsort(-counts)
        for pi in order:
            if q[pi] >= p.persistence_alpha or counts[pi] < p.min_members:
                break
            y, x = pos[pi]
            cand = np.nonzero(hot[:, pi])[0]
            cand = np.array([i for i in cand if i not in claimed])
            if len(cand) < p.min_members:
                continue
            patches = _patches(res[cand], y, x, p.window)
            sims = patches @ patches.T
            np.fill_diagonal(sims, np.nan)
            medoid = int(np.nanargmax(np.nanmean(sims, axis=1)))
            core = [medoid] + [j for j in range(len(cand)) if j != medoid and sims[medoid, j] >= p.template_similarity]
            if len(core) < p.min_members:
                continue
            template = patches[core].mean(axis=0)
            template /= max(np.linalg.norm(template), 1e-9)
            match, aligned = _best_match(res, template, y, x, p.window)
            members = np.nonzero(match >= p.template_similarity)[0]
            members = np.array([i for i in members if i not in claimed])
            if len(members) < p.min_members:
                continue
            mp = aligned[members]
            msims = mp @ mp.T
            consensus = float((msims.sum() - len(members)) / max(len(members) * (len(members) - 1), 1))
            if consensus < p.min_consensus:
                continue
            rng = ctx.rng("null", pi)
            ctrl = rng.choice(np.setdiff1d(np.arange(N), members), size=min(200, N - len(members)), replace=False)
            cp = _patches(res[ctrl], y, x, p.window)
            null = float(np.mean((cp @ cp.T)[np.triu_indices(len(ctrl), 1)])) if len(ctrl) > 1 else 0.0
            claimed.update(int(i) for i in members)
            self._report(ctx, a, out, p, members=np.array(members), kind="localized", region=(y, x, p.window),
                         signals={"persistence": (int(counts[pi]), float(q[pi]), base),
                                  "repetition": (consensus, null), "hot_z": float(np.median(z[members, pi]))})
        return claimed

    # ------------------------------------------------------------------ blended
    def _blended(self, ctx: DetectorContext, a: DatasetAnalysis, res: np.ndarray, p: TriggerParams,
                 out: DetectorResult, claimed: set[int]) -> None:
        N = len(res)
        R = res.reshape(N, -1).astype(np.float64)
        R -= R.mean(axis=0, keepdims=True)
        R /= np.maximum(np.linalg.norm(R, axis=1, keepdims=True), 1e-9)
        S = R @ R.T
        np.fill_diagonal(S, 0.0)
        comp = a.duplicate_components()
        S[comp[:, None] == comp[None, :]] = 0.0
        adj = S >= p.blend_similarity
        degree = adj.sum(axis=1)
        uf = UnionFind(N)
        rows, cols = np.nonzero(np.triu(adj, 1))
        for i, j in zip(rows, cols):
            uf.union(int(i), int(j))
        labels = uf.components()
        for root in np.unique(labels):
            members = np.nonzero(labels == root)[0]
            members = np.array([i for i in members if i not in claimed and degree[i] > 0])
            if len(members) < p.min_members or len(members) > p.blend_max_fraction * N:
                continue
            # Single-linkage components can chain in a few bystanders; keep only members that correlate with the
            # group's consensus pattern at the level implied by the pairwise threshold (ρ_template ≈ √ρ_pair).
            template = R[members].mean(axis=0)
            template /= max(np.linalg.norm(template), 1e-9)
            members = members[R[members] @ template >= np.sqrt(p.blend_similarity)]
            if len(members) < p.min_members:
                continue
            sub = S[np.ix_(members, members)]
            consensus = float(sub.sum() / max(len(members) * (len(members) - 1), 1))
            if consensus < p.blend_similarity:
                continue
            null_idx = ctx.rng("blend-null").choice(np.setdiff1d(np.arange(N), members),
                                                    size=min(200, N - len(members)), replace=False)
            ns = S[np.ix_(null_idx, null_idx)]
            null = float(ns.sum() / max(len(null_idx) * (len(null_idx) - 1), 1))
            self._report(ctx, a, out, p, members=members, kind="blended", region=None,
                         signals={"repetition": (consensus, null)})

    # ------------------------------------------------------------------ model dependence
    def _occlusion(self, ctx: DetectorContext, a: DatasetAnalysis, members: np.ndarray, region, p: TriggerParams
                   ) -> dict | None:
        model = ctx.optional_asset("model")
        if model is None or region is None:
            return None
        y, x, win = region
        rng = ctx.rng("occlusion")
        sel = members if len(members) <= p.occlusion_samples else rng.choice(members, p.occlusion_samples, replace=False)
        others = np.setdiff1d(np.arange(a.n), members)
        ctrl = rng.choice(others, size=min(len(sel), len(others)), replace=False)

        def occlude(imgs: np.ndarray) -> np.ndarray:
            out = imgs.copy()
            blurred = np.stack([ndimage.median_filter(im, size=(win + 3, win + 3, 1)) for im in imgs])
            out[:, y:y + win, x:x + win] = blurred[:, y:y + win, x:x + win]
            return out

        def flip_rate(idx: np.ndarray) -> tuple[float, int]:
            imgs = a.images[idx]
            before = model.predict_proba(imgs).argmax(1)
            after = model.predict_proba(occlude(imgs)).argmax(1)
            return float((before != after).mean()), int((before != after).sum())

        r_members, n_members = flip_rate(sel)
        r_ctrl, _ = flip_rate(ctrl)
        ratio = r_members / max(r_ctrl, 1.0 / max(len(ctrl), 1))
        return {"member_flip_rate": r_members, "member_flips": n_members, "members_tested": int(len(sel)),
                "control_flip_rate": r_ctrl, "controls_tested": int(len(ctrl)), "ratio": ratio,
                "dependent": bool(r_members >= 0.3 and ratio >= p.occlusion_min_ratio)}

    # ------------------------------------------------------------------ reporting
    def _report(self, ctx, a: DatasetAnalysis, out: DetectorResult, p: TriggerParams, *, members: np.ndarray,
                kind: str, region, signals: dict) -> None:
        N = a.n
        member = np.zeros(N, dtype=bool)
        member[members] = True
        corroboration: list[str] = []
        lines: list[str] = []
        H, W = a.images.shape[1:3]
        if kind == "localized":
            y, x, win = region
            place = _where(y, x, win, H, W)
            cnt, qv, base = signals["persistence"]
            corroboration.append("spatially persistent high-frequency energy")
            lines.append(f"{len(members)} images carry a repeated {win}×{win} high-frequency pattern at the {place} "
                         f"(window energy a median {signals['hot_z']:.1f} robust SD above normal for that position; "
                         f"{cnt} hot images versus {base * N:.1f} expected, q = {fmt_p(qv)})")
        else:
            place = "whole image"
            lines.append(f"{len(members)} images share an additive residual component across the whole frame")
        consensus, null = signals["repetition"]
        corroboration.append("pattern repetition")
        lines.append(f"the residual patterns correlate at {consensus:.2f} on average versus {null:.2f} for random images")

        contributors = a.contributors.astype(object)
        c_best, c_enrich, c_p, c_n = _fisher_enrichment(member, contributors)
        if c_best and c_p < p.enrichment_alpha:
            corroboration.append("contributor concentration")
            lines.append(f"{c_n} of them come from contributor {c_best}, {c_enrich:.1f}× more common than in the "
                         f"remaining contributor population (Fisher p = {fmt_p(c_p)})")
        labels = np.array([a.dataset.classes[l] if l >= 0 else "" for l in a.labels], dtype=object)
        l_best, l_enrich, l_p, l_n = _fisher_enrichment(member, labels)
        if l_best and l_p < p.enrichment_alpha:
            corroboration.append("class correlation")
            lines.append(f"{l_n} are labelled '{l_best}' ({l_enrich:.1f}× the base rate, Fisher p = {fmt_p(l_p)})")
        occ = self._occlusion(ctx, a, members, region, p)
        if occ is not None:
            if occ["dependent"]:
                corroboration.append("model dependence")
                lines.append(f"occluding the region changes the model's prediction for {pct(occ['member_flip_rate'])} "
                             f"of these images versus {pct(occ['control_flip_rate'])} of control images")
            else:
                lines.append(f"occluding the region changes the model's prediction for only "
                             f"{pct(occ['member_flip_rate'])} of these images (controls {pct(occ['control_flip_rate'])}); "
                             "no model dependence was demonstrated")
        n_sig = len(corroboration)
        independent = {"contributor concentration", "class correlation", "model dependence"} & set(corroboration)
        if "model dependence" in corroboration and "class correlation" in corroboration:
            severity, verdict = Severity.HIGH, "Trigger-like artifact with class correlation and demonstrated model dependence"
        elif "class correlation" in corroboration:
            severity, verdict = Severity.HIGH, "Trigger-like artifact correlated with a target class"
        elif independent:
            severity, verdict = Severity.MEDIUM, "Possible trigger-like artifact"
        else:
            severity, verdict = Severity.LOW, "Repeated artifact without concentration or class correlation"
        confidence = min(0.97, 0.45 + 0.13 * n_sig)
        attack = "localized_trigger" if kind == "localized" else "blended_trigger"

        evidence = []
        ordered = list(members[np.argsort([a.ids[i] for i in members])])
        tiles = []
        for i in ordered[:24]:
            img = a.images[i]
            if region is not None:
                y, x, win = region
                tiles.append(overlay_region(img, y, x, y + win, x + win, "flag", scale=2))
            else:
                tiles.append(img)
        evidence.append(sheet_evidence(ctx, tiles, ["flag"] * len(tiles), f"Samples carrying the artifact ({len(members)})",
                                       "Red outline: the artifact window." if region else "Images sharing the residual.",
                                       {"sample_ids": [a.ids[i] for i in ordered[:200]]}))
        if kind == "localized" and out.section and out.section["persistence"]["grid"]:
            grid = np.array(out.section["persistence"]["grid"], dtype=float)
            evidence.append(type(evidence[0])(
                id=ctx.evidence_id("heatmap"), kind=EvidenceKind.HEATMAP, title="Spatial persistence heatmap",
                summary="Number of images whose high-frequency energy is anomalous at each window position.",
                data={"grid": grid.astype(int).tolist(), "window": p.window, "stride": p.stride},
                blob=ctx.blobs.put_png(heatmap(grid, cell=16))))
            y, x, win = region
            patch = a.images[ordered[0]][y:y + win, x:x + win]
            evidence.append(type(evidence[0])(
                id=ctx.evidence_id("template"), kind=EvidenceKind.CONTACT_SHEET, title="Artifact close-up",
                summary=f"{win}×{win} region from {a.ids[ordered[0]]}, enlarged.",
                blob=ctx.blobs.put_png(np.repeat(np.repeat(patch, 12, 0), 12, 1))))
        evidence.append(stat_evidence(ctx, "Contributor distribution", "Artifact-bearing samples per contributor.",
                                      {"members": dict(Counter(str(c) or "unattributed" for c in contributors[member])),
                                       "dataset": dict(Counter(str(c) or "unattributed" for c in contributors))},
                                      kind=EvidenceKind.DISTRIBUTION))
        evidence.append(stat_evidence(ctx, "Class distribution", "Labels of artifact-bearing samples vs the dataset.",
                                      {"members": dict(Counter(str(l) for l in labels[member])),
                                       "dataset": dict(Counter(str(l) for l in labels))}, kind=EvidenceKind.DISTRIBUTION))
        if occ is not None:
            evidence.append(table_evidence(ctx, "Occlusion test", "Prediction change when the artifact window is "
                                           "replaced by its local median, members versus random controls.",
                                           ["group", "tested", "prediction changed"],
                                           [["artifact-bearing", occ["members_tested"], pct(occ["member_flip_rate"])],
                                            ["control", occ["controls_tested"], pct(occ["control_flip_rate"])]]))
        title = (f"{verdict}: {len(members)} samples"
                 + (f", {c_best}" if "contributor concentration" in corroboration else "")
                 + (f" → '{l_best}'" if "class correlation" in corroboration else ""))
        reason = "; ".join(lines) + "."
        reason = reason[0].upper() + reason[1:]
        out.findings.append(ProposedFinding(
            attack_class=attack, asset_type=AssetType.DATASET, asset_id=a.dataset.name,
            subject=f"trigger:{kind}:{place}:" + ",".join(sorted(a.ids[i] for i in members))[:120],
            title=title, reason=reason, severity=severity, confidence=round(confidence, 3),
            raw_score=round(consensus, 4), threshold=p.min_consensus if kind == "localized" else p.blend_similarity,
            score_semantics="mean pairwise residual-pattern correlation", evidence=evidence,
            access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
            affected_samples=[ref(a.samples[i], "artifact-bearing") for i in ordered[:200]],
            affected_count=len(members),
            affected_contributors=[c_best] if "contributor concentration" in corroboration else [],
            corroborating_signals=corroboration, deterministic=False, calibrated=bool(ctx.calibrated),
            recommended_action=("Quarantine the artifact-bearing samples, retrain without them and test the deployed "
                                "model for dependence on this pattern." if severity == Severity.HIGH else
                                "Inspect the artifact; confirm whether it is a legitimate overlay."),
            tags={"kind": kind, "region": place, "target_class": l_best or "", "signals": str(n_sig)}))
        for i in members:
            out.flags.append(SampleFlag(a.ids[i], a.samples[i].contributor, attack, self.spec.id, confidence, severity,
                                        a.samples[i].batch))
        out.artifacts.setdefault("groups", []).append({"kind": kind, "members": [a.ids[i] for i in members],
                                                       "region": region, "target": l_best})

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: TriggerParams = ctx.params  # type: ignore[assignment]
        a = analysis(ctx)
        if a.n < 3 * p.min_members:
            return DetectorResult(abstained=f"only {a.n} readable samples (< {3 * p.min_members})")
        res = _residuals(a.images, p.sigma)
        out = DetectorResult(samples_processed=a.n)
        claimed = self._localized(ctx, a, res, p, out)
        self._blended(ctx, a, res, p, out, claimed)
        out.metrics = {"groups": len(out.findings), "flagged": len(out.flags), "model_occlusion": ctx.mode == "artifact+model"}
        return out
