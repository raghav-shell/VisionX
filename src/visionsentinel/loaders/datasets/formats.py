"""Dataset format readers: VisionSentinel manifest, COCO, YOLO, Pascal VOC, ImageFolder, plain directory.

Every reader converts to the internal :class:`Dataset`. Malformed entries are recorded as
:class:`ParseIssue` (and later surfaced by the annotation-integrity detector); unsafe entries such as
traversal paths abort loading with :class:`UnsafeInputError`.
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

from ...core.errors import LoaderError, ProfileError, ResourceLimitError, UnsafeInputError
from ...core.limits import ResourceLimits
from ...core.profiles import load_yaml_strict
from ..images import IMAGE_SUFFIXES
from ..safe_io import load_json_bounded, normalise_member_name, parse_json_bounded, read_bounded, resolve_within, safe_text
from .model import Box, Dataset, ParseIssue, Sample, derive_labels_from_boxes

META_FIELDS = ("contributor", "batch", "source", "sensor", "timestamp")
csv.field_size_limit(1 << 20)


def _finite(*vals: Any) -> bool:
    try:
        return all(math.isfinite(float(v)) for v in vals)
    except (TypeError, ValueError):
        return False


def _iter_images(root: Path, limits: ResourceLimits) -> list[str]:
    root_r = root.resolve()
    out: list[str] = []
    for p in sorted(root_r.rglob("*")):
        if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file():
            rel = p.relative_to(root_r).as_posix()
            resolve_within(root_r, rel)  # rejects symlinks escaping the root
            out.append(rel)
            if len(out) > limits.max_dataset_samples:
                raise ResourceLimitError(f"dataset exceeds {limits.max_dataset_samples} samples")
    return out


# ---------------------------------------------------------------------------- manifest

def _parse_bbox(value: Any) -> list[float] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = [v for v in value.replace(",", " ").split() if v]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("bbox must have four numbers [x, y, w, h]")
    return [float(v) for v in value]


def _sample_from_record(rec: dict[str, Any], line: str, issues: list[ParseIssue]) -> Sample:
    file = rec.get("file") or rec.get("path") or rec.get("file_name")
    if not isinstance(file, str):
        raise LoaderError(f"{line}: record has no 'file' field")
    rel = normalise_member_name(file)
    sid = safe_text(rec.get("id"), 128) or rel
    s = Sample(id=sid, rel_path=rel, label=safe_text(rec.get("label"), 128),
               declared_digest=safe_text(rec.get("sha256"), 80), split=safe_text(rec.get("split"), 32))
    for f in META_FIELDS:
        setattr(s, f, safe_text(rec.get(f), 128))
    boxes = rec.get("boxes")
    try:
        if boxes:
            if not isinstance(boxes, list):
                raise ValueError("'boxes' must be a list")
            for b in boxes[:512]:
                x, y, w, h = _parse_bbox(b.get("bbox"))  # type: ignore[misc]
                s.boxes.append(Box(safe_text(b.get("category"), 128) or (s.label or "object"), x, y, w, h,
                                   raw=str(b.get("bbox"))[:80]))
        elif rec.get("bbox") not in (None, ""):
            bb = _parse_bbox(rec.get("bbox"))
            if bb:
                s.boxes.append(Box(s.label or "object", *bb, raw=str(rec.get("bbox"))[:80]))
    except (ValueError, TypeError, AttributeError) as exc:
        issues.append(ParseIssue(line, f"unparseable bounding box: {exc}", sid))
    for k, v in rec.items():
        if k not in {"file", "path", "file_name", "id", "label", "sha256", "split", "bbox", "boxes", *META_FIELDS}:
            text = safe_text(v, 128)
            if text is not None and len(s.extra) < 16:
                s.extra[safe_text(k, 32) or "?"] = text
    return s


def load_manifest(root: Path, limits: ResourceLimits) -> Dataset:
    issues: list[ParseIssue] = []
    samples: list[Sample] = []
    info: dict[str, Any] = {}
    if (root / "dataset.json").is_file():
        raw = load_json_bounded(root / "dataset.json", limits)
        if not isinstance(raw, dict):
            raise LoaderError("dataset.json must be an object")
        info = raw
    if (root / "manifest.jsonl").is_file():
        data = read_bounded(root / "manifest.jsonl", limits.max_json_bytes)
        for n, line in enumerate(data.decode("utf-8", errors="strict").splitlines(), start=1):
            if not line.strip():
                continue
            rec = parse_json_bounded(line.encode(), limits, name=f"manifest.jsonl:{n}")
            if not isinstance(rec, dict):
                raise LoaderError(f"manifest.jsonl:{n}: each line must be a JSON object")
            samples.append(_sample_from_record(rec, f"manifest.jsonl:{n}", issues))
            if len(samples) > limits.max_dataset_samples:
                raise ResourceLimitError(f"manifest exceeds {limits.max_dataset_samples} samples")
    else:
        data = read_bounded(root / "manifest.csv", limits.max_json_bytes)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        for n, row in enumerate(reader, start=2):
            samples.append(_sample_from_record(dict(row), f"manifest.csv:{n}", issues))
            if len(samples) > limits.max_dataset_samples:
                raise ResourceLimitError(f"manifest exceeds {limits.max_dataset_samples} samples")
    ids = [s.id for s in samples]
    if len(ids) != len(set(ids)):
        raise LoaderError("manifest contains duplicate sample ids")
    classes = info.get("classes")
    if not (isinstance(classes, list) and all(isinstance(c, str) for c in classes)):
        classes = sorted({s.label for s in samples if s.label} | {b.category for s in samples for b in s.boxes})
    return Dataset(name=safe_text(info.get("name"), 128) or root.name, root=root, format="manifest",
                   classes=[c[:128] for c in classes], samples=samples, limits=limits, issues=issues)


# ---------------------------------------------------------------------------- COCO

def find_coco_file(root: Path) -> Path | None:
    if (root / "annotations.json").is_file():
        return root / "annotations.json"
    if (root / "annotations").is_dir():
        for candidate in sorted((root / "annotations").glob("*.json")):
            return candidate
    return None


def load_coco(root: Path, limits: ResourceLimits, ann_path: Path | None = None) -> Dataset:
    ann_path = ann_path or find_coco_file(root)
    if ann_path is None:
        raise LoaderError("no COCO annotation file found")
    doc = load_json_bounded(ann_path, limits)
    if not isinstance(doc, dict) or not isinstance(doc.get("images"), list):
        raise LoaderError(f"{ann_path.name}: not a COCO document (missing 'images')")
    issues: list[ParseIssue] = []
    cats: dict[Any, str] = {}
    for c in doc.get("categories") or []:
        if isinstance(c, dict) and "id" in c:
            cats[c["id"]] = safe_text(c.get("name"), 128) or f"category_{c['id']}"
    image_base = root / "images" if (root / "images").is_dir() else root
    by_id: dict[Any, Sample] = {}
    samples: list[Sample] = []
    for n, img in enumerate(doc["images"]):
        if not isinstance(img, dict) or "file_name" not in img or "id" not in img:
            issues.append(ParseIssue(f"images[{n}]", "image entry lacks 'id' or 'file_name'"))
            continue
        rel = normalise_member_name(str(img["file_name"]))
        if image_base != root and not (root / rel).is_file():
            rel = f"images/{rel}"
        s = Sample(id=f"{img['id']}", rel_path=rel,
                   declared_width=int(img["width"]) if _finite(img.get("width")) else None,
                   declared_height=int(img["height"]) if _finite(img.get("height")) else None,
                   timestamp=safe_text(img.get("date_captured"), 64))
        for f in ("contributor", "batch", "source", "sensor"):
            setattr(s, f, safe_text(img.get(f), 128))
        if img["id"] in by_id:
            issues.append(ParseIssue(f"images[{n}]", f"duplicate image id {img['id']!r}"))
            continue
        by_id[img["id"]] = s
        samples.append(s)
        if len(samples) > limits.max_dataset_samples:
            raise ResourceLimitError(f"dataset exceeds {limits.max_dataset_samples} samples")
    for n, ann in enumerate(doc.get("annotations") or []):
        if not isinstance(ann, dict):
            continue
        s = by_id.get(ann.get("image_id"))
        if s is None:
            issues.append(ParseIssue(f"annotations[{n}]", f"references unknown image_id {ann.get('image_id')!r}"))
            continue
        bbox = ann.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4 and _finite(*bbox)):
            issues.append(ParseIssue(f"annotations[{n}]", "bbox is not four finite numbers", s.id))
            continue
        cat = cats.get(ann.get("category_id"))
        if cat is None:
            issues.append(ParseIssue(f"annotations[{n}]", f"unknown category_id {ann.get('category_id')!r}", s.id))
            continue
        s.boxes.append(Box(cat, *map(float, bbox), raw=str(bbox)[:80]))
    notes: list[str] = []
    derive_labels_from_boxes(samples, notes)
    return Dataset(name=root.name, root=root, format="coco", classes=[cats[k] for k in sorted(cats, key=str)],
                   samples=samples, limits=limits, issues=issues, notes=notes)


# ---------------------------------------------------------------------------- YOLO

def load_yolo(root: Path, limits: ResourceLimits) -> Dataset:
    cfg_path = root / "data.yaml"
    try:
        cfg = load_yaml_strict(cfg_path, max_bytes=256 * 1024) if cfg_path.is_file() else {}
    except ProfileError as exc:
        raise LoaderError(f"data.yaml: {exc}") from exc
    names = cfg.get("names") if isinstance(cfg, dict) else None
    if isinstance(names, dict):
        names = [str(names[k]) for k in sorted(names, key=lambda x: int(x))]
    if not isinstance(names, list) or not names:
        raise LoaderError("YOLO dataset needs data.yaml with a non-empty 'names' list",
                          hint="the 'path' key in data.yaml is ignored; images/ and labels/ are read relative to the dataset root")
    names = [safe_text(n, 128) or "?" for n in names]
    issues: list[ParseIssue] = []
    samples: list[Sample] = []
    for rel in _iter_images(root / "images", limits) if (root / "images").is_dir() else []:
        img_rel = f"images/{rel}"
        split = rel.split("/")[0] if "/" in rel else None
        s = Sample(id=img_rel, rel_path=img_rel, split=split)
        label_rel = "labels/" + str(Path(rel).with_suffix(".txt").as_posix())
        label_path = root / label_rel
        if label_path.is_file():
            resolve_within(root, label_rel)
            text = read_bounded(label_path, 1 << 20).decode("utf-8", errors="replace")
            for ln, line in enumerate(text.splitlines(), start=1):
                parts = line.split()
                if not parts:
                    continue
                if len(parts) != 5 or not _finite(*parts):
                    issues.append(ParseIssue(f"{label_rel}:{ln}", f"malformed YOLO line {line[:60]!r}", s.id))
                    continue
                cls = int(float(parts[0]))
                if not 0 <= cls < len(names):
                    issues.append(ParseIssue(f"{label_rel}:{ln}", f"class index {cls} outside names", s.id))
                    continue
                cx, cy, w, h = map(float, parts[1:])
                # Stored normalised; converted to pixels after indexing (see Dataset.finalize_yolo).
                s.boxes.append(Box(names[cls], cx, cy, w, h, raw="yolo:" + " ".join(parts[1:])))
        samples.append(s)
    return Dataset(name=root.name, root=root, format="yolo", classes=names, samples=samples, limits=limits,
                   issues=issues)


def finalize_yolo(ds: Dataset) -> None:
    """Convert normalised centre boxes to pixel top-left boxes once image sizes are known."""
    for s in ds.samples:
        if not s.width or not s.height:
            continue
        for b in s.boxes:
            if b.raw and b.raw.startswith("yolo:"):
                cx, cy, w, h = b.x, b.y, b.w, b.h
                b.x, b.y, b.w, b.h = (cx - w / 2) * s.width, (cy - h / 2) * s.height, w * s.width, h * s.height
    notes: list[str] = []
    derive_labels_from_boxes(ds.samples, notes)
    ds.notes.extend(notes)


# ---------------------------------------------------------------------------- Pascal VOC

def load_voc(root: Path, limits: ResourceLimits) -> Dataset:
    ann_dir = root / "Annotations"
    img_dir = "JPEGImages" if (root / "JPEGImages").is_dir() else "images"
    issues: list[ParseIssue] = []
    samples: list[Sample] = []
    classes: set[str] = set()
    for xml_path in sorted(ann_dir.glob("*.xml")):
        rel_xml = f"Annotations/{xml_path.name}"
        resolve_within(root, rel_xml)
        data = read_bounded(xml_path, limits.max_xml_bytes)
        try:
            tree = DefusedET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        except DefusedXmlException as exc:
            raise UnsafeInputError(f"{rel_xml}: forbidden XML construct ({type(exc).__name__})") from exc
        except DefusedET.ParseError as exc:
            issues.append(ParseIssue(rel_xml, f"malformed XML: {exc}"))
            continue
        fname = (tree.findtext("filename") or xml_path.with_suffix(".jpg").name).strip()
        rel = f"{img_dir}/{normalise_member_name(fname)}"
        s = Sample(id=rel, rel_path=rel)
        size = tree.find("size")
        if size is not None and _finite(size.findtext("width"), size.findtext("height")):
            s.declared_width, s.declared_height = int(float(size.findtext("width"))), int(float(size.findtext("height")))
        for k in ("contributor", "batch", "source", "sensor", "timestamp"):
            val = tree.findtext(k)
            if val:
                setattr(s, k, safe_text(val, 128))
        for obj in tree.findall("object")[:512]:
            name = safe_text(obj.findtext("name"), 128) or "?"
            bb = obj.find("bndbox")
            vals = [bb.findtext(t) if bb is not None else None for t in ("xmin", "ymin", "xmax", "ymax")]
            if not _finite(*vals):
                issues.append(ParseIssue(rel_xml, f"object {name!r} has a non-numeric bndbox", s.id))
                continue
            x0, y0, x1, y1 = map(float, vals)
            s.boxes.append(Box(name, x0, y0, x1 - x0, y1 - y0, raw=f"voc:{x0},{y0},{x1},{y1}"))
            classes.add(name)
        samples.append(s)
        if len(samples) > limits.max_dataset_samples:
            raise ResourceLimitError(f"dataset exceeds {limits.max_dataset_samples} samples")
    notes: list[str] = []
    derive_labels_from_boxes(samples, notes)
    return Dataset(name=root.name, root=root, format="voc", classes=sorted(classes), samples=samples,
                   limits=limits, issues=issues, notes=notes)


# ---------------------------------------------------------------------------- ImageFolder / plain

def load_imagefolder(root: Path, limits: ResourceLimits) -> Dataset:
    samples: list[Sample] = []
    classes = sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith("."))
    for cls in classes:
        for rel in _iter_images(root / cls, limits):
            path = f"{cls}/{rel}"
            samples.append(Sample(id=path, rel_path=path, label=safe_text(cls, 128)))
            if len(samples) > limits.max_dataset_samples:
                raise ResourceLimitError(f"dataset exceeds {limits.max_dataset_samples} samples")
    return Dataset(name=root.name, root=root, format="imagefolder", classes=classes, samples=samples, limits=limits)


def load_plain(root: Path, limits: ResourceLimits) -> Dataset:
    samples = [Sample(id=rel, rel_path=rel) for rel in _iter_images(root, limits)]
    return Dataset(name=root.name, root=root, format="images", classes=[], samples=samples, limits=limits,
                   notes=["unlabelled image directory: no labels, annotations or contributor metadata"])


# ---------------------------------------------------------------------------- metadata sidecar

def apply_metadata_sidecar(ds: Dataset) -> None:
    """Optional ``metadata.csv`` (file, contributor, batch, source, sensor, timestamp) for any format."""
    path = ds.root / "metadata.csv"
    if not path.is_file() or ds.format == "manifest":
        return
    data = read_bounded(path, ds.limits.max_json_bytes).decode("utf-8")
    by_path = {s.rel_path: s for s in ds.samples}
    matched = 0
    for n, row in enumerate(csv.DictReader(io.StringIO(data)), start=2):
        file = row.get("file")
        if not file:
            ds.issues.append(ParseIssue(f"metadata.csv:{n}", "row without 'file'"))
            continue
        s = by_path.get(normalise_member_name(file))
        if s is None:
            ds.issues.append(ParseIssue(f"metadata.csv:{n}", f"file {file[:80]!r} not in dataset"))
            continue
        for f in META_FIELDS:
            if row.get(f):
                setattr(s, f, safe_text(row[f], 128))
        matched += 1
    ds.notes.append(f"metadata.csv applied to {matched} samples")
