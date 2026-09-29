"""Benchmark artefacts are strict JSON and only report FPR from real controls."""

from __future__ import annotations

import json

from visionsentinel.attacklab.runner import load_scenario
from visionsentinel.evaluation.benchmark import BenchmarkReport, FamilyEvaluationRow, write_benchmark_artifacts


def test_clean_baseline_is_declared_as_a_negative_control():
    scenario = load_scenario("clean_baseline")
    assert scenario.negative_control is True
    assert scenario.attack["type"] == "clean_dataset"
    assert scenario.expected["expected_detectors"] == []


def test_benchmark_json_uses_null_for_unmeasured_fpr(tmp_path):
    row = FamilyEvaluationRow(
        attack_family="label_flip", scenario_id="positive-only", evaluation_tier="evaluation",
        total_samples=1, true_positives=1, false_positives=0, tpr=1.0, tpr_ci=(0.2, 1.0),
        fpr=None, fpr_ci=None, auroc=None, auroc_ci=None, overall_disposition="REVIEW", passed_fitness=True,
    )
    report = BenchmarkReport(1, 1, 1.0, None, [row], "summary")
    json_path, _ = write_benchmark_artifacts(report, tmp_path)
    raw = json_path.read_text()
    assert "NaN" not in raw and "Infinity" not in raw
    assert json.loads(raw)["mean_fpr"] is None
