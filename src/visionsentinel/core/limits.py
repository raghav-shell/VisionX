"""Resource limits applied at every untrusted-input boundary."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResourceLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_file_bytes: int = Field(default=64 * 1024**2, gt=0, description="Largest single sample/config file.")
    max_model_bytes: int = Field(default=512 * 1024**2, gt=0)
    max_json_bytes: int = Field(default=64 * 1024**2, gt=0, description="Largest annotation/manifest JSON.")
    max_json_depth: int = Field(default=64, gt=0)
    max_json_elements: int = Field(default=5_000_000, gt=0)
    max_xml_bytes: int = Field(default=4 * 1024**2, gt=0)
    max_image_pixels: int = Field(default=40_000_000, gt=0, description="Width × height before decoding.")
    max_image_side: int = Field(default=16_384, gt=0)
    max_dataset_samples: int = Field(default=200_000, gt=0)
    max_archive_members: int = Field(default=250_000, gt=0)
    max_archive_total_bytes: int = Field(default=8 * 1024**3, gt=0)
    max_compression_ratio: float = Field(default=200.0, gt=1.0)
    max_tensor_elements: int = Field(default=200_000_000, gt=0, description="Largest single parameter tensor.")
    max_ledger_records: int = Field(default=5_000_000, gt=0)
    max_ledger_line_bytes: int = Field(default=1 * 1024**2, gt=0)
    worker_memory_bytes: int = Field(default=4 * 1024**3, gt=0)
    worker_cpu_seconds: int = Field(default=1800, gt=0)
    worker_call_timeout_s: float = Field(default=300.0, gt=0)
