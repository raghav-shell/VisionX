"""Dataset loading with format auto-detection.

Detection order: VisionSentinel manifest → COCO → YOLO → Pascal VOC → ImageFolder → plain images.
"""

from __future__ import annotations

from pathlib import Path

from ...core.errors import LoaderError, UnsafeInputError
from ...core.limits import ResourceLimits
from ..images import IMAGE_SUFFIXES
from .formats import (
    apply_metadata_sidecar,
    finalize_yolo,
    find_coco_file,
    load_coco,
    load_imagefolder,
    load_manifest,
    load_plain,
    load_voc,
    load_yolo,
)
from .model import Box, Dataset, ParseIssue, Sample

FORMATS = ("auto", "manifest", "coco", "yolo", "voc", "imagefolder", "images")


def detect_format(root: Path) -> str:
    if (root / "manifest.jsonl").is_file() or (root / "manifest.csv").is_file():
        return "manifest"
    if find_coco_file(root) is not None:
        return "coco"
    if (root / "data.yaml").is_file() and (root / "images").is_dir():
        return "yolo"
    if (root / "Annotations").is_dir():
        return "voc"
    subdirs = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if len(subdirs) >= 2 and not any(p.suffix.lower() in IMAGE_SUFFIXES for p in root.iterdir() if p.is_file()):
        with_images = [d for d in subdirs if any(p.suffix.lower() in IMAGE_SUFFIXES for p in d.iterdir())]
        if len(with_images) >= 2:
            return "imagefolder"
    return "images"


def open_dataset(path: str | Path, limits: ResourceLimits | None = None, *, fmt: str = "auto",
                 name: str | None = None, index: bool = True, progress=None) -> Dataset:
    limits = limits or ResourceLimits()
    root = Path(path)
    if root.is_symlink():
        raise UnsafeInputError(f"dataset root {root} is a symbolic link")
    if not root.is_dir():
        raise LoaderError(f"dataset path {root} is not a directory",
                          hint="archives must be imported first: visionsentinel assets import <archive>")
    root = root.resolve()
    if fmt not in FORMATS:
        raise LoaderError(f"unknown dataset format {fmt!r}", hint=f"choose one of {', '.join(FORMATS)}")
    kind = detect_format(root) if fmt == "auto" else fmt
    loader = {"manifest": load_manifest, "coco": load_coco, "yolo": load_yolo, "voc": load_voc,
              "imagefolder": load_imagefolder, "images": load_plain}[kind]
    ds = loader(root, limits)
    if name:
        ds.name = name
    if not ds.samples:
        raise LoaderError(f"no samples found in {root} (format: {kind})")
    apply_metadata_sidecar(ds)
    if index:
        ds.index(progress)
        if kind == "yolo":
            finalize_yolo(ds)
            ds._digest = None
    return ds


__all__ = ["Box", "Dataset", "ParseIssue", "Sample", "open_dataset", "detect_format", "FORMATS"]
