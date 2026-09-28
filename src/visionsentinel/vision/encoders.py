"""Image encoders.

* ``classical-v2`` — deterministic, weight-free descriptor. The dominant object is segmented against
  the border-estimated background, the chip is rotated into the object's principal-axis frame and
  described by symmetry-pooled HOG, width profiles, elongation and object/background colour; this is
  concatenated with rotation-invariant ring statistics (ring-relative gradient orientations, radial
  profiles, rotation-invariant LBP, radial power spectrum, Hu moments) and global image statistics
  (brightness, contrast, saturation, sharpness, entropy, colour balance, blur, noise, clipping). Always
  available. It
  captures shape, texture and colour statistics, not semantics, so detectors that need semantic
  similarity run DEGRADED with it.
* ``reference-model`` — penultimate activations of the *approved* model (trained on trusted data).
* ``foundation`` — a vendored foundation encoder (DINOv2 / OpenCLIP / torchvision ResNet) loaded from
  ``assets/models`` after SHA-256 verification. Never downloaded at runtime.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from ..core.hashing import digest_json, sha256_file

CLASSICAL_VERSION = "classical-v2"


@dataclass
class Encoder:
    id: str
    digest: str
    semantic: bool
    description: str
    fn: Callable[[np.ndarray], np.ndarray]
    batch_size: int = 64

    def encode(self, images: np.ndarray) -> np.ndarray:
        """``images``: N×H×W×3 uint8 → N×D float32 raw features (see :func:`normalise_embeddings`)."""
        chunks = [self.fn(images[i:i + self.batch_size]) for i in range(0, len(images), self.batch_size)]
        return np.concatenate(chunks, axis=0).astype(np.float32) if chunks else np.zeros((0, 1), np.float32)


def normalise_embeddings(features: np.ndarray, reference: np.ndarray | None = None) -> np.ndarray:
    """Z-score each dimension (statistics from ``reference`` when given, else from ``features``) and
    L2-normalise rows, so cosine similarity weighs every descriptor dimension comparably."""
    base = features if reference is None else reference
    mu = base.mean(axis=0)
    sd = base.std(axis=0)
    z = (features - mu) / np.where(sd > 1e-8, sd, 1.0)
    return (z / np.maximum(np.linalg.norm(z, axis=1, keepdims=True), 1e-8)).astype(np.float32)


# ----------------------------------------------------------------------------- classical descriptor

_LBP_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]


def _block(v: np.ndarray) -> np.ndarray:
    v = np.sign(v) * np.sqrt(np.abs(v))
    return v / max(float(np.linalg.norm(v)), 1e-8)


def _lbp_riu2(y: np.ndarray) -> np.ndarray:
    c = y[1:-1, 1:-1]
    bits = np.stack([(y[1 + dy:y.shape[0] - 1 + dy, 1 + dx:y.shape[1] - 1 + dx] >= c) for dy, dx in _LBP_OFFSETS])
    transitions = np.sum(bits != np.roll(bits, 1, axis=0), axis=0)
    ones = bits.sum(axis=0)
    code = np.where(transitions <= 2, ones, 9)
    return np.bincount(code.reshape(-1), minlength=10)[:10].astype(np.float64)


def _hu(sal: np.ndarray, yy: np.ndarray, xx: np.ndarray) -> np.ndarray:
    m00 = sal.sum() + 1e-8
    cx, cy = (sal * xx).sum() / m00, (sal * yy).sum() / m00
    x, y = xx - cx, yy - cy

    def mu(p: int, q: int) -> float:
        return float((sal * x**p * y**q).sum())

    def eta(p: int, q: int) -> float:
        return mu(p, q) / m00 ** (1 + (p + q) / 2)
    n20, n02, n11 = eta(2, 0), eta(0, 2), eta(1, 1)
    n30, n03, n21, n12 = eta(3, 0), eta(0, 3), eta(2, 1), eta(1, 2)
    h = np.array([
        n20 + n02,
        (n20 - n02) ** 2 + 4 * n11**2,
        (n30 - 3 * n12) ** 2 + (3 * n21 - n03) ** 2,
        (n30 + n12) ** 2 + (n21 + n03) ** 2,
        (n30 - 3 * n12) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2)
        + (3 * n21 - n03) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2),
        (n20 - n02) * ((n30 + n12) ** 2 - (n21 + n03) ** 2) + 4 * n11 * (n30 + n12) * (n21 + n03),
        (3 * n21 - n03) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2)
        - (n30 - 3 * n12) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2),
    ])
    return -np.sign(h) * np.log10(np.abs(h) + 1e-12)


def ring_features(images: np.ndarray) -> np.ndarray:
    n, H, W = images.shape[:3]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    cy, cx = (H - 1) / 2, (W - 1) / 2
    r = np.hypot(yy - cy, xx - cx) / (min(H, W) / 2)
    phi = np.arctan2(yy - cy, xx - cx)
    ring3 = np.digitize(r, [0.25, 0.55, 0.95]).reshape(-1)
    ring8 = np.minimum((r * 8).astype(int), 8).reshape(-1)
    ring8_n = np.maximum(np.bincount(ring8, minlength=9)[:8], 1)
    centre = (r < 0.35).reshape(-1)
    fy, fx = np.meshgrid(np.fft.fftfreq(H), np.fft.fftfreq(W), indexing="ij")
    fbands = np.digitize(np.hypot(fy, fx), np.geomspace(0.02, 0.5, 9)).reshape(-1)
    fband_n = np.maximum(np.bincount(fbands, minlength=10)[1:9], 1)
    feats = []
    for img in images:
        rgb = img.astype(np.float64) / 255.0
        y = rgb @ _LUMA
        gy, gx = ndimage.sobel(y, axis=0), ndimage.sobel(y, axis=1)
        mag = np.hypot(gx, gy).reshape(-1)
        rel = np.mod(np.arctan2(gy, gx) - phi, np.pi).reshape(-1)
        obins = np.minimum((rel / np.pi * 8).astype(int), 7)
        grad = np.bincount(ring3 * 8 + obins, weights=mag, minlength=32)[:24].reshape(3, 8)
        ring_energy = grad.sum(axis=1)
        grad = grad / np.maximum(ring_energy[:, None], 1e-8)
        yf = y.reshape(-1)
        mean8 = np.bincount(ring8, weights=yf, minlength=9)[:8] / ring8_n
        sq8 = np.bincount(ring8, weights=yf**2, minlength=9)[:8] / ring8_n
        std8 = np.sqrt(np.maximum(sq8 - mean8**2, 0))
        flat = rgb.reshape(-1, 3)
        cm, sm = flat[centre].mean(axis=0), flat[~centre].mean(axis=0)
        colour = np.concatenate([cm, flat[centre].std(axis=0), sm, flat[~centre].std(axis=0), cm - sm])
        u8 = (y * 255).astype(np.int16)
        lbp = np.concatenate([_lbp_riu2(u8), _lbp_riu2(u8[H // 4: 3 * H // 4, W // 4: 3 * W // 4])])
        spec = (np.abs(np.fft.fft2(y - y.mean())) ** 2).reshape(-1)
        bands = np.bincount(fbands, weights=spec, minlength=10)[1:9] / fband_n
        sal = np.abs(y - np.median(y.reshape(-1)[~centre]))
        sal = np.where(sal > np.percentile(sal, 60), sal, 0.0)
        feats.append(np.concatenate([
            _block(grad.reshape(-1)), _block(np.log1p(ring_energy)), _block(mean8), _block(std8),
            _block(colour), _block(lbp / max(lbp.sum(), 1)), _block(np.log1p(bands)), _block(_hu(sal, yy, xx)),
        ]))
    return np.asarray(feats, dtype=np.float32)


# ----------------------------------------------------------------------------- canonical-frame descriptor

_LUMA = np.array([0.299, 0.587, 0.114])


def _hog(y: np.ndarray, cell: int = 8, bins: int = 9) -> np.ndarray:
    gy, gx = ndimage.sobel(y, axis=0), ndimage.sobel(y, axis=1)
    mag = np.hypot(gx, gy)
    b = np.minimum((np.mod(np.arctan2(gy, gx), np.pi) / np.pi * bins).astype(int), bins - 1)
    H, W = y.shape
    ch, cw = H // cell, W // cell
    ci = (np.arange(H)[:, None] // cell).clip(max=ch - 1) * cw + (np.arange(W)[None, :] // cell).clip(max=cw - 1)
    return np.bincount((ci * bins + b).reshape(-1), weights=mag.reshape(-1), minlength=ch * cw * bins
                       ).reshape(ch, cw, bins)


def _canonical(img: np.ndarray, size: int = 40) -> np.ndarray:
    rgb = img.astype(np.float64) / 255.0
    H, W = rgb.shape[:2]
    e = max(2, H // 12)
    border = np.concatenate([rgb[:e].reshape(-1, 3), rgb[-e:].reshape(-1, 3), rgb[:, :e].reshape(-1, 3),
                             rgb[:, -e:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    spread = border.std(axis=0).mean() + 0.02
    d = ndimage.gaussian_filter(np.linalg.norm(rgb - bg, axis=-1), 1.0)
    mask = d > max(np.percentile(d, 85), 2.5 * spread)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    lab, n = ndimage.label(mask)
    if n:
        idx = np.arange(1, n + 1)
        mass = ndimage.sum(d, lab, idx)
        cy_k = ndimage.sum(yy, lab, idx) / np.maximum(ndimage.sum(np.ones_like(d), lab, idx), 1)
        cx_k = ndimage.sum(xx, lab, idx) / np.maximum(ndimage.sum(np.ones_like(d), lab, idx), 1)
        best = int(idx[np.argmax(mass / (1 + 0.05 * np.hypot(cy_k - H / 2, cx_k - W / 2)))])
        mask = ndimage.binary_dilation(lab == best, iterations=1)
    w = d * mask + 1e-9
    m0 = w.sum()
    cy, cx = (w * yy).sum() / m0, (w * xx).sum() / m0
    cxx = (w * (xx - cx) ** 2).sum() / m0
    cyy = (w * (yy - cy) ** 2).sum() / m0
    cxy = (w * (xx - cx) * (yy - cy)).sum() / m0
    ev, evec = np.linalg.eigh(np.array([[cxx, cxy], [cxy, cyy]]))
    theta = np.arctan2(evec[1, 1], evec[0, 1])
    c, s = np.cos(theta), np.sin(theta)
    u, v = np.mgrid[0:size, 0:size].astype(np.float64) - (size - 1) / 2
    xi, yi = cx + v * c - u * s, cy + v * s + u * c
    crop = np.stack([ndimage.map_coordinates(rgb[..., k], [yi, xi], order=1, mode="reflect") for k in range(3)], -1)
    cm = ndimage.map_coordinates(mask.astype(np.float64), [yi, xi], order=1) > 0.5
    y = crop @ _LUMA
    hsum = _hog(y) + _hog(y[::-1, ::-1]) + _hog(y[::-1]) + _hog(y[:, ::-1])
    hsum = np.sqrt(hsum / max(float(np.linalg.norm(hsum)), 1e-8)).reshape(-1)
    along = cm.sum(axis=0).astype(np.float64)
    along = along + along[::-1]
    across = cm.sum(axis=1).astype(np.float64)
    across = across + across[::-1]
    step = size // 10
    prof = np.array([along[i * step:(i + 1) * step].mean() for i in range(10)]
                    + [across[i * step:(i + 1) * step].mean() for i in range(10)]) / size
    shape = np.array([mask.mean() * 10, np.log(np.sqrt(ev[1] / max(ev[0], 1e-6)) + 1e-6), np.sqrt(ev[1]) / 10,
                      np.sqrt(max(ev[0], 0)) / 10])
    obj = rgb[mask].mean(axis=0) if mask.any() else bg
    ostd = rgb[mask].std(axis=0) if mask.any() else np.zeros(3)
    return np.concatenate([hsum, prof, shape, obj, bg, obj - bg, ostd])


def classical_features(images: np.ndarray) -> np.ndarray:
    from .quality import AXES, image_statistics

    stats = image_statistics(images)
    global_stats = np.stack([stats[a] for a in AXES], axis=1)
    return np.concatenate([np.stack([_canonical(img) for img in images]), ring_features(images), global_stats],
                          axis=1).astype(np.float32)


def classical_encoder() -> Encoder:
    return Encoder(id=CLASSICAL_VERSION, digest=digest_json({"encoder": CLASSICAL_VERSION, "v": 2}), semantic=False,
                   description="Deterministic object-canonicalised shape/texture/colour descriptor (no learned weights).",
                   fn=classical_features, batch_size=256)


def model_encoder(model_id: str, model_digest: str, fn: Callable[[np.ndarray], np.ndarray]) -> Encoder:
    return Encoder(id=f"reference-model:{model_id}", digest=digest_json({"encoder": "reference-model",
                                                                         "model": model_digest}),
                   semantic=True, description="Penultimate activations of the approved reference model.", fn=fn)


# ----------------------------------------------------------------------------- vendored foundation encoders

@dataclass
class FoundationStatus:
    available: bool
    reason: str
    encoder: Encoder | None = None


def foundation_encoder(models_dir: Path) -> FoundationStatus:
    """Load a vendored encoder described by ``assets/models/manifest.json`` (never downloads)."""
    manifest_path = models_dir / "manifest.json"
    if not manifest_path.is_file():
        return FoundationStatus(False, "required local encoder weights not installed (assets/models/manifest.json absent)")
    try:
        manifest = json.loads(manifest_path.read_text())
        entry = manifest["encoders"][0]
        weights = models_dir / entry["file"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return FoundationStatus(False, f"encoder manifest malformed: {exc}")
    if not weights.is_file():
        return FoundationStatus(False, f"required local encoder weights not installed ({entry['file']})")
    actual = sha256_file(weights)
    if actual != entry.get("sha256"):
        return FoundationStatus(False, f"encoder weights checksum mismatch for {entry['file']} (expected "
                                       f"{entry.get('sha256')}, found {actual})")
    try:
        import torch
    except ImportError:
        return FoundationStatus(False, "PyTorch is not installed")
    kind = entry.get("kind")
    try:
        if kind == "torchvision_resnet":
            import torchvision  # noqa: F401

            from torchvision.models import resnet18, resnet50
            net = (resnet50 if entry.get("arch") == "resnet50" else resnet18)(weights=None)
            net.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
            net.fc = torch.nn.Identity()
        elif kind == "dinov2":
            repo = models_dir / entry["repo_dir"]
            net = torch.hub.load(str(repo), entry.get("arch", "dinov2_vits14"), source="local", pretrained=False)
            net.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
        else:
            return FoundationStatus(False, f"unsupported vendored encoder kind {kind!r}")
    except ImportError as exc:
        return FoundationStatus(False, f"encoder runtime not installed: {exc.name}")
    net.eval()
    size = int(entry.get("input_size", 224))
    mean = torch.tensor(entry.get("mean", [0.485, 0.456, 0.406])).view(1, 3, 1, 1)
    std = torch.tensor(entry.get("std", [0.229, 0.224, 0.225])).view(1, 3, 1, 1)

    def fn(images: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            x = torch.from_numpy(images).permute(0, 3, 1, 2).float() / 255.0
            x = torch.nn.functional.interpolate(x, size=(size, size), mode="bilinear", align_corners=False)
            return net((x - mean) / std).reshape(len(images), -1).numpy()

    enc = Encoder(id=f"foundation:{entry.get('name', kind)}", digest=actual, semantic=True,
                  description=f"Vendored {entry.get('name', kind)} encoder (checksum verified).", fn=fn, batch_size=32)
    return FoundationStatus(True, "vendored encoder verified", enc)
