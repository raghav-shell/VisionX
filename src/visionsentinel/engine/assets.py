"""Asset preparation and capability probing.

Each supplied asset is opened by its loader; the loader reports what it can actually provide. The
union is the scan's probed capability set, recorded per capability with its source asset.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts import AssetDescriptor, AssetType, Capability
from ..core.events import EventLog
from ..core.profiles import Profile
from ..core.workspace import Workspace
from ..data_assurance.analysis import DatasetAnalysis
from ..loaders.datasets import Dataset, open_dataset
from ..vision.encoders import Encoder
from .request import ScanRequest


@dataclass
class PreparedAssets:
    objects: dict[str, Any] = field(default_factory=dict)
    descriptors: list[AssetDescriptor] = field(default_factory=list)
    probed: dict[Capability, tuple[str, str | None]] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)
    encoder: Encoder | None = None
    encoder_notes: list[str] = field(default_factory=list)
    closers: list[Callable[[], None]] = field(default_factory=list)

    def probe(self, caps: dict[Capability, tuple[str, str | None]]) -> None:
        for cap, value in caps.items():
            self.probed.setdefault(cap, value)

    def close(self) -> None:
        for fn in reversed(self.closers):
            try:
                fn()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
        self.closers.clear()


DATASET_ROLES = {
    "dataset": (AssetType.DATASET, None),
    "reference_dataset": (AssetType.REFERENCE_DATASET, Capability.REFERENCE_DATASET),
    "probe_dataset": (AssetType.PROBE_DATASET, Capability.PROBE_DATASET),
    "suspect_inputs": (AssetType.SUSPECT_INPUTS, Capability.SUSPECT_INPUTS),
    "operational_data": (AssetType.OPERATIONAL_DATA, Capability.OPERATIONAL_DATA),
}


def load_datasets(request: ScanRequest, profile: Profile, prepared: PreparedAssets, events: EventLog) -> None:
    for role, (atype, role_cap) in DATASET_ROLES.items():
        path: Path | None = getattr(request, role)
        if path is None:
            continue
        fmt = request.dataset_format if role == "dataset" else "auto"
        ds = open_dataset(path, profile.limits, fmt=fmt,
                          progress=lambda n, r=role: events.emit(f"{r}: {n} samples indexed"))
        events.emit(f"{role.replace('_', ' ')} indexed: {len(ds.samples)} samples ({ds.format}), "
                    f"{len(ds.readable)} readable, digest {ds.digest[7:19]}")
        prepared.objects[role] = ds
        prepared.descriptors.append(AssetDescriptor(role=atype, asset_id=ds.name, name=ds.name, path=str(path),
                                                    digest=ds.digest, format=ds.format, details=ds.summary()))
        if role == "dataset":
            prepared.probe(ds.capabilities("dataset"))
            prepared.facts.update({"dataset.present": True, "dataset.samples": len(ds.samples),
                                   "dataset.classes": len(ds.classes)})
        elif role_cap is not None and ds.readable:
            prepared.probed[role_cap] = (role, f"{len(ds.readable)} readable samples")
            prepared.facts[f"{role}.samples"] = len(ds.readable)


def build_analyses(prepared: PreparedAssets, profile: Profile, workspace: Workspace, events: EventLog) -> None:
    enc = prepared.encoder
    assert enc is not None
    ref: DatasetAnalysis | None = None
    if "reference_dataset" in prepared.objects:
        ref = DatasetAnalysis(prepared.objects["reference_dataset"], resolution=profile.analysis.resolution,
                              encoder=enc, seed=profile.seed, cache_dir=workspace.cache, emit=events.emit)
        prepared.objects["reference_analysis"] = ref
    for role, key in (("dataset", "dataset_analysis"), ("operational_data", "operational_analysis"),
                      ("probe_dataset", "probe_analysis"), ("suspect_inputs", "suspect_analysis")):
        ds: Dataset | None = prepared.objects.get(role)
        if ds is not None and ds.readable:
            prepared.objects[key] = DatasetAnalysis(ds, resolution=profile.analysis.resolution, encoder=enc,
                                                    seed=profile.seed, reference=ref, cache_dir=workspace.cache,
                                                    emit=events.emit)
