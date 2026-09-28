"""End-to-end protected inference: keys → trust root → signed inference → verify → tamper → scan."""

from __future__ import annotations

import json

import pytest

from visionsentinel.attacklab.corpus import generate_clean_set, write_corpus
from visionsentinel.cli.main import main
from visionsentinel.contracts import CoverageState, Disposition, Severity
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan


@pytest.fixture()
def protected(model_zoo, tmp_path, capsys):
    key = tmp_path / "keys" / "ledger.pem"
    assert main(["keys", "generate", "--out", str(key), "--roles", "ledger,anchor"]) == 0
    trust = tmp_path / "trust.json"
    assert main(["trust-root", "init", "--out", str(trust), "--key", str(key),
                 "--approve-model", str(model_zoo["approved"])]) == 0
    write_corpus(generate_clean_set(24, 77, "ops"), tmp_path / "ops", name="ops")
    ledger, anchor = tmp_path / "ledger.jsonl", tmp_path / "anchors.jsonl"
    assert main(["infer", "--model", str(model_zoo["approved"]), "--inputs", str(tmp_path / "ops" / "images"),
                 "--ledger", str(ledger), "--key", str(key), "--anchor", str(anchor), "--checkpoint-every", "8"]) == 0
    capsys.readouterr()
    return {"trust": trust, "ledger": ledger, "anchor": anchor, "inputs": tmp_path / "ops" / "images", "root": tmp_path}


def test_cli_verify_intact_then_tampered(protected, capsys):
    args = ["verify", str(protected["ledger"]), "--trust-root", str(protected["trust"]), "--anchor",
            str(protected["anchor"]), "--inputs", str(protected["inputs"])]
    assert main(args) == 0
    assert "LEDGER INTACT" in capsys.readouterr().out
    lines = protected["ledger"].read_text().splitlines()
    rec = json.loads(lines[5])
    rec["body"]["output"]["label"] = "aircraft" if rec["body"]["output"]["label"] != "aircraft" else "vessel"
    lines[5] = json.dumps(rec)
    protected["ledger"].write_text("\n".join(lines) + "\n")
    assert main(args) == 1
    assert "Record 5: FAILED" in capsys.readouterr().out
    assert main(["verify", "--ledger", str(protected["ledger"]), "--trust-root", str(protected["trust"])]) == 1


def test_scan_reports_verified_ledger_and_full_provenance_coverage(protected, tmp_path):
    r = run_scan(ScanRequest(ledger=protected["ledger"], trust_root=protected["trust"], anchor=protected["anchor"],
                             inference_inputs=protected["inputs"], profile="selftest"),
                 workspace=Workspace(tmp_path / "ws").ensure())
    integrity = next(f for f in r.findings if f.detector_id == "provenance.ledger_integrity")
    assert integrity.severity == Severity.INFO and integrity.recommended_disposition == Disposition.ACCEPT
    binding = next(f for f in r.findings if f.detector_id == "provenance.binding")
    assert binding.severity == Severity.INFO
    rows = {row.attack_class: row.state for row in r.coverage.rows}
    for cls in ("record_modification", "record_deletion", "record_reorder", "record_replay", "record_truncation",
                "signature_forgery", "model_binding_violation", "input_substitution"):
        assert rows[cls] == CoverageState.ASSESSED, cls
    assert rows["signing_key_compromise"] == CoverageState.UNSUPPORTED
    assert r.sections["provenance.ledger_integrity"]["ledger"]["intact"] is True


def test_scan_quarantines_a_tampered_ledger_and_withholds_truncation_without_anchor(protected, tmp_path):
    lines = protected["ledger"].read_text().splitlines()
    del lines[6]
    protected["ledger"].write_text("\n".join(lines) + "\n")
    r = run_scan(ScanRequest(ledger=protected["ledger"], trust_root=protected["trust"], profile="selftest"),
                 workspace=Workspace(tmp_path / "ws").ensure())
    bad = [f for f in r.findings if f.detector_id == "provenance.ledger_integrity" and f.severity != Severity.INFO]
    assert bad and all(f.recommended_disposition == Disposition.QUARANTINE for f in bad)
    assert any(f.attack_class == "record_deletion" for f in bad)
    assert all(f.severity == Severity.CRITICAL for f in bad)
    rows = {row.attack_class: row for row in r.coverage.rows}
    assert rows["record_truncation"].state == CoverageState.NOT_ASSESSED
    assert "does not assess this class" in rows["record_truncation"].reason
    assert any("anchor" in e for e in rows["record_truncation"].recommended_evidence)
    assert r.summary.overall_disposition == Disposition.QUARANTINE
