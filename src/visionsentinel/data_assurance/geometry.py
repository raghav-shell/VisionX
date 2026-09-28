"""Annotation geometry integrity.

Deterministic checks (impossible, degenerate, out-of-frame, clipped, tiny, giant and unparseable
boxes) plus robust statistics: per-category modified z-scores of log relative area, and a
contributor-versus-rest Mann–Whitney test of box size per category (Benjamini–Hochberg), which
exposes systematic box inflation or shrinkage by one annotator.
"""

from __future__ import annotations

import math
from collections import defaultdict

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
from ..core.detector import Detector, DetectorResult, Params, SampleFlag
from ..core.stats import benjamini_hochberg, fmt_p, robust_z
from ..evidence.render import overlay_region
from ..loaders.images import resize
from .common import DATA_ASSUMPTIONS, dataset, join_ids, ref, sheet_evidence, table_evidence

HARD_CHECKS = {
    "degenerate": (Severity.MEDIUM, "zero or negative width/height"),
    "outside": (Severity.MEDIUM, "box lies entirely outside the image"),
    "clipped": (Severity.LOW, "box extends beyond the image border"),
    "tiny": (Severity.LOW, "box is smaller than the minimum plausible size"),
    "giant": (Severity.LOW, "box covers almost the whole image"),
    "unparseable": (Severity.MEDIUM, "annotation could not be parsed"),
}


class GeometryParams(Params):
    tiny_px: float = Field(default=3.0, ge=0)
    giant_fraction: float = Field(default=0.95, gt=0, le=1)
    clip_tolerance: float = Field(default=1.0, ge=0)
    z_threshold: float = Field(default=3.5, gt=0, description="Iglewicz–Hoaglin modified z-score cut-off.")
    shift_alpha: float = Field(default=0.01, gt=0, lt=1)
    min_shift_effect: float = Field(default=0.25, gt=0, description="|median log-area difference| (≈ 28% size change).")
    min_group: int = Field(default=15, ge=5)


class AnnotationGeometry(Detector):
    Params = GeometryParams
    spec = DetectorSpec(
        id="data.annotation_geometry", version="1.0.0", title="Annotation geometry integrity", layer=Layer.DATA,
        summary="Validates bounding boxes deterministically and uses robust statistics to find category outliers "
                "and contributor-specific systematic box shifts.",
        required=[Capability.DATASET_ANNOTATIONS], optional=[Capability.CONTRIBUTOR_METADATA],
        modes=[DetectorMode(name="robust", description="deterministic validity + median/MAD statistics")],
        supports=[AttackSupport(attack_class="annotation_tampering", level=SupportLevel.FULL)],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.TABLE, EvidenceKind.DISTRIBUTION, EvidenceKind.CONTACT_SHEET],
        limitations=["Checks geometry, not whether the box encloses the right object (see label consistency).",
                     "Categories with very few boxes cannot support outlier statistics."],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
        references=["Iglewicz & Hoaglin (1993) How to Detect and Handle Outliers. ASQC."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: GeometryParams = ctx.params  # type: ignore[assignment]
        ds = dataset(ctx)
        res = DetectorResult()
        hard: dict[tuple[str, str], list] = defaultdict(list)
        valid: list[tuple] = []
        n_boxes = 0
        for s in ds.samples:
            W, H = s.width or s.declared_width, s.height or s.declared_height
            for b in s.boxes:
                n_boxes += 1
                if not all(math.isfinite(v) for v in (b.x, b.y, b.w, b.h)):
                    hard[("unparseable", s.contributor or "unattributed")].append((s, b))
                    continue
                if b.w <= 0 or b.h <= 0:
                    kind = "degenerate"
                elif W and H and (b.x >= W or b.y >= H or b.x + b.w <= 0 or b.y + b.h <= 0):
                    kind = "outside"
                elif W and H and (b.x < -p.clip_tolerance or b.y < -p.clip_tolerance
                                  or b.x + b.w > W + p.clip_tolerance or b.y + b.h > H + p.clip_tolerance):
                    kind = "clipped"
                elif b.w < p.tiny_px or b.h < p.tiny_px:
                    kind = "tiny"
                elif W and H and b.w * b.h >= p.giant_fraction * W * H:
                    kind = "giant"
                else:
                    kind = None
                if kind:
                    hard[(kind, s.contributor or "unattributed")].append((s, b))
                if kind in (None, "tiny", "giant", "clipped") and W and H and b.w > 0 and b.h > 0:
                    valid.append((s, b, math.log(b.w * b.h / (W * H)), math.log(b.w / b.h)))
        for issue in ds.issues:
            sample = next((s for s in ds.samples if s.id == issue.sample_id), None)
            if sample is not None:
                hard[("unparseable", sample.contributor or "unattributed")].append((sample, None))
        res.samples_processed = n_boxes
        by_id = {s.id: s for s in ds.samples}

        for (kind, contributor), items in sorted(hard.items()):
            severity, text = HARD_CHECKS[kind]
            samples = list({s.id: s for s, _ in items}.values())
            ev = table_evidence(ctx, f"{kind} boxes ({contributor})", text,
                                ["sample", "category", "x", "y", "w", "h", "image"],
                                [[s.id, b.category if b else "—",
                                  *([round(v, 2) for v in b.as_list()] if b else ["—"] * 4),
                                  f"{s.width}x{s.height}"] for s, b in items])
            evidence = [ev]
            tiles = [(s, b) for s, b in items if b is not None and s.readable][:8]
            if tiles:
                imgs = []
                for s, b in tiles:
                    img = resize(ds.load(s), 64) if (s.width or 0) > 64 else ds.load(s)
                    sc = img.shape[0] / max(s.height or img.shape[0], 1)
                    x0, y0 = int(max(0, b.x * sc)), int(max(0, b.y * sc))
                    x1 = int(min(img.shape[1], max(x0 + 1, (b.x + b.w) * sc)))
                    y1 = int(min(img.shape[0], max(y0 + 1, (b.y + b.h) * sc)))
                    imgs.append(overlay_region(img, min(y0, img.shape[0] - 1), min(x0, img.shape[1] - 1), y1, x1,
                                               "warn", scale=2))
                evidence.append(sheet_evidence(ctx, imgs, ["warn"] * len(imgs), "Boxes drawn on their images",
                                               "Amber outline: the declared box (clamped to the frame)."))
            res.findings.append(ProposedFinding(
                attack_class="annotation_tampering", asset_type=AssetType.DATASET, asset_id=ds.name,
                subject=f"geometry:{kind}:{contributor}",
                title=f"{len(items)} {kind} annotation(s) from {contributor}",
                reason=(f"{len(items)} bounding boxes from {contributor} fail a deterministic geometry check ({text}); "
                        f"affected samples: {join_ids([s.id for s in samples])}."),
                severity=severity, confidence=1.0, evidence=evidence, access_assumptions=DATA_ASSUMPTIONS,
                limitations=self.spec.limitations, affected_samples=[ref(s, kind) for s in samples[:200]],
                affected_count=len(samples), affected_contributors=[contributor] if contributor != "unattributed" else [],
                deterministic=True, calibrated=True,
                recommended_action="Correct or remove the invalid boxes before training.", tags={"check": kind}))
            for s in samples:
                res.flags.append(SampleFlag(s.id, s.contributor, "annotation_tampering", self.spec.id, 0.9, severity,
                                            s.batch))

        # --- statistical outliers per category
        by_cat: dict[str, list] = defaultdict(list)
        for row in valid:
            by_cat[row[1].category].append(row)
        outliers: dict[str, list] = defaultdict(list)
        for cat, rows in by_cat.items():
            if len(rows) < p.min_group:
                continue
            z = robust_z(np.array([r[2] for r in rows]))
            for r, zz in zip(rows, z):
                if abs(zz) > p.z_threshold:
                    outliers[r[0].contributor or "unattributed"].append((r, float(zz)))
        for contributor, items in sorted(outliers.items()):
            rows = [[r[0].id, r[1].category, round(math.exp(r[2]) * 100, 2), round(z, 2)] for r, z in items]
            ev = table_evidence(ctx, f"Size outliers ({contributor})", "Relative box area (% of image) and modified "
                                "z-score within the category.", ["sample", "category", "area %", "modified z"], rows)
            res.findings.append(ProposedFinding(
                attack_class="annotation_tampering", asset_type=AssetType.DATASET, asset_id=ds.name,
                subject=f"geometry:outlier:{contributor}", title=f"{len(items)} atypically sized box(es) from {contributor}",
                reason=(f"{len(items)} boxes from {contributor} have a relative area more than {p.z_threshold} robust "
                        f"standard deviations from the median of their category."),
                severity=Severity.LOW, confidence=0.6, raw_score=float(max(abs(z) for _, z in items)),
                threshold=p.z_threshold, score_semantics="max |modified z| of log relative area", evidence=[ev],
                access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                affected_samples=[ref(r[0], f"z={z:.1f}") for r, z in items[:200]], affected_count=len(items),
                affected_contributors=[contributor] if contributor != "unattributed" else [],
                deterministic=False, calibrated=bool(ctx.calibrated),
                recommended_action="Spot-check these annotations.", tags={"check": "outlier"}))

        # --- contributor-specific systematic shifts.
        # A contributor is flagged only if it differs, in the same direction, from the majority of the other
        # contributors *individually*; a pooled "rest" baseline would let one aberrant contributor make every
        # other contributor look shifted.
        tests = []
        for cat, rows in by_cat.items():
            groups = defaultdict(list)
            for r in rows:
                if r[0].contributor:
                    groups[r[0].contributor].append(r[2])
            names = sorted(c for c, v in groups.items() if len(v) >= p.min_group)
            if len(names) < 3:
                continue
            for c in names:
                mine = np.array(groups[c])
                for d in names:
                    if d == c:
                        continue
                    other = np.array(groups[d])
                    pv = float(sps.mannwhitneyu(mine, other, alternative="two-sided").pvalue)
                    tests.append((c, cat, d, float(np.median(mine) - np.median(other)), len(mine), pv))
        if tests:
            qs = benjamini_hochberg([t[-1] for t in tests])
            verdicts: dict[tuple[str, str], list] = defaultdict(list)
            for t, q in zip(tests, qs):
                verdicts[(t[0], t[1])].append((t[2], t[3], t[4], float(q)))
            shifted: dict[str, list] = defaultdict(list)
            for (c, cat), comps in verdicts.items():
                sig = [x for x in comps if x[3] < p.shift_alpha and abs(x[1]) >= p.min_shift_effect]
                pos = [x for x in sig if x[1] > 0]
                neg = [x for x in sig if x[1] < 0]
                side = pos if len(pos) >= len(neg) else neg
                if len(side) * 3 >= 2 * len(comps) and side:
                    eff = float(np.median([x[1] for x in side]))
                    shifted[c].append((cat, eff, side[0][2], len(side), len(comps), max(x[3] for x in side)))
            for c, items in shifted.items():
                desc = "; ".join(f"'{cat}' boxes {math.exp(eff) * 100 - 100:+.0f}% area versus {k} of {m} other "
                                 f"contributors (max q = {fmt_p(q)})" for cat, eff, _, k, m, q in items)
                ev = table_evidence(ctx, f"Box-size shift for {c}", "Median log-area difference against each other "
                                    "contributor per category (pairwise Mann–Whitney U, BH-adjusted).",
                                    ["category", "median area change", "boxes", "contributors differing", "max q"],
                                    [[cat, f"{math.exp(eff) * 100 - 100:+.1f}%", n, f"{k}/{m}", q]
                                     for cat, eff, n, k, m, q in items], kind=EvidenceKind.DISTRIBUTION)
                cats = {it[0] for it in items}
                affected = [r[0] for r in valid if r[0].contributor == c and r[1].category in cats]
                big = max(abs(it[1]) for it in items)
                res.findings.append(ProposedFinding(
                    attack_class="annotation_tampering", asset_type=AssetType.CONTRIBUTOR, asset_id=c,
                    subject=f"geometry:shift:{c}", title=f"{c}'s boxes differ systematically in size",
                    reason=(f"Contributor {c}'s annotations differ from the other contributors': {desc}. Either the "
                            "boxes were resized, or objects of a different size class carry this label — compare with "
                            "the label-consistency findings for the same contributor."),
                    severity=Severity.HIGH if big >= 2 * p.min_shift_effect else Severity.MEDIUM, confidence=0.8,
                    raw_score=round(big, 4), threshold=p.min_shift_effect, score_semantics="|median log-area shift|",
                    evidence=[ev], access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                    affected_samples=[ref(s, "shifted box") for s in list({s.id: s for s in affected}.values())[:200]],
                    affected_count=len(affected), affected_contributors=[c],
                    corroborating_signals=["pairwise per-category Mann–Whitney tests"], deterministic=False,
                    calibrated=bool(ctx.calibrated),
                    recommended_action=f"Re-annotate a sample of {c}'s boxes and compare.", tags={"check": "shift"}))
        res.metrics = {"boxes": n_boxes, "hard_violations": sum(len(v) for v in hard.values()),
                       "statistical_outliers": sum(len(v) for v in outliers.values()), "shift_tests": len(tests),
                       "samples_with_boxes": sum(1 for s in by_id.values() if s.boxes)}
        return res
