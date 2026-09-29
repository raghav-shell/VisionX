"""Shared asset compatibility contracts used by API and engine layers."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import AssetKind


@dataclass(frozen=True)
class ScanAssetInput:
    """The authoritative web-asset compatibility contract for one scan input."""

    field: str
    kinds: frozenset[AssetKind]


SCAN_ASSET_INPUTS = (
    ScanAssetInput("dataset", frozenset({AssetKind.DATASET})),
    ScanAssetInput("reference_dataset", frozenset({AssetKind.DATASET})),
    ScanAssetInput("probe_dataset", frozenset({AssetKind.DATASET})),
    ScanAssetInput("suspect_inputs", frozenset({AssetKind.DATASET})),
    ScanAssetInput("operational_data", frozenset({AssetKind.DATASET})),
    ScanAssetInput("model", frozenset({AssetKind.MODEL})),
    ScanAssetInput("reference_model", frozenset({AssetKind.MODEL})),
    ScanAssetInput("preprocess", frozenset({AssetKind.PREPROCESS})),
    ScanAssetInput("reference_fingerprint", frozenset({AssetKind.FINGERPRINT})),
    ScanAssetInput("ledger", frozenset({AssetKind.LEDGER})),
    ScanAssetInput("trust_root", frozenset({AssetKind.TRUST_ROOT})),
    ScanAssetInput("anchor", frozenset({AssetKind.ANCHOR})),
    ScanAssetInput("inference_inputs", frozenset({AssetKind.INPUTS})),
)
