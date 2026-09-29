"""System information: health, detector registry, profiles, catalogues, sandbox isolation status."""

from __future__ import annotations

import threading
from importlib import metadata

from fastapi import APIRouter, Depends
from sqlalchemy import select

from ... import __version__
from ...contracts import ATTACK_CLASSES, CAPABILITY_INFO, Role
from ...core.profiles import list_profiles, load_profile
from ...engine.registry import default_registry
from ...provenance.trust import load_trust_root
from ...provenance.verifier import verify_ledger
from ...storage import Scan
from ..deps import get_state, require
from ..state import AppState

router = APIRouter(prefix="/api/system", tags=["system"])
_SANDBOX: dict = {}
_SANDBOX_LOCK = threading.Lock()


def _version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def sandbox_status() -> dict:
    """Start one sandboxed onnxruntime worker on a tiny graph and record which isolation measures held."""
    with _SANDBOX_LOCK:
        if _SANDBOX:
            return _SANDBOX
        try:
            import onnx
            from onnx import TensorProto, helper

            from ...loaders.models.sandbox import SandboxLimits, SandboxWorker

            g = helper.make_graph([helper.make_node("Identity", ["x"], ["y"])], "probe",
                                  [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
                                  [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])])
            m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)])
            m.ir_version = 8
            onnx.checker.check_model(m)
            w = SandboxWorker("onnxruntime", m.SerializeToString(),
                              SandboxLimits(memory_bytes=4 * 1024**3, cpu_seconds=60, call_timeout_s=30,
                                            max_model_bytes=1024 * 1024))
            try:
                header, _ = w.call("probe_isolation")
                _SANDBOX.update(available=True, isolation=w.info, probe=header["result"])
            finally:
                w.close()
        except Exception as exc:  # noqa: BLE001 - reported as unavailable with the reason
            _SANDBOX.update(available=False, error=f"{type(exc).__name__}: {exc}")
        return _SANDBOX


@router.get("/info")
def info(state: AppState = Depends(get_state)) -> dict:
    """Unauthenticated minimal information for the VisionX workspace."""
    return {"product": "VisionX", "version": __version__, "demo_mode": state.settings.demo_mode}


@router.get("/status", dependencies=[Depends(require(Role.VIEWER))])
def system_status(state: AppState = Depends(get_state)) -> dict:
    trust = load_trust_root(state.keys.trust_root)
    audit = None
    if state.keys.audit_ledger.is_file():
        rep = verify_ledger(state.keys.audit_ledger, trust,
                            anchors=state.keys.audit_anchor if state.keys.audit_anchor.is_file() else None)
        audit = {"intact": rep.intact, "counts": rep.counts, "anchors": len(rep.anchors)}
    with state.db.session() as s:
        latest = s.scalars(select(Scan).order_by(Scan.created_at.desc()).limit(1)).first()
        running = s.query(Scan).filter(Scan.status.in_(["PENDING", "PROBING", "PLANNED", "RUNNING"])).count()
    return {
        "version": __version__, "demo_mode": state.settings.demo_mode, "default_profile": state.settings.default_profile,
        "audit_ledger": audit, "running_scans": running,
        "latest_scan": {"id": latest.id, "status": latest.status, "name": latest.name,
                        "overall_disposition": latest.overall_disposition} if latest else None,
        "engine": {"onnxruntime": _version("onnxruntime"), "torch": _version("torch"), "numpy": _version("numpy"),
                   "detectors": len(default_registry())},
        "trust_root": {"digest": trust.digest, "keys": len(trust.keys), "approved_models": len(trust.approved_models)},
        "network": {"outbound": "none — no runtime code path opens external connections",
                    "verified_by": "egress-guarded test suite and 'visionsentinel selftest --airgap'"},
    }


@router.get("/sandbox", dependencies=[Depends(require(Role.VIEWER))])
def sandbox() -> dict:
    return sandbox_status()


@router.get("/detectors", dependencies=[Depends(require(Role.VIEWER))])
def detectors() -> dict:
    return {"detectors": [s.model_dump(mode="json") for s in default_registry().specs()]}


@router.get("/profiles", dependencies=[Depends(require(Role.VIEWER))])
def profiles() -> dict:
    out = []
    reg = default_registry()
    for name in list_profiles():
        p = load_profile(name, reg)
        out.append({"name": p.name, "description": p.description, "budget": p.budget.value, "digest": p.digest,
                    "withheld": [c.value for c in p.access.deny], "seed": p.seed})
    return {"profiles": out}


@router.get("/catalog", dependencies=[Depends(require(Role.VIEWER))])
def catalog() -> dict:
    return {
        "attack_classes": [{"id": a.id, "layer": a.layer.value, "title": a.title, "description": a.description,
                            "unsupported_reason": a.unsupported_reason, "recommended_evidence": list(a.recommended_evidence)}
                           for a in ATTACK_CLASSES.values()],
        "capabilities": [{"id": c.value, "title": i.title, "group": i.group, "description": i.description}
                         for c, i in CAPABILITY_INFO.items()],
    }
