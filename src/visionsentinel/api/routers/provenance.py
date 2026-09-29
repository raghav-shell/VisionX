"""Provenance and Cryptographic Inference Ledger endpoints."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ...contracts import Role
from ...provenance.trust import load_trust_root
from ...provenance.verifier import verify_ledger
from ...storage import Asset
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


class VerifyLedgerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_path: str | None = None
    ledger_asset_id: str | None = None
    trust_root_path: str | None = None
    anchor_path: str | None = None
    inputs_dir: str | None = None


class TamperLedgerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_asset_id: str | None = None
    tamper_mode: str = Field(description="edit | delete | swap | replay | truncate | bad_sig")
    target_seq: int = Field(default=2, ge=0)
    new_output_label: str = Field(default="civilian_vehicle")


@router.post("/verify", dependencies=[Depends(require(Role.VIEWER))])
def verify_ledger_endpoint(body: VerifyLedgerBody, state: AppState = Depends(get_state)) -> dict:
    ledger_file: Path | None = None
    if body.ledger_asset_id:
        with state.db.session() as s:
            a = s.get(Asset, body.ledger_asset_id)
            if a:
                ledger_file = Path(a.path)
    elif body.ledger_path:
        ledger_file = Path(body.ledger_path)
    else:
        # Default to workspace audit ledger if exists
        ledger_file = state.keys.audit_ledger

    if not ledger_file or not ledger_file.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"ledger file {str(ledger_file)!r} not found")

    trust_root_path = Path(body.trust_root_path) if body.trust_root_path else state.keys.trust_root
    trust = load_trust_root(trust_root_path)

    anchors = Path(body.anchor_path) if body.anchor_path else (state.keys.audit_anchor if state.keys.audit_anchor.is_file() else None)
    inputs = Path(body.inputs_dir) if body.inputs_dir else None

    report = verify_ledger(ledger_file, trust, anchors=anchors, inputs_dir=inputs)
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
            if a:
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

    return {"records": records, "count": len(records), "ledger_path": str(ledger_file)}


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
        "tampered_path": str(out_file),
        "mode": body.tamper_mode,
        "target_seq": target_idx,
        "original_count": len(lines),
        "tampered_count": len(tampered),
    }
