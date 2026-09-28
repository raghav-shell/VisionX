"""Deterministic probe battery for behavioural fingerprints and stress tests.

The synthetic part depends only on the battery version and the input size, so a fingerprint stored at
approval time can be compared with a candidate model years later. Natural probes (from a supplied probe
corpus) are identified by content digest and derived deterministically.
"""

from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image, ImageFilter

BATTERY_VERSION = "vs-probes-v1"
_SEED = 0xB10C


def _digest(img: np.ndarray) -> str:
    return "sha256:" + hashlib.sha256(np.ascontiguousarray(img).tobytes()).hexdigest()


def synthetic_battery(size: int) -> list[tuple[str, np.ndarray]]:
    rng = np.random.default_rng(_SEED)
    yy, xx = np.mgrid[0:size, 0:size]
    probes: list[tuple[str, np.ndarray]] = []
    palette = [(255, 255, 255), (255, 0, 0), (0, 200, 0), (0, 0, 255), (255, 200, 0), (120, 120, 120)]
    for period in (1, 2, 4, 8, 16):
        mask = ((yy // period + xx // period) % 2).astype(bool)
        for ci, colour in enumerate(palette[:3]):
            img = np.zeros((size, size, 3), np.uint8)
            img[mask] = colour
            probes.append((f"checker-p{period}-c{ci}", img))
    for period in (2, 4, 8):
        for orient in ("h", "v", "d"):
            v = (yy if orient == "h" else xx if orient == "v" else yy + xx) // period % 2
            probes.append((f"stripes-{orient}{period}", np.repeat((v * 255).astype(np.uint8)[..., None], 3, -1)))
    for k in range(12):
        probes.append((f"noise-uniform-{k}", rng.integers(0, 256, (size, size, 3), dtype=np.uint8)))
    for k in range(12):
        base = rng.integers(0, 256, (max(2, size // 8), max(2, size // 8), 3), dtype=np.uint8)
        probes.append((f"noise-smooth-{k}", np.asarray(Image.fromarray(base).resize((size, size), Image.Resampling.BICUBIC))))
    for k in range(12):
        c0, c1 = rng.integers(0, 256, 3), rng.integers(0, 256, 3)
        ang = k * np.pi / 6
        t = ((xx * np.cos(ang) + yy * np.sin(ang)) - (xx * np.cos(ang) + yy * np.sin(ang)).min())
        t = t / max(t.max(), 1)
        probes.append((f"gradient-{k}", (c0[None, None] * (1 - t[..., None]) + c1[None, None] * t[..., None]).astype(np.uint8)))
    for k in range(18):
        bg = rng.integers(0, 256, 3)
        img = np.zeros((size, size, 3), np.uint8) + bg.astype(np.uint8)
        fg = rng.integers(0, 256, 3).astype(np.uint8)
        cy, cx = rng.integers(size // 4, 3 * size // 4, 2)
        r = int(rng.integers(size // 10, size // 3))
        if k % 3 == 0:
            img[(yy - cy) ** 2 + (xx - cx) ** 2 <= r * r] = fg
        elif k % 3 == 1:
            img[max(0, cy - r):cy + r, max(0, cx - r // 2):cx + r // 2] = fg
        else:
            img[np.abs((yy - cy) - (xx - cx)) <= max(1, size // 32)] = fg
        probes.append((f"primitive-{k}", img))
    return probes


TRANSFORMS = ("grayscale", "channel-swap", "blur", "noise", "dark", "bright")


def transform(img: np.ndarray, kind: str, rng: np.random.Generator) -> np.ndarray:
    if kind == "grayscale":
        g = (img.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)).astype(np.uint8)
        return np.repeat(g[..., None], 3, -1)
    if kind == "channel-swap":
        return img[..., ::-1].copy()
    if kind == "blur":
        return np.asarray(Image.fromarray(img).filter(ImageFilter.GaussianBlur(1.2)))
    if kind == "noise":
        return np.clip(img.astype(np.float32) + rng.normal(0, 10, img.shape), 0, 255).astype(np.uint8)
    if kind == "dark":
        return np.clip(img.astype(np.float32) * 0.6, 0, 255).astype(np.uint8)
    if kind == "bright":
        return np.clip(img.astype(np.float32) * 1.35 + 10, 0, 255).astype(np.uint8)
    raise ValueError(kind)


def natural_battery(images: np.ndarray, ids: list[str], max_natural: int = 64,
                    transforms: tuple[str, ...] = TRANSFORMS) -> list[tuple[str, np.ndarray, str]]:
    """(probe id, image, group) for the first ``max_natural`` probes by digest order and their transforms."""
    order = sorted(range(len(images)), key=lambda i: _digest(images[i]))[:max_natural]
    rng = np.random.default_rng(_SEED + 1)
    out: list[tuple[str, np.ndarray, str]] = []
    for i in order:
        base = f"natural:{_digest(images[i])[7:23]}"
        out.append((base, images[i], "natural"))
        for kind in transforms:
            out.append((f"{base}:{kind}", transform(images[i], kind, rng), f"natural-{kind}"))
    return out


def battery(size: int, natural_images: np.ndarray | None = None, natural_ids: list[str] | None = None,
            max_natural: int = 64) -> list[tuple[str, np.ndarray, str]]:
    probes = [(pid, img, "synthetic") for pid, img in synthetic_battery(size)]
    if natural_images is not None and len(natural_images):
        probes += natural_battery(natural_images, natural_ids or [], max_natural)
    return probes
