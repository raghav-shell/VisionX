"""Scan-level encoder selection: vendored foundation → approved reference model → classical descriptor."""

from __future__ import annotations

from ..contracts import Capability
from ..core.profiles import Profile
from ..core.workspace import repo_root
from ..vision.encoders import classical_encoder, foundation_encoder, model_encoder
from .assets import PreparedAssets


def select_encoder(prepared: PreparedAssets, profile: Profile) -> None:
    notes: list[str] = []
    for choice in profile.analysis.encoder_preference:
        if choice == "foundation":
            status = foundation_encoder(repo_root() / "assets" / "models")
            if status.available and status.encoder is not None:
                prepared.encoder = status.encoder
                notes.append(f"foundation encoder selected: {status.encoder.id}")
                break
            notes.append(f"foundation encoder unavailable: {status.reason}")
        elif choice == "reference_model":
            ref = prepared.objects.get("reference_model")
            if ref is not None and getattr(ref, "has_activations", False):
                prepared.encoder = model_encoder(ref.name, ref.artifact_digest, ref.features)
                notes.append(f"approved reference model used as encoder ({ref.name}, penultimate activations)")
                break
            notes.append("reference-model encoder unavailable: no approved reference model with activation access")
        elif choice == "classical":
            prepared.encoder = classical_encoder()
            notes.append("classical-v2 weight-free descriptor selected (non-semantic)")
            break
    if prepared.encoder is None:
        prepared.encoder = classical_encoder()
        notes.append("classical-v2 weight-free descriptor selected as last resort")
    prepared.encoder_notes = notes
    if prepared.encoder.semantic:
        prepared.probed[Capability.SEMANTIC_ENCODER] = ("runtime", prepared.encoder.id)
