"""Findings endpoints: inspection and disposition override requests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from ...contracts import Disposition, Role, Severity
from ...storage import Decision, FindingState
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/findings", tags=["findings"])


class DecisionRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_disposition: Disposition
    reason_code: str = Field(min_length=1, max_length=64)
    justification: str = Field(min_length=1, max_length=1000)


@router.get("", dependencies=[Depends(require(Role.VIEWER))])
def list_findings(
    scan_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    disposition: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as s:
        q = select(FindingState).order_by(desc(FindingState.created_at))
        if scan_id:
            q = q.filter(FindingState.scan_id == scan_id)
        if severity:
            q = q.filter(FindingState.severity == severity.upper())
        if disposition:
            q = q.filter(FindingState.disposition == disposition.upper())

        total = s.query(FindingState).count()
        rows = s.scalars(q.offset(offset).limit(limit)).all()
        return {
            "total": total,
            "findings": [
                {
                    "finding_id": r.finding_id,
                    "scan_id": r.scan_id,
                    "detector_id": r.detector_id,
                    "attack_class": r.attack_class,
                    "layer": r.layer,
                    "severity": r.severity,
                    "original_disposition": r.original_disposition,
                    "disposition": r.disposition,
                    "deterministic": r.deterministic,
                    "title": r.title,
                    "confidence": r.confidence,
                    "owner": r.owner,
                    "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
                    "acknowledged_by": r.acknowledged_by,
                    "decision_id": r.decision_id,
                }
                for r in rows
            ],
        }


@router.get("/{finding_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_finding(finding_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        fs = s.get(FindingState, finding_id)
        if fs is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"finding {finding_id!r} not found")
        scan_id = fs.scan_id

    # Retrieve detailed finding object from scan result
    res = state.result(scan_id)
    if res is not None:
        for f in res.findings:
            if f.id == finding_id:
                out = f.model_dump(mode="json")
                out["current_disposition"] = fs.disposition
                out["owner"] = fs.owner
                out["acknowledged_by"] = fs.acknowledged_by
                return out

    return {
        "id": fs.finding_id,
        "scan_id": fs.scan_id,
        "detector_id": fs.detector_id,
        "attack_class": fs.attack_class,
        "severity": fs.severity,
        "recommended_disposition": fs.original_disposition,
        "disposition": fs.disposition,
        "title": fs.title,
        "confidence": fs.confidence,
        "owner": fs.owner,
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
        return {
            "decision_id": dec.id,
            "status": dec.status,
            "finding_id": dec.finding_id,
            "target_disposition": dec.to_disposition,
            "requires_second_user": dec.sensitive,
            "from_disposition": dec.from_disposition,
        }
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
