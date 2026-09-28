"""Per-detector execution context."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from pydantic import BaseModel

from ..contracts import BlobRef, DetectorSpec
from .capabilities import CapabilitySet
from .determinism import rng_for
from .errors import CapabilityError
from .limits import ResourceLimits
from .profiles import CalibrationConfig, Profile

if TYPE_CHECKING:  # pragma: no cover
    from .detector import DetectorResult


class BlobSink(Protocol):
    def put_bytes(self, data: bytes, media_type: str) -> BlobRef: ...

    def put_json(self, obj: Any) -> BlobRef: ...

    def put_png(self, image: np.ndarray) -> BlobRef: ...


@dataclass
class DetectorContext:
    scan_id: str
    spec: DetectorSpec
    mode: str
    params: BaseModel
    calibration: CalibrationConfig | None
    profile: Profile
    capabilities: CapabilitySet
    assets: Mapping[str, Any]
    blobs: BlobSink
    seed: int
    upstream: Mapping[str, "DetectorResult"]
    shared: dict[str, Any]
    emit: Callable[[str], None]
    _evidence_counter: int = field(default=0, init=False)

    @property
    def detector_id(self) -> str:
        return self.spec.id

    @property
    def limits(self) -> ResourceLimits:
        return self.profile.limits

    @property
    def calibrated(self) -> bool:
        return bool(self.calibration and self.calibration.calibrated)

    def rng(self, *labels: object) -> np.random.Generator:
        return rng_for(self.seed, self.spec.id, *labels)

    def asset(self, key: str) -> Any:
        value = self.assets.get(key)
        if value is None:
            raise CapabilityError(f"{self.spec.id} requested asset {key!r} that negotiation did not provide")
        return value

    def optional_asset(self, key: str) -> Any:
        return self.assets.get(key)

    def evidence_id(self, *parts: object) -> str:
        self._evidence_counter += 1
        material = "|".join([self.scan_id, self.spec.id, str(self._evidence_counter), *map(str, parts)])
        return "EV-" + hashlib.sha256(material.encode()).hexdigest()[:12].upper()
