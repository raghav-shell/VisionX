"""The default detector registry: every detector shipped with VisionSentinel, in execution order."""

from __future__ import annotations

from functools import lru_cache

from .. import data_assurance, model_assurance
from ..core.registry import DetectorRegistry


def build_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    data_assurance.register(registry)
    model_assurance.register(registry)
    registry.validate()
    return registry


@lru_cache(maxsize=1)
def default_registry() -> DetectorRegistry:
    return build_registry()
