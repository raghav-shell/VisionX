"""Provenance and Cryptographic Inference Ledger endpoints."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ...contracts import AssetLifecycle, Role
from ...provenance.keys import generate_key, save_private_key, trust_entry
from ...provenance.ledger import LedgerWriter
from ...provenance.trust import TrustRootError, load_trust_root, parse_trust_root
from ...provenance.verifier import verify_ledger
from ...storage import Asset
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


class VerifyLedgerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_asset_id: str | None = None
    trust_root_asset_id: str | None = None
    anchor_asset_id: str | None = None
    inputs_asset_id: str | None = None


class TamperLedgerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_asset_id: str | None = None
    tamper_mode: str = Field(description="edit | delete | swap | replay | truncate | bad_sig")
    target_seq: int = Field(default=2, ge=0)
    new_output_label: str = Field(default="civilian_vehicle")


class TrustRootImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trust_root_asset_id: str


class RevokeKeyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key_id: str = Field(min_length=12, max_length=80)
    reason: str = Field(min_length=10, max_length=500)


class RotateKeyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(pattern="^(ledger|audit|report)$")
    reason: str = Field(min_length=10, max_length=500)


def _write_trust_root(state: AppState, document: dict) -> None:
    """Validate then atomically install a public trust root; preserve the prior root for recovery."""
    rendered = json.dumps(document, indent=1, sort_keys=True).encode("utf-8") + b"\n"
    parse_trust_root(rendered)
    root = state.keys.trust_root
    backup = root.with_suffix(".previous.json")
    if root.exists():
        backup.write_bytes(root.read_bytes())
    pending = root.with_suffix(".pending")
    pending.write_bytes(rendered)
    pending.replace(root)


def _asset_file(asset_id: str, kinds: tuple[str, ...], state: AppState, field: str) -> Path:
    with state.db.session() as s:
        asset = s.get(Asset, asset_id)
        if asset is None or asset.kind not in kinds:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"{field} must identify an imported {'/'.join(kinds)} asset")
        if (asset.details or {}).get("lifecycle", AssetLifecycle.ACTIVE.value) != AssetLifecycle.ACTIVE.value:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{field} is archived")
        return Path(asset.path)


@router.post("/verify", dependencies=[Depends(require(Role.VIEWER))])
def verify_ledger_endpoint(body: VerifyLedgerBody, state: AppState = Depends(get_state)) -> dict:
    def asset_path(asset_id: str | None, field: str) -> Path | None:
        if not asset_id:
            return None
        expected = {"ledger_asset_id": ("ledger",), "trust_root_asset_id": ("trust_root",),
                    "anchor_asset_id": ("anchor",), "inputs_asset_id": ("inputs",)}[field]
        return _asset_file(asset_id, expected, state, field)

    # The local audit ledger/trust root are trusted defaults. All operator-supplied
    # input is resolved through the workspace asset registry, never as a raw path.
    ledger_file = asset_path(body.ledger_asset_id, "ledger_asset_id") or state.keys.audit_ledger

    if not ledger_file.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"ledger file {str(ledger_file)!r} not found")

    trust = load_trust_root(asset_path(body.trust_root_asset_id, "trust_root_asset_id") or state.keys.trust_root)

    anchors = asset_path(body.anchor_asset_id, "anchor_asset_id") or (state.keys.audit_anchor if state.keys.audit_anchor.is_file() else None)
    inputs = asset_path(body.inputs_asset_id, "inputs_asset_id")

    report = verify_ledger(ledger_file, trust, anchors=anchors, inputs=inputs)
    return report.to_dict()


@router.get("/inspect", dependencies=[Depends(require(Role.VIEWER))])
def inspect_ledger(
    asset_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    state: AppState = Depends(get_state),
) -> dict:
    ledger_file = state.keys.audit_ledger
    if asset_id:
        with state.db.session() as s:
            a = s.get(Asset, asset_id)
            if a is None or a.kind != "ledger":
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "asset_id must identify an imported ledger")
            ledger_file = Path(a.path)

    if not ledger_file.is_file():
        return {"records": [], "count": 0}

    lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
    records = []
    for line in lines[-limit:]:
        if line.strip():
            try:
                records.append(json.loads(line))
            except Exception:
                continue

    return {"records": records, "count": len(records), "source": "asset" if asset_id else "audit_ledger"}


@router.get("/trust-root", dependencies=[Depends(require(Role.VIEWER))])
def trust_root_status(state: AppState = Depends(get_state)) -> dict:
    raw = json.loads(state.keys.trust_root.read_text(encoding="utf-8"))
    parsed = load_trust_root(state.keys.trust_root)
    return {"digest": parsed.digest, "name": parsed.name, "keys": raw.get("keys", []),
            "approved_models": raw.get("approved_models", []), "recovery_backup_present": state.keys.trust_root.with_suffix(".previous.json").is_file()}


@router.post("/trust-root/import")
def import_trust_root(body: TrustRootImportBody, principal: Principal = Depends(mutation(Role.ADMIN)),
                      state: AppState = Depends(get_state)) -> dict:
    source = _asset_file(body.trust_root_asset_id, ("trust_root",), state, "trust_root_asset_id")
    try:
        doc = json.loads(source.read_text(encoding="utf-8"))
        _write_trust_root(state, doc)
    except (OSError, ValueError, TrustRootError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid trust root: {exc}") from exc
    state.audit.record(principal.username, "import_trust_root", body.trust_root_asset_id,
                       new=load_trust_root(state.keys.trust_root).digest)
    return trust_root_status(state)


@router.post("/trust-root/revoke")
def revoke_trust_key(body: RevokeKeyBody, principal: Principal = Depends(mutation(Role.ADMIN)),
                     state: AppState = Depends(get_state)) -> dict:
    doc = json.loads(state.keys.trust_root.read_text(encoding="utf-8"))
    entry = next((x for x in doc.get("keys", []) if x.get("key_id") == body.key_id), None)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "key not found in active trust root")
    entry["revoked"] = True
    entry["comment"] = (str(entry.get("comment", "")) + f" | revoked: {body.reason}")[:200]
    _write_trust_root(state, doc)
    state.audit.record(principal.username, "revoke_trust_key", body.key_id, old="ACTIVE", new="REVOKED",
                       justification=body.reason)
    return trust_root_status(state)


@router.post("/trust-root/rotate")
def rotate_workspace_key(body: RotateKeyBody, principal: Principal = Depends(mutation(Role.ADMIN)),
                         state: AppState = Depends(get_state)) -> dict:
    """Rotate a workspace signer and retain the public predecessor for historical verification."""
    key = generate_key()
    save_private_key(key, state.workspace.keys / f"{body.role}.pem")
    doc = json.loads(state.keys.trust_root.read_text(encoding="utf-8"))
    for entry in doc.get("keys", []):
        if body.role in entry.get("roles", []) and not entry.get("revoked"):
            entry["revoked"] = True
            entry["comment"] = (str(entry.get("comment", "")) + " | superseded by rotation")[:200]
    doc.setdefault("keys", []).append(trust_entry(key, [body.role, "anchor"] if body.role != "report" else ["report"],
                                                     f"workspace {body.role} key (rotated)"))
    _write_trust_root(state, doc)
    setattr(state.keys, body.role, key)
    if body.role == "audit":
        state.audit.ledger = LedgerWriter(state.keys.audit_ledger, key, purpose="audit", checkpoint_every=32,
                                          anchor_path=state.keys.audit_anchor)
    state.audit.record(principal.username, "rotate_workspace_key", body.role, old="ACTIVE", new="ROTATED",
                       justification=body.reason)
    return trust_root_status(state)


@router.get("/anchors/export", dependencies=[Depends(require(Role.VIEWER))])
def export_anchors(state: AppState = Depends(get_state)) -> Response:
    if not state.keys.audit_anchor.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no audit anchors have been produced yet")
    return Response(content=state.keys.audit_anchor.read_bytes(), media_type="application/x-ndjson",
                    headers={"Content-Disposition": 'attachment; filename="audit.anchors.jsonl"'})


@router.post("/anchors/verify", dependencies=[Depends(require(Role.VIEWER))])
def verify_anchor_import(body: VerifyLedgerBody, state: AppState = Depends(get_state)) -> dict:
    if not body.anchor_asset_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "anchor_asset_id is required")
    anchors = _asset_file(body.anchor_asset_id, ("anchor",), state, "anchor_asset_id")
    ledger = _asset_file(body.ledger_asset_id, ("ledger",), state, "ledger_asset_id") if body.ledger_asset_id else state.keys.audit_ledger
    trust = load_trust_root(state.keys.trust_root)
    return verify_ledger(ledger, trust, anchors=anchors).to_dict()


@router.post("/tamper")
def simulate_tamper(
    body: TamperLedgerBody,
    principal: Principal = Depends(mutation(Role.ANALYST)),
    state: AppState = Depends(get_state),
) -> dict:
    """Generate a tampered copy of a ledger for live defence verification demonstration."""
    source_ledger = state.keys.audit_ledger
    if body.ledger_asset_id:
        with state.db.session() as s:
            a = s.get(Asset, body.ledger_asset_id)
            if a:
                source_ledger = Path(a.path)

    if not source_ledger.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "source ledger not found")

    lines = [json.loads(line) for line in source_ledger.read_text(encoding="utf-8").strip().splitlines() if line.strip()]
    if len(lines) < 3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ledger has too few records to simulate attack")

    target_idx = min(body.target_seq, len(lines) - 1)
    tampered = list(lines)

    if body.tamper_mode == "edit":
        rec = dict(tampered[target_idx])
        if "body" in rec and isinstance(rec["body"], dict):
            body_dict = dict(rec["body"])
            if "output" in body_dict and isinstance(body_dict["output"], dict):
                body_dict["output"] = dict(body_dict["output"])
                body_dict["output"]["label"] = body.new_output_label
            else:
                body_dict["tampered"] = True
            rec["body"] = body_dict
        tampered[target_idx] = rec
    elif body.tamper_mode == "delete":
        tampered.pop(target_idx)
    elif body.tamper_mode == "swap":
        if target_idx < len(tampered) - 1:
            tampered[target_idx], tampered[target_idx + 1] = tampered[target_idx + 1], tampered[target_idx]
    elif body.tamper_mode == "replay":
        tampered.insert(target_idx, dict(tampered[target_idx]))
    elif body.tamper_mode == "bad_sig":
        rec = dict(tampered[target_idx])
        rec["sig"] = "00" * 64
        tampered[target_idx] = rec
    elif body.tamper_mode == "truncate":
        tampered = tampered[:target_idx]

    out_dir = state.workspace.root / "tampered_ledgers"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"tampered_{body.tamper_mode}_{secrets.token_hex(4)}.jsonl"
    with out_file.open("w", encoding="utf-8") as f:
        for rec in tampered:
            f.write(json.dumps(rec) + "\n")

    return {
        "tampered_ledger": out_file.name,
        "mode": body.tamper_mode,
        "target_seq": target_idx,
        "original_count": len(lines),
        "tampered_count": len(tampered),
    }
