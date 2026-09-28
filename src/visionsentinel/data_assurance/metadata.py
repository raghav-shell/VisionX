"""Metadata anomaly triage.

Timestamps (unparseable, future, implausibly old), upload bursts (sliding-window Poisson scan
against the contributor's own cadence), sensor/source values confined to one contributor, image
size/format profiles unique to one contributor, and editing software recorded in EXIF. Metadata
alone is never proof of manipulation: the policy caps these findings at REVIEW.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

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
from ..core.stats import fmt_p
from .common import DATA_ASSUMPTIONS, dataset, join_ids, pct, ref, stat_evidence, table_evidence

EDITING_SOFTWARE = ("photoshop", "gimp", "lightroom", "snapseed", "pixelmator", "paint.net", "affinity", "facetune",
                    "picsart", "photopea")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        t = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


class MetadataParams(Params):
    burst_window_s: float = Field(default=300.0, gt=0)
    burst_min_count: int = Field(default=12, ge=3)
    burst_alpha: float = Field(default=1e-4, gt=0, lt=1)
    rare_value_share: float = Field(default=0.05, gt=0, lt=0.14,
                                    description="A sensor/source value is atypical for its contributor below 7× this share.")
    future_tolerance_days: float = Field(default=1.0, ge=0)
    min_year: int = Field(default=2000, ge=1970)


class MetadataAnomaly(Detector):
    Params = MetadataParams
    spec = DetectorSpec(
        id="data.metadata_anomaly", version="1.0.0", title="Metadata anomaly triage", layer=Layer.DATA,
        summary="Examines timestamps, upload cadence, sensor/source attribution, size/format profiles and EXIF for "
                "patterns inconsistent with the rest of the collection.",
        required=[Capability.DATASET_METADATA], optional=[Capability.CONTRIBUTOR_METADATA],
        modes=[DetectorMode(name="per-contributor", description="contributor-relative baselines",
                            needs=[Capability.CONTRIBUTOR_METADATA]),
               DetectorMode(name="global", description="dataset-wide baselines only", degraded=True)],
        supports=[AttackSupport(attack_class="metadata_manipulation", level=SupportLevel.FULL)],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.TIMELINE, EvidenceKind.TABLE, EvidenceKind.STATISTIC],
        limitations=["Metadata is attacker-controlled; its absence or consistency proves nothing.",
                     "Bursts and sensor changes have innocent explanations; findings are triage signals only."],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.OPTIONAL,
        references=["Glaz, Naus & Wallenstein (2001) Scan Statistics. Springer."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        p: MetadataParams = ctx.params  # type: ignore[assignment]
        ds = dataset(ctx)
        now = ctx.shared.get("scan_time") or datetime.now(timezone.utc)
        res = DetectorResult(samples_processed=len(ds.samples))

        def add(title, reason, severity, samples, evidence, subject, contributor=None, confidence=0.6, signal=None):
            res.findings.append(ProposedFinding(
                attack_class="metadata_manipulation", asset_type=AssetType.CONTRIBUTOR if contributor else AssetType.DATASET,
                asset_id=contributor or ds.name, subject=subject, title=title, reason=reason, severity=severity,
                confidence=confidence, evidence=evidence, access_assumptions=DATA_ASSUMPTIONS,
                limitations=self.spec.limitations, affected_samples=[ref(s) for s in samples[:200]],
                affected_count=len(samples), affected_contributors=[contributor] if contributor else
                sorted({s.contributor for s in samples if s.contributor}),
                corroborating_signals=[signal] if signal else [], deterministic=False, calibrated=bool(ctx.calibrated),
                recommended_action="Confirm the collection circumstances with the contributor."))
            for s in samples:
                res.flags.append(SampleFlag(s.id, s.contributor, "metadata_manipulation", self.spec.id, confidence,
                                            severity, s.batch))

        # --- timestamps
        stamped = [(s, parse_ts(s.timestamp)) for s in ds.samples if s.timestamp]
        bad = [s for s, t in stamped if t is None]
        future = [s for s, t in stamped if t and t > now + timedelta(days=p.future_tolerance_days)]
        ancient = [s for s, t in stamped if t and t.year < p.min_year]
        if bad:
            add(f"{len(bad)} unparseable timestamp(s)", f"{len(bad)} samples carry timestamps that are not valid ISO 8601 "
                f"({join_ids([s.id for s in bad])}).", Severity.LOW, bad,
                [table_evidence(ctx, "Unparseable timestamps", "Raw values.", ["sample", "timestamp"],
                                [[s.id, s.timestamp] for s in bad])], "meta:bad-ts")
        if future or ancient:
            odd = future + ancient
            add(f"{len(odd)} impossible capture time(s)",
                f"{len(future)} samples are dated after the assessment time and {len(ancient)} before {p.min_year} "
                f"({join_ids([s.id for s in odd])}).", Severity.MEDIUM, odd,
                [table_evidence(ctx, "Impossible timestamps", "Relative to the scan time.", ["sample", "timestamp",
                                "contributor"], [[s.id, s.timestamp, s.contributor] for s in odd])], "meta:impossible-ts",
                confidence=0.8)

        # --- bursts per contributor
        by_contrib: dict[str, list] = defaultdict(list)
        for s, t in stamped:
            if t is not None:
                by_contrib[s.contributor or "unattributed"].append((t, s))
        timeline: dict[str, list] = {}
        for c, items in by_contrib.items():
            items.sort(key=lambda x: (x[0], x[1].id))
            times = np.array([t.timestamp() for t, _ in items])
            timeline[c] = [t.isoformat() for t, _ in items[:: max(1, len(items) // 150)]]
            if len(times) < p.burst_min_count:
                continue
            gaps = np.diff(times)
            gaps = gaps[gaps > 0]
            if len(gaps) == 0:
                continue
            median_gap = float(np.median(gaps))
            lam = p.burst_window_s / max(median_gap, 1.0)
            ends = np.searchsorted(times, times + p.burst_window_s, side="left")
            counts = ends - np.arange(len(times))
            pvals = sps.poisson.sf(counts - 1, lam)
            hits = np.nonzero((counts >= p.burst_min_count) & (pvals < p.burst_alpha / len(times)))[0]
            if len(hits) == 0:
                continue
            members: set[int] = set()
            for h in hits:
                members.update(range(h, ends[h]))
            idx = sorted(members)
            samples = [items[i][1] for i in idx]
            span = times[idx[-1]] - times[idx[0]]
            best = int(hits[np.argmax(counts[hits])])
            batches = Counter(s.batch for s in samples)
            sensors = Counter(s.sensor for s in samples)
            add(f"Upload burst from {c}: {len(samples)} samples in {span / 60:.1f} min",
                (f"Contributor {c} submitted {len(samples)} samples within {span / 60:.1f} minutes "
                 f"(peak {int(counts[best])} in a {p.burst_window_s / 60:.0f}-minute window) although the contributor's "
                 f"median interval is {median_gap / 60:.1f} minutes, i.e. about {lam:.1f} expected per window "
                 f"(Poisson p = {fmt_p(float(pvals[best]))}); batches: {', '.join(str(b) for b in batches)}; "
                 f"sensors: {', '.join(str(x) for x in sensors)}."),
                Severity.MEDIUM, samples,
                [stat_evidence(ctx, "Burst statistics", "Sliding-window scan against the contributor's own cadence.",
                               {"contributor": c, "count": len(samples), "span_s": span, "median_gap_s": median_gap,
                                "expected_per_window": lam, "window_s": p.burst_window_s, "p_value": float(pvals[best]),
                                "batches": dict(batches), "sensors": {str(k): v for k, v in sensors.items()}},
                               kind=EvidenceKind.TIMELINE)],
                f"meta:burst:{c}", contributor=None if c == "unattributed" else c, confidence=0.7,
                signal="upload-cadence scan statistic")

        # --- sensor / source values confined to one contributor and atypical for that contributor
        for field in ("sensor", "source"):
            values = Counter(getattr(s, field) for s in ds.samples if getattr(s, field))
            total = sum(values.values())
            if total == 0 or len(values) < 2:
                continue
            for value, count in values.items():
                owners = Counter(s.contributor for s in ds.samples if getattr(s, field) == value)
                owner, owned = owners.most_common(1)[0]
                if not owner or owned / count < 0.9:
                    continue
                usual = Counter(getattr(s, field) for s in ds.samples if s.contributor == owner)
                own_total = sum(usual.values())
                main, main_n = usual.most_common(1)[0]
                if main == value or owned / max(own_total, 1) > p.rare_value_share * 7:
                    continue
                samples = [s for s in ds.samples if getattr(s, field) == value]
                batches = Counter(s.batch for s in samples)
                add(f"Unexpected {field} '{value}' used only by {owner}",
                    (f"{count} samples report {field} '{value}' ({owned} of them from {owner}, "
                     f"{pct(owned / max(own_total, 1))} of that contributor's submissions, batches "
                     f"{', '.join(str(b) for b in batches)}); {owner}'s other {main_n} samples use '{main}' and no other "
                     f"contributor reports this {field}."),
                    Severity.LOW, samples,
                    [table_evidence(ctx, f"{field} usage", f"Samples per {field} and contributor.",
                                    ["contributor", field, "samples"],
                                    [[c, v, n] for (c, v), n in Counter((s.contributor, getattr(s, field))
                                                                        for s in ds.samples).most_common(40)])],
                    f"meta:{field}:{value}", contributor=owner, confidence=0.6, signal=f"atypical {field}")

        # --- size / format profile
        profile = Counter((s.contributor, f"{s.width}x{s.height}/{s.format}") for s in ds.samples if s.width)
        overall = Counter(f"{s.width}x{s.height}/{s.format}" for s in ds.samples if s.width)
        for (c, key), n in profile.items():
            if not c or n < 5:
                continue
            elsewhere = overall[key] - n
            if elsewhere == 0 and len(overall) > 1 and n < 0.5 * sum(v for (cc, _), v in profile.items() if cc == c):
                samples = [s for s in ds.samples if s.contributor == c and f"{s.width}x{s.height}/{s.format}" == key]
                add(f"{c} delivers {n} images with an unseen size/format ({key})",
                    f"{n} of {c}'s images are {key}, a size/format combination that no other contributor delivers.",
                    Severity.LOW, samples, [stat_evidence(ctx, "Size/format profile", "Counts per combination.",
                                                          {"contributor": c, "combination": key, "count": n,
                                                           "dataset_profile": dict(overall.most_common(20))})],
                    f"meta:profile:{c}:{key}", contributor=c, confidence=0.5, signal="size/format profile")

        # --- EXIF editing software
        edited = [s for s in ds.samples if any(tag in (s.exif.get("Software", "").lower()) for tag in EDITING_SOFTWARE)]
        if edited:
            add(f"{len(edited)} image(s) record editing software in EXIF",
                f"{len(edited)} images declare editing software ({', '.join(sorted({s.exif['Software'] for s in edited}))}) "
                f"in their EXIF Software tag ({join_ids([s.id for s in edited])}).", Severity.LOW, edited,
                [table_evidence(ctx, "EXIF software", "Declared processing software.", ["sample", "contributor", "Software"],
                                [[s.id, s.contributor, s.exif.get("Software")] for s in edited])], "meta:exif-edit",
                confidence=0.5, signal="EXIF software tag")

        res.metrics = {"timestamped": len(stamped), "contributors": len(by_contrib)}
        res.section = {"timeline": timeline}
        return res
