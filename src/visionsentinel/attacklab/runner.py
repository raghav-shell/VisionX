"""Attack Lab scenario loader, orchestrator, and fitness gate evaluator."""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..contracts import Disposition, ScanResult, Severity
from ..core.determinism import rng_for
from ..core.workspace import Workspace
from ..engine.request import ScanRequest
from ..engine.scan import run_scan
from .corpus import ContributorProfile, generate_clean_set, generate_contributor, write_corpus
from .data_attacks import (
    duplicate_flood,
    label_flip_random,
    label_flip_targeted,
    stamp,
    systematic_mislabel,
    trigger_pattern,
)
from .drift_attacks import operational_batch
from .synthetic import CLASSES

log = logging.getLogger(__name__)


class ScenarioManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scenario_id: str
    title: str
    attack_class: str
    description: str
    seed: int = 42
    evaluation_family: str = "evaluation"
    base: dict[str, Any] = Field(default_factory=dict)
    attack: dict[str, Any] = Field(default_factory=dict)
    fitness_gates: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)


@dataclass
class ScenarioRunResult:
    scenario_id: str
    title: str
    attack_class: str
    passed_fitness: bool
    detected_expected_signals: bool
    scan_id: str
    overall_disposition: str
    findings_count: int
    critical_count: int
    review_count: int
    detected_detectors: list[str]
    missing_detectors: list[str]
    fitness_notes: list[str]
    report_digest: str
    details: dict[str, Any] = field(default_factory=dict)
    scan_result: ScanResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "attack_class": self.attack_class,
            "passed_fitness": self.passed_fitness,
            "detected_expected_signals": self.detected_expected_signals,
            "scan_id": self.scan_id,
            "overall_disposition": self.overall_disposition,
            "findings_count": self.findings_count,
            "critical_count": self.critical_count,
            "review_count": self.review_count,
            "detected_detectors": self.detected_detectors,
            "missing_detectors": self.missing_detectors,
            "fitness_notes": self.fitness_notes,
            "report_digest": self.report_digest,
            "details": self.details,
        }


def list_scenarios(scenarios_dir: Path | None = None) -> list[ScenarioManifest]:
    s_dir = scenarios_dir or (Path(__file__).resolve().parents[3] / "scenarios")
    if not s_dir.is_dir():
        return []
    manifests: list[ScenarioManifest] = []
    for p in sorted(s_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if data and isinstance(data, dict) and "scenario_id" in data:
                manifests.append(ScenarioManifest.model_validate(data))
        except Exception as exc:
            log.warning("failed to parse scenario %s: %s", p, exc)
    return manifests


def load_scenario(path_or_id: str | Path, scenarios_dir: Path | None = None) -> ScenarioManifest:
    p = Path(path_or_id)
    if p.is_file():
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return ScenarioManifest.model_validate(data)
    s_dir = scenarios_dir or (Path(__file__).resolve().parents[3] / "scenarios")
    for s in list_scenarios(s_dir):
        if s.scenario_id == str(path_or_id):
            return s
    candidate = s_dir / f"{path_or_id}.yaml"
    if candidate.is_file():
        data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        return ScenarioManifest.model_validate(data)
    raise FileNotFoundError(f"scenario {path_or_id!r} not found")


def run_scenario(
    manifest: ScenarioManifest,
    workspace: Workspace,
    *,
    profile: str = "selftest",
) -> ScenarioRunResult:
    """Execute a controlled attack scenario, evaluate fitness gates, run scan and report detection performance."""
    run_dir = workspace.root / "attack_runs" / f"{manifest.scenario_id}_{secrets.token_hex(4)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    seed = manifest.seed
    rng = rng_for(seed, "scenario", manifest.scenario_id)

    scan_req = ScanRequest(name=f"AttackLab: {manifest.title}", profile=profile)
    truth_records = []
    fitness_notes: list[str] = []
    passed_fitness = True

    # 1. Dataset Generation & Attack Injection
    if manifest.attack.get("type") in ("label_flip_targeted", "label_flip_random", "systematic_mislabel",
                                       "duplicate_flood", "patch_poison"):
        contrib_confs = manifest.base.get("contributors", [
            {"name": "Alpha", "samples": 80, "sensor": "EO-A2", "source": "f1"},
            {"name": "Bravo", "samples": 80, "sensor": "EO-B1", "source": "f2"},
            {"name": "Charlie", "samples": 80, "sensor": "UAV-C3", "source": "f3"},
            {"name": "Delta", "samples": 80, "sensor": "SAT-D4", "source": "f4"},
        ])
        records = []
        for c in contrib_confs:
            p = ContributorProfile(
                name=c["name"],
                samples=c["samples"],
                sensor=c.get("sensor", "EO-A2"),
                source=c.get("source", "field"),
            )
            records.extend(generate_contributor(p, seed=seed + hash(c["name"]) % 10000))

        # Apply specific attack
        att = manifest.attack
        att_type = att["type"]
        affected_ids = []

        if att_type == "label_flip_targeted":
            affected_ids = label_flip_targeted(
                records,
                source=att.get("source_class", "armoured_vehicle"),
                target=att.get("target_class", "civilian_vehicle"),
                rate=att.get("rate", 0.3),
                rng=rng,
                contributor=att.get("contributor"),
            )
        elif att_type == "systematic_mislabel":
            affected_ids = systematic_mislabel(
                records,
                contributor=att.get("contributor", "Charlie"),
                mapping=att.get("mapping", {"air_defence": "civilian_aircraft"}),
                fraction=att.get("fraction", 0.7),
                rng=rng,
            )
        elif att_type == "duplicate_flood":
            affected_ids = duplicate_flood(
                records,
                contributor=att.get("contributor", "Delta"),
                n_sources=att.get("clusters", 3),
                copies=att.get("copies_per_cluster", 8),
                rng=rng,
            )
        elif att_type == "patch_poison":
            c_name = att.get("contributor", "Delta")
            t_kind = att.get("trigger_kind", "checker")
            t_size = att.get("trigger_size", 6)
            pos = att.get("position", "bottom-right")
            tgt = att.get("target_class", "naval_vessel")
            p_count = att.get("poison_count", 20)

            pat = trigger_pattern(t_kind, t_size, seed=seed)
            cand = [r for r in records if r.contributor == c_name]
            chosen = rng.choice(len(cand), size=min(p_count, len(cand)), replace=False)
            for idx in chosen:
                r = cand[idx]
                r.image = stamp(r.image, pat, pos)
                r.label = tgt
                r.truth.append("localized_trigger")
                affected_ids.append(r.id)

        # Fitness gate check
        min_aff = manifest.fitness_gates.get("expected_affected_min", 1)
        if len(affected_ids) < min_aff:
            passed_fitness = False
            fitness_notes.append(f"affected samples ({len(affected_ids)}) < min required ({min_aff})")

        ds_path = run_dir / "dataset"
        write_corpus(records, ds_path, name=f"{manifest.scenario_id}_attacked")
        scan_req.dataset = ds_path

        # Add clean reference for kNN & OOF
        ref_records = generate_clean_set(160, seed=seed + 777, label="ref")
        ref_path = run_dir / "reference"
        write_corpus(ref_records, ref_path, name="clean_reference")
        scan_req.reference_dataset = ref_path

    # 2. Drift Attack Injection
    elif manifest.attack.get("type") in ("illumination_shift", "semantic_shift"):
        ref_records = generate_clean_set(manifest.base.get("reference_size", 120), seed=seed, label="ref")
        
        if manifest.attack["type"] == "illumination_shift":
            op_records = operational_batch(
                manifest.base.get("operational_size", 120),
                seed=seed + 100,
                shift="low_light",
                label="ops_illum",
            )
        else:
            op_records = operational_batch(
                manifest.base.get("operational_size", 120),
                seed=seed + 100,
                class_weights=manifest.attack.get("class_weights", {"naval_vessel": 4.0}),
                label="ops_sem",
            )

        ref_path = run_dir / "reference_drift"
        op_path = run_dir / "incoming_drift"
        write_corpus(ref_records, ref_path, name="clean_reference_drift")
        write_corpus(op_records, op_path, name="incoming_operational_drift")
        scan_req.reference_dataset = ref_path
        scan_req.operational_data = op_path

    # Execute Scan
    scan_result: ScanResult = run_scan(scan_req, workspace=workspace)

    # Check detector responses against expected
    detected_detectors = [e.detector_id for e in scan_result.executions if e.findings > 0]
    expected_detectors = manifest.expected.get("expected_detectors", [])
    missing_detectors = [d for d in expected_detectors if d not in detected_detectors]
    detected_expected_signals = len(missing_detectors) == 0

    return ScenarioRunResult(
        scenario_id=manifest.scenario_id,
        title=manifest.title,
        attack_class=manifest.attack_class,
        passed_fitness=passed_fitness,
        detected_expected_signals=detected_expected_signals,
        scan_id=scan_result.scan_id,
        overall_disposition=scan_result.summary.overall_disposition.value if scan_result.summary else "REVIEW",
        findings_count=len(scan_result.findings),
        critical_count=sum(1 for f in scan_result.findings if f.severity == Severity.CRITICAL),
        review_count=sum(1 for f in scan_result.findings if f.recommended_disposition == Disposition.REVIEW),
        detected_detectors=detected_detectors,
        missing_detectors=missing_detectors,
        fitness_notes=fitness_notes,
        report_digest=scan_result.report_digest,
        details={"executions": [e.model_dump(mode="json") for e in scan_result.executions]},
        scan_result=scan_result,
    )
