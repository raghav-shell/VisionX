"""Reports never execute or load anything: every untrusted string is escaped; tampered evidence is refused."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

import pytest

from visionsentinel.attacklab.corpus import ContributorProfile, generate_contributor, write_corpus
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan
from visionsentinel.evidence import EvidenceStore
from visionsentinel.provenance.keys import generate_key, public_bytes
from visionsentinel.reporting import verify_manifest, write_report

XSS = '<script>alert("x")</script>'
IMG = '<img src=x onerror=alert(1)>'


@pytest.fixture(scope="module")
def hostile_scan(tmp_path_factory):
    root = tmp_path_factory.mktemp("hostile")
    recs = []
    for name in (XSS, IMG, "Alpha"):
        recs += generate_contributor(ContributorProfile(name, 30, "EO-A2", f"src {name}", session_size=10), seed=3)
    for r in recs[:30]:
        r.sensor = '"><svg onload=alert(2)>'
    import numpy as np
    from visionsentinel.attacklab import data_attacks as atk
    atk.duplicate_flood(recs, XSS, 2, 6, np.random.default_rng(0))
    write_corpus(recs, root / "ds", name=f"dataset {IMG}")
    ws = Workspace(root / "ws").ensure()
    result = run_scan(ScanRequest(dataset=root / "ds", name=f"scan {XSS}", profile="selftest"), workspace=ws)
    return result, ws, root


class _Elements(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, list[tuple[str, str | None]]]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))


def test_html_report_escapes_every_untrusted_string(hostile_scan):
    result, ws, root = hostile_scan
    paths = write_report(result, root / "out", EvidenceStore(ws.evidence))
    html = paths["report.html"].read_text()
    parser = _Elements()
    parser.feed(html)
    names = {t for t, _ in parser.tags}
    assert not names & {"script", "svg", "iframe", "object", "embed", "form", "link", "base"}
    for tag, attrs in parser.tags:
        for key, value in attrs:
            assert not key.startswith("on"), f"event handler attribute on <{tag}>"
            if key in ("src", "href"):
                assert (value or "").startswith("data:image/png;base64,"), f"<{tag} {key}={value!r}>"
    assert "&lt;script&gt;" in html and XSS not in html
    assert 'http-equiv="Content-Security-Policy"' in html and "default-src 'none'" in html
    assert re.search(r"https?://", html) is None, "the report must not reference any network resource"


def test_report_bundle_is_manifested_and_signable(hostile_scan):
    result, ws, root = hostile_scan
    key = generate_key()
    paths = write_report(result, root / "signed", EvidenceStore(ws.evidence), key)
    report_dir = paths["report.html"].parent
    assert verify_manifest(report_dir, public_bytes(key)) == []
    manifest = json.loads(paths["manifest.json"].read_text())
    assert {f["file"] for f in manifest["files"]} == {"report.json", "report.html", "coverage.md"}
    assert manifest["result_digest"] == result.report_digest
    paths["report.html"].write_text(paths["report.html"].read_text().replace("Assurance report", "All clear"))
    assert any("report.html" in p for p in verify_manifest(report_dir, public_bytes(key)))
    assert any("signature" in p for p in verify_manifest(report_dir, public_bytes(generate_key())))


def test_tampered_evidence_is_flagged_not_rendered(hostile_scan, tmp_path):
    result, ws, root = hostile_scan
    store = EvidenceStore(ws.evidence)
    blob = next(ev.blob for f in result.findings for ev in f.evidence if ev.blob and ev.blob.media_type == "image/png")
    path = store.path_for(blob.digest)
    original = path.read_bytes()
    try:
        path.write_bytes(original[:-8] + b"\x00" * 8)
        html = write_report(result, tmp_path, store)["report.html"].read_text()
        assert "EVIDENCE INTEGRITY FAILURE" in html
    finally:
        path.write_bytes(original)
