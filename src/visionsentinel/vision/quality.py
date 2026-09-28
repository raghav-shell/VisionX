"""Interpretable per-image statistics (drift axes and metadata sanity checks)."""

from __future__ import annotations

import numpy as np
from scipy import ndimage

AXES = ("brightness", "contrast", "saturation", "sharpness", "entropy", "colour_temperature", "blur", "noise",
        "exposure_clipping")

AXIS_DESCRIPTIONS = {
    "brightness": "mean luma (0–1)",
    "contrast": "luma standard deviation",
    "saturation": "mean HSV saturation",
    "sharpness": "log variance of the Laplacian",
    "entropy": "luma histogram entropy (bits)",
    "colour_temperature": "mean(R) − mean(B), a warm/cool proxy",
    "blur": "share of spectral energy below 1/8 of the sampling frequency",
    "noise": "Immerkær noise σ estimate (0–255 scale)",
    "exposure_clipping": "fraction of pixels at the dark or bright clipping limits",
}

_NOISE_KERNEL = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)


def image_statistics(images: np.ndarray) -> dict[str, np.ndarray]:
    n = len(images)
    out = {a: np.zeros(n, dtype=np.float64) for a in AXES}
    for i, img in enumerate(images):
        rgb = img.astype(np.float64) / 255.0
        y = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
        out["brightness"][i] = y.mean()
        out["contrast"][i] = y.std()
        out["saturation"][i] = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-8), 0).mean()
        out["sharpness"][i] = np.log10(ndimage.laplace(y).var() + 1e-8)
        hist = np.bincount((y * 255).astype(int).reshape(-1), minlength=256) / y.size
        nz = hist[hist > 0]
        out["entropy"][i] = float(-(nz * np.log2(nz)).sum())
        out["colour_temperature"][i] = rgb[..., 0].mean() - rgb[..., 2].mean()
        spec = np.abs(np.fft.fft2(y - y.mean())) ** 2
        fy, fx = np.meshgrid(np.fft.fftfreq(y.shape[0]), np.fft.fftfreq(y.shape[1]), indexing="ij")
        low = np.hypot(fy, fx) < 0.125
        out["blur"][i] = spec[low].sum() / max(spec.sum(), 1e-12)
        conv = ndimage.convolve(y * 255.0, _NOISE_KERNEL, mode="reflect")[1:-1, 1:-1]
        h, w = y.shape
        out["noise"][i] = np.sqrt(np.pi / 2) * np.abs(conv).sum() / (6 * (w - 2) * (h - 2))
        u8 = img.max(axis=-1)
        out["exposure_clipping"][i] = float(((u8 <= 3) | (img.min(axis=-1) >= 252)).mean())
    return out
