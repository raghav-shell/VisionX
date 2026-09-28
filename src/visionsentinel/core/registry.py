"""Explicit detector registry.

Registration is explicit (no entry-point discovery, no import-time side effects) so that a scan can
prove which detectors exist and the planner can prove none was skipped.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..contracts import ATTACK_CLASSES, DetectorSpec
from .detector import Detector
from .errors import ConfigurationError


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: dict[str, Detector] = {}

    def register(self, detector: type[Detector] | Detector) -> None:
        instance = detector() if isinstance(detector, type) else detector
        spec = instance.spec
        if spec.id in self._detectors:
            raise ConfigurationError(f"detector {spec.id!r} registered twice")
        self._detectors[spec.id] = instance

    def get(self, detector_id: str) -> Detector:
        try:
            return self._detectors[detector_id]
        except KeyError as exc:
            raise ConfigurationError(f"unknown detector {detector_id!r}") from exc

    def ids(self) -> list[str]:
        return list(self._detectors)

    def specs(self) -> list[DetectorSpec]:
        return [d.spec for d in self._detectors.values()]

    def __iter__(self) -> Iterator[Detector]:
        return iter(self._detectors.values())

    def __len__(self) -> int:
        return len(self._detectors)

    def validate(self) -> None:
        """Check dependency references and that each attack class id is catalogued."""
        for det in self._detectors.values():
            for dep in det.spec.depends_on:
                if dep not in self._detectors:
                    raise ConfigurationError(f"{det.spec.id} depends on unregistered detector {dep!r}")
            for s in det.spec.supports:
                if s.attack_class not in ATTACK_CLASSES:  # pragma: no cover - contracts also check
                    raise ConfigurationError(f"{det.spec.id}: unknown attack class {s.attack_class}")
        self.order()

    def order(self) -> list[str]:
        """Topological order by ``depends_on``; ties keep registration order."""
        remaining = {i: set(d.spec.depends_on) for i, d in self._detectors.items()}
        ordered: list[str] = []
        while remaining:
            ready = [i for i in self._detectors if i in remaining and not (remaining[i] - set(ordered))]
            if not ready:
                raise ConfigurationError(f"dependency cycle among detectors: {sorted(remaining)}")
            for i in ready:
                ordered.append(i)
                del remaining[i]
        return ordered
