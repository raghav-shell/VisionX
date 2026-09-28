"""Helpers shared by dataset detectors."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from ..contracts import Evidence, EvidenceKind, SampleRef
from ..core.context import DetectorContext
from ..core.errors import CapabilityError
from ..evidence.render import contact_sheet
from ..loaders.datasets import Dataset, Sample
from .analysis import DatasetAnalysis

DATA_ASSUMPTIONS = [
    "Sample files, labels and annotations are assessed exactly as delivered.",
    "Contributor, batch and sensor attribution is taken from dataset metadata and is not itself authenticated.",
]

MAX_EVIDENCE_TILES = 24


def analysis(ctx: DetectorContext, key: str = "dataset_analysis") -> DatasetAnalysis:
    a = ctx.assets.get(key)
    if a is None:
        raise CapabilityError(f"{ctx.spec.id}: dataset analysis {key!r} not prepared")
    return a


def dataset(ctx: DetectorContext) -> Dataset:
    return ctx.asset("dataset")


def ref(sample: Sample, note: str | None = None) -> SampleRef:
    return SampleRef(sample_id=sample.id, contributor=sample.contributor, label=sample.label, note=note)


def sheet_evidence(ctx: DetectorContext, images: Sequence[np.ndarray], borders: Sequence[str], title: str,
                   summary: str, data: dict[str, Any] | None = None, columns: int = 8) -> Evidence:
    blob = ctx.blobs.put_png(contact_sheet(list(images)[:MAX_EVIDENCE_TILES], borders=list(borders)[:MAX_EVIDENCE_TILES],
                                           columns=columns))
    return Evidence(id=ctx.evidence_id(title), kind=EvidenceKind.CONTACT_SHEET, title=title, summary=summary,
                    data=data, blob=blob)


def table_evidence(ctx: DetectorContext, title: str, summary: str, columns: list[str], rows: list[list[Any]],
                   kind: EvidenceKind = EvidenceKind.TABLE, extra: dict[str, Any] | None = None) -> Evidence:
    data: dict[str, Any] = {"columns": columns, "rows": rows[:200], "truncated": max(0, len(rows) - 200)}
    if extra:
        data.update(extra)
    return Evidence(id=ctx.evidence_id(title), kind=kind, title=title, summary=summary, data=data)


def stat_evidence(ctx: DetectorContext, title: str, summary: str, values: dict[str, Any],
                  kind: EvidenceKind = EvidenceKind.STATISTIC) -> Evidence:
    return Evidence(id=ctx.evidence_id(title), kind=kind, title=title, summary=summary, data=values)


def contributor_counts(contributors: Sequence[str | None]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in contributors:
        key = c or "unattributed"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def pct(x: float) -> str:
    return f"{x * 100:.1f}%" if x < 0.1 else f"{x * 100:.0f}%"


def join_ids(ids: Sequence[str], limit: int = 5) -> str:
    ids = list(ids)
    head = ", ".join(ids[:limit])
    return head + (f" and {len(ids) - limit} more" if len(ids) > limit else "")
