"""Safe image decoding.

Dimensions are read from the header and checked against pixel and side limits *before* any
decode. Only raster formats on an allow-list are decoded (SVG and other document formats are
refused). Truncated or corrupt files raise :class:`LoaderError` rather than being silently padded.
"""

from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image, ImageFile, UnidentifiedImageError

from ..core.errors import LoaderError, ResourceLimitError, UnsafeInputError
from ..core.limits import ResourceLimits
from .safe_io import read_bounded, safe_text

ALLOWED_FORMATS = frozenset({"PNG", "JPEG", "BMP", "TIFF", "WEBP"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"})
ImageFile.LOAD_TRUNCATED_IMAGES = False

_EXIF_KEEP = {"Make", "Model", "Software", "DateTime", "DateTimeOriginal", "LensModel", "BodySerialNumber"}
_EXIF_NAMES = {v: k for k, v in ExifTags.TAGS.items()}


@dataclass
class ImageInfo:
    format: str
    mode: str
    width: int
    height: int
    size_bytes: int
    jpeg_quality: int | None = None
    quant_digest: str | None = None
    exif: dict[str, str] = field(default_factory=dict)


def _estimate_jpeg_quality(im: Image.Image) -> tuple[int | None, str | None]:
    q = getattr(im, "quantization", None)
    if not q:
        return None, None
    tables = [np.asarray(q[k], dtype=np.float64) for k in sorted(q)]
    digest = hashlib.sha256(b"".join(t.astype(np.uint16).tobytes() for t in tables)).hexdigest()[:16]
    # IJG scaling: luminance table mean vs the standard table mean at quality 50 (≈57.6).
    mean = float(tables[0].mean())
    scale = mean / 57.625 * 100.0
    quality = int(round((200.0 - scale) / 2.0)) if scale <= 100 else int(round(5000.0 / scale))
    return max(1, min(100, quality)), digest


def _exif(im: Image.Image) -> dict[str, str]:
    try:
        raw = im.getexif()
    except Exception:  # noqa: BLE001 - malformed EXIF is ignored, not fatal
        return {}
    out: dict[str, str] = {}
    for name in _EXIF_KEEP:
        tag = _EXIF_NAMES.get(name)
        if tag is not None and tag in raw:
            val = safe_text(raw.get(tag), 128)
            if val:
                out[name] = val
    try:
        sub = raw.get_ifd(0x8769)
        for name in ("DateTimeOriginal", "LensModel", "BodySerialNumber"):
            tag = _EXIF_NAMES.get(name)
            if tag in sub and name not in out:
                val = safe_text(sub.get(tag), 128)
                if val:
                    out[name] = val
    except Exception:  # noqa: BLE001
        pass
    return out


def _open_checked(data: bytes, name: str, limits: ResourceLimits) -> Image.Image:
    if data[:5].lower().startswith(b"<?xml") or b"<svg" in data[:512].lower():
        raise UnsafeInputError(f"{name}: SVG/XML documents are not accepted as images")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError) as exc:
        raise LoaderError(f"{name}: not a decodable image ({exc})") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ResourceLimitError(f"{name}: decompression bomb rejected") from exc
    if im.format not in ALLOWED_FORMATS:
        raise UnsafeInputError(f"{name}: image format {im.format!r} is not on the allow-list")
    w, h = im.size
    if w <= 0 or h <= 0:
        raise LoaderError(f"{name}: invalid dimensions {w}x{h}")
    if w > limits.max_image_side or h > limits.max_image_side or w * h > limits.max_image_pixels:
        raise ResourceLimitError(f"{name}: {w}x{h} exceeds image limits")
    return im


def probe_image(path: Path, limits: ResourceLimits) -> ImageInfo:
    """Header metadata plus a full decodability check (JPEG decoded at reduced scale for speed)."""
    data = read_bounded(path, limits.max_file_bytes)
    im = _open_checked(data, path.name, limits)
    quality, qd = _estimate_jpeg_quality(im) if im.format == "JPEG" else (None, None)
    info = ImageInfo(format=im.format or "?", mode=im.mode, width=im.size[0], height=im.size[1],
                     size_bytes=len(data), jpeg_quality=quality, quant_digest=qd, exif=_exif(im))
    try:
        if im.format == "JPEG":
            im.draft("RGB", (max(1, im.size[0] // 8), max(1, im.size[1] // 8)))
        im.load()
    except (OSError, SyntaxError, ValueError) as exc:
        raise LoaderError(f"{path.name}: corrupt or truncated image ({exc})") from exc
    return info


def decode_bytes(data: bytes, name: str, limits: ResourceLimits) -> np.ndarray:
    im = _open_checked(data, name, limits)
    Image.MAX_IMAGE_PIXELS = limits.max_image_pixels
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im.load()
            if getattr(im, "n_frames", 1) > 1:
                im.seek(0)
            rgb = im.convert("RGB")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ResourceLimitError(f"{name}: decompression bomb rejected") from exc
    except (OSError, SyntaxError, ValueError) as exc:
        raise LoaderError(f"{name}: corrupt or truncated image ({exc})") from exc
    return np.asarray(rgb, dtype=np.uint8)


def load_image(path: Path, limits: ResourceLimits) -> np.ndarray:
    """Decode ``path`` into an ``H×W×3`` uint8 RGB array after all safety checks."""
    return decode_bytes(read_bounded(path, limits.max_file_bytes), path.name, limits)


def resize(image: np.ndarray, size: int) -> np.ndarray:
    """Square resize with area averaging (down) / bilinear (up); deterministic."""
    if image.shape[0] == size and image.shape[1] == size:
        return image
    im = Image.fromarray(image)
    down = im.size[0] > size or im.size[1] > size
    return np.asarray(im.resize((size, size), Image.Resampling.BOX if down else Image.Resampling.BILINEAR),
                      dtype=np.uint8)
