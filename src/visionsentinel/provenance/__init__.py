"""Provenance: canonical JSON, Ed25519 hash-chained ledger, Merkle checkpoints, trust root and verifier.

This package's import must stay light: ``python -m visionsentinel.provenance.verifier`` runs with the
standard library and ``cryptography`` only, so nothing heavier is imported at package import time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..core.registry import DetectorRegistry


def register(registry: "DetectorRegistry") -> None:
    from .detectors import InferenceBinding, LedgerIntegrity

    registry.register(LedgerIntegrity)
    registry.register(InferenceBinding)
