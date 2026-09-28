"""Export corpus records to standard dataset formats (COCO, YOLO, Pascal VOC, ImageFolder).

Used to build loader fixtures and to demonstrate that every assurance check runs identically
whatever format a contributor delivers.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image

from .corpus import Record
from .synthetic import CLASSES


def _save(img: np.ndarray, path: Path, fmt: str = "PNG") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(path, format=fmt)


def export_coco(records: list[Record], out: Path, classes: tuple[str, ...] = CLASSES) -> Path:
    cats = [{"id": i + 1, "name": c} for i, c in enumerate(classes)]
    cid = {c: i + 1 for i, c in enumerate(classes)}
    images, anns = [], []
    for n, r in enumerate(records, start=1):
        fname = f"{r.id}.png"
        _save(r.image, out / "images" / fname)
        img = {"id": n, "file_name": fname, "width": int(r.image.shape[1]), "height": int(r.image.shape[0])}
        for k in ("contributor", "batch", "source", "sensor"):
            if getattr(r, k):
                img[k] = getattr(r, k)
        if r.timestamp:
            img["date_captured"] = r.timestamp
        images.append(img)
        if r.bbox:
            anns.append({"id": len(anns) + 1, "image_id": n, "category_id": cid[r.label], "bbox": r.bbox,
                         "area": r.bbox[2] * r.bbox[3], "iscrowd": 0})
    (out / "annotations").mkdir(parents=True, exist_ok=True)
    path = out / "annotations" / "instances.json"
    path.write_text(json.dumps({"images": images, "annotations": anns, "categories": cats}))
    return out


def export_yolo(records: list[Record], out: Path, classes: tuple[str, ...] = CLASSES) -> Path:
    cid = {c: i for i, c in enumerate(classes)}
    (out / "data.yaml").parent.mkdir(parents=True, exist_ok=True)
    (out / "data.yaml").write_text("names:\n" + "".join(f"  - {c}\n" for c in classes))
    for r in records:
        _save(r.image, out / "images" / "train" / f"{r.id}.png")
        lines = []
        if r.bbox:
            h, w = r.image.shape[:2]
            x, y, bw, bh = r.bbox
            lines.append(f"{cid[r.label]} {(x + bw / 2) / w:.6f} {(y + bh / 2) / h:.6f} {bw / w:.6f} {bh / h:.6f}")
        lp = out / "labels" / "train" / f"{r.id}.txt"
        lp.parent.mkdir(parents=True, exist_ok=True)
        lp.write_text("\n".join(lines) + ("\n" if lines else ""))
    meta = ["file,contributor,batch,source,sensor,timestamp"]
    for r in records:
        meta.append(",".join([f"images/train/{r.id}.png", r.contributor or "", r.batch or "", r.source or "",
                              r.sensor or "", r.timestamp or ""]))
    (out / "metadata.csv").write_text("\n".join(meta) + "\n")
    return out


def export_voc(records: list[Record], out: Path) -> Path:
    (out / "Annotations").mkdir(parents=True, exist_ok=True)
    for r in records:
        fname = f"{r.id}.png"
        _save(r.image, out / "JPEGImages" / fname)
        h, w = r.image.shape[:2]
        objs = ""
        if r.bbox:
            x, y, bw, bh = r.bbox
            objs = (f"<object><name>{escape(r.label)}</name><bndbox><xmin>{x:.1f}</xmin><ymin>{y:.1f}</ymin>"
                    f"<xmax>{x + bw:.1f}</xmax><ymax>{y + bh:.1f}</ymax></bndbox></object>")
        meta = "".join(f"<{k}>{escape(getattr(r, k))}</{k}>" for k in ("contributor", "batch", "source", "sensor",
                                                                       "timestamp") if getattr(r, k))
        xml = (f"<annotation><filename>{escape(fname)}</filename><size><width>{w}</width><height>{h}</height>"
               f"<depth>3</depth></size>{meta}{objs}</annotation>")
        (out / "Annotations" / f"{r.id}.xml").write_text(xml)
    return out


def export_imagefolder(records: list[Record], out: Path) -> Path:
    for r in records:
        _save(r.image, out / r.label / f"{r.id}.png")
    return out
