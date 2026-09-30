"""Attack Lab scenario loader, orchestrator, and fitness gate evaluator."""

from __future__ import annotations

import json
import io
import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..contracts import Disposition, ScanResult, ScenarioEvaluationStatus, Severity
from ..core.determinism import derive_seed, rng_for
from ..core.hashing import sha256_digest, sha256_file
from ..core.workspace import Workspace
from ..engine.request import ScanRequest
from ..loaders.models import open_model
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
from . import model_attacks
from ..provenance.inference import InferenceRecorder
from ..provenance.canonical import canonical_bytes
from ..provenance.ledger import LedgerWriter
from ..provenance.trust import load_trust_root
from ..provenance.verifier import verify_ledger
from ..provenance.workspace_keys import ensure_keys
from .training import DEMO_PREPROCESS, save_onnx, train_model

log = logging.getLogger(__name__)


class ScenarioManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    title: str
    attack_class: str
    description: str
    seed: int = 42
    evaluation_family: str = "evaluation"
    negative_control: bool = False
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
    manifest_valid: bool = True
    generation_succeeded: bool = True
    ground_truth_valid: bool = True
    scan_executed: bool = True
    finding_expectation_satisfied: bool = True
    policy_expectation_satisfied: bool = True
    evaluation_status: ScenarioEvaluationStatus = ScenarioEvaluationStatus.DETECTOR_SUCCESS
    evaluation_notes: list[str] = field(default_factory=list)
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
            "manifest_valid": self.manifest_valid,
            "generation_succeeded": self.generation_succeeded,
            "ground_truth_valid": self.ground_truth_valid,
            "scan_executed": self.scan_executed,
            "finding_expectation_satisfied": self.finding_expectation_satisfied,
            "policy_expectation_satisfied": self.policy_expectation_satisfied,
            "evaluation_status": self.evaluation_status.value,
            "evaluation_notes": self.evaluation_notes,
            "details": self.details,
        }


def validate_manifest(manifest: ScenarioManifest, registry=None) -> list[str]:
    """Validate one manifest against the live detector registry and generator contract."""
    from ..engine.registry import default_registry

    registry = registry or default_registry()
    errors: list[str] = []
    attack_type = manifest.attack.get("type")
    generator = GENERATOR_REGISTRY.get(attack_type)
    if generator is None:
        errors.append(f"unsupported attack generator {attack_type!r}")
    elif not callable(generator.handler):
        errors.append(f"attack generator {attack_type!r} has no executable handler")
    detector_ids = set(registry.ids())
    for detector_id in manifest.expected.get("expected_detectors", []):
        if detector_id not in detector_ids:
            errors.append(f"expected detector {detector_id!r} is not registered")
    allowed_expected = {"truth_tag", "expected_detectors", "expected_min_findings", "expected_disposition"}
    errors.extend(f"unsupported expected field {key!r}" for key in set(manifest.expected) - allowed_expected)
    allowed_fitness = {"min_samples", "expected_affected_min", "max_false_positive_rate", "min_probability_delta"}
    errors.extend(f"unsupported fitness field {key!r}" for key in set(manifest.fitness_gates) - allowed_fitness)
    expected_disposition = manifest.expected.get("expected_disposition")
    if expected_disposition is not None:
        try:
            Disposition(expected_disposition)
        except ValueError:
            errors.append(f"unsupported expected disposition {expected_disposition!r}")
    return errors


def validate_scenarios(scenarios_dir: Path | None = None) -> list[ScenarioManifest]:
    """Parse every scenario file and reject duplicates, stale detectors, and unsupported generators."""
    s_dir = scenarios_dir or (Path(__file__).resolve().parents[3] / "scenarios")
    manifests: list[ScenarioManifest] = []
    errors: list[str] = []
    for path in sorted(s_dir.glob("*.yaml")):
        try:
            manifest = ScenarioManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            errors.extend(f"{path.name}: {error}" for error in validate_manifest(manifest))
            manifests.append(manifest)
        except Exception as exc:
            errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    seen: set[str] = set()
    for manifest in manifests:
        if manifest.scenario_id in seen:
            errors.append(f"duplicate scenario id {manifest.scenario_id!r}")
        seen.add(manifest.scenario_id)
    if errors:
        raise ValueError("scenario validation failed: " + "; ".join(errors))
    return manifests


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


def _model_substitution(
    manifest: ScenarioManifest,
    run_dir: Path,
    scan_req: ScanRequest,
) -> tuple[list, list[str], dict[str, Any]]:
    """Build and verify the candidate/reference pair declared by a model-substitution manifest."""
    base = manifest.base
    attack = manifest.attack
    seed = manifest.seed
    architecture = base["architecture"]
    class_names = list(base.get("class_names", DEMO_PREPROCESS.class_names))
    cfg = DEMO_PREPROCESS.model_copy(update={"class_names": class_names})
    training_samples = int(base["training_samples"])
    probe_size = int(base["probe_size"])
    epochs = int(attack["training_epochs"])
    threads = int(attack["training_threads"])
    batch = int(attack["batch_size"])
    learning_rate = float(attack["learning_rate"])
    label_mapping = dict(attack["label_mapping"])
    unknown = (set(label_mapping) | set(label_mapping.values())) - set(class_names)
    if unknown:
        raise ValueError(f"model substitution label mapping contains unknown classes: {sorted(unknown)}")

    train_records = generate_clean_set(training_samples, derive_seed(seed, "model", "training"), label="model_train")
    try:
        reference_labels = np.asarray([class_names.index(record.label) for record in train_records], dtype=np.int64)
        candidate_labels = np.asarray([class_names.index(label_mapping[record.label]) for record in train_records],
                                      dtype=np.int64)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"model substitution label mapping does not cover generated classes: {exc}") from exc
    images = np.stack([record.image for record in train_records])

    reference, reference_report = train_model(
        images, reference_labels, seed=derive_seed(seed, "model", "reference"), epochs=epochs,
        lr=learning_rate, batch=batch, cfg=cfg, threads=threads, architecture=architecture,
    )
    candidate, candidate_report = train_model(
        images, candidate_labels, seed=derive_seed(seed, "model", "candidate"), epochs=epochs,
        lr=learning_rate, batch=batch, cfg=cfg, threads=threads, architecture=architecture,
    )
    reference_path = save_onnx(reference, run_dir / "reference.onnx", cfg, architecture=architecture,
                                doc=f"Attack Lab reference generated from scenario {manifest.scenario_id}")
    candidate_path = save_onnx(candidate, run_dir / "candidate.onnx", cfg, architecture=architecture,
                               doc=f"Attack Lab substituted candidate generated from scenario {manifest.scenario_id}")

    probe_records = generate_clean_set(probe_size, derive_seed(seed, "model", "probe"), label="model_probe")
    probe_images = np.stack([record.image for record in probe_records])
    reference_handle = open_model(reference_path)
    candidate_handle = open_model(candidate_path)
    try:
        reference_probs = reference_handle.predict_proba(probe_images)
        candidate_probs = candidate_handle.predict_proba(probe_images)
        reference_predictions = reference_probs.argmax(axis=1)
        candidate_predictions = candidate_probs.argmax(axis=1)
        deltas = np.max(np.abs(candidate_probs - reference_probs), axis=1)
        min_delta = float(manifest.fitness_gates["min_probability_delta"])
        changed = (candidate_predictions != reference_predictions) | (deltas >= min_delta)
        affected_ids = [record.id for record, is_changed in zip(probe_records, changed) if is_changed]
        for record, is_changed in zip(probe_records, changed):
            if is_changed:
                record.truth.append(manifest.attack_class)
        details = {
            "architecture": architecture,
            "reference_model": {"path": str(reference_path), "artifact_digest": reference_handle.artifact_digest,
                                 "param_digest": reference_handle.param_digest},
            "candidate_model": {"path": str(candidate_path), "artifact_digest": candidate_handle.artifact_digest,
                                 "param_digest": candidate_handle.param_digest},
            "training": {"reference_accuracy": reference_report.train_accuracy,
                          "candidate_accuracy": candidate_report.train_accuracy},
            "probe_comparison": {"probe_count": len(probe_records), "affected_count": len(affected_ids),
                                  "max_probability_delta": float(deltas.max()),
                                  "mean_probability_delta": float(deltas.mean()),
                                  "min_probability_delta": min_delta},
        }
    finally:
        candidate_handle.close()
        reference_handle.close()

    probe_path = run_dir / "probe"
    write_corpus(probe_records, probe_path, name=f"{manifest.scenario_id}_probe", classes=tuple(class_names))
    details["probe_dataset"] = str(probe_path)
    scan_req.model = candidate_path
    scan_req.reference_model = reference_path
    scan_req.probe_dataset = probe_path
    scan_req.architecture = architecture
    return probe_records, affected_ids, details


def _model_weight_perturbation(
    manifest: ScenarioManifest,
    run_dir: Path,
    scan_req: ScanRequest,
) -> tuple[list, list[str], dict[str, Any]]:
    """Generate a clean model, perturb manifest-selected parameters, and verify the tampering."""
    base = manifest.base
    attack = manifest.attack
    seed = manifest.seed
    architecture = base["architecture"]
    class_names = list(base.get("class_names", DEMO_PREPROCESS.class_names))
    cfg = DEMO_PREPROCESS.model_copy(update={"class_names": class_names})
    train_records = generate_clean_set(int(base["training_samples"]), derive_seed(seed, "weights", "training"),
                                       label="weight_train")
    labels = np.asarray([class_names.index(record.label) for record in train_records], dtype=np.int64)
    images = np.stack([record.image for record in train_records])
    reference, training_report = train_model(
        images, labels, seed=derive_seed(seed, "weights", "reference"), epochs=int(attack["training_epochs"]),
        lr=float(attack["learning_rate"]), batch=int(attack["batch_size"]), cfg=cfg,
        threads=int(attack["training_threads"]), architecture=architecture,
    )
    reference_path = save_onnx(reference, run_dir / "reference.onnx", cfg, architecture=architecture,
                                doc=f"Attack Lab reference generated from scenario {manifest.scenario_id}")
    reference_proto = model_attacks.load(reference_path)
    targets = list(attack["target_parameters"])
    available = {initializer.name for initializer in reference_proto.graph.initializer}
    missing = [target for target in targets if target not in available]
    if missing:
        raise ValueError(f"requested perturbation parameters are absent from the model: {missing}")
    original_target_digests = {
        initializer.name: sha256_digest(np.ascontiguousarray(model_attacks.numpy_helper.to_array(initializer)).tobytes())
        for initializer in reference_proto.graph.initializer if initializer.name in targets
    }
    perturbation_seed = derive_seed(seed, "weights", "perturbation", *targets)
    candidate_proto = model_attacks.perturb_weights(
        reference_proto, targets, float(attack["noise_scale"]), seed=perturbation_seed,
    )
    candidate_path = model_attacks.save(candidate_proto, run_dir / "candidate.onnx", cfg)
    candidate_proto_check = model_attacks.load(candidate_path)
    tampered_target_digests = {
        initializer.name: sha256_digest(np.ascontiguousarray(model_attacks.numpy_helper.to_array(initializer)).tobytes())
        for initializer in candidate_proto_check.graph.initializer if initializer.name in targets
    }
    changed_targets = [target for target in targets if original_target_digests[target] != tampered_target_digests[target]]
    if not changed_targets:
        raise ValueError("weight perturbation did not change any requested parameter")

    reference_handle = open_model(reference_path)
    candidate_handle = open_model(candidate_path)
    try:
        reference_param_digest = reference_handle.param_digest
        candidate_param_digest = candidate_handle.param_digest
        if reference_param_digest == candidate_param_digest:
            raise ValueError("weight perturbation left the canonical model parameter digest unchanged")
        probe_records = generate_clean_set(int(base["probe_size"]), derive_seed(seed, "weights", "probe"),
                                           label="weight_probe")
        probe_images = np.stack([record.image for record in probe_records])
        reference_probs = reference_handle.predict_proba(probe_images)
        candidate_probs = candidate_handle.predict_proba(probe_images)
        behavior_delta = np.max(np.abs(candidate_probs - reference_probs), axis=1)
        behavior_changed = int(np.count_nonzero(behavior_delta >= float(attack["min_probability_delta"])))
        details = {
            "architecture": architecture,
            "reference_model": {"path": str(reference_path), "artifact_digest": reference_handle.artifact_digest,
                                 "param_digest": reference_param_digest},
            "candidate_model": {"path": str(candidate_path), "artifact_digest": candidate_handle.artifact_digest,
                                 "param_digest": candidate_param_digest},
            "training_accuracy": training_report.train_accuracy,
            "perturbation": {"target_parameters": targets, "changed_parameters": changed_targets,
                              "noise_scale": float(attack["noise_scale"]),
                              "seed_derivation": ["manifest.seed", "weights", "perturbation", *targets],
                              "derived_seed": perturbation_seed,
                              "original_target_digests": original_target_digests,
                              "tampered_target_digests": tampered_target_digests},
            "probe_comparison": {"probe_count": len(probe_records), "behavior_changed_count": behavior_changed,
                                  "max_probability_delta": float(behavior_delta.max()),
                                  "mean_probability_delta": float(behavior_delta.mean()),
                                  "min_probability_delta": float(attack["min_probability_delta"])},
            "ground_truth_tags": [manifest.attack_class],
        }
    finally:
        candidate_handle.close()
        reference_handle.close()

    probe_path = run_dir / "probe"
    write_corpus(probe_records, probe_path, name=f"{manifest.scenario_id}_probe", classes=tuple(class_names))
    details["probe_dataset"] = str(probe_path)
    scan_req.model = candidate_path
    scan_req.reference_model = reference_path
    scan_req.probe_dataset = probe_path
    scan_req.architecture = architecture
    return probe_records, changed_targets, details


def _ledger_record_tampering(
    manifest: ScenarioManifest,
    workspace: Workspace,
    run_dir: Path,
    scan_req: ScanRequest,
) -> tuple[list, list[str], dict[str, Any]]:
    """Create a real signed ledger, verify it, then edit one signed record without re-signing it."""
    base = manifest.base
    attack = manifest.attack
    seed = manifest.seed
    architecture = base["architecture"]
    class_names = list(base.get("class_names", DEMO_PREPROCESS.class_names))
    cfg = DEMO_PREPROCESS.model_copy(update={"class_names": class_names})
    training_records = generate_clean_set(int(base["training_samples"]), derive_seed(seed, "ledger", "training"),
                                          label="ledger_train")
    labels = np.asarray([class_names.index(record.label) for record in training_records], dtype=np.int64)
    images = np.stack([record.image for record in training_records])
    model, training_report = train_model(
        images, labels, seed=derive_seed(seed, "ledger", "model"), epochs=int(base["training_epochs"]),
        lr=float(base["learning_rate"]), batch=int(base["batch_size"]), cfg=cfg,
        threads=int(base["training_threads"]), architecture=architecture,
    )
    model_path = save_onnx(model, run_dir / base["model_filename"], cfg, architecture=architecture,
                           doc=f"Attack Lab model for scenario {manifest.scenario_id}")
    model_handle = open_model(model_path)
    keys = ensure_keys(workspace)
    ledger_path = run_dir / base["ledger_filename"]
    anchor_path = run_dir / base["anchor_filename"]
    inputs_path = run_dir / base["inputs_directory"]
    inputs_path.mkdir(parents=True, exist_ok=True)
    writer = LedgerWriter(ledger_path, keys.ledger, purpose=base["ledger_purpose"],
                          checkpoint_every=int(base["checkpoint_interval"]), anchor_path=anchor_path)
    recorder = InferenceRecorder(model_handle, writer, inference_config=base["inference_config"])
    records = generate_clean_set(int(base["records_count"]), derive_seed(seed, "ledger", "records"), label="ledger")
    try:
        for record in records:
            buffer = io.BytesIO()
            from PIL import Image
            Image.fromarray(record.image).save(buffer, format=base["input_format"])
            data = buffer.getvalue()
            name = f"{record.id}.{base['input_extension']}"
            (inputs_path / name).write_bytes(data)
            recorder.record(data, name, record.image)
        writer.checkpoint()
    finally:
        model_handle.close()

    trust = load_trust_root(keys.trust_root)
    clean_report = verify_ledger(ledger_path, trust, anchors=anchor_path, inputs=inputs_path)
    if not clean_report.intact:
        raise ValueError("generated clean ledger failed verification before tampering")

    records_json = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    target_sequence = int(attack["target_sequence"])
    target = next((record for record in records_json if record.get("seq") == target_sequence), None)
    if target is None:
        raise ValueError(f"ledger target sequence {target_sequence} was not generated")
    field_path = str(attack["tampered_field"]).split(".")
    container: Any = target
    for part in field_path[:-1]:
        if not isinstance(container, dict) or part not in container:
            raise ValueError(f"ledger tamper path {attack['tampered_field']!r} is absent")
        container = container[part]
    if not isinstance(container, dict) or field_path[-1] not in container:
        raise ValueError(f"ledger tamper path {attack['tampered_field']!r} is absent")
    original_value = container[field_path[-1]]
    original_signature = target["sig"]
    container[field_path[-1]] = attack["new_value"]
    if container[field_path[-1]] == original_value:
        raise ValueError("ledger tampering did not change the declared field")

    tampered_path = run_dir / base["tampered_ledger_filename"]
    tampered_path.write_bytes(b"".join(canonical_bytes(record) + b"\n" for record in records_json))
    tampered_report = verify_ledger(tampered_path, trust, anchors=anchor_path, inputs=inputs_path)
    failed = next((record for record in tampered_report.records if record.seq == target_sequence), None)
    if tampered_report.intact or failed is None or failed.status == "VALID":
        raise ValueError("tampered ledger remained cryptographically valid")
    clean_digest = sha256_file(ledger_path)
    tampered_digest = sha256_file(tampered_path)
    if clean_digest == tampered_digest:
        raise ValueError("tampering did not change the ledger digest")
    tampered_record = next(record for record in records_json if record.get("seq") == target_sequence)
    details = {
        "model": {"path": str(model_path), "training_accuracy": training_report.train_accuracy},
        "ledger": {"clean_path": str(ledger_path), "tampered_path": str(tampered_path),
                    "clean_digest": clean_digest, "tampered_digest": tampered_digest,
                    "trust_root_path": str(keys.trust_root), "anchor_path": str(anchor_path),
                    "inputs_path": str(inputs_path), "clean_intact": clean_report.intact,
                    "tampered_intact": tampered_report.intact},
        "tampering": {"target_sequence": target_sequence, "field": attack["tampered_field"],
                       "original_value": original_value, "new_value": attack["new_value"],
                       "signature_preserved": tampered_record["sig"] == original_signature,
                       "verification_status": failed.status, "verification_classes": failed.classes},
        "ground_truth_tags": [manifest.attack_class],
    }
    scan_req.ledger = tampered_path
    scan_req.trust_root = keys.trust_root
    scan_req.anchor = anchor_path
    scan_req.inference_inputs = inputs_path
    return records, [str(target_sequence)], details


GeneratorResult = tuple[list, list[str], dict[str, Any]]
GeneratorHandler = Callable[[ScenarioManifest, Workspace, Path, ScanRequest, np.random.Generator], GeneratorResult]


def _generate_clean_dataset(manifest: ScenarioManifest, workspace: Workspace, run_dir: Path,
                            scan_req: ScanRequest, rng: np.random.Generator) -> GeneratorResult:
    del workspace, rng
    contributors = manifest.base.get("contributors", [])
    if not contributors:
        raise ValueError("clean negative controls require declared contributors")
    records = []
    for contributor in contributors:
        profile = ContributorProfile(contributor["name"], contributor["samples"],
                                     contributor["sensor"], contributor["source"])
        records.extend(generate_contributor(profile, seed=derive_seed(manifest.seed, "contributor", contributor["name"])))
    dataset_path = run_dir / "dataset"
    write_corpus(records, dataset_path, name=f"{manifest.scenario_id}_clean")
    scan_req.dataset = dataset_path
    reference_records = generate_clean_set(manifest.base.get("reference_size", len(records)),
                                            seed=derive_seed(manifest.seed, "reference"), label="ref")
    reference_path = run_dir / "reference"
    write_corpus(reference_records, reference_path, name="clean_reference")
    scan_req.reference_dataset = reference_path
    return records, [], {}


def _generate_dataset_attack(manifest: ScenarioManifest, workspace: Workspace, run_dir: Path,
                             scan_req: ScanRequest, rng: np.random.Generator) -> GeneratorResult:
    del workspace
    base = manifest.base
    attack = manifest.attack
    contributors = base.get("contributors", [])
    if not contributors:
        raise ValueError("dataset generators require declared contributors")
    records = []
    for contributor in contributors:
        profile = ContributorProfile(contributor["name"], contributor["samples"],
                                     contributor["sensor"], contributor["source"])
        records.extend(generate_contributor(profile, seed=derive_seed(manifest.seed, "contributor", contributor["name"])))

    attack_type = attack["type"]
    if attack_type == "label_flip_targeted":
        affected_ids = label_flip_targeted(records, source=attack["source_class"], target=attack["target_class"],
                                           rate=attack["rate"], rng=rng, contributor=attack.get("contributor"))
    elif attack_type == "label_flip_random":
        classes = tuple(attack.get("classes", base.get("classes", sorted({record.label for record in records}))))
        affected_ids = label_flip_random(records, rate=attack["rate"], rng=rng, classes=classes,
                                         contributor=attack.get("contributor"))
    elif attack_type == "systematic_mislabel":
        affected_ids = systematic_mislabel(records, contributor=attack["contributor"], mapping=attack["mapping"],
                                            fraction=attack["fraction"], rng=rng)
    elif attack_type == "duplicate_flood":
        affected_ids = duplicate_flood(records, contributor=attack["contributor"],
                                       n_sources=attack["clusters"], copies=attack["copies_per_cluster"], rng=rng)
    elif attack_type == "patch_poison":
        pattern = trigger_pattern(attack["trigger_kind"], attack["trigger_size"], seed=manifest.seed)
        candidates = [record for record in records if record.contributor == attack["contributor"]]
        chosen = rng.choice(len(candidates), size=min(attack["poison_count"], len(candidates)), replace=False)
        affected_ids = []
        for index in chosen:
            record = candidates[int(index)]
            record.image = stamp(record.image, pattern, attack["position"])
            record.label = attack["target_class"]
            record.truth.append("localized_trigger")
            affected_ids.append(record.id)
    else:
        raise ValueError(f"no dataset handler for registered generator {attack_type!r}")

    dataset_path = run_dir / "dataset"
    write_corpus(records, dataset_path, name=f"{manifest.scenario_id}_attacked")
    scan_req.dataset = dataset_path
    reference_records = generate_clean_set(base["reference_size"],
                                           seed=derive_seed(manifest.seed, "reference"), label="ref")
    reference_path = run_dir / "reference"
    write_corpus(reference_records, reference_path, name="clean_reference")
    scan_req.reference_dataset = reference_path
    return records, affected_ids, {}


def _generate_drift_attack(manifest: ScenarioManifest, workspace: Workspace, run_dir: Path,
                           scan_req: ScanRequest, rng: np.random.Generator) -> GeneratorResult:
    del workspace, rng
    base = manifest.base
    attack = manifest.attack
    reference_records = generate_clean_set(base["reference_size"],
                                           seed=derive_seed(manifest.seed, "reference"), label="ref")
    attack_type = attack["type"]
    if attack_type == "illumination_shift":
        operational_records = operational_batch(base["operational_size"],
                                                seed=derive_seed(manifest.seed, "operational", "illumination"),
                                                shift=attack["shift"], label=attack["label"])
    elif attack_type == "semantic_shift":
        operational_records = operational_batch(base["operational_size"],
                                                seed=derive_seed(manifest.seed, "operational", "semantic"),
                                                class_weights=attack["class_weights"], label=attack["label"])
    else:
        raise ValueError(f"no drift handler for registered generator {attack_type!r}")
    for record in operational_records:
        record.truth.append(manifest.attack_class)
    reference_path = run_dir / "reference_drift"
    operational_path = run_dir / "incoming_drift"
    write_corpus(reference_records, reference_path, name="clean_reference_drift")
    write_corpus(operational_records, operational_path, name="incoming_operational_drift")
    scan_req.reference_dataset = reference_path
    scan_req.operational_data = operational_path
    return operational_records, [record.id for record in operational_records], {}


@dataclass(frozen=True)
class GeneratorSpec:
    attack_type: str
    family: str
    handler: GeneratorHandler


def _generate_model_substitution(manifest: ScenarioManifest, workspace: Workspace, run_dir: Path,
                                 scan_req: ScanRequest, rng: np.random.Generator) -> GeneratorResult:
    del workspace, rng
    return _model_substitution(manifest, run_dir, scan_req)


def _generate_weight_perturbation(manifest: ScenarioManifest, workspace: Workspace, run_dir: Path,
                                  scan_req: ScanRequest, rng: np.random.Generator) -> GeneratorResult:
    del workspace, rng
    return _model_weight_perturbation(manifest, run_dir, scan_req)


def _generate_record_edit(manifest: ScenarioManifest, workspace: Workspace, run_dir: Path,
                          scan_req: ScanRequest, rng: np.random.Generator) -> GeneratorResult:
    del rng
    return _ledger_record_tampering(manifest, workspace, run_dir, scan_req)


GENERATOR_REGISTRY: dict[str, GeneratorSpec] = {
    "clean_dataset": GeneratorSpec("clean_dataset", "dataset", _generate_clean_dataset),
    "label_flip_targeted": GeneratorSpec("label_flip_targeted", "dataset", _generate_dataset_attack),
    "label_flip_random": GeneratorSpec("label_flip_random", "dataset", _generate_dataset_attack),
    "systematic_mislabel": GeneratorSpec("systematic_mislabel", "dataset", _generate_dataset_attack),
    "duplicate_flood": GeneratorSpec("duplicate_flood", "dataset", _generate_dataset_attack),
    "patch_poison": GeneratorSpec("patch_poison", "dataset", _generate_dataset_attack),
    "illumination_shift": GeneratorSpec("illumination_shift", "drift", _generate_drift_attack),
    "semantic_shift": GeneratorSpec("semantic_shift", "drift", _generate_drift_attack),
    "model_substitution": GeneratorSpec("model_substitution", "model", _generate_model_substitution),
    "weight_perturbation": GeneratorSpec("weight_perturbation", "model", _generate_weight_perturbation),
    "record_edit": GeneratorSpec("record_edit", "provenance", _generate_record_edit),
}


def _generation_failure(manifest: ScenarioManifest, error: Exception) -> ScenarioRunResult:
    message = f"generation failed: {type(error).__name__}: {error}"
    return ScenarioRunResult(
        scenario_id=manifest.scenario_id, title=manifest.title, attack_class=manifest.attack_class,
        passed_fitness=False, detected_expected_signals=False, scan_id="", overall_disposition="ERROR",
        findings_count=0, critical_count=0, review_count=0, detected_detectors=[], missing_detectors=[],
        fitness_notes=[message], report_digest="", manifest_valid=True, generation_succeeded=False,
        ground_truth_valid=False, scan_executed=False, finding_expectation_satisfied=False,
        policy_expectation_satisfied=False, evaluation_status=ScenarioEvaluationStatus.GENERATION_FAILED,
        evaluation_notes=[message], details={"error": message}, scan_result=None,
    )


def run_scenario(
    manifest: ScenarioManifest,
    workspace: Workspace,
    *,
    profile: str = "selftest",
) -> ScenarioRunResult:
    """Execute a controlled attack scenario, evaluate fitness gates, run scan and report detection performance."""
    manifest_errors = validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("invalid scenario manifest: " + "; ".join(manifest_errors))
    run_dir = workspace.root / "attack_runs" / f"{manifest.scenario_id}_{secrets.token_hex(4)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    seed = manifest.seed
    rng = rng_for(seed, "scenario", manifest.scenario_id)

    scan_req = ScanRequest(name=f"AttackLab: {manifest.title}", profile=profile)
    truth_records = []
    generated_records: list = []
    affected_ids: list[str] = []
    fitness_notes: list[str] = []
    passed_fitness = True

    # 1. Dispatch through the authoritative generator registry.
    generation_error: Exception | None = None
    generator_type = manifest.attack.get("type")
    spec = GENERATOR_REGISTRY.get(generator_type)
    model_details: dict[str, Any] = {}
    if spec is None:
        raise ValueError(f"unsupported attack generator {generator_type!r}")
    try:
        generated_records, affected_ids, model_details = spec.handler(manifest, workspace, run_dir, scan_req, rng)
    except Exception as exc:
        generation_error = exc
        model_details = {"error": f"{type(exc).__name__}: {exc}"}

    if generation_error is not None:
        return _generation_failure(manifest, generation_error)

    truth_records = generated_records
    min_samples = manifest.fitness_gates.get("min_samples")
    if min_samples is not None and len(truth_records) < min_samples:
        passed_fitness = False
        fitness_notes.append(f"generated samples ({len(truth_records)}) < required minimum ({min_samples})")
    min_affected = manifest.fitness_gates.get("expected_affected_min")
    if min_affected is not None and len(affected_ids) < min_affected:
        passed_fitness = False
        fitness_notes.append(f"affected samples ({len(affected_ids)}) < required minimum ({min_affected})")
    expected_truth = manifest.expected.get("truth_tag")
    truth_tags = (set(model_details.get("ground_truth_tags", []))
                  if manifest.attack.get("type") in {"weight_perturbation", "record_edit"}
                  else {tag for record in truth_records for tag in record.truth})
    ground_truth_valid = expected_truth is None or expected_truth in truth_tags
    if not ground_truth_valid:
        passed_fitness = False
        fitness_notes.append(f"expected truth tag {expected_truth!r} absent from generated ground truth")

    # Execute Scan
    scan_result: ScanResult = run_scan(scan_req, workspace=workspace)

    # Check detector responses against expectations declared by the manifest.
    detected_detectors = [e.detector_id for e in scan_result.executions if e.findings > 0]
    expected_detectors = manifest.expected.get("expected_detectors", [])
    missing_detectors = [d for d in expected_detectors if d not in detected_detectors]
    detected_expected_signals = len(missing_detectors) == 0
    expected_findings = manifest.expected.get("expected_min_findings", 0)
    finding_expectation_satisfied = len(scan_result.findings) >= expected_findings
    expected_disposition = manifest.expected.get("expected_disposition")
    policy_expectation_satisfied = (expected_disposition is None
                                    or scan_result.summary is not None
                                    and scan_result.summary.overall_disposition == Disposition(expected_disposition))
    evaluation_notes = []
    if missing_detectors:
        evaluation_notes.append(f"missing expected detectors: {', '.join(missing_detectors)}")
    if not finding_expectation_satisfied:
        evaluation_notes.append(f"findings {len(scan_result.findings)} < expected minimum {expected_findings}")
    if not policy_expectation_satisfied:
        evaluation_notes.append(f"disposition did not satisfy {expected_disposition}")
    if not passed_fitness:
        evaluation_status = ScenarioEvaluationStatus.FITNESS_FAILED
    elif not ground_truth_valid:
        evaluation_status = ScenarioEvaluationStatus.GENERATION_FAILED
    elif detected_expected_signals and finding_expectation_satisfied and policy_expectation_satisfied:
        evaluation_status = ScenarioEvaluationStatus.DETECTOR_SUCCESS
    else:
        evaluation_status = ScenarioEvaluationStatus.DETECTOR_MISS

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
        ground_truth_valid=ground_truth_valid,
        finding_expectation_satisfied=finding_expectation_satisfied,
        policy_expectation_satisfied=policy_expectation_satisfied,
        evaluation_status=evaluation_status,
        evaluation_notes=evaluation_notes,
        details={"executions": [e.model_dump(mode="json") for e in scan_result.executions],
                 **(model_details if manifest.attack.get("type") in {"model_substitution", "weight_perturbation", "record_edit"} else {})},
        scan_result=scan_result,
    )
