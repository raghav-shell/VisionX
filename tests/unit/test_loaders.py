"""Dataset format loaders normalise every format into the same representation."""

from __future__ import annotations

import json

import numpy as np
import pytest

from visionsentinel.attacklab.corpus import ContributorProfile, generate_contributor, write_corpus
from visionsentinel.attacklab.exporters import export_coco, export_imagefolder, export_voc, export_yolo
from visionsentinel.contracts import Capability
from visionsentinel.loaders.datasets import detect_format, open_dataset


@pytest.fixture(scope="module")
def records():
    out = []
    for name, sensor in (("Alpha", "EO-A2"), ("Bravo", "EO-B1"), ("Charlie", "UAV-C3")):
        out += generate_contributor(ContributorProfile(name=name, samples=10, sensor=sensor, source=f"unit-{name}",
                                                       session_size=5), seed=3)
    return out


def test_manifest_round_trip_and_capabilities(tmp_path, records):
    write_corpus(records, tmp_path / "ds", name="unit")
    ds = open_dataset(tmp_path / "ds")
    assert ds.format == "manifest" and len(ds.samples) == 30 and len(ds.readable) == 30
    caps = ds.capabilities("dataset")
    for c in (Capability.DATASET_IMAGES, Capability.DATASET_LABELS, Capability.DATASET_ANNOTATIONS,
              Capability.DATASET_METADATA, Capability.CONTRIBUTOR_METADATA):
        assert c in caps
    assert ds.contributors() == ["Alpha", "Bravo", "Charlie"]
    s = ds.samples[0]
    assert s.digest and s.digest == s.declared_digest
    assert s.width == 64 and s.format == "PNG"
    assert not (tmp_path / "ds" / "truth.json").exists(), "ground truth must never sit inside the dataset"


def test_coco_labels_boxes_and_metadata(tmp_path, records):
    export_coco(records, tmp_path / "coco")
    assert detect_format(tmp_path / "coco") == "coco"
    ds = open_dataset(tmp_path / "coco")
    assert len(ds.samples) == 30
    assert all(s.label == r.label for s, r in zip(ds.samples, records))
    assert ds.samples[0].boxes[0].as_list() == pytest.approx(records[0].bbox)
    assert Capability.CONTRIBUTOR_METADATA in ds.capabilities("dataset")


def test_yolo_normalised_boxes_become_pixels(tmp_path, records):
    export_yolo(records, tmp_path / "yolo")
    assert detect_format(tmp_path / "yolo") == "yolo"
    ds = open_dataset(tmp_path / "yolo")
    by_id = {r.id: r for r in records}
    for s in ds.samples:
        rid = s.rel_path.rsplit("/", 1)[-1][:-4]
        assert s.boxes[0].as_list() == pytest.approx(by_id[rid].bbox, abs=1e-3)
        assert s.label == by_id[rid].label
        assert s.contributor == by_id[rid].contributor  # from metadata.csv sidecar


def test_voc_and_imagefolder(tmp_path, records):
    export_voc(records, tmp_path / "voc")
    ds = open_dataset(tmp_path / "voc")
    assert ds.format == "voc" and len(ds.samples) == 30
    assert ds.samples[0].boxes and ds.samples[0].contributor
    export_imagefolder(records, tmp_path / "folder")
    ds2 = open_dataset(tmp_path / "folder")
    assert ds2.format == "imagefolder"
    assert set(ds2.classes) == {r.label for r in records}
    assert Capability.CONTRIBUTOR_METADATA not in ds2.capabilities("dataset")


def test_plain_directory_has_no_labels(tmp_path, records):
    export_imagefolder(records[:6], tmp_path / "tmp")
    flat = tmp_path / "flat"
    flat.mkdir()
    for p in (tmp_path / "tmp").rglob("*.png"):
        (flat / p.name).write_bytes(p.read_bytes())
    ds = open_dataset(flat)
    assert ds.format == "images"
    caps = ds.capabilities("dataset")
    assert Capability.DATASET_IMAGES in caps and Capability.DATASET_LABELS not in caps


def test_digest_is_stable_and_label_sensitive(tmp_path, records):
    write_corpus(records, tmp_path / "a", name="a")
    d1 = open_dataset(tmp_path / "a").digest
    assert open_dataset(tmp_path / "a").digest == d1
    lines = (tmp_path / "a" / "manifest.jsonl").read_text().splitlines()
    rec = json.loads(lines[0])
    rec["label"] = "aircraft" if rec["label"] != "aircraft" else "truck"
    lines[0] = json.dumps(rec)
    (tmp_path / "a" / "manifest.jsonl").write_text("\n".join(lines) + "\n")
    assert open_dataset(tmp_path / "a").digest != d1


def test_corrupt_and_missing_files_are_recorded_not_dropped(tmp_path, records):
    write_corpus(records, tmp_path / "c", name="c")
    target = tmp_path / "c" / records[0].id.join(["images/alpha/", ".png"])
    target.write_bytes(target.read_bytes()[:60])  # truncated PNG
    (tmp_path / "c" / "images" / "alpha" / f"{records[1].id}.png").unlink()
    ds = open_dataset(tmp_path / "c")
    assert len(ds.samples) == 30
    errors = {s.id: s.error_kind for s in ds.samples if s.error}
    assert errors == {records[0].id: "unreadable", records[1].id: "unreadable"}
    assert len(ds.readable) == 28


def test_decoded_images_are_rgb_uint8(tmp_path, records):
    write_corpus(records[:3], tmp_path / "d", name="d")
    ds = open_dataset(tmp_path / "d")
    img = ds.load(ds.samples[0], size=32)
    assert img.dtype == np.uint8 and img.shape == (32, 32, 3)
