"""Drift engine: operational covariate shift, semantic shift and drift-versus-manipulation reasoning."""

from __future__ import annotations

from ..core.registry import DetectorRegistry
from .detectors import CovariateDrift, DriftInterpretation, SemanticDrift

DETECTORS = (CovariateDrift, SemanticDrift, DriftInterpretation)


def register(registry: DetectorRegistry) -> None:
    for det in DETECTORS:
        registry.register(det)
