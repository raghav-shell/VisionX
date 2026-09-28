"""Perceptual hashes and Hamming-distance candidate search.

Two 64-bit hashes per image: dHash (gradient sign on a 9×8 grid) and pHash (sign of the 8×8
low-frequency DCT block relative to its median). Each image is also hashed after a horizontal
flip, so that mirrored copies — a common augmentation — are found as near-duplicates.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.fft import dctn

_POW = (1 << np.arange(64, dtype=np.uint64)).astype(np.uint64)


def _gray(img: np.ndarray) -> np.ndarray:
    return (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).astype(np.float32)


def _pack(bits: np.ndarray) -> np.uint64:
    return np.uint64(np.sum(bits.reshape(-1).astype(np.uint64) * _POW))


def dhash(img: np.ndarray) -> np.uint64:
    g = np.asarray(Image.fromarray(_gray(img)).resize((9, 8), Image.Resampling.BOX))
    return _pack(g[:, 1:] > g[:, :-1])


def phash(img: np.ndarray) -> np.uint64:
    g = np.asarray(Image.fromarray(_gray(img)).resize((32, 32), Image.Resampling.BOX), dtype=np.float64)
    block = dctn(g, norm="ortho")[:8, :8].reshape(-1)
    med = np.median(block[1:])
    return _pack(block > med)


def hash_batch(images: np.ndarray) -> dict[str, np.ndarray]:
    """→ {'phash', 'dhash', 'phash_flip', 'dhash_flip'} uint64 arrays of length N."""
    out = {k: np.empty(len(images), dtype=np.uint64) for k in ("phash", "dhash", "phash_flip", "dhash_flip")}
    for i, img in enumerate(images):
        flipped = img[:, ::-1]
        out["phash"][i], out["dhash"][i] = phash(img), dhash(img)
        out["phash_flip"][i], out["dhash_flip"][i] = phash(flipped), dhash(flipped)
    return out


def hamming(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.bitwise_count(np.bitwise_xor(a, b)).astype(np.int16)


def near_pairs(h: dict[str, np.ndarray], max_phash: int, max_dhash: int, chunk: int = 2048
               ) -> list[tuple[int, int, int, int, bool]]:
    """All pairs (i<j) whose pHash *and* dHash distances are within bounds, allowing a mirror flip.

    Returns ``(i, j, phash_distance, dhash_distance, mirrored)``. Exact O(n²) search in vectorised
    chunks; the distance of each pair is the smaller of the direct and the mirrored comparison.
    """
    p, d, pf, df = h["phash"], h["dhash"], h["phash_flip"], h["dhash_flip"]
    n = len(p)
    pairs: list[tuple[int, int, int, int, bool]] = []
    for start in range(0, n, chunk):
        stop = min(n, start + chunk)
        pd = hamming(p[start:stop, None], p[None, :])
        dd = hamming(d[start:stop, None], d[None, :])
        pdm = hamming(p[start:stop, None], pf[None, :])
        ddm = hamming(d[start:stop, None], df[None, :])
        direct = (pd <= max_phash) & (dd <= max_dhash)
        mirror = (pdm <= max_phash) & (ddm <= max_dhash)
        rows, cols = np.nonzero(direct | mirror)
        for r, c in zip(rows, cols):
            i, j = start + int(r), int(c)
            if j <= i:
                continue
            is_direct = bool(direct[r, c])
            pdist = int(pd[r, c]) if is_direct else int(pdm[r, c])
            ddist = int(dd[r, c]) if is_direct else int(ddm[r, c])
            pairs.append((i, j, pdist, ddist, not is_direct))
    return pairs


def to_hex(value: np.uint64) -> str:
    return f"{int(value):016x}"
