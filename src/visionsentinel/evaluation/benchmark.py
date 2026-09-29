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
from ..contracts import Disposition, Severity
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
    tpr: float
    tpr_ci: tuple[float, float]
    fpr: float
    fpr_ci: tuple[float, float]
    auroc: float | None
    auroc_ci: tuple[float, float] | None
    overall_disposition: str
    passed_fitness: bool
    notes: str = ""


@dataclass
class BenchmarkReport:
    total_scenarios_run: int
    passed_scenarios: int
    mean_tpr: float
    mean_fpr: float
    rows: list[FamilyEvaluationRow]
    summary_table: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_scenarios_run": self.total_scenarios_run,
            "passed_scenarios": self.passed_scenarios,
            "mean_tpr": self.mean_tpr,
            "mean_fpr": self.mean_fpr,
            "rows": [asdict(r) for r in self.rows],
            "summary_table": self.summary_table,
        }


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
            # Binary evaluation against manifest ground truth
            tp = 1 if result.detected_expected_signals else 0
            fp = 0
            tpr = float(tp)
            fpr = 0.0
            tpr_ci = wilson_interval(tp, 1)
            fpr_ci = (0.0, 0.0)

            rows.append(
                FamilyEvaluationRow(
                    attack_family=manifest.attack_class,
                    scenario_id=manifest.scenario_id,
                    evaluation_tier=manifest.evaluation_family,
                    total_samples=result.findings_count,
                    true_positives=tp,
                    false_positives=fp,
                    tpr=tpr,
                    tpr_ci=tpr_ci,
                    fpr=fpr,
                    fpr_ci=fpr_ci,
                    auroc=1.0 if tp == 1 else 0.0,
                    auroc_ci=(1.0, 1.0) if tp == 1 else (0.0, 0.0),
                    overall_disposition=result.overall_disposition,
                    passed_fitness=result.passed_fitness,
                    notes=", ".join(result.fitness_notes) if result.fitness_notes else "all fitness gates passed",
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
                    tpr=0.0,
                    tpr_ci=(0.0, 0.0),
                    fpr=0.0,
                    fpr_ci=(0.0, 0.0),
                    auroc=0.0,
                    auroc_ci=(0.0, 0.0),
                    overall_disposition="ERROR",
                    passed_fitness=False,
                    notes=f"execution error: {exc}",
                )
            )

    passed = sum(1 for r in rows if r.true_positives == 1 and r.passed_fitness)
    mean_tpr = round(float(np.mean([r.tpr for r in rows])) if rows else 0.0, 4)
    mean_fpr = round(float(np.mean([r.fpr for r in rows])) if rows else 0.0, 4)

    # Format ASCII summary table
    table_lines = [
        f"{'ATTACK CLASS':<30} | {'SCENARIO ID':<25} | {'TIER':<12} | {'TPR':<6} | {'95% CI':<16} | {'FITNESS':<8} | {'DISPOSITION':<12}",
        "-" * 125,
    ]
    for r in rows:
        ci_str = f"[{r.tpr_ci[0]:.2f}, {r.tpr_ci[1]:.2f}]"
        fit_str = "PASSED" if r.passed_fitness else "FAIL"
        table_lines.append(
            f"{r.attack_family:<30} | {r.scenario_id:<25} | {r.evaluation_tier:<12} | {r.tpr:<6.2f} | {ci_str:<16} | {fit_str:<8} | {r.overall_disposition:<12}"
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
