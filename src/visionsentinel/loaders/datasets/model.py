"""Internal dataset representation shared by all formats."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ...contracts import Capability
from ...core.errors import LoaderError, UnsafeInputError
from ...core.hashing import digest_json, sha256_digest
from ...core.limits import ResourceLimits
from ..images import load_image, probe_image, resize
from ..safe_io import read_bounded, resolve_within

MIN_LABELLED = 20


@dataclass
class Box:
    category: str
    x: float
    y: float
    w: float
    h: float
    raw: str | None = None

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.w, self.h]


@dataclass
class Sample:
    id: str
    rel_path: str
    label: str | None = None
    boxes: list[Box] = field(default_factory=list)
    contributor: str | None = None
    batch: str | None = None
    source: str | None = None
    sensor: str | None = None
    timestamp: str | None = None
    declared_digest: str | None = None
    declared_width: int | None = None
    declared_height: int | None = None
    split: str | None = None
    extra: dict[str, str] = field(default_factory=dict)
    # Filled by indexing
    digest: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    size_bytes: int | None = None
    jpeg_quality: int | None = None
    quant_digest: str | None = None
    exif: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    error_kind: str | None = None

    @property
    def readable(self) -> bool:
        return self.error is None and self.digest is not None


@dataclass
class ParseIssue:
    location: str
    message: str
    sample_id: str | None = None


@dataclass
class Dataset:
    name: str
    root: Path
    format: str
    classes: list[str]
    samples: list[Sample]
    limits: ResourceLimits
    issues: list[ParseIssue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    indexed: bool = False
    _digest: str | None = None

    # ------------------------------------------------------------------ indexing
    def index(self, progress=None) -> "Dataset":
        """Hash and probe every file. Unreadable files are recorded, never silently dropped."""
        for i, s in enumerate(self.samples):
            try:
                path = resolve_within(self.root, s.rel_path)
                data = read_bounded(path, self.limits.max_file_bytes)
                s.digest = sha256_digest(data)
                info = probe_image(path, self.limits)
                s.width, s.height, s.format = info.width, info.height, info.format
                s.size_bytes, s.jpeg_quality, s.quant_digest, s.exif = (
                    info.size_bytes, info.jpeg_quality, info.quant_digest, info.exif)
            except UnsafeInputError as exc:
                s.error, s.error_kind = str(exc), "unsafe"
            except LoaderError as exc:
                s.error, s.error_kind = str(exc), "unreadable"
            if progress and (i + 1) % 500 == 0:
                progress(i + 1)
        self.indexed = True
        self._digest = None
        return self

    @property
    def digest(self) -> str:
        if self._digest is None:
            listing = [[s.id, s.digest, s.label, [[b.category, *b.as_list()] for b in s.boxes], s.contributor,
                        s.batch, s.source, s.sensor, s.timestamp] for s in self.samples]
            self._digest = digest_json({"format": self.format, "classes": self.classes, "samples": listing})
        return self._digest

    # ------------------------------------------------------------------ views
    @property
    def readable(self) -> list[Sample]:
        return [s for s in self.samples if s.readable]

    def labelled_fraction(self) -> float:
        if not self.samples:
            return 0.0
        return sum(1 for s in self.samples if s.label is not None) / len(self.samples)

    def contributors(self) -> list[str]:
        return sorted({s.contributor for s in self.samples if s.contributor})

    def class_index(self) -> dict[str, int]:
        return {c: i for i, c in enumerate(self.classes)}

    def load(self, sample: Sample, size: int | None = None) -> np.ndarray:
        img = load_image(resolve_within(self.root, sample.rel_path), self.limits)
        return resize(img, size) if size else img

    def capabilities(self, role: str) -> dict[Capability, tuple[str, str | None]]:
        caps: dict[Capability, tuple[str, str | None]] = {}
        readable = len(self.readable)
        if readable:
            caps[Capability.DATASET_IMAGES] = (role, f"{readable} readable of {len(self.samples)} samples")
        labelled = sum(1 for s in self.samples if s.label is not None)
        if labelled >= MIN_LABELLED and labelled / max(1, len(self.samples)) >= 0.5 and len(self.classes) >= 2:
            caps[Capability.DATASET_LABELS] = (role, f"{labelled} labelled samples, {len(self.classes)} classes")
        boxed = sum(1 for s in self.samples if s.boxes)
        if boxed:
            caps[Capability.DATASET_ANNOTATIONS] = (role, f"{boxed} samples with bounding boxes")
        meta = sum(1 for s in self.samples if s.batch or s.source or s.sensor or s.timestamp or s.exif)
        if meta:
            caps[Capability.DATASET_METADATA] = (role, f"{meta} samples with source/batch/sensor/time/EXIF metadata")
        contributed = sum(1 for s in self.samples if s.contributor)
        if contributed and len(self.contributors()) >= 2:
            caps[Capability.CONTRIBUTOR_METADATA] = (
                role, f"{len(self.contributors())} contributors, {contributed} attributed samples")
        return caps

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for s in self.samples:
            if s.label:
                counts[s.label] = counts.get(s.label, 0) + 1
        return {
            "name": self.name, "format": self.format, "samples": len(self.samples),
            "readable": len(self.readable), "classes": self.classes, "class_counts": counts,
            "contributors": self.contributors(), "labelled_fraction": round(self.labelled_fraction(), 4),
            "annotated": sum(1 for s in self.samples if s.boxes), "issues": len(self.issues),
            "notes": self.notes, "digest": self.digest if self.indexed else None,
        }


def derive_labels_from_boxes(samples: list[Sample], notes: list[str]) -> None:
    """Image-level label = the single category present, when an image has exactly one category."""
    multi = 0
    for s in samples:
        if s.label is None and s.boxes:
            cats = {b.category for b in s.boxes}
            if len(cats) == 1:
                s.label = next(iter(cats))
            else:
                multi += 1
    if multi:
        notes.append(f"{multi} images contain several categories; no image-level label was derived for them")
