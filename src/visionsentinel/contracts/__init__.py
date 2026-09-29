"""Domain contracts: the vocabulary every VisionSentinel component speaks."""

from .catalog import ATTACK_CLASSES, CAPABILITY_INFO, AttackClassInfo, CapabilityInfo, attack_class
from .assets import SCAN_ASSET_INPUTS, ScanAssetInput
from .enums import (
    AssetKind, AssetLifecycle, AssetType,
    Availability,
    BudgetTier,
    CalibrationRequirement,
    Capability,
    CoverageState,
    Disposition,
    EvidenceKind,
    ExecutionState, JobKind, JobStatus,
    Layer,
    Role,
    RuntimeClass,
    ScanStatus,
    Severity,
    SupportLevel,
)
from .models import (
    AssetDescriptor,
    AttackSupport,
    BlobRef,
    CapabilityRecord,
    ContributorAssessment,
    CoverageRow,
    CoverageStatement,
    DetectorExecution,
    DetectorMode,
    DetectorSpec,
    Evidence,
    EvidenceGraph,
    Finding,
    GraphEdge,
    GraphNode,
    Negotiation,
    ProposedFinding,
    ReproductionInfo,
    SampleRef,
    ScanEvent,
    ScanResult,
    ScanSummary,
    UnsupportedAttack,
)

__all__ = [
    "ATTACK_CLASSES", "CAPABILITY_INFO", "AttackClassInfo", "CapabilityInfo", "attack_class",
    "SCAN_ASSET_INPUTS", "ScanAssetInput",
    "AssetKind", "AssetLifecycle", "AssetType", "Availability", "BudgetTier", "CalibrationRequirement", "Capability", "CoverageState",
    "Disposition", "EvidenceKind", "ExecutionState", "JobKind", "JobStatus", "Layer", "Role", "RuntimeClass", "ScanStatus",
    "Severity", "SupportLevel",
    "AssetDescriptor", "AttackSupport", "BlobRef", "CapabilityRecord", "ContributorAssessment",
    "CoverageRow", "CoverageStatement", "DetectorExecution", "DetectorMode", "DetectorSpec", "Evidence",
    "EvidenceGraph", "Finding", "GraphEdge", "GraphNode", "Negotiation", "ProposedFinding",
    "ReproductionInfo", "SampleRef", "ScanEvent", "ScanResult", "ScanSummary", "UnsupportedAttack",
]
