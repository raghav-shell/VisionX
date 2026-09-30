"""Enumerations shared by every VisionSentinel component.

Ordering matters for several of them (severity, disposition, budget); the ``rank`` helpers give
the total order explicitly instead of relying on declaration order.
"""

from __future__ import annotations

from enum import StrEnum


class Capability(StrEnum):
    """A unit of access that an assessment may or may not have."""

    DATASET_IMAGES = "DATASET_IMAGES"
    DATASET_LABELS = "DATASET_LABELS"
    DATASET_ANNOTATIONS = "DATASET_ANNOTATIONS"
    DATASET_METADATA = "DATASET_METADATA"
    CONTRIBUTOR_METADATA = "CONTRIBUTOR_METADATA"

    MODEL_ARTIFACT = "MODEL_ARTIFACT"
    MODEL_PREDICT = "MODEL_PREDICT"
    MODEL_LOGITS = "MODEL_LOGITS"
    MODEL_GRAPH = "MODEL_GRAPH"
    MODEL_PARAMETERS = "MODEL_PARAMETERS"
    MODEL_ACTIVATIONS = "MODEL_ACTIVATIONS"
    MODEL_GRADIENTS = "MODEL_GRADIENTS"

    REFERENCE_MODEL = "REFERENCE_MODEL"
    REFERENCE_MODEL_DIGEST = "REFERENCE_MODEL_DIGEST"
    REFERENCE_FINGERPRINT = "REFERENCE_FINGERPRINT"
    REFERENCE_DATASET = "REFERENCE_DATASET"
    PROBE_DATASET = "PROBE_DATASET"
    SUSPECT_INPUTS = "SUSPECT_INPUTS"

    INFERENCE_LEDGER = "INFERENCE_LEDGER"
    LEDGER_TRUST_ROOT = "LEDGER_TRUST_ROOT"
    LEDGER_ANCHOR = "LEDGER_ANCHOR"
    INFERENCE_INPUTS = "INFERENCE_INPUTS"
    PREPROCESSING_CONFIG = "PREPROCESSING_CONFIG"

    OPERATIONAL_DATA = "OPERATIONAL_DATA"
    SEMANTIC_ENCODER = "SEMANTIC_ENCODER"


class Availability(StrEnum):
    """Planned availability of a detector for a particular scan."""

    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    BUDGET_EXCLUDED = "BUDGET_EXCLUDED"


class ExecutionState(StrEnum):
    """What actually happened when the orchestrator reached a detector."""

    COMPLETED = "COMPLETED"
    COMPLETED_DEGRADED = "COMPLETED_DEGRADED"
    ABSTAINED = "ABSTAINED"
    NOT_RUN = "NOT_RUN"
    ERROR = "ERROR"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    @classmethod
    def max(cls, *values: "Severity") -> "Severity":
        return max(values, key=lambda s: s.rank)


_SEVERITY_RANK = {Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3, Severity.CRITICAL: 4}


class Disposition(StrEnum):
    ACCEPT = "ACCEPT"
    REVIEW = "REVIEW"
    QUARANTINE = "QUARANTINE"

    @property
    def rank(self) -> int:
        return _DISPOSITION_RANK[self]

    @classmethod
    def max(cls, *values: "Disposition") -> "Disposition":
        return max(values, key=lambda d: d.rank)

    @classmethod
    def min(cls, *values: "Disposition") -> "Disposition":
        return min(values, key=lambda d: d.rank)


_DISPOSITION_RANK = {Disposition.ACCEPT: 0, Disposition.REVIEW: 1, Disposition.QUARANTINE: 2}


class CoverageState(StrEnum):
    ASSESSED = "ASSESSED"
    PARTIALLY_ASSESSED = "PARTIALLY_ASSESSED"
    NOT_ASSESSED = "NOT_ASSESSED"
    FAILED_TO_EXECUTE = "FAILED_TO_EXECUTE"
    UNSUPPORTED = "UNSUPPORTED"


class BudgetTier(StrEnum):
    TRIAGE = "TRIAGE"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
    FORENSIC = "FORENSIC"

    @property
    def rank(self) -> int:
        return _BUDGET_RANK[self]


_BUDGET_RANK = {BudgetTier.TRIAGE: 0, BudgetTier.STANDARD: 1, BudgetTier.DEEP: 2, BudgetTier.FORENSIC: 3}


class Layer(StrEnum):
    """The assurance layer a detector or attack class belongs to."""

    DATA = "DATA"
    MODEL = "MODEL"
    PROVENANCE = "PROVENANCE"
    DRIFT = "DRIFT"


class SupportLevel(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"


class RuntimeClass(StrEnum):
    FAST = "FAST"
    MODERATE = "MODERATE"
    EXPENSIVE = "EXPENSIVE"


class CalibrationRequirement(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"  # deterministic checks (digests, signatures, schema)
    OPTIONAL = "OPTIONAL"
    REQUIRED = "REQUIRED"


class AssetType(StrEnum):
    DATASET = "DATASET"
    REFERENCE_DATASET = "REFERENCE_DATASET"
    PROBE_DATASET = "PROBE_DATASET"
    SUSPECT_INPUTS = "SUSPECT_INPUTS"
    OPERATIONAL_DATA = "OPERATIONAL_DATA"
    MODEL = "MODEL"
    REFERENCE_MODEL = "REFERENCE_MODEL"
    INFERENCE_LEDGER = "INFERENCE_LEDGER"
    TRUST_ROOT = "TRUST_ROOT"
    CONTRIBUTOR = "CONTRIBUTOR"
    SAMPLE = "SAMPLE"


class AssetKind(StrEnum):
    """Kinds accepted by the workspace asset registry."""

    DATASET = "dataset"
    MODEL = "model"
    PREPROCESS = "preprocess"
    LEDGER = "ledger"
    ANCHOR = "anchor"
    TRUST_ROOT = "trust_root"
    INPUTS = "inputs"
    FINGERPRINT = "fingerprint"


class AssetLifecycle(StrEnum):
    """Lifecycle states stored in the asset registry metadata."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class EvidenceKind(StrEnum):
    STATISTIC = "STATISTIC"
    TABLE = "TABLE"
    CONTACT_SHEET = "CONTACT_SHEET"
    PAIR_COMPARISON = "PAIR_COMPARISON"
    HEATMAP = "HEATMAP"
    HASH_LIST = "HASH_LIST"
    GRAPH = "GRAPH"
    DISTRIBUTION = "DISTRIBUTION"
    CONFUSION_MATRIX = "CONFUSION_MATRIX"
    DIFF = "DIFF"
    CRYPTO_CHECK = "CRYPTO_CHECK"
    TIMELINE = "TIMELINE"
    SERIES = "SERIES"
    TEXT = "TEXT"


class Role(StrEnum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    APPROVER = "APPROVER"
    ADMIN = "ADMIN"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]


_ROLE_RANK = {Role.VIEWER: 0, Role.ANALYST: 1, Role.APPROVER: 2, Role.ADMIN: 3}


class ScanStatus(StrEnum):
    PENDING = "PENDING"
    PROBING = "PROBING"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    SEALED = "SEALED"
    FAILED = "FAILED"

    @property
    def terminal(self) -> bool:
        return self in {ScanStatus.SEALED, ScanStatus.FAILED}


class JobStatus(StrEnum):
    """Persisted lifecycle states for local background jobs."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    @property
    def terminal(self) -> bool:
        return self in {JobStatus.COMPLETED, JobStatus.FAILED}

    @classmethod
    def active_values(cls) -> tuple[str, ...]:
        return tuple(status.value for status in cls if not status.terminal)


class JobKind(StrEnum):
    """Known long-running operations exposed through the local job API."""

    ATTACK_LAB = "attacklab"


class ScenarioEvaluationStatus(StrEnum):
    """Independent outcomes of Attack Lab generation and assessment."""

    GENERATION_FAILED = "generation_failed"
    FITNESS_FAILED = "fitness_failed"
    DETECTOR_SUCCESS = "detector_success"
    DETECTOR_MISS = "detector_miss"
    INVALID_MANIFEST = "invalid_manifest"
    EXECUTION_ERROR = "execution_error"
