from __future__ import annotations

from pathlib import Path

from visionsentinel.attacklab import runner
from visionsentinel.attacklab.runner import load_scenario
from visionsentinel.core.workspace import Workspace


def test_ledger_tampering_is_a_real_post_signature_edit(tmp_path):
    manifest = load_scenario("ledger_tamper")
    result = runner.run_scenario(manifest, Workspace(tmp_path / "workspace").ensure())

    assert result.generation_succeeded
    assert result.scan_executed
    assert result.scan_result is not None
    assert result.evaluation_status.value == "detector_success"
    assert result.overall_disposition == manifest.expected["expected_disposition"]
    assert result.findings_count >= manifest.expected["expected_min_findings"]
    assert set(manifest.expected["expected_detectors"]) <= set(result.detected_detectors)

    ledger = result.details["ledger"]
    tampering = result.details["tampering"]
    assert ledger["clean_intact"] is True
    assert ledger["tampered_intact"] is False
    assert ledger["clean_digest"] != ledger["tampered_digest"]
    assert tampering["target_sequence"] == manifest.attack["target_sequence"]
    assert tampering["field"] == manifest.attack["tampered_field"]
    assert tampering["original_value"] != tampering["new_value"]
    assert tampering["signature_preserved"] is True
    assert tampering["verification_status"] != "VALID"
    assert tampering["verification_classes"]

    asset_paths = {asset.path for asset in result.scan_result.assets}
    assert ledger["tampered_path"] in asset_paths
    assert ledger["trust_root_path"] in asset_paths
    assert Path(ledger["anchor_path"]).is_file()
    assert Path(ledger["inputs_path"]).is_dir()
    assert not any(str(path).endswith(".pem") for path in asset_paths)


def test_invalid_ledger_target_is_generation_failure(tmp_path):
    manifest = load_scenario("ledger_tamper").model_copy(deep=True)
    manifest.attack["target_sequence"] = manifest.base["records_count"] + 100

    result = runner.run_scenario(manifest, Workspace(tmp_path / "workspace").ensure())

    assert not result.generation_succeeded
    assert not result.scan_executed
    assert result.evaluation_status.value == "generation_failed"
    assert "target sequence" in result.evaluation_notes[0]
