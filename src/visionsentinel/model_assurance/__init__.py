"""Model assurance engine: identity, structure, behaviour and backdoor indicators."""

from __future__ import annotations

from ..core.registry import DetectorRegistry
from .activations import ActivationAnalysis
from .behaviour import BehaviouralFingerprint
from .identity import ArchitectureFingerprint, ArtifactDigest
from .intake import ModelIntake
from .reconstruction import TriggerReconstruction
from .strip import Strip
from .stress import BlackBoxStress
from .weights import WeightStatistics

DETECTORS = (ModelIntake, ArtifactDigest, ArchitectureFingerprint, WeightStatistics, BehaviouralFingerprint,
             BlackBoxStress, Strip, ActivationAnalysis, TriggerReconstruction)


def register(registry: DetectorRegistry) -> None:
    for det in DETECTORS:
        registry.register(det)
