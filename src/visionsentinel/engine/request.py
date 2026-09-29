"""Scan request: which assets to assess, with which profile."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..contracts import SCAN_ASSET_INPUTS


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="assessment", max_length=120)
    profile: str = "baseline"
    dataset: Path | None = None
    dataset_format: str = "auto"
    reference_dataset: Path | None = None
    probe_dataset: Path | None = None
    suspect_inputs: Path | None = None
    operational_data: Path | None = None
    model: Path | None = None
    reference_model: Path | None = None
    architecture: str | None = Field(default=None, description="Known architecture id for bare state dicts.")
    preprocess: Path | None = None
    reference_fingerprint: Path | None = None
    ledger: Path | None = None
    trust_root: Path | None = None
    anchor: Path | None = None
    inference_inputs: Path | None = None
    scan_id: str | None = None

    def supplied(self) -> dict[str, Path]:
        keys = tuple(spec.field for spec in SCAN_ASSET_INPUTS)
        return {k: getattr(self, k) for k in keys if getattr(self, k) is not None}
