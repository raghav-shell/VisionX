"""Governance endpoints: two-person rule approval, rejection and cryptographic audit log queries."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, func, select

from ...contracts import Role
from ...core.errors import AuthorizationError, DecisionConflictError, DecisionNotFoundError, GovernanceError
from ...provenance.trust import load_trust_root
from ...provenance.verifier import verify_ledger
from ...storage import AuditEvent, Decision, FindingState
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/governance", tags=["governance"])


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    justification: str = ""


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    justification: str = ""


def serialize_decision(decision: Decision, finding_state: FindingState | None = None) -> dict[str, Any]:
    """Canonical Decision representation using persisted fields plus derived finding state."""
    return {
        "id": decision.id,
        "finding_id": decision.finding_id,
        "scan_id": decision.scan_id,
        "requested_by": decision.requested_by,
        "requested_at": decision.requested_at.isoformat() if decision.requested_at else None,
        "from_disposition": decision.from_disposition,
        "to_disposition": decision.to_disposition,
        "reason_code": decision.reason_code,
        "justification": decision.justification,
        "sensitive": decision.sensitive,
        "status": decision.status,
        "decided_by": decision.decided_by,
        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
        "decision_note": decision.decision_note,
        "current_disposition": finding_state.disposition if finding_state is not None else None,
    }


def _decision_http_error(exc: GovernanceError) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    if isinstance(exc, DecisionNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, DecisionConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


def _finding_states(s, finding_ids: list[str]) -> dict[str, FindingState]:
    if not finding_ids:
        return {}
    rows = s.scalars(select(FindingState).where(FindingState.finding_id.in_(finding_ids))).all()
    return {row.finding_id: row for row in rows}


@router.get("/decisions", dependencies=[Depends(require(Role.VIEWER))])
def list_decisions(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as s:
        filters = []
        if status_filter:
            filters.append(Decision.status == status_filter.upper())
        base = select(Decision).where(*filters)
        total = s.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = s.scalars(base.order_by(desc(Decision.requested_at), desc(Decision.id)).offset(offset).limit(limit)).all()
        finding_states = _finding_states(s, [row.finding_id for row in rows])
        return {
            "total": total,
            "decisions": [serialize_decision(r, finding_states.get(r.finding_id)) for r in rows],
        }


@router.get("/decisions/{decision_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_decision(decision_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        decision = s.get(Decision, decision_id)
        if decision is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"decision {decision_id!r} not found")
        finding_state = s.get(FindingState, decision.finding_id)
        return serialize_decision(decision, finding_state)


@router.post("/decisions/{decision_id}/approve")
def approve_decision(
    decision_id: str,
    body: ApproveBody,
    principal: Principal = Depends(mutation(Role.VIEWER)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        dec = state.governance.approve(
            actor=principal.user,
            decision_id=decision_id,
            note=body.justification,
        )
        with state.db.session() as s:
            return serialize_decision(dec, s.get(FindingState, dec.finding_id))
    except GovernanceError as exc:
        raise _decision_http_error(exc) from exc


@router.post("/decisions/{decision_id}/reject")
def reject_decision(
    decision_id: str,
    body: RejectBody,
    principal: Principal = Depends(mutation(Role.VIEWER)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        dec = state.governance.reject(
            actor=principal.user,
            decision_id=decision_id,
            note=body.justification,
        )
        with state.db.session() as s:
            return serialize_decision(dec, s.get(FindingState, dec.finding_id))
    except GovernanceError as exc:
        raise _decision_http_error(exc) from exc


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
