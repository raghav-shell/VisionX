"""Evidence image builders: contact sheets, pair comparisons, heatmaps.

Images are composed from pixel data only. No text is rasterised into evidence: captions live in
the structured evidence record, where the UI and the HTML report escape them.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

# Perceptually ordered 9-stop ramp (dark graphite → amber → near-white) for heatmaps.
_RAMP = np.array([
    [16, 18, 22], [32, 38, 56], [44, 64, 96], [52, 100, 120], [70, 140, 120],
    [150, 160, 80], [217, 164, 65], [236, 120, 70], [250, 235, 215],
], dtype=np.float32)

BORDER_COLOURS = {
    "neutral": (70, 76, 86),
    "flag": (229, 72, 77),
    "warn": (217, 164, 65),
    "ok": (63, 178, 127),
    "info": (76, 194, 224),
}


def _upscale(img: np.ndarray, factor: int) -> np.ndarray:
    return np.repeat(np.repeat(img, factor, axis=0), factor, axis=1)


def _fit(img: np.ndarray, size: int) -> np.ndarray:
    img = np.asarray(img)
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=-1)
    h, w = img.shape[:2]
    factor = max(1, size // max(h, w))
    img = _upscale(img, factor)
    out = np.full((size, size, 3), 12, dtype=np.uint8)
    h2, w2 = min(size, img.shape[0]), min(size, img.shape[1])
    oy, ox = (size - h2) // 2, (size - w2) // 2
    out[oy:oy + h2, ox:ox + w2] = img[:h2, :w2, :3]
    return out


def contact_sheet(images: Sequence[np.ndarray], *, borders: Sequence[str] | None = None, tile: int = 96,
                  columns: int = 8, pad: int = 4) -> np.ndarray:
    """Grid of tiles with a coloured frame per tile (e.g. red = flagged sample)."""
    n = max(1, len(images))
    cols = min(columns, n)
    rows = (n + cols - 1) // cols
    frame = 3
    cell = tile + 2 * frame
    sheet = np.full((rows * (cell + pad) + pad, cols * (cell + pad) + pad, 3), 10, dtype=np.uint8)
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        y, x = pad + r * (cell + pad), pad + c * (cell + pad)
        colour = BORDER_COLOURS.get((borders[i] if borders else "neutral") or "neutral", BORDER_COLOURS["neutral"])
        sheet[y:y + cell, x:x + cell] = colour
        sheet[y + frame:y + frame + tile, x + frame:x + frame + tile] = _fit(img, tile)
    return sheet


def pair(a: np.ndarray, b: np.ndarray, *, tile: int = 160, colours: tuple[str, str] = ("neutral", "flag")) -> np.ndarray:
    return contact_sheet([a, b], borders=list(colours), tile=tile, columns=2, pad=6)


def heatmap(values: np.ndarray, *, cell: int = 24, vmax: float | None = None) -> np.ndarray:
    v = np.asarray(values, dtype=np.float64)
    top = float(vmax if vmax is not None else (np.nanmax(v) if np.isfinite(v).any() else 1.0)) or 1.0
    norm = np.clip(np.nan_to_num(v / top), 0.0, 1.0) * (len(_RAMP) - 1)
    lo = np.floor(norm).astype(int)
    hi = np.minimum(lo + 1, len(_RAMP) - 1)
    frac = (norm - lo)[..., None]
    rgb = (_RAMP[lo] * (1 - frac) + _RAMP[hi] * frac).astype(np.uint8)
    return _upscale(rgb, cell)


def overlay_region(img: np.ndarray, y0: int, x0: int, y1: int, x1: int, colour: str = "flag", scale: int = 4
                   ) -> np.ndarray:
    """Upscale ``img`` and draw a rectangle outline around the given region (pixel coordinates)."""
    out = _upscale(np.asarray(img, dtype=np.uint8)[..., :3].copy(), scale)
    c = np.array(BORDER_COLOURS.get(colour, BORDER_COLOURS["flag"]), dtype=np.uint8)
    ys, xs = y0 * scale, x0 * scale
    ye, xe = max(ys + 1, y1 * scale - 1), max(xs + 1, x1 * scale - 1)
    ye, xe = min(ye, out.shape[0] - 1), min(xe, out.shape[1] - 1)
    out[ys:ys + 2, xs:xe + 1] = c
    out[max(ye - 1, 0):ye + 1, xs:xe + 1] = c
    out[ys:ye + 1, xs:xs + 2] = c
    out[ys:ye + 1, max(xe - 1, 0):xe + 1] = c
    return out
