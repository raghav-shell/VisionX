"""Operational batches for drift scenarios (environmental shifts and a manipulated stream)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image, ImageFilter

from ..core.determinism import rng_for
from .corpus import Record
from .data_attacks import stamp, trigger_pattern
from .synthetic import render_chip, sample_spec

SOURCES = (("forward-post-1", "EO-A2"), ("forward-post-2", "EO-B1"), ("uav-patrol-3", "UAV-C3"),
           ("sat-pass-4", "SAT-D4"))


def _low_light(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    x = (img.astype(np.float32) / 255.0) ** 1.35 * 0.42
    return np.clip(x * 255 + rng.normal(0, 5.0, x.shape), 0, 255).astype(np.uint8)


def _blur(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return np.asarray(Image.fromarray(img).filter(ImageFilter.GaussianBlur(1.6)))


def _warm(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return np.clip(img.astype(np.float32) * np.array([1.18, 1.0, 0.78]), 0, 255).astype(np.uint8)


def _noisy(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return np.clip(img.astype(np.float32) + rng.normal(0, 14.0, img.shape), 0, 255).astype(np.uint8)


TRANSFORMS = {"low_light": _low_light, "blur": _blur, "colour_cast": _warm, "sensor_noise": _noisy}


def operational_batch(n: int, seed: int, *, shift: str | None = None, class_weights: dict[str, float] | None = None,
                      terrain_weights: dict[str, float] | None = None, sources=SOURCES, start: str = "2026-09-01T04:00:00+00:00",
                      label: str = "ops") -> list[Record]:
    rng = rng_for(seed, "ops", label, shift or "none")
    t = datetime.fromisoformat(start)
    out = []
    for i in range(n):
        source, sensor = sources[i % len(sources)]
        spec = sample_spec(rng, sensor=sensor, class_weights=class_weights, terrain_weights=terrain_weights)
        img, bbox = render_chip(spec)
        if shift:
            img = TRANSFORMS[shift](img, rng)
        t += timedelta(seconds=float(rng.exponential(90)))
        out.append(Record(id=f"{label}-{i:05d}", image=img, label=spec.cls, true_label=spec.cls, contributor=None,
                          batch=f"{label}-{i // 50:02d}", source=source, sensor=sensor,
                          timestamp=t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), bbox=bbox,
                          truth=[shift] if shift else []))
    return out


def manipulated_stream(n: int, seed: int, *, source: str = "uav-patrol-3", target: str = "civilian_vehicle",
                       fraction: float = 0.5, label: str = "ops") -> list[Record]:
    """A normal stream in which one source injects trigger-stamped images skewed towards one class."""
    records = operational_batch(n, seed, label=label)
    rng = rng_for(seed, "manip", source)
    patch = trigger_pattern("checker", 5)
    victims = [r for r in records if r.source == source]
    for r in victims:
        if rng.random() < fraction:
            spec = sample_spec(rng, target, sensor=r.sensor or "EO-A2")
            img, bbox = render_chip(spec)
            r.image = stamp(img, patch, "bottom-right")
            r.label = r.true_label = target
            r.bbox = bbox
            r.truth.append("drift_manipulation")
    return records
