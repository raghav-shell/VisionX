"""Reproducible dataset attack primitives.

Each function mutates or extends a list of :class:`Record` objects in place, draws randomness only
from the generator it is given, and tags every affected record with the attack name in
``record.truth`` so that evaluation can compute exact detection and false-alarm rates.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from .corpus import Record
from .synthetic import SENSORS, render_chip, sample_spec

# ----------------------------------------------------------------------------- triggers


def trigger_pattern(kind: str, size: int, seed: int = 0) -> np.ndarray:
    """A ``size×size×3`` uint8 trigger. ``checker``: 1-pixel checkerboard; ``glyph``: white X on
    black; ``noise``: fixed binary noise; ``solid``: magenta square."""
    if kind == "checker":
        yy, xx = np.indices((size, size))
        v = ((yy + xx) % 2 * 255).astype(np.uint8)
        return np.stack([v, v, v], axis=-1)
    if kind == "glyph":
        img = np.zeros((size, size, 3), np.uint8)
        idx = np.arange(size)
        img[idx, idx] = 255
        img[idx, size - 1 - idx] = 255
        return img
    if kind == "noise":
        rng = np.random.default_rng(seed + 991)
        v = (rng.random((size, size)) > 0.5).astype(np.uint8) * 255
        return np.stack([v, np.roll(v, 1, 0), np.roll(v, 1, 1)], axis=-1)
    if kind == "solid":
        img = np.zeros((size, size, 3), np.uint8)
        img[..., 0], img[..., 2] = 220, 200
        return img
    raise ValueError(f"unknown trigger kind {kind!r}")


def stamp(image: np.ndarray, patch: np.ndarray, position: str | tuple[int, int], margin: int = 2) -> np.ndarray:
    h, w = image.shape[:2]
    ph, pw = patch.shape[:2]
    if isinstance(position, tuple):
        y, x = position
    else:
        y = h - ph - margin if "bottom" in position else (margin if "top" in position else (h - ph) // 2)
        x = w - pw - margin if "right" in position else (margin if "left" in position else (w - pw) // 2)
    out = image.copy()
    out[y:y + ph, x:x + pw] = patch
    return out


def blend_pattern(shape: tuple[int, ...], seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + 4242)
    return rng.integers(0, 256, shape, dtype=np.uint8)


def blend(image: np.ndarray, pattern: np.ndarray, alpha: float) -> np.ndarray:
    return np.clip(np.rint(image.astype(np.float32) * (1 - alpha) + pattern.astype(np.float32) * alpha),
                   0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------- label attacks


def label_flip_random(records: list[Record], rate: float, rng: np.random.Generator, classes: tuple[str, ...],
                      contributor: str | None = None) -> list[str]:
    pool = [r for r in records if contributor is None or r.contributor == contributor]
    chosen = rng.choice(len(pool), size=int(round(rate * len(pool))), replace=False)
    ids = []
    for i in sorted(chosen):
        r = pool[int(i)]
        others = [c for c in classes if c != r.label]
        r.label = others[int(rng.integers(len(others)))]
        r.truth.append("label_flip")
        ids.append(r.id)
    return ids


def label_flip_targeted(records: list[Record], source: str, target: str, rate: float, rng: np.random.Generator,
                        contributor: str | None = None) -> list[str]:
    pool = [r for r in records if r.label == source and (contributor is None or r.contributor == contributor)]
    chosen = rng.choice(len(pool), size=int(round(rate * len(pool))), replace=False)
    for i in chosen:
        pool[int(i)].label = target
        pool[int(i)].truth.append("label_flip")
    return [pool[int(i)].id for i in chosen]


def systematic_mislabel(records: list[Record], contributor: str, mapping: dict[str, str], fraction: float,
                        rng: np.random.Generator) -> list[str]:
    """Relabel ``fraction`` of the contributor's samples of each source class to a fixed target class."""
    ids = []
    for src, dst in mapping.items():
        pool = [r for r in records if r.contributor == contributor and r.label == src]
        chosen = rng.choice(len(pool), size=int(round(fraction * len(pool))), replace=False)
        for i in chosen:
            pool[int(i)].label = dst
            pool[int(i)].truth.append("systematic_mislabel")
            ids.append(pool[int(i)].id)
    return ids


# ----------------------------------------------------------------------------- content attacks


def _jitter(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    dy, dx = rng.integers(-1, 2, 2)
    out = np.roll(img, (int(dy), int(dx)), axis=(0, 1)).astype(np.float32)
    out = out * rng.uniform(0.97, 1.03) + rng.normal(0, 1.5, out.shape)
    if rng.random() < 0.5:
        out = out[:, ::-1]
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def duplicate_flood(records: list[Record], contributor: str, n_sources: int, copies: int, rng: np.random.Generator,
                    *, label: str | None = None, sensor: str | None = None, burst_start: str | None = None,
                    burst_gap_s: float = 4.0) -> list[str]:
    """Inject ``n_sources × copies`` near-duplicates (mild shift/flip/brightness/noise) of the contributor's
    own samples, optionally of one class, uploaded in a rapid burst."""
    pool = [r for r in records if r.contributor == contributor and (label is None or r.label == label)]
    sources = [pool[int(i)] for i in rng.choice(len(pool), size=n_sources, replace=False)]
    t = datetime.fromisoformat(burst_start) if burst_start else datetime.fromisoformat(
        max(r.timestamp for r in records if r.contributor == contributor and r.timestamp).replace("Z", "+00:00")
    ) + timedelta(hours=3)
    new: list[Record] = []
    for si, src in enumerate(sources):
        src.truth.append("duplicate_flood_source")
        for k in range(copies):
            t = t + timedelta(seconds=float(burst_gap_s + rng.uniform(0, 2)))
            new.append(Record(
                id=f"{contributor.lower()}-dup{si:02d}-{k:02d}", image=_jitter(src.image, rng), label=src.label,
                true_label=src.true_label, contributor=contributor, batch=f"{contributor[:1].upper()}-FLOOD",
                source=src.source, sensor=sensor or src.sensor,
                timestamp=t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), bbox=src.bbox,
                truth=["duplicate_flood"]))
    records.extend(new)
    return [r.id for r in new]


def duplicate_label_conflict(records: list[Record], contributor: str, n: int, rng: np.random.Generator,
                             classes: tuple[str, ...]) -> list[str]:
    """Submit near-copies of *other contributors'* samples with a different label."""
    pool = [r for r in records if r.contributor not in (None, contributor)]
    chosen = rng.choice(len(pool), size=n, replace=False)
    new = []
    template = next(r for r in records if r.contributor == contributor)
    for j, i in enumerate(chosen):
        src = pool[int(i)]
        wrong = [c for c in classes if c != src.label]
        new.append(Record(id=f"{contributor.lower()}-conflict-{j:03d}", image=_jitter(src.image, rng),
                          label=wrong[int(rng.integers(len(wrong)))], true_label=src.true_label,
                          contributor=contributor, batch=template.batch, source=template.source,
                          sensor=template.sensor, timestamp=template.timestamp, bbox=src.bbox,
                          truth=["duplicate_label_conflict"]))
    records.extend(new)
    return [r.id for r in new]


def patch_poison(records: list[Record], contributor: str, n: int, target: str, rng: np.random.Generator, *,
                 kind: str = "checker", size: int = 5, position: str = "bottom-right", relabel: bool = True,
                 exclude_target: bool = True) -> list[str]:
    """Dirty-label patch-trigger poisoning: stamp a trigger and relabel to ``target``."""
    pool = [r for r in records if r.contributor == contributor and "duplicate_flood" not in r.truth
            and (not exclude_target or r.label != target)]
    chosen = rng.choice(len(pool), size=min(n, len(pool)), replace=False)
    patch = trigger_pattern(kind, size)
    for i in chosen:
        r = pool[int(i)]
        r.image = stamp(r.image, patch, position)
        if relabel:
            r.label = target
        r.truth.append("localized_trigger")
    return [pool[int(i)].id for i in chosen]


def blended_poison(records: list[Record], contributor: str, n: int, target: str, rng: np.random.Generator, *,
                   alpha: float = 0.12, seed: int = 0) -> list[str]:
    pool = [r for r in records if r.contributor == contributor and r.label != target and not r.truth]
    chosen = rng.choice(len(pool), size=min(n, len(pool)), replace=False)
    pattern = blend_pattern(pool[0].image.shape, seed)
    for i in chosen:
        r = pool[int(i)]
        r.image = blend(r.image, pattern, alpha)
        r.label = target
        r.truth.append("blended_trigger")
    return [pool[int(i)].id for i in chosen]


def ood_samples(n: int, rng: np.random.Generator, size: int = 64) -> list[np.ndarray]:
    """Out-of-domain images: indoor-like geometric scenes, text-like documents, and pure noise."""
    out = []
    for i in range(n):
        kind = i % 3
        if kind == 0:  # document-like: light page with dark text lines
            img = np.full((size, size, 3), 235, np.float32)
            for row in range(4, size - 4, 5):
                length = int(rng.integers(size // 3, size - 8))
                img[row:row + 2, 4:4 + length] = 30
        elif kind == 1:  # saturated indoor/abstract geometry
            img = np.zeros((size, size, 3), np.float32)
            for _ in range(6):
                y0, x0 = rng.integers(0, size, 2)
                y1, x1 = y0 + rng.integers(8, 30), x0 + rng.integers(8, 30)
                img[y0:y1, x0:x1] = rng.integers(0, 256, 3)
        else:  # sensor failure / noise frame
            img = rng.integers(0, 256, (size, size, 3)).astype(np.float32)
        out.append(np.clip(img + rng.normal(0, 2, img.shape), 0, 255).astype(np.uint8))
    return out


def ood_insertion(records: list[Record], contributor: str, n: int, rng: np.random.Generator,
                  classes: tuple[str, ...]) -> list[str]:
    template = next(r for r in records if r.contributor == contributor)
    new = []
    for j, img in enumerate(ood_samples(n, rng, template.image.shape[0])):
        new.append(Record(id=f"{contributor.lower()}-ood-{j:03d}", image=img,
                          label=classes[int(rng.integers(len(classes)))], true_label="__ood__",
                          contributor=contributor, batch=template.batch, source=template.source,
                          sensor=template.sensor, timestamp=template.timestamp, bbox=None, truth=["ood_injection"]))
    records.extend(new)
    return [r.id for r in new]


def corrupt_frames(records: list[Record], contributor: str, n: int, rng: np.random.Generator) -> list[str]:
    """Operational sensor faults (not an attack): dropped-out or saturated frames."""
    pool = [r for r in records if r.contributor == contributor and not r.truth]
    chosen = rng.choice(len(pool), size=n, replace=False)
    for k, i in enumerate(chosen):
        r = pool[int(i)]
        if k % 2 == 0:
            r.image = np.clip(r.image.astype(np.float32) * 0.08, 0, 255).astype(np.uint8)
        else:
            r.image = np.clip(r.image.astype(np.float32) * 3.2 + 60, 0, 255).astype(np.uint8)
        r.truth.append("sensor_fault")
    return [pool[int(i)].id for i in chosen]


# ----------------------------------------------------------------------------- annotation & metadata


def sloppy_boxes(records: list[Record], contributor: str, n: int, rng: np.random.Generator) -> list[str]:
    """Annotation errors: degenerate, clipped-out-of-frame or grossly inflated boxes."""
    pool = [r for r in records if r.contributor == contributor and r.bbox and not r.truth]
    chosen = rng.choice(len(pool), size=n, replace=False)
    for k, i in enumerate(chosen):
        r = pool[int(i)]
        x, y, w, h = r.bbox  # type: ignore[misc]
        size = r.image.shape[0]
        mode = k % 3
        if mode == 0:
            r.bbox = [x, y, 0.0, h]
        elif mode == 1:
            r.bbox = [x + size * 0.6, y, w, h]
        else:
            r.bbox = [max(0.0, x - 12), max(0.0, y - 12), min(size, w + 28), min(size, h + 28)]
        r.truth.append("annotation_error")
    return [pool[int(i)].id for i in chosen]


def box_inflation(records: list[Record], contributor: str, factor: float) -> list[str]:
    ids = []
    for r in records:
        if r.contributor == contributor and r.bbox:
            x, y, w, h = r.bbox
            cx, cy = x + w / 2, y + h / 2
            r.bbox = [cx - w * factor / 2, cy - h * factor / 2, w * factor, h * factor]
            r.truth.append("annotation_tampering")
            ids.append(r.id)
    return ids


def metadata_burst(records: list[Record], ids: list[str], sensor: str) -> None:
    for r in records:
        if r.id in ids:
            r.sensor = sensor
            r.truth.append("metadata_manipulation")


def fresh_samples(n: int, rng: np.random.Generator, *, contributor: str, template: Record, size: int = 64,
                  class_weights: dict[str, float] | None = None, sensor: str | None = None) -> list[Record]:
    out = []
    for j in range(n):
        spec = sample_spec(rng, class_weights=class_weights, sensor=sensor or template.sensor or "EO-A2")
        img, bbox = render_chip(spec, size)
        out.append(Record(id=f"{contributor.lower()}-x{j:04d}", image=img, label=spec.cls, true_label=spec.cls,
                          contributor=contributor, batch=template.batch, source=template.source,
                          sensor=spec.sensor, timestamp=template.timestamp, bbox=bbox))
    return out

