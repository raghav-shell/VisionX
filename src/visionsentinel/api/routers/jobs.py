"""Read-only API for persisted local background jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select

from ...contracts import JobStatus, Role
from ...storage import Job
from ..deps import get_state, require
from ..state import AppState

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def serialize_job(job: Job) -> dict:
    """Serialize only persisted job data and safe derived lifecycle information."""
    return {
        "id": job.id,
        "kind": job.kind,
        "subject": job.subject,
        "status": job.status,
        "terminal": _is_terminal(job.status),
        "started_by": job.started_by,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "steps": list(job.steps or []),
        "scan_id": job.scan_id,
        "result": job.result,
        "error": job.error,
    }


def _is_terminal(value: str) -> bool:
    try:
        return JobStatus(value).terminal
    except ValueError:
        return False


def _status_filter(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return JobStatus(value.upper()).value
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unsupported job status") from exc


@router.get("", dependencies=[Depends(require(Role.VIEWER))])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    kind: str | None = Query(default=None, min_length=1),
    started_by: str | None = Query(default=None, min_length=1),
    state: AppState = Depends(get_state),
) -> dict:
    requested_status = _status_filter(status_filter)
    with state.db.session() as session:
        query = select(Job)
        count_query = select(func.count()).select_from(Job)
        if requested_status is not None:
            query = query.where(Job.status == requested_status)
            count_query = count_query.where(Job.status == requested_status)
        if kind is not None:
            query = query.where(Job.kind == kind)
            count_query = count_query.where(Job.kind == kind)
        if started_by is not None:
            query = query.where(Job.started_by == started_by)
            count_query = count_query.where(Job.started_by == started_by)
        query = query.order_by(desc(Job.started_at), desc(Job.id)).offset(offset).limit(limit)
        rows = session.scalars(query).all()
        total = session.scalar(count_query) or 0
        return {"total": total, "offset": offset, "limit": limit,
                "jobs": [serialize_job(job) for job in rows]}


@router.get("/{job_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_job(job_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"job {job_id!r} not found")
        return serialize_job(job)
