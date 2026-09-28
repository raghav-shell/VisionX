"""Model assurance engine: identity, structure, behaviour and backdoor indicators."""

from __future__ import annotations

from ..core.registry import DetectorRegistry
from .behaviour import BehaviouralFingerprint
from .identity import ArchitectureFingerprint, ArtifactDigest
from .intake import ModelIntake
from .weights import WeightStatistics

DETECTORS = (ModelIntake, ArtifactDigest, ArchitectureFingerprint, WeightStatistics, BehaviouralFingerprint)


def register(registry: DetectorRegistry) -> None:
    for det in DETECTORS:
        registry.register(det)
