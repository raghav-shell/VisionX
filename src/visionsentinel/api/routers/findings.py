"""Findings endpoints: immutable detector results plus mutable governance state."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import asc, desc, func, select

from ...contracts import Disposition, Finding, Role, ScanStatus, Severity
from ...core.errors import GovernanceError
from ...storage import AuditEvent, Decision, FindingState, Scan
from ..deps import Principal, get_state, mutation, require
from ..state import AppState
from .governance import _decision_http_error, serialize_decision

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/findings", tags=["findings"])


class DecisionRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_disposition: Disposition
    reason_code: str
    justification: str


class OwnerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner: str


class CommentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def _state_dict(row: FindingState) -> dict[str, Any]:
    """Serialize only fields defined by the current FindingState model."""
    return {
        "finding_id": row.finding_id,
        "scan_id": row.scan_id,
        "detector_id": row.detector_id,
        "attack_class": row.attack_class,
        "layer": row.layer,
        "severity": row.severity,
        "original_disposition": row.original_disposition,
        "disposition": row.disposition,
        "deterministic": row.deterministic,
        "title": row.title,
        "confidence": row.confidence,
        "owner": row.owner,
        "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "acknowledged_by": row.acknowledged_by,
        "status": row.status,
    }


def _decision_dict(decision: Decision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
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
    }


def _decision_metadata(decisions: list[Decision]) -> dict[str, dict[str, Any] | None]:
    """Derive pending/latest decisions from timestamps, not a copied status vocabulary."""
    ordered = sorted(decisions, key=lambda item: (item.requested_at, item.id), reverse=True)
    pending = next((item for item in ordered if item.decided_at is None), None)
    latest = ordered[0] if ordered else None
    return {"pending": _decision_dict(pending), "latest": _decision_dict(latest)}


def _decision_metadata_for(s, finding_ids: list[str]) -> dict[str, dict[str, dict[str, Any] | None]]:
    if not finding_ids:
        return {}
    rows = s.scalars(
        select(Decision)
        .where(Decision.finding_id.in_(finding_ids))
        .order_by(desc(Decision.requested_at), desc(Decision.id))
    ).all()
    grouped: dict[str, list[Decision]] = defaultdict(list)
    for row in rows:
        grouped[row.finding_id].append(row)
    return {finding_id: _decision_metadata(grouped.get(finding_id, [])) for finding_id in finding_ids}


def _finding_row(row: FindingState, decisions: dict[str, dict[str, dict[str, Any] | None]]) -> dict[str, Any]:
    result = _state_dict(row)
    result["decisions"] = decisions.get(row.finding_id, {"pending": None, "latest": None})
    return result


def _governance_state_response(row: FindingState) -> dict[str, Any]:
    return {"governance": {"state": _state_dict(row)}}


def _result_status_is_in_progress(scan: Scan) -> bool:
    return scan.status not in {ScanStatus.SEALED.value, ScanStatus.FAILED.value}


def _load_result(state: AppState, scan: Scan):
    if scan.result_path is None:
        if _result_status_is_in_progress(scan):
            raise HTTPException(status.HTTP_409_CONFLICT, "scan result is not ready")
        raise HTTPException(status.HTTP_409_CONFLICT, "sealed scan result is unavailable")
    try:
        result = state.result(scan.id)
    except Exception as exc:  # JSON/schema failures must not leak paths or internals.
        log.warning("unable to load result for scan %s: %s", scan.id, type(exc).__name__)
        raise HTTPException(status.HTTP_409_CONFLICT, "sealed scan result is invalid") from exc
    if result is None:
        if _result_status_is_in_progress(scan):
            raise HTTPException(status.HTTP_409_CONFLICT, "scan result is not ready")
        raise HTTPException(status.HTTP_409_CONFLICT, "sealed scan result is unavailable")
    return result


def _immutable_finding(result, finding_id: str) -> Finding:
    finding = next((item for item in result.findings if item.id == finding_id), None)
    if finding is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "sealed result does not contain the requested finding")
    return finding


@router.get("", dependencies=[Depends(require(Role.VIEWER))])
def list_findings(
    scan_id: str | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    disposition: Disposition | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as s:
        filters = []
        if scan_id:
            filters.append(FindingState.scan_id == scan_id)
        if severity is not None:
            filters.append(FindingState.severity == severity.value)
        if disposition is not None:
            filters.append(FindingState.disposition == disposition.value)

        base = select(FindingState).where(*filters)
        total = s.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = s.scalars(base.order_by(asc(FindingState.finding_id)).offset(offset).limit(limit)).all()
        decisions = _decision_metadata_for(s, [row.finding_id for row in rows])
        return {"total": total, "findings": [_finding_row(row, decisions) for row in rows]}


@router.get("/{finding_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_finding(finding_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        row = s.get(FindingState, finding_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"finding {finding_id!r} not found")
        scan = s.get(Scan, row.scan_id)
        decisions = _decision_metadata_for(s, [finding_id]).get(finding_id, {"pending": None, "latest": None})

    if scan is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "finding parent scan is unavailable")
    result = _load_result(state, scan)
    finding = _immutable_finding(result, finding_id)
    return {
        "immutable": finding.model_dump(mode="json"),
        "governance": {"state": _state_dict(row), "decisions": decisions},
    }


@router.post("/{finding_id}/acknowledge")
def acknowledge_finding(
    finding_id: str,
    principal: Principal = Depends(mutation(Role.VIEWER)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        row = state.governance.acknowledge(principal.user, finding_id)
        return _governance_state_response(row)
    except GovernanceError as exc:
        raise _decision_http_error(exc) from exc


@router.post("/{finding_id}/owner")
def assign_finding_owner(
    finding_id: str,
    body: OwnerBody,
    principal: Principal = Depends(mutation(Role.VIEWER)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        row = state.governance.assign(principal.user, finding_id, body.owner)
        return _governance_state_response(row)
    except GovernanceError as exc:
        raise _decision_http_error(exc) from exc


@router.post("/{finding_id}/comment")
def comment_on_finding(
    finding_id: str,
    body: CommentBody,
    principal: Principal = Depends(mutation(Role.VIEWER)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        state.governance.comment(principal.user, finding_id, body.text)
        with state.db.session() as session:
            row = session.get(FindingState, finding_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"finding {finding_id!r} not found")
        return _governance_state_response(row)
    except GovernanceError as exc:
        raise _decision_http_error(exc) from exc


@router.get("/{finding_id}/history", dependencies=[Depends(require(Role.VIEWER))])
def finding_governance_history(finding_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as session:
        if session.get(FindingState, finding_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"finding {finding_id!r} not found")
        rows = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.target == finding_id)
            .order_by(asc(AuditEvent.id))
        ).all()
        return {
            "finding_id": finding_id,
            "total": len(rows),
            "events": [
                {
                    "id": row.id,
                    "timestamp": row.ts.isoformat() if row.ts else None,
                    "actor": row.actor,
                    "action": row.action,
                    "old_state": row.old_state,
                    "new_state": row.new_state,
                    "reason_code": row.reason_code,
                    "justification": row.justification,
                    "ledger_seq": row.ledger_seq,
                    "entry_hash": row.entry_hash,
                }
                for row in rows
            ],
        }


@router.post("/{finding_id}/decision", status_code=status.HTTP_201_CREATED)
def request_decision(
    finding_id: str,
    body: DecisionRequestBody,
    principal: Principal = Depends(mutation(Role.ANALYST)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        dec = state.governance.request_decision(
            actor=principal.user,
            finding_id=finding_id,
            to=body.target_disposition,
            reason_code=body.reason_code,
            justification=body.justification,
        )
        with state.db.session() as session:
            return serialize_decision(dec, session.get(FindingState, dec.finding_id))
    except GovernanceError as exc:
        raise _decision_http_error(exc) from exc
