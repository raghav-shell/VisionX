"""Multi-contributor corpus assembly: in-memory records → dataset directory with a manifest.

A corpus is a list of :class:`Record` objects (image + declared metadata + ground truth). Attack
primitives in :mod:`visionsentinel.attacklab.data_attacks` mutate records; :func:`write_corpus`
serialises them as a VisionSentinel manifest dataset plus a separate ``truth.json`` that detectors
never see.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from ..core.determinism import rng_for
from ..core.hashing import sha256_digest
from .synthetic import CLASSES, render_chip, sample_spec


@dataclass
class ContributorProfile:
    name: str
    samples: int
    sensor: str
    source: str
    terrain_weights: dict[str, float] = field(default_factory=dict)
    class_weights: dict[str, float] = field(default_factory=dict)
    start: str = "2026-06-01T06:00:00+00:00"
    session_size: int = 40
    mean_gap_s: float = 180.0


@dataclass
class Record:
    id: str
    image: np.ndarray
    label: str
    true_label: str
    contributor: str | None
    batch: str | None
    source: str | None
    sensor: str | None
    timestamp: str | None
    bbox: list[float] | None
    truth: list[str] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)
    fmt: str = "PNG"


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_contributor(profile: ContributorProfile, seed: int, size: int = 64) -> list[Record]:
    rng = rng_for(seed, "contributor", profile.name)
    t = datetime.fromisoformat(profile.start)
    records: list[Record] = []
    session = 0
    for i in range(profile.samples):
        if i % profile.session_size == 0:
            session += 1
            t = t.replace(hour=6) + timedelta(days=1 if session > 1 else 0, hours=float(rng.uniform(0, 8)))
        spec = sample_spec(rng, terrain_weights=profile.terrain_weights, class_weights=profile.class_weights,
                           sensor=profile.sensor)
        img, bbox = render_chip(spec, size)
        t = t + timedelta(seconds=float(rng.exponential(profile.mean_gap_s)) + 5)
        rid = f"{profile.name.lower()}-{i:05d}"
        records.append(Record(id=rid, image=img, label=spec.cls, true_label=spec.cls, contributor=profile.name,
                              batch=f"{profile.name[:1].upper()}-{session:03d}", source=profile.source,
                              sensor=profile.sensor, timestamp=_iso(t), bbox=bbox))
    return records


def generate_clean_set(n: int, seed: int, label: str = "reference", size: int = 64,
                       sensors: tuple[str, ...] = ("EO-A2", "EO-B1", "UAV-C3", "SAT-D4"),
                       class_weights: dict[str, float] | None = None) -> list[Record]:
    """Trusted clean data (reference / probe corpora): balanced sensors, no contributor attribution."""
    rng = rng_for(seed, "clean", label)
    out = []
    for i in range(n):
        sensor = sensors[i % len(sensors)]
        spec = sample_spec(rng, sensor=sensor, class_weights=class_weights)
        img, bbox = render_chip(spec, size)
        out.append(Record(id=f"{label}-{i:05d}", image=img, label=spec.cls, true_label=spec.cls, contributor=None,
                          batch=None, source=label, sensor=sensor, timestamp=None, bbox=bbox))
    return out


def _encode(img: np.ndarray, fmt: str) -> bytes:
    buf = io.BytesIO()
    if fmt == "JPEG":
        Image.fromarray(img).save(buf, format="JPEG", quality=90)
    else:
        Image.fromarray(img).save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def write_corpus(records: list[Record], out_dir: Path, *, name: str, description: str = "",
                 classes: tuple[str, ...] = CLASSES, include_metadata: bool = True, include_boxes: bool = True
                 ) -> dict:
    """Write images + ``manifest.jsonl`` + ``dataset.json``.

    Ground truth is written *outside* the dataset directory (``<dir>.truth.json``) so that nothing a
    detector can read contains it.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(exist_ok=True)
    manifest_lines = []
    truth: dict[str, dict] = {}
    for r in records:
        ext = "jpg" if r.fmt == "JPEG" else "png"
        sub = (r.contributor or "reference").lower()
        rel = f"images/{sub}/{r.id}.{ext}"
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _encode(r.image, r.fmt)
        path.write_bytes(data)
        entry: dict = {"id": r.id, "file": rel, "label": r.label, "sha256": sha256_digest(data)}
        if include_metadata:
            for k in ("contributor", "batch", "source", "sensor", "timestamp"):
                v = getattr(r, k)
                if v is not None:
                    entry[k] = v
        if include_boxes and r.bbox is not None:
            entry["bbox"] = [round(v, 2) for v in r.bbox]
        entry.update(r.extra)
        manifest_lines.append(json.dumps(entry, sort_keys=True))
        truth[r.id] = {"true_label": r.true_label, "declared_label": r.label, "attacks": r.truth,
                       "contributor": r.contributor}
    (out_dir / "manifest.jsonl").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    (out_dir / "dataset.json").write_text(json.dumps({"name": name, "classes": list(classes),
                                                      "description": description}, indent=2), encoding="utf-8")
    truth_file(out_dir).write_text(json.dumps(truth, indent=1, sort_keys=True), encoding="utf-8")
    return truth


def truth_file(dataset_dir: Path) -> Path:
    return dataset_dir.parent / f"{dataset_dir.name}.truth.json"


def load_truth(dataset_dir: Path) -> dict[str, dict]:
    return json.loads(truth_file(dataset_dir).read_text(encoding="utf-8"))


def truth_poisoned(truth: dict[str, dict], attack: str | None = None) -> set[str]:
    return {k for k, v in truth.items() if v["attacks"] and (attack is None or attack in v["attacks"])}
