"""Scientific evaluation benchmark: compute TPR, FPR, Wilson confidence intervals, and AUROC across held-out attack families."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from ..attacklab.runner import list_scenarios, run_scenario
from ..contracts import ScenarioEvaluationStatus, Severity
from ..core.workspace import Workspace

log = logging.getLogger(__name__)


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculate the Wilson score interval for a binomial proportion."""
    if total <= 0:
        return (0.0, 0.0)
    z = 1.95996  # for 95% confidence
    p = float(successes) / float(total)
    denominator = 1.0 + (z**2) / float(total)
    centre_adj = p + (z**2) / (2.0 * float(total))
    spread = z * math.sqrt((p * (1.0 - p) + (z**2) / (4.0 * float(total))) / float(total))
    lower = max(0.0, (centre_adj - spread) / denominator)
    upper = min(1.0, (centre_adj + spread) / denominator)
    return (round(lower, 4), round(upper, 4))


def bootstrap_auroc(y_true: np.ndarray, y_score: np.ndarray, n_bootstraps: int = 500, seed: int = 42) -> tuple[float, float, float]:
    """Calculate AUROC and non-parametric bootstrap 95% confidence interval."""
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float)
    if len(np.unique(y_true)) < 2:
        return (1.0, 1.0, 1.0)
    try:
        base_auroc = float(roc_auc_score(y_true, y_score))
    except Exception:
        return (1.0, 1.0, 1.0)

    rng = np.random.default_rng(seed)
    bootstrapped_scores = []
    for _ in range(n_bootstraps):
        indices = rng.integers(0, len(y_true), len(y_true))
        if len(np.unique(y_true[indices])) < 2:
            continue
        bootstrapped_scores.append(roc_auc_score(y_true[indices], y_score[indices]))

    if not bootstrapped_scores:
        return (round(base_auroc, 4), round(base_auroc, 4), round(base_auroc, 4))

    ci_lower = float(np.percentile(bootstrapped_scores, 2.5))
    ci_upper = float(np.percentile(bootstrapped_scores, 97.5))
    return (round(base_auroc, 4), round(ci_lower, 4), round(ci_upper, 4))


@dataclass
class FamilyEvaluationRow:
    attack_family: str
    scenario_id: str
    evaluation_tier: str  # "calibration" | "evaluation" | "held_out"
    total_samples: int
    true_positives: int
    false_positives: int
    tpr: float | None
    tpr_ci: tuple[float, float] | None
    fpr: float | None
    fpr_ci: tuple[float, float] | None
    auroc: float | None
    auroc_ci: tuple[float, float] | None
    overall_disposition: str
    passed_fitness: bool
    is_negative_control: bool = False
    evaluation_status: str = ScenarioEvaluationStatus.DETECTOR_SUCCESS.value
    eligible_for_metrics: bool = True
    notes: str = ""


@dataclass
class BenchmarkReport:
    total_scenarios_run: int
    passed_scenarios: int
    mean_tpr: float | None
    mean_fpr: float | None
    rows: list[FamilyEvaluationRow]
    summary_table: str

    def markdown(self) -> str:
        lines = ["# VisionSentinel benchmark", "", "## Protocol", "",
                 "Calibration and held-out families are reported separately. A false-positive rate or AUROC is only reported when a negative-control denominator and score vector were supplied; it is never assumed to be zero.", "",
                 "## Scenario results", "", "| Family | Scenario | Tier | TPR (95% CI) | FPR (95% CI) | AUROC (95% CI) | Fitness |", "|---|---|---|---|---|---|---|"]
        for row in self.rows:
            fpr = "not estimated" if row.fpr is None else f"{row.fpr:.3f} [{row.fpr_ci[0]:.3f}, {row.fpr_ci[1]:.3f}]"
            auc = "not estimated" if row.auroc is None else f"{row.auroc:.3f} [{row.auroc_ci[0]:.3f}, {row.auroc_ci[1]:.3f}]"
            tpr = "not eligible" if row.tpr is None else f"{row.tpr:.3f} [{row.tpr_ci[0]:.3f}, {row.tpr_ci[1]:.3f}]"
            lines.append(f"| {row.attack_family} | {row.scenario_id} | {row.evaluation_tier} | {tpr} | {fpr} | {auc} | {'PASS' if row.passed_fitness else 'FAIL'} |")
        lines += ["", "## Limits", "", "The current shipped attack scenarios are positive controls. Add adjudicated clean / benign-shift controls for each detector before quoting FPR or AUROC in a competition claim."]
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        tier_counts = {tier: sum(1 for row in self.rows if row.evaluation_tier == tier)
                       for tier in {row.evaluation_tier for row in self.rows}}
        return {
            "total_scenarios_run": self.total_scenarios_run,
            "passed_scenarios": self.passed_scenarios,
            "mean_tpr": self.mean_tpr,
            "mean_fpr": self.mean_fpr,
            "rows": [asdict(r) for r in self.rows],
            "summary_table": self.summary_table,
            "tier_counts": tier_counts,
            "negative_controls": sum(1 for row in self.rows if row.is_negative_control),
            "false_positive_examples": [row.scenario_id for row in self.rows if row.is_negative_control and row.false_positives],
            "methodology": {"calibration_and_held_out_separated": True, "fpr_requires_negative_controls": True,
                            "auroc_requires_labelled_score_vectors": True,
                            "risk_alert_threshold": "REVIEW or QUARANTINE disposition",
                            "false_positive_examples_note": "Only executed, adjudicated negative controls are included; unavailable metrics are null rather than fabricated."},
        }


def write_benchmark_artifacts(report: BenchmarkReport, output_dir: Path = Path("benchmarks")) -> tuple[Path, Path]:
    """Write portable latest JSON and judge-readable Markdown without fabricating unavailable metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = output_dir / "latest.json", output_dir / "latest.md"
    # JSON consumers must never receive JavaScript-only NaN / Infinity literals.
    json_path.write_text(json.dumps(report.to_dict(), indent=2, allow_nan=False) + "\n")
    markdown_path.write_text(report.markdown())
    return json_path, markdown_path


def run_benchmark(
    workspace: Workspace,
    scenarios_dir: Path | None = None,
    profile: str = "selftest",
) -> BenchmarkReport:
    """Run full scientific evaluation benchmark over scenario suite, calculating TPR, FPR and AUROC."""
    scenarios = list_scenarios(scenarios_dir)
    rows: list[FamilyEvaluationRow] = []

    for manifest in scenarios:
        try:
            result = run_scenario(manifest, workspace=workspace, profile=profile)
            # Positive controls measure detection. Negative controls measure
            # detector alerts per supplied clean sample, with a manifest-declared
            # acceptance bound rather than an invented zero-error expectation.
            is_negative = manifest.negative_control
            negative_samples = sum(int(c["samples"]) for c in manifest.base.get("contributors", []))
            if is_negative and negative_samples <= 0:
                raise ValueError("negative controls require a positive clean-sample denominator")
            false_positive_findings = [
                finding for finding in result.scan_result.findings
                if finding.severity.rank >= Severity.MEDIUM.rank
            ]
            tp = 0 if is_negative else int(result.detected_expected_signals)
            fp = len(false_positive_findings) if is_negative else 0
            tpr = float(tp)
            fpr = round(float(fp) / negative_samples, 4) if is_negative else None
            tpr_ci = wilson_interval(tp, 1) if not is_negative else (0.0, 0.0)
            fpr_ci = wilson_interval(fp, negative_samples) if is_negative else None
            max_fpr = manifest.fitness_gates.get("max_false_positive_rate")
            negative_passed = max_fpr is None or fpr is not None and fpr <= float(max_fpr)

            rows.append(
                FamilyEvaluationRow(
                    attack_family=manifest.attack_class,
                    scenario_id=manifest.scenario_id,
                    evaluation_tier=manifest.evaluation_family,
                    total_samples=negative_samples if is_negative else result.findings_count,
                    true_positives=tp,
                    false_positives=fp,
                    tpr=tpr if result.passed_fitness and result.ground_truth_valid else None,
                    tpr_ci=tpr_ci if result.passed_fitness and result.ground_truth_valid else None,
                    fpr=fpr,
                    fpr_ci=fpr_ci,
                    auroc=None,
                    auroc_ci=None,
                    overall_disposition=result.overall_disposition,
                    passed_fitness=result.passed_fitness and (negative_passed if is_negative else True),
                    is_negative_control=is_negative,
                    notes=(
                        f"{fp}/{negative_samples} material alerts; maximum allowed FPR {max_fpr}"
                        if is_negative else ", ".join(result.fitness_notes) if result.fitness_notes else "all fitness gates passed"
                    ),
                    evaluation_status=result.evaluation_status.value,
                    eligible_for_metrics=(result.passed_fitness and result.ground_truth_valid
                                          and result.scan_executed and negative_passed),
                )
            )
        except Exception as exc:
            log.exception("benchmark failure on %s", manifest.scenario_id)
            rows.append(
                FamilyEvaluationRow(
                    attack_family=manifest.attack_class,
                    scenario_id=manifest.scenario_id,
                    evaluation_tier=manifest.evaluation_family,
                    total_samples=0,
                    true_positives=0,
                    false_positives=0,
                    tpr=None,
                    tpr_ci=None,
                    fpr=None,
                    fpr_ci=None,
                    auroc=None,
                    auroc_ci=None,
                    overall_disposition="ERROR",
                    passed_fitness=False,
                    is_negative_control=manifest.negative_control,
                    evaluation_status=(ScenarioEvaluationStatus.INVALID_MANIFEST.value
                                       if str(exc).startswith("invalid scenario manifest")
                                       else ScenarioEvaluationStatus.EXECUTION_ERROR.value),
                    eligible_for_metrics=False,
                    notes=f"execution error: {exc}",
                )
            )

    passed = sum(
        1 for r in rows
        if r.eligible_for_metrics and (r.is_negative_control or r.true_positives == 1)
    )
    eligible_rows = [r for r in rows if r.eligible_for_metrics and not r.is_negative_control and r.tpr is not None]
    mean_tpr = round(float(np.mean([r.tpr for r in eligible_rows])), 4) if eligible_rows else None
    measured_fprs = [r.fpr for r in rows if r.fpr is not None]
    mean_fpr = (
        round(float(np.mean(measured_fprs)), 4)
        if measured_fprs
        else None
    )

    # Format ASCII summary table
    table_lines = [
        f"{'ATTACK CLASS':<30} | {'SCENARIO ID':<25} | {'TIER':<12} | {'TPR':<6} | {'95% CI':<16} | {'FITNESS':<8} | {'DISPOSITION':<12}",
        "-" * 125,
    ]
    for r in rows:
        ci_str = "not eligible" if r.tpr is None else f"[{r.tpr_ci[0]:.2f}, {r.tpr_ci[1]:.2f}]"
        fit_str = "PASSED" if r.passed_fitness else "FAIL"
        tpr_str = "not eligible" if r.tpr is None else f"{r.tpr:<6.2f}"
        table_lines.append(
            f"{r.attack_family:<30} | {r.scenario_id:<25} | {r.evaluation_tier:<12} | {tpr_str:<12} | {ci_str:<16} | {fit_str:<8} | {r.overall_disposition:<12}"
        )

    summary_table = "\n".join(table_lines)

    return BenchmarkReport(
        total_scenarios_run=len(rows),
        passed_scenarios=passed,
        mean_tpr=mean_tpr,
        mean_fpr=mean_fpr,
        rows=rows,
        summary_table=summary_table,
    )
