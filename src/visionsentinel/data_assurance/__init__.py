"""Data assurance engine: dataset-level integrity detectors."""

from __future__ import annotations

from ..core.registry import DetectorRegistry
from .duplicates import DuplicateLabelConflict, NearDuplicateFlooding
from .geometry import AnnotationGeometry
from .integrity import ManifestIntegrity
from .labels import LabelConsistency, SystematicMislabel
from .metadata import MetadataAnomaly
from .ood import OutOfDistribution
from .trigger import TriggerArtifactAnalysis

# Order matters only where a detector optionally consumes another's result (systematic mislabelling
# excludes samples the OOD detector flagged); hard dependencies are declared in each spec.
DETECTORS = (ManifestIntegrity, NearDuplicateFlooding, DuplicateLabelConflict, OutOfDistribution, LabelConsistency,
             SystematicMislabel, AnnotationGeometry, MetadataAnomaly, TriggerArtifactAnalysis)


def register(registry: DetectorRegistry) -> None:
    for det in DETECTORS:
        registry.register(det)
