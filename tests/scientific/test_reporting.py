"""Report content: all fifteen sections, coverage statement honesty, scan comparison."""

from __future__ import annotations

import json

from visionsentinel.contracts import CoverageState
from visionsentinel.evidence import EvidenceStore
from visionsentinel.reporting import compare_scans, coverage_markdown, write_report

SECTIONS = ["Executive assurance summary", "Assets assessed", "Access assumptions", "Capability plan", "Findings",
            "Contributor assessment", "Model integrity", "Provenance state", "Drift assessment", "Coverage",
            "Unsupported and unassessed", "Known limitations", "Reproduction metadata", "Tool and software versions",
            "Cryptographic report digest"]


def test_report_contains_every_section_and_is_offline(attacked_scan, tmp_path):
    result, ws, _ = attacked_scan
    paths = write_report(result, tmp_path, EvidenceStore(ws.evidence))
    html = paths["report.html"].read_text()
    for i, title in enumerate(SECTIONS, start=1):
        assert f"{i} · {title}" in html, title
    assert "does <b>not</b> certify" in html
    doc = json.loads(paths["report.json"].read_text())
    assert doc["schema"] == "visionsentinel/report/v1" and doc["result"]["scan_id"] == result.scan_id


def test_report_never_claims_unassessed_classes_were_assessed(attacked_scan):
    result, _, _ = attacked_scan
    md = coverage_markdown(result)
    for row in result.coverage.rows:
        if row.state != CoverageState.ASSESSED:
            assert f"`{row.attack_class}`) — {row.state.value.replace('_', ' ').lower()}" in md
            if row.state == CoverageState.UNSUPPORTED:
                assert row.reason in md
    executed = {e.detector_id for e in result.executions if e.state.value.startswith("COMPLETED")}
    for row in result.coverage.rows:
        if row.state == CoverageState.ASSESSED:
            assert set(row.detectors) & executed


def test_compare_explains_the_difference(clean_scan, attacked_scan):
    clean, _ = clean_scan
    attacked, _, _ = attacked_scan
    diff = compare_scans(clean, attacked)
    assert diff["new_findings"] and any(c["contributor"] == "Delta" for c in diff["contributor_changes"])
    assert any(c["role"] == "DATASET" and c["status"] == "changed" for c in diff["asset_changes"])
    assert diff["summary"]["overall"][0] != diff["summary"]["overall"][1] or diff["new_findings"]
    same = compare_scans(attacked, attacked)
    assert not same["new_findings"] and not same["resolved_findings"] and same["explanation"] == ["no material change"]
