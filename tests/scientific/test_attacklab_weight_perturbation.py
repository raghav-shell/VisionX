from __future__ import annotations

import pytest

from visionsentinel.attacklab import model_attacks, runner
from visionsentinel.attacklab.runner import load_scenario
from visionsentinel.attacklab.training import DEMO_PREPROCESS
from visionsentinel.core.workspace import Workspace
from visionsentinel.loaders.models import open_model


def test_manifest_target_is_present_and_perturbation_is_deterministic(model_zoo, tmp_path):
    manifest = load_scenario("modified_weights")
    targets = manifest.attack["target_parameters"]
    reference = model_attacks.load(model_zoo["approved"])

    first = model_attacks.perturb_weights(reference, targets, manifest.attack["noise_scale"],
                                          seed=manifest.seed)
    second = model_attacks.perturb_weights(reference, targets, manifest.attack["noise_scale"],
                                           seed=manifest.seed)
    first_path = model_attacks.save(first, tmp_path / "first.onnx", DEMO_PREPROCESS)
    second_path = model_attacks.save(second, tmp_path / "second.onnx", DEMO_PREPROCESS)
    reference_path = model_zoo["approved"]
    original = open_model(reference_path)
    first_handle = open_model(first_path)
    second_handle = open_model(second_path)
    try:
        assert first_handle.artifact_digest == second_handle.artifact_digest
        assert first_handle.param_digest == second_handle.param_digest
        assert original.artifact_digest != first_handle.artifact_digest
        assert original.param_digest != first_handle.param_digest
    finally:
        second_handle.close()
        first_handle.close()
        original.close()


def test_invalid_target_parameter_is_rejected(model_zoo):
    reference = model_attacks.load(model_zoo["approved"])
    with pytest.raises(ValueError, match="absent from the model"):
        model_attacks.perturb_weights(reference, ["not-a-real-parameter"], 0.15, seed=17)


def test_weight_perturbation_runs_as_an_ordinary_scan(tmp_path):
    manifest = load_scenario("modified_weights")
    result = runner.run_scenario(manifest, Workspace(tmp_path / "workspace").ensure())

    assert result.generation_succeeded
    assert result.scan_executed
    assert result.scan_result is not None
    assert result.evaluation_status.value == "detector_success"
    assert result.overall_disposition == manifest.expected["expected_disposition"]
    assert result.findings_count >= manifest.expected["expected_min_findings"]
    assert set(manifest.expected["expected_detectors"]) <= set(result.detected_detectors)

    perturbation = result.details["perturbation"]
    assert perturbation["changed_parameters"] == manifest.attack["target_parameters"]
    assert perturbation["original_target_digests"] != perturbation["tampered_target_digests"]
    assert result.details["reference_model"]["artifact_digest"] != result.details["candidate_model"]["artifact_digest"]
    assert result.details["reference_model"]["param_digest"] != result.details["candidate_model"]["param_digest"]
    assert result.scan_result.executions
    assert result.scan_result.findings
