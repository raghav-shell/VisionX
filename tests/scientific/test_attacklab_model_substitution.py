from __future__ import annotations

import json

import numpy as np

from visionsentinel.attacklab import runner
from visionsentinel.attacklab.runner import load_scenario, validate_manifest
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.registry import default_registry
from visionsentinel.engine.request import ScanRequest


def test_model_substitution_manifest_uses_live_registry():
    manifest = load_scenario("model_swap")

    assert manifest.attack["type"] == "model_substitution"
    assert validate_manifest(manifest) == []
    registered = set(default_registry().ids())
    assert set(manifest.expected["expected_detectors"]) <= registered


def test_model_substitution_runs_with_real_assets_and_external_truth(tmp_path):
    manifest = load_scenario("model_swap")
    result = runner.run_scenario(manifest, Workspace(tmp_path / "workspace").ensure())

    assert result.generation_succeeded
    assert result.scan_executed
    assert result.scan_result is not None
    assert result.evaluation_status.value == "detector_success"
    assert result.overall_disposition == manifest.expected["expected_disposition"]
    assert result.findings_count >= manifest.expected["expected_min_findings"]
    assert len(result.missing_detectors) == 0

    reference = result.details["reference_model"]
    candidate = result.details["candidate_model"]
    assert reference["artifact_digest"] != candidate["artifact_digest"]
    assert reference["param_digest"] != candidate["param_digest"]
    assert result.details["probe_comparison"]["affected_count"] >= manifest.fitness_gates["expected_affected_min"]

    assert (tmp_path / "workspace" / "attack_runs").is_dir()
    attack_runs = tmp_path / "workspace" / "attack_runs"
    assert any(attack_runs.glob("*/candidate.onnx"))
    assert any(attack_runs.glob("*/reference.onnx"))
    assert any(attack_runs.glob("*/probe/manifest.jsonl"))
    assert result.details["probe_dataset"]
    assert any(asset.path == result.details["probe_dataset"] for asset in result.scan_result.assets)


def test_model_substitution_artifacts_are_deterministic(tmp_path):
    manifest = load_scenario("model_swap")
    first_request = ScanRequest()
    second_request = ScanRequest()
    first_records, first_affected, first_details = runner._model_substitution(
        manifest, tmp_path / "first", first_request
    )
    second_records, second_affected, second_details = runner._model_substitution(
        manifest, tmp_path / "second", second_request
    )

    assert first_affected == second_affected
    assert [record.id for record in first_records] == [record.id for record in second_records]
    assert first_details["reference_model"]["artifact_digest"] == second_details["reference_model"]["artifact_digest"]
    assert first_details["candidate_model"]["artifact_digest"] == second_details["candidate_model"]["artifact_digest"]
    assert first_details["reference_model"]["param_digest"] == second_details["reference_model"]["param_digest"]
    assert first_details["candidate_model"]["param_digest"] == second_details["candidate_model"]["param_digest"]
    truth = json.loads((tmp_path / "first" / "probe.truth.json").read_text())
    assert any(manifest.attack_class in row["attacks"] for row in truth.values())
    manifest_rows = (tmp_path / "first" / "probe" / "manifest.jsonl").read_text().splitlines()
    assert all("attacks" not in row and "truth" not in row for row in manifest_rows)
    assert first_request.model is not None and first_request.reference_model is not None
    assert first_request.probe_dataset is not None
    assert np.isfinite(first_details["probe_comparison"]["mean_probability_delta"])


def test_malformed_model_generation_is_classified_as_generation_failure(tmp_path, monkeypatch):
    manifest = load_scenario("model_swap")

    def fail_generation(*args, **kwargs):
        raise ValueError("malformed generated model")

    monkeypatch.setattr(runner, "train_model", fail_generation)
    result = runner.run_scenario(manifest, Workspace(tmp_path / "workspace").ensure())

    assert not result.generation_succeeded
    assert not result.scan_executed
    assert result.evaluation_status.value == "generation_failed"
    assert "malformed generated model" in result.evaluation_notes[0]
