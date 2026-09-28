"""The default detector registry: every detector shipped with VisionSentinel, in execution order."""

from __future__ import annotations

from functools import lru_cache

from ..core.registry import DetectorRegistry


def build_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    registry.validate()
    return registry


@lru_cache(maxsize=1)
def default_registry() -> DetectorRegistry:
    return build_registry()
