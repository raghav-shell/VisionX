"""Untrusted-input boundary: traversal, symlinks, XXE, bombs, oversize and malformed inputs."""

from __future__ import annotations

import io
import json
import os
import struct
import tarfile
import zipfile
import zlib

import numpy as np
import pytest
from PIL import Image

from visionsentinel.core.errors import LoaderError, ResourceLimitError, UnsafeInputError
from visionsentinel.core.limits import ResourceLimits
from visionsentinel.loaders.archives import extract_archive
from visionsentinel.loaders.datasets import open_dataset
from visionsentinel.loaders.images import load_image
from visionsentinel.loaders.safe_io import normalise_member_name, parse_json_bounded, resolve_within, safe_text


def _png(path, size=8):
    Image.fromarray(np.zeros((size, size, 3), np.uint8)).save(path)


def _manifest(root, entries):
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.jsonl").write_text("\n".join(json.dumps(e) for e in entries) + "\n")


@pytest.mark.parametrize("name", ["../etc/passwd", "a/../../b", "/etc/passwd", "C:\\Windows\\x", "..\\..\\x",
                                  "ok/\x00.png", "", "./../x"])
def test_member_names_are_confined(name):
    with pytest.raises(UnsafeInputError):
        normalise_member_name(name)


def test_manifest_traversal_is_rejected(tmp_path):
    _manifest(tmp_path / "ds", [{"file": "../../../../etc/hostname", "label": "truck"}])
    with pytest.raises(UnsafeInputError, match="traversal"):
        open_dataset(tmp_path / "ds")


def test_coco_absolute_filename_is_rejected(tmp_path):
    root = tmp_path / "coco"
    root.mkdir()
    (root / "annotations.json").write_text(json.dumps({"images": [{"id": 1, "file_name": "/etc/passwd"}],
                                                       "annotations": [], "categories": []}))
    with pytest.raises(UnsafeInputError, match="absolute"):
        open_dataset(root)


def test_symlink_escape_is_blocked(tmp_path):
    root = tmp_path / "ds"
    root.mkdir()
    outside = tmp_path / "secret.png"
    _png(outside)
    os.symlink(outside, root / "link.png")
    _png(root / "ok.png")
    _manifest(root, [{"file": "link.png", "label": "a"}, {"file": "ok.png", "label": "b"}])
    ds = open_dataset(root)
    link = next(s for s in ds.samples if s.rel_path == "link.png")
    assert link.error_kind == "unsafe" and "escapes" in link.error
    with pytest.raises(UnsafeInputError):
        resolve_within(root, "link.png")
    plain = tmp_path / "plain"
    plain.mkdir()
    _png(plain / "a.png")
    os.symlink(outside, plain / "b.png")
    with pytest.raises(UnsafeInputError):
        open_dataset(plain)


def test_dataset_root_symlink_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    _png(real / "a.png")
    os.symlink(real, tmp_path / "alias")
    with pytest.raises(UnsafeInputError):
        open_dataset(tmp_path / "alias")


XXE = """<?xml version="1.0"?>
<!DOCTYPE annotation [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<annotation><filename>a.png</filename><object><name>&xxe;</name>
<bndbox><xmin>1</xmin><ymin>1</ymin><xmax>4</xmax><ymax>4</ymax></bndbox></object></annotation>"""

LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>
<annotation><filename>&lol3;</filename></annotation>"""


@pytest.mark.parametrize("payload", [XXE, LAUGHS], ids=["xxe", "billion-laughs"])
def test_voc_xml_attacks_are_rejected(tmp_path, payload):
    root = tmp_path / "voc"
    (root / "Annotations").mkdir(parents=True)
    (root / "JPEGImages").mkdir()
    _png(root / "JPEGImages" / "a.png")
    (root / "Annotations" / "a.xml").write_text(payload)
    with pytest.raises(UnsafeInputError, match="forbidden XML"):
        open_dataset(root)


def test_oversized_and_deep_json_rejected():
    limits = ResourceLimits(max_json_bytes=1000, max_json_depth=20)
    with pytest.raises(ResourceLimitError):
        parse_json_bounded(b"[" + b"1," * 600 + b"1]", limits)
    with pytest.raises(ResourceLimitError):
        parse_json_bounded(b"[" * 50 + b"]" * 50, limits)
    with pytest.raises(ResourceLimitError):
        parse_json_bounded(b"[" * 100000 + b"]" * 100000, ResourceLimits(max_json_bytes=10**6))
    with pytest.raises(LoaderError):
        parse_json_bounded(b'{"a": NaN}', limits)


def _png_header_only(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 16)) + chunk(b"IEND", b"")


def test_decompression_bomb_rejected_before_decoding(tmp_path):
    p = tmp_path / "bomb.png"
    p.write_bytes(_png_header_only(60000, 60000))
    with pytest.raises(ResourceLimitError):
        load_image(p, ResourceLimits())


def test_svg_disguised_as_png_rejected(tmp_path):
    p = tmp_path / "evil.png"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>')
    with pytest.raises(UnsafeInputError, match="SVG"):
        load_image(p, ResourceLimits())


def test_oversized_file_rejected(tmp_path):
    p = tmp_path / "big.png"
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (64, 64, 3), dtype=np.uint8)).save(p)
    with pytest.raises(ResourceLimitError):
        load_image(p, ResourceLimits(max_file_bytes=100))


def _zip(path, members: dict[str, bytes], symlink: str | None = None):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
        if symlink:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (0o120777 << 16)
            zf.writestr(info, "/etc/passwd")


def test_zip_slip_rejected_and_cleaned(tmp_path):
    arc = tmp_path / "slip.zip"
    _zip(arc, {"ok.txt": b"x", "../../evil.txt": b"pwned"})
    with pytest.raises(UnsafeInputError):
        extract_archive(arc, tmp_path / "out", ResourceLimits())
    assert not (tmp_path / "out").exists()
    assert not (tmp_path.parent / "evil.txt").exists()


def test_zip_symlink_member_rejected(tmp_path):
    arc = tmp_path / "link.zip"
    _zip(arc, {"ok.txt": b"x"}, symlink="link")
    with pytest.raises(UnsafeInputError, match="symbolic link"):
        extract_archive(arc, tmp_path / "out", ResourceLimits())


def test_zip_bomb_rejected(tmp_path):
    arc = tmp_path / "bomb.zip"
    _zip(arc, {"zeros.bin": b"\x00" * (8 * 1024 * 1024)})
    with pytest.raises(ResourceLimitError, match="compression ratio"):
        extract_archive(arc, tmp_path / "out", ResourceLimits())


def test_tar_link_and_absolute_rejected(tmp_path):
    arc = tmp_path / "evil.tar"
    with tarfile.open(arc, "w") as tf:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)
    with pytest.raises(UnsafeInputError):
        extract_archive(arc, tmp_path / "out", ResourceLimits())
    arc2 = tmp_path / "abs.tar"
    with tarfile.open(arc2, "w") as tf:
        data = b"x"
        info = tarfile.TarInfo("/tmp/abs.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    with pytest.raises(UnsafeInputError):
        extract_archive(arc2, tmp_path / "out2", ResourceLimits())


def test_valid_archive_extracts(tmp_path):
    arc = tmp_path / "ok.zip"
    _zip(arc, {"a/b.txt": b"hello"})
    names = extract_archive(arc, tmp_path / "out", ResourceLimits())
    assert names == ["a/b.txt"] and (tmp_path / "out" / "a" / "b.txt").read_bytes() == b"hello"


def test_yolo_yaml_with_python_tags_rejected(tmp_path):
    root = tmp_path / "yolo"
    (root / "images").mkdir(parents=True)
    _png(root / "images" / "a.png")
    (root / "data.yaml").write_text("names: !!python/object/apply:os.system ['echo pwned']\n")
    with pytest.raises(LoaderError):
        open_dataset(root)


def test_metadata_text_is_sanitised():
    assert safe_text("Delta\x1b[31m\r\n<script>") == "Delta[31m<script>"
    assert len(safe_text("x" * 1000, 64)) == 64
