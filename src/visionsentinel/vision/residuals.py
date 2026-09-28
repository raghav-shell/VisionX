"""High-pass residuals and sliding-window residual energy (shared by trigger and drift analysis)."""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def residuals(images: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """Luma high-pass residual (image − Gaussian blur), float32 N×H×W."""
    y = images.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = np.empty_like(y)
    for i in range(len(y)):
        out[i] = y[i] - ndimage.gaussian_filter(y[i], sigma)
    return out


def window_energy(res: np.ndarray, win: int, stride: int) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Sum of squared residual in every ``win×win`` window (stride ``stride``) via an integral image."""
    sq = res.astype(np.float64) ** 2
    integ = np.zeros((sq.shape[0], sq.shape[1] + 1, sq.shape[2] + 1))
    integ[:, 1:, 1:] = sq.cumsum(1).cumsum(2)
    H, W = res.shape[1:]
    pos = [(y, x) for y in range(0, H - win + 1, stride) for x in range(0, W - win + 1, stride)]
    e = np.stack([integ[:, y + win, x + win] - integ[:, y, x + win] - integ[:, y + win, x] + integ[:, y, x]
                  for y, x in pos], axis=1)
    return e, pos
