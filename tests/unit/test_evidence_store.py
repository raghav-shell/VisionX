from __future__ import annotations

import numpy as np
import pytest

from visionsentinel.core.errors import EvidenceIntegrityError, UnsafeInputError
from visionsentinel.evidence import EvidenceStore, GraphBuilder, neighbourhood
from visionsentinel.evidence.render import contact_sheet, heatmap, overlay_region


def test_content_addressing_is_idempotent_and_verified(tmp_path):
    store = EvidenceStore(tmp_path)
    ref1 = store.put_json({"b": 2, "a": 1})
    ref2 = store.put_json({"a": 1, "b": 2})
    assert ref1.digest == ref2.digest  # canonical JSON → identical content → one blob
    assert store.get(ref1.digest) == b'{"a":1,"b":2}'
    assert store.media_type(ref1.digest) == "application/json"


def test_tampered_evidence_is_never_returned(tmp_path):
    store = EvidenceStore(tmp_path)
    ref = store.put_png(np.zeros((4, 4, 3), dtype=np.uint8))
    path = store.path_for(ref.digest)
    data = bytearray(path.read_bytes())
    data[-5] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(EvidenceIntegrityError, match="altered"):
        store.get(ref.digest)
    assert store.verify(ref.digest) is False


@pytest.mark.parametrize("digest", ["../../etc/passwd", "sha256:../../x", "sha256:" + "g" * 64, "md5:abc"])
def test_digest_addresses_cannot_traverse(tmp_path, digest):
    with pytest.raises(UnsafeInputError):
        EvidenceStore(tmp_path).path_for(digest)


def test_only_generated_formats_are_accepted(tmp_path):
    store = EvidenceStore(tmp_path)
    with pytest.raises(UnsafeInputError):
        store.put_bytes(b"<svg onload=alert(1)></svg>", "image/svg+xml")
    with pytest.raises(UnsafeInputError):
        store.put_bytes(b"<html><script>x</script></html>", "application/json")


def test_renderers_produce_uint8_rgb():
    imgs = [np.random.default_rng(i).integers(0, 255, (16, 16, 3), dtype=np.uint8) for i in range(5)]
    sheet = contact_sheet(imgs, borders=["flag", "ok", "neutral", "warn", "info"], tile=32, columns=3)
    assert sheet.dtype == np.uint8 and sheet.ndim == 3 and sheet.shape[2] == 3
    hm = heatmap(np.arange(16).reshape(4, 4), cell=4)
    assert hm.shape == (16, 16, 3)
    ov = overlay_region(imgs[0], 2, 2, 6, 6, scale=2)
    assert ov.shape == (32, 32, 3)


def test_graph_neighbourhood():
    g = GraphBuilder()
    g.node("c", "Contributor", "Delta")
    g.node("s", "Sample", "s1")
    g.node("f", "Finding", "F1")
    g.node("x", "Sample", "unrelated")
    g.edge("s", "c", "SUPPLIED_BY")
    g.edge("s", "f", "FLAGGED_BY")
    sub = neighbourhood(g.build(), "f", depth=2)
    assert {n.id for n in sub.nodes} == {"c", "s", "f"}
