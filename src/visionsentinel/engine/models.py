"""Scan asset hook: models, reference artifacts, stored fingerprints and the trust root."""

from __future__ import annotations

from ..contracts import AssetDescriptor, AssetType, Capability
from ..core.errors import VisionSentinelError
from ..core.events import EventLog
from ..core.hashing import sha256_file
from ..core.profiles import Profile
from ..core.workspace import Workspace
from ..loaders.models import ModelHandle, open_model
from ..model_assurance.behaviour import load_fingerprint
from ..provenance.trust import TrustRootError, load_trust_root
from .assets import PreparedAssets
from .request import ScanRequest


def _summary(m: ModelHandle) -> str:
    st = m.status
    flags = [("predict", st.predict), ("logits", st.logits), ("graph", st.graph), ("params", st.parameters),
             ("activations", st.activations), ("gradients", st.gradients)]
    return " ".join(f"{k} {'✓' if v else '✗'}" for k, v in flags)


def load_models(request: ScanRequest, profile: Profile, prepared: PreparedAssets, events: EventLog,
                workspace: Workspace) -> None:
    rejected: list[dict] = []
    supplied = 0
    for role, path in (("model", request.model), ("reference_model", request.reference_model)):
        if path is None:
            continue
        supplied += 1
        prepared.facts["model.supplied"] = True
        try:
            handle = open_model(path, profile.limits, preprocess_path=request.preprocess if role == "model" else None,
                                architecture=request.architecture, name=path.stem)
        except VisionSentinelError as exc:
            digest = None
            try:
                digest = sha256_file(path, max_bytes=profile.limits.max_model_bytes)
            except (OSError, VisionSentinelError):
                pass
            rejected.append({"role": role, "name": path.name, "error": str(exc), "type": type(exc).__name__,
                             "digest": digest})
            events.emit(f"{role.replace('_', ' ')} REJECTED: {type(exc).__name__}: {exc}", level="error")
            continue
        prepared.closers.append(handle.close)
        prepared.objects[role] = handle
        atype = AssetType.MODEL if role == "model" else AssetType.REFERENCE_MODEL
        prepared.descriptors.append(AssetDescriptor(role=atype, asset_id=handle.name, name=path.name, path=str(path),
                                                    digest=handle.artifact_digest, format=handle.format,
                                                    details=handle.describe()))
        events.emit(f"{role.replace('_', ' ')} probed ({handle.format}, sandboxed): {_summary(handle)}")
        for note in handle.status.notes:
            events.emit(f"  {note}")
        if role == "model":
            prepared.probe(handle.capabilities("model"))
            prepared.facts["model.num_classes"] = handle.num_classes or 0
            prepared.facts["model.format"] = handle.format
        else:
            prepared.probed[Capability.REFERENCE_MODEL_DIGEST] = ("reference_model", handle.artifact_digest[7:19])
            if handle.status.predict or handle.status.parameters:
                prepared.probed[Capability.REFERENCE_MODEL] = (
                    "reference_model", f"{handle.format}; " + ("executable" if handle.status.predict else "weights only"))
    prepared.objects["rejected_models"] = rejected
    prepared.objects["models_supplied"] = supplied

    if request.reference_fingerprint is not None:
        prepared.objects["reference_fingerprint"] = load_fingerprint(request.reference_fingerprint)
        prepared.probed[Capability.REFERENCE_FINGERPRINT] = ("reference_fingerprint", request.reference_fingerprint.name)

    if request.trust_root is not None:
        try:
            trust = load_trust_root(request.trust_root)
        except TrustRootError as exc:
            raise VisionSentinelError(f"trust root {request.trust_root.name}: {exc}") from exc
        prepared.objects["trust_root"] = trust
        prepared.probed[Capability.LEDGER_TRUST_ROOT] = ("trust_root", f"{len(trust.keys)} keys, digest {trust.digest[7:19]}")
        if trust.approved_models:
            prepared.probed[Capability.REFERENCE_MODEL_DIGEST] = (
                "trust_root", f"{len(trust.approved_models)} approved model binding(s)")
        prepared.descriptors.append(AssetDescriptor(role=AssetType.TRUST_ROOT, asset_id=trust.name, name=trust.name,
                                                    path=str(request.trust_root), digest=trust.digest, format="json",
                                                    details={"keys": list(trust.keys),
                                                             "approved_models": len(trust.approved_models)}))
        events.emit(f"trust root loaded: '{trust.name}', {len(trust.keys)} key(s), "
                    f"{len(trust.approved_models)} approved model(s)")
