"""Static catalogues: what each capability means, and the universe of attack classes.

The attack-class catalogue is the denominator of every coverage statement. A class that no
registered detector supports is reported as UNSUPPORTED with the reason and the evidence that
would be needed to assess it; it is never silently omitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import Capability, Layer


@dataclass(frozen=True)
class CapabilityInfo:
    title: str
    group: str
    description: str


CAPABILITY_INFO: dict[Capability, CapabilityInfo] = {
    Capability.DATASET_IMAGES: CapabilityInfo("Dataset images", "dataset", "Decodable image files for every sample."),
    Capability.DATASET_LABELS: CapabilityInfo("Labels", "dataset", "An image-level class label for samples."),
    Capability.DATASET_ANNOTATIONS: CapabilityInfo("Annotations", "dataset", "Bounding-box annotations."),
    Capability.DATASET_METADATA: CapabilityInfo(
        "Sample metadata", "dataset", "Source, batch, sensor, timestamp or EXIF information."
    ),
    Capability.CONTRIBUTOR_METADATA: CapabilityInfo(
        "Contributor metadata", "dataset", "Attribution of samples to contributors."
    ),
    Capability.MODEL_ARTIFACT: CapabilityInfo("Model artifact", "model", "The serialized model file bytes."),
    Capability.MODEL_PREDICT: CapabilityInfo("Model predictions", "model", "Top-1 class predictions for chosen inputs."),
    Capability.MODEL_LOGITS: CapabilityInfo("Model scores", "model", "Per-class scores (logits or probabilities)."),
    Capability.MODEL_GRAPH: CapabilityInfo("Model graph", "model", "Computational graph / architecture."),
    Capability.MODEL_PARAMETERS: CapabilityInfo("Weights", "model", "Parameter tensors."),
    Capability.MODEL_ACTIVATIONS: CapabilityInfo(
        "Activations", "model", "Internal (penultimate) representations for chosen inputs."
    ),
    Capability.MODEL_GRADIENTS: CapabilityInfo("Gradients", "model", "Loss gradients with respect to the input."),
    Capability.REFERENCE_MODEL: CapabilityInfo(
        "Reference model", "reference", "The approved model artifact, executable for comparison."
    ),
    Capability.REFERENCE_MODEL_DIGEST: CapabilityInfo(
        "Approved model digest", "reference", "Approved artifact/parameter digests from the trust root."
    ),
    Capability.REFERENCE_FINGERPRINT: CapabilityInfo(
        "Approved behaviour fingerprint", "reference", "Stored probe-battery outputs of the approved model."
    ),
    Capability.REFERENCE_DATASET: CapabilityInfo(
        "Reference dataset", "reference", "Trusted clean data used to calibrate distances and drift."
    ),
    Capability.PROBE_DATASET: CapabilityInfo("Probe corpus", "reference", "Clean labelled probes for model testing."),
    Capability.SUSPECT_INPUTS: CapabilityInfo(
        "Suspect inputs", "reference", "Operational inputs suspected of carrying a trigger."
    ),
    Capability.INFERENCE_LEDGER: CapabilityInfo("Inference ledger", "provenance", "Signed inference records."),
    Capability.LEDGER_TRUST_ROOT: CapabilityInfo(
        "Trust root", "provenance", "Public keys and approved model bindings."
    ),
    Capability.LEDGER_ANCHOR: CapabilityInfo(
        "External anchor", "provenance", "Merkle checkpoints held outside the ledger."
    ),
    Capability.INFERENCE_INPUTS: CapabilityInfo(
        "Inference inputs", "provenance", "The raw inputs referenced by inference records."
    ),
    Capability.PREPROCESSING_CONFIG: CapabilityInfo(
        "Preprocessing config", "model", "Declared resize/normalisation applied before inference."
    ),
    Capability.OPERATIONAL_DATA: CapabilityInfo(
        "Operational data", "drift", "Incoming operational images to compare with the reference."
    ),
    Capability.SEMANTIC_ENCODER: CapabilityInfo(
        "Semantic encoder", "runtime", "A learned image encoder (vendored foundation model or approved model)."
    ),
}


@dataclass(frozen=True)
class AttackClassInfo:
    id: str
    layer: Layer
    title: str
    description: str
    # Only for classes that no detector in this product addresses:
    unsupported_reason: str | None = None
    recommended_evidence: tuple[str, ...] = field(default_factory=tuple)


def _a(id: str, layer: Layer, title: str, description: str, *, unsupported: str | None = None,
       recommend: tuple[str, ...] = ()) -> AttackClassInfo:
    return AttackClassInfo(id, layer, title, description, unsupported, recommend)


ATTACK_CLASSES: dict[str, AttackClassInfo] = {
    a.id: a
    for a in [
        # ---------------------------------------------------------------- data layer
        _a("label_flip", Layer.DATA, "Label flipping",
           "Individual samples relabelled to a wrong class, randomly or towards a target class."),
        _a("systematic_mislabel", Layer.DATA, "Systematic mislabelling",
           "A contributor consistently relabels one class as another."),
        _a("duplicate_flood", Layer.DATA, "Near-duplicate flooding",
           "Many near-identical samples injected to shift class balance or induce memorisation."),
        _a("duplicate_label_conflict", Layer.DATA, "Duplicate-label conflict",
           "The same visual content submitted with conflicting labels."),
        _a("annotation_tampering", Layer.DATA, "Annotation geometry tampering",
           "Impossible, degenerate or systematically shifted bounding boxes."),
        _a("metadata_manipulation", Layer.DATA, "Metadata manipulation",
           "Forged or anomalous source, sensor, timestamp, size or compression metadata."),
        _a("ood_injection", Layer.DATA, "Out-of-distribution injection",
           "Samples outside the operational domain inserted into training data."),
        _a("localized_trigger", Layer.DATA, "Localized trigger poisoning",
           "Dirty-label poisoning in which a small patch trigger is stamped onto samples."),
        _a("blended_trigger", Layer.DATA, "Blended trigger poisoning",
           "Poisoning in which a trigger pattern is alpha-blended across the whole image."),
        _a("corrupted_samples", Layer.DATA, "Corrupted or substituted files",
           "Missing, unreadable or digest-mismatched sample files."),
        _a("clean_label_poisoning", Layer.DATA, "Clean-label poisoning",
           "Labels stay consistent with content while features are perturbed to plant a behaviour.",
           unsupported="Labels remain correct and perturbations are optimised to be imperceptible; label "
                       "consistency and artifact-correlation detectors are neither designed nor validated "
                       "for this attack.",
           recommend=("Representation analysis of a model trained on this data (spectral signatures, "
                      "activation clustering) with a validated clean-label benchmark",
                      "Contributor provenance controls and robust training (e.g. partition aggregation)")),
        _a("sample_specific_trigger", Layer.DATA, "Sample-specific / warping triggers",
           "Triggers that differ per sample (input-aware) or apply smooth geometric warping.",
           unsupported="These triggers leave no repeated pixel pattern, so artifact correlation cannot "
                       "observe them; no detector here has been validated against them.",
           recommend=("White-box model analysis with a detector validated for dynamic triggers",
                      "Held-out trusted data for fine-pruning or re-training comparison")),
        # ---------------------------------------------------------------- model layer
        _a("model_substitution", Layer.MODEL, "Model artifact substitution",
           "The deployed model file is not the approved artifact."),
        _a("model_graph_modification", Layer.MODEL, "Model graph modification",
           "Operators, layers or connections were added, removed or rewired (incl. architectural backdoors)."),
        _a("model_weight_tampering", Layer.MODEL, "Weight tampering",
           "Parameters were changed (fine-tuned, perturbed or replaced) under the same architecture."),
        _a("behavioural_divergence", Layer.MODEL, "Behavioural divergence",
           "The model behaves differently from the approved model on a fixed probe battery."),
        _a("model_backdoor_patch", Layer.MODEL, "Patch-trigger backdoor",
           "The model maps inputs containing a small patch trigger to an attacker-chosen class."),
        _a("model_backdoor_blended", Layer.MODEL, "Blended-trigger backdoor",
           "The model responds to a trigger blended across the whole input."),
        _a("runtime_trigger_input", Layer.MODEL, "Trigger-bearing runtime input",
           "An operational input carries a trigger that dominates the model's prediction."),
        _a("model_corruption", Layer.MODEL, "Parameter corruption",
           "Non-finite, exploding or degenerate parameter tensors."),
        _a("adversarial_evasion", Layer.MODEL, "Adversarial evasion",
           "Small input perturbations crafted per input to cause misclassification.",
           unsupported="Adversarial robustness is a property of the decision boundary, not an integrity "
                       "violation of the artifact; it needs certified or attack-based robustness "
                       "evaluation which is out of scope.",
           recommend=("Dedicated robustness evaluation (e.g. PGD/AutoAttack or certified bounds)",)),
        # ---------------------------------------------------------------- provenance layer
        _a("record_modification", Layer.PROVENANCE, "Record modification",
           "A historical inference record was edited."),
        _a("record_deletion", Layer.PROVENANCE, "Record deletion",
           "A record was removed from the middle of the ledger."),
        _a("record_reorder", Layer.PROVENANCE, "Record reordering", "Records were swapped or reordered."),
        _a("record_replay", Layer.PROVENANCE, "Record replay", "An old record was duplicated into the ledger."),
        _a("record_truncation", Layer.PROVENANCE, "Ledger truncation",
           "Records were removed from the end of the ledger."),
        _a("signature_forgery", Layer.PROVENANCE, "Signature forgery / corruption",
           "A record carries an invalid signature or an unknown or revoked key."),
        _a("model_binding_violation", Layer.PROVENANCE, "Model binding violation",
           "An inference was produced by a model that is not approved."),
        _a("input_substitution", Layer.PROVENANCE, "Input substitution",
           "The stored input no longer matches the digest bound into the record."),
        _a("config_binding_violation", Layer.PROVENANCE, "Configuration binding violation",
           "An inference used a preprocessing configuration that is not approved."),
        _a("signing_key_compromise", Layer.PROVENANCE, "Signing-key compromise",
           "An attacker holding the signing key issues new, validly signed records.",
           unsupported="Records signed with a stolen key are cryptographically valid; the ledger can only "
                       "bound the damage to the interval after the last external anchor.",
           recommend=("Hardware-backed signing keys", "Frequent external Merkle anchors kept off-host",
                      "Key rotation and revocation in the trust root")),
        # ---------------------------------------------------------------- drift layer
        _a("operational_drift", Layer.DRIFT, "Operational distribution shift",
           "Incoming data differ in low-level imaging conditions (illumination, blur, noise, sensor)."),
        _a("semantic_drift", Layer.DRIFT, "Semantic distribution shift",
           "Incoming data differ in content or class mix."),
        _a("drift_manipulation", Layer.DRIFT, "Manipulated operational stream",
           "Distribution change concentrated in one source with artifact or target-class signatures."),
    ]
}


def attack_class(id: str) -> AttackClassInfo:
    try:
        return ATTACK_CLASSES[id]
    except KeyError as exc:  # pragma: no cover - programming error guard
        raise KeyError(f"unknown attack class {id!r}") from exc
