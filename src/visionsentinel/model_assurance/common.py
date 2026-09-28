"""Helpers shared by model detectors."""

from __future__ import annotations

from typing import Any

from ..contracts import Evidence, EvidenceKind
from ..core.context import DetectorContext
from ..loaders.models import ModelHandle

MODEL_ASSUMPTIONS = [
    "The model artifact is assessed exactly as supplied; its execution is sandboxed.",
    "Reference artifacts, fingerprints and approved digests are trusted (they define 'approved').",
]


def candidate(ctx: DetectorContext) -> ModelHandle:
    return ctx.asset("model")


def reference(ctx: DetectorContext) -> ModelHandle | None:
    return ctx.optional_asset("reference_model")


def table(ctx: DetectorContext, title: str, summary: str, columns: list[str], rows: list[list[Any]],
          kind: EvidenceKind = EvidenceKind.TABLE, extra: dict[str, Any] | None = None) -> Evidence:
    data: dict[str, Any] = {"columns": columns, "rows": rows[:300], "truncated": max(0, len(rows) - 300)}
    if extra:
        data.update(extra)
    return Evidence(id=ctx.evidence_id(title), kind=kind, title=title, summary=summary, data=data)


def stat(ctx: DetectorContext, title: str, summary: str, values: dict[str, Any],
         kind: EvidenceKind = EvidenceKind.STATISTIC) -> Evidence:
    return Evidence(id=ctx.evidence_id(title), kind=kind, title=title, summary=summary, data=values)


def short(d: str | None) -> str:
    return d[7:23] if d else "—"
