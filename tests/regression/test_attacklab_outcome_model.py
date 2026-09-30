"""The Attack Lab runner exposes one typed outcome for every scientific run stage."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np

from visionsentinel.attacklab.corpus import Record
from visionsentinel.attacklab.runner import GeneratorSpec, ScenarioManifest, run_scenario
from visionsentinel.attacklab import runner
from visionsentinel.contracts import ScenarioEvaluationStatus
from visionsentinel.core.workspace import Workspace


def _manifest(**overrides) -> ScenarioManifest:
    data = {
        "scenario_id": "outcome-" + str(id(overrides)),
        "title": "Outcome contract test",
        "attack_class": "synthetic",
        "description": "test manifest",
        "attack": {"type": "outcome_test"},
        "fitness_gates": {"min_samples": 1},
        "expected": {"truth_tag": "synthetic"},
    }
    data.update(overrides)
    return ScenarioManifest.model_validate(data)


def _record() -> Record:
    return Record(
        id="outcome-record",
        image=np.zeros((4, 4, 3), dtype=np.uint8),
        label="class",
        true_label="class",
        contributor=None,
        batch=None,
        source="test",
        sensor=None,
        timestamp=None,
        bbox=None,
        truth=["synthetic"],
    )


def _scan_result(findings=None):
    return SimpleNamespace(
        scan_id="scan-outcome",
        report_digest="digest",
        executions=[],
        findings=findings or [],
        summary=None,
    )


def test_runner_returns_canonical_outcomes_without_scanning_invalid_or_unfit_runs(tmp_path, monkeypatch):
    calls = []

    def generator(manifest, workspace, run_dir, scan_req, rng):
        return [_record()], ["outcome-record"], {}

    monkeypatch.setitem(runner.GENERATOR_REGISTRY, "outcome_test", GeneratorSpec("outcome_test", "test", generator))
    monkeypatch.setattr(runner, "run_scan", lambda *args, **kwargs: calls.append(True) or _scan_result())

    invalid = _manifest(expected={"unsupported": True})
    invalid_result = run_scenario(invalid, Workspace(tmp_path / "invalid"))
    assert invalid_result.evaluation_status is ScenarioEvaluationStatus.INVALID_MANIFEST
    assert not invalid_result.manifest_valid

    unfit = _manifest(fitness_gates={"min_samples": 2})
    unfit_result = run_scenario(unfit, Workspace(tmp_path / "unfit"))
    assert unfit_result.evaluation_status is ScenarioEvaluationStatus.FITNESS_FAILED
    assert not unfit_result.scan_executed
    assert not calls


def test_runner_distinguishes_generation_execution_and_detector_outcomes(tmp_path, monkeypatch):
    manifest = _manifest()
    monkeypatch.setitem(
        runner.GENERATOR_REGISTRY,
        "outcome_test",
        GeneratorSpec("outcome_test", "test", lambda *args: (_ for _ in ()).throw(ValueError("bad artifact"))),
    )
    generated = run_scenario(manifest, Workspace(tmp_path / "generation"))
    assert generated.evaluation_status is ScenarioEvaluationStatus.GENERATION_FAILED
    assert "bad artifact" in generated.evaluation_notes[0]

    def generator(manifest, workspace, run_dir, scan_req, rng):
        return [_record()], ["outcome-record"], {}

    monkeypatch.setitem(runner.GENERATOR_REGISTRY, "outcome_test", GeneratorSpec("outcome_test", "test", generator))
    monkeypatch.setattr(runner, "run_scan", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("backend unavailable")))
    execution = run_scenario(manifest, Workspace(tmp_path / "execution"))
    assert execution.evaluation_status is ScenarioEvaluationStatus.EXECUTION_ERROR
    assert execution.generation_succeeded
    assert execution.ground_truth_valid
    assert not execution.scan_executed

    monkeypatch.setattr(runner, "run_scan", lambda *args, **kwargs: _scan_result())
    miss_manifest = _manifest(expected={"truth_tag": "synthetic", "expected_min_findings": 1})
    miss = run_scenario(miss_manifest, Workspace(tmp_path / "miss"))
    assert miss.evaluation_status is ScenarioEvaluationStatus.DETECTOR_MISS
    assert miss.scan_executed

    success = run_scenario(manifest, Workspace(tmp_path / "success"))
    assert success.evaluation_status is ScenarioEvaluationStatus.DETECTOR_SUCCESS
    assert success.scan_executed
    json.dumps(success.to_dict(), allow_nan=False)
