"""Governance endpoints: two-person rule approval, rejection and cryptographic audit log queries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from ...contracts import Role
from ...provenance.trust import load_trust_root
from ...provenance.verifier import verify_ledger
from ...storage import AuditEvent, Decision
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/governance", tags=["governance"])


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    justification: str = Field(min_length=1, max_length=1000)


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    justification: str = Field(min_length=1, max_length=1000)


@router.get("/decisions", dependencies=[Depends(require(Role.VIEWER))])
def list_decisions(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as s:
        q = select(Decision).order_by(desc(Decision.created_at))
        if status_filter:
            q = q.filter(Decision.status == status_filter.upper())
        total = s.query(Decision).count()
        rows = s.scalars(q.offset(offset).limit(limit)).all()
        return {
            "total": total,
            "decisions": [
                {
                    "id": r.id,
                    "finding_id": r.finding_id,
                    "scan_id": r.scan_id,
                    "requested_by": r.requested_by,
                    "approved_by": r.approved_by,
                    "status": r.status,
                    "original_disposition": r.original_disposition,
                    "target_disposition": r.target_disposition,
                    "effective_disposition": r.effective_disposition,
                    "reason_code": r.reason_code,
                    "justification": r.justification,
                    "requires_second_user": r.requires_second_user,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "decided_at": r.decided_at.isoformat() if r.decided_at else None,
                }
                for r in rows
            ],
        }


@router.post("/decisions/{decision_id}/approve")
def approve_decision(
    decision_id: str,
    body: ApproveBody,
    principal: Principal = Depends(mutation(Role.APPROVER)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        dec = state.governance.approve(
            actor=principal.user,
            decision_id=decision_id,
            note=body.justification,
        )
        return {
            "decision_id": dec.id,
            "status": dec.status,
            "approved_by": dec.decided_by,
            "effective_disposition": dec.to_disposition,
        }
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/decisions/{decision_id}/reject")
def reject_decision(
    decision_id: str,
    body: RejectBody,
    principal: Principal = Depends(mutation(Role.APPROVER)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        dec = state.governance.reject(
            actor=principal.user,
            decision_id=decision_id,
            note=body.justification,
        )
        return {
            "decision_id": dec.id,
            "status": dec.status,
            "decided_by": dec.decided_by,
        }
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/audit", dependencies=[Depends(require(Role.VIEWER))])
def list_audit_events(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    verify: bool = Query(default=False),
    state: AppState = Depends(get_state),
) -> dict:
    verification = None
    if verify and state.keys.audit_ledger.is_file():
        trust = load_trust_root(state.keys.trust_root)
        rep = verify_ledger(
            state.keys.audit_ledger,
            trust,
            anchors=state.keys.audit_anchor if state.keys.audit_anchor.is_file() else None,
        )
        verification = {
            "intact": rep.intact,
            "valid_records": rep.counts.get("VALID", 0),
            "failed_records": rep.counts.get("FAILED", 0),
            "untrusted_records": rep.counts.get("UNTRUSTED", 0),
            "anchors_verified": len(rep.anchors),
        }

    with state.db.session() as s:
        q = select(AuditEvent).order_by(desc(AuditEvent.id))
        if actor:
            q = q.filter(AuditEvent.actor == actor)
        if action:
            q = q.filter(AuditEvent.action == action)
        total = s.query(AuditEvent).count()
        rows = s.scalars(q.offset(offset).limit(limit)).all()
        return {
            "total": total,
            "verification": verification,
            "events": [
                {
                    "id": r.id,
                    "timestamp": r.ts.isoformat() if r.ts else None,
                    "actor": r.actor,
                    "action": r.action,
                    "target": r.target,
                    "old_state": r.old_state,
                    "new_state": r.new_state,
                    "justification": r.justification,
                    "ledger_seq": r.ledger_seq,
                    "entry_hash": r.entry_hash,
                }
                for r in rows
            ],
        }
