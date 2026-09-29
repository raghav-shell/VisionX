"""Background execution of scans and jobs, with persisted progress for the live event stream."""

from __future__ import annotations

import json
import logging
import secrets
import traceback
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from ..contracts import JobStatus, ScanResult, ScanStatus
from ..core.errors import RunnerUnavailableError
from ..engine.request import ScanRequest
from ..engine.scan import new_scan_id, run_scan
from ..reporting import write_report
from ..storage import FindingState, Job, Scan, ScanEvent
from .state import AppState

log = logging.getLogger(__name__)

INTERRUPTED_SCAN_REASON = "interrupted by previous process shutdown"
INTERRUPTED_JOB_REASON = "interrupted by previous process shutdown"


def recover_interrupted_work(state: AppState) -> dict[str, int]:
    """Reconcile work that cannot have a surviving worker after a process restart."""
    recovered_scans: list[tuple[str, str]] = []
    recovered_jobs: list[tuple[str, str]] = []
    active_scans = {status.value for status in ScanStatus if not status.terminal}
    with state.db.session() as session:
        scans = session.scalars(select(Scan).where(Scan.status.in_(active_scans))).all()
        for scan in scans:
            old = scan.status
            scan.status = ScanStatus.FAILED.value
            scan.completed_at = _now()
            scan.error = INTERRUPTED_SCAN_REASON
            last_seq = max((seq for (seq,) in session.query(ScanEvent.seq)
                            .filter(ScanEvent.scan_id == scan.id).all()), default=0)
            session.add(ScanEvent(scan_id=scan.id, seq=last_seq + 1, t_ms=0, level="error",
                                  message=INTERRUPTED_SCAN_REASON))
            recovered_scans.append((scan.id, old))

        jobs = session.scalars(select(Job).where(Job.status == JobStatus.RUNNING.value)).all()
        for job in jobs:
            old = job.status
            job.status = JobStatus.FAILED.value
            job.completed_at = _now()
            job.error = INTERRUPTED_JOB_REASON
            steps = list(job.steps or [])
            steps.append({"name": "recovery", "detail": INTERRUPTED_JOB_REASON, "status": "error",
                          "at": _now().isoformat()})
            job.steps = steps
            recovered_jobs.append((job.id, old))

    for scan_id, old in recovered_scans:
        state.audit.record("system", "recover_scan", scan_id, old=old, new=ScanStatus.FAILED.value,
                           justification=INTERRUPTED_SCAN_REASON)
    for job_id, old in recovered_jobs:
        state.audit.record("system", "recover_job", job_id, old=old, new=JobStatus.FAILED.value,
                           justification=INTERRUPTED_JOB_REASON)
    return {"scans": len(recovered_scans), "jobs": len(recovered_jobs)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def index_result(state: AppState, result: ScanResult, report_dir: str | None) -> None:
    """Persist a sealed result: JSON file, scan summary row and mutable finding-state rows."""
    path = state.workspace.scans / f"{result.scan_id}.json"
    path.write_text(result.model_dump_json())
    s_ = result.summary
    with state.db.session() as s:
        scan = s.get(Scan, result.scan_id)
        if scan is None:
            scan = Scan(id=result.scan_id, name=result.name, status=result.status.value, profile=result.profile,
                        created_at=result.created_at)
            s.add(scan)
        scan.status = result.status.value
        scan.completed_at = result.completed_at
        scan.overall_disposition = s_.overall_disposition.value if s_ else None
        scan.findings = len(result.findings)
        scan.critical = sum(1 for f in result.findings if f.severity.value == "CRITICAL")
        scan.quarantine = sum(1 for f in result.findings if f.recommended_disposition.value == "QUARANTINE")
        scan.review = sum(1 for f in result.findings if f.recommended_disposition.value == "REVIEW")
        scan.coverage_assessed, scan.coverage_partial, scan.coverage_total = (
            result.coverage.assessed, result.coverage.partial, result.coverage.total)
        scan.result_path, scan.report_dir, scan.report_digest = str(path), report_dir, result.report_digest
        scan.plan = {"plan": [n.model_dump(mode="json") for n in result.plan]}
        s.flush()
        layers = {e.detector_id: e.layer.value for e in result.executions}
        for f in result.findings:
            if s.get(FindingState, f.id) is None:
                s.add(FindingState(finding_id=f.id, scan_id=result.scan_id, detector_id=f.detector_id,
                                   attack_class=f.attack_class, layer=layers.get(f.detector_id, ""),
                                   severity=f.severity.value, original_disposition=f.recommended_disposition.value,
                                   disposition=f.recommended_disposition.value, deterministic=f.deterministic,
                                   title=f.title[:500], confidence=f.confidence))


class JobContext:
    def __init__(self, state: AppState, job_id: str) -> None:
        self.state, self.job_id = state, job_id

    def step(self, name: str, detail: str = "", status: str = "done", data: dict | None = None) -> None:
        with self.state.db.session() as s:
            job = s.get(Job, self.job_id)
            steps = list(job.steps or [])
            steps.append({"name": name, "detail": detail, "status": status, "at": _now().isoformat(),
                          **({"data": data} if data else {})})
            job.steps = steps

    def link_scan(self, scan_id: str) -> None:
        with self.state.db.session() as s:
            s.get(Job, self.job_id).scan_id = scan_id


class JobRunner:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self._lifecycle_lock = threading.Lock()
        self._accepting = True
        self.pool = ThreadPoolExecutor(max_workers=state.settings.scan_workers, thread_name_prefix="vs-job")

    def _ensure_accepting(self) -> None:
        if not self._accepting:
            raise RunnerUnavailableError("background work is unavailable during application shutdown")

    # ------------------------------------------------------------------ scans
    def create_scan(self, request: ScanRequest, user: str | None) -> tuple[str, ScanRequest]:
        scan_id = new_scan_id(_now())
        request = request.model_copy(update={"scan_id": scan_id})
        with self.state.db.session() as s:
            s.add(Scan(id=scan_id, name=request.name, status=ScanStatus.PENDING.value, profile=request.profile,
                       request=json.loads(request.model_dump_json()), created_by=user))
        self.state.audit.record(user or "system", "start_scan", scan_id, new=ScanStatus.PENDING.value,
                                extra={"profile": request.profile})
        return scan_id, request

    def submit_scan(self, request: ScanRequest, user: str | None) -> str:
        with self._lifecycle_lock:
            self._ensure_accepting()
            scan_id, request = self.create_scan(request, user)
            self.pool.submit(self.execute_scan, scan_id, request)
        return scan_id

    def execute_scan(self, scan_id: str, request: ScanRequest) -> ScanResult | None:
        db = self.state.db

        def on_event(ev) -> None:
            with db.session() as s:
                s.add(ScanEvent(scan_id=scan_id, seq=ev.seq, t_ms=ev.t_ms, level=ev.level, message=ev.message[:2000],
                                detector_id=ev.detector_id))

        def on_plan(result: ScanResult) -> None:
            with db.session() as s:
                s.execute(update(Scan).where(Scan.id == scan_id).values(
                    status=ScanStatus.RUNNING.value,
                    plan={"plan": [n.model_dump(mode="json") for n in result.plan],
                          "capabilities": [c.model_dump(mode="json") for c in result.capabilities]}))

        with db.session() as s:
            s.execute(update(Scan).where(Scan.id == scan_id).values(status=ScanStatus.PROBING.value))
        try:
            result = run_scan(request, workspace=self.state.workspace, on_event=on_event, on_plan=on_plan)
            paths = write_report(result, self.state.workspace.reports, self.state.store, self.state.keys.report)
            index_result(self.state, result, str(paths["report.html"].parent))
            self.state.audit.record("system", "seal_scan", scan_id, old=ScanStatus.RUNNING.value,
                                    new=ScanStatus.SEALED.value, extra={"report_digest": result.report_digest})
            return result
        except Exception as exc:  # noqa: BLE001 - recorded as a failed scan, never swallowed
            log.exception("scan %s failed", scan_id)
            with db.session() as s:
                s.execute(update(Scan).where(Scan.id == scan_id).values(
                    status=ScanStatus.FAILED.value, error=f"{type(exc).__name__}: {exc}"[:2000],
                    completed_at=_now()))
                last = max((seq for (seq,) in s.query(ScanEvent.seq).filter(ScanEvent.scan_id == scan_id).all()), default=0)
                s.add(ScanEvent(scan_id=scan_id, seq=last + 1, t_ms=0, level="error",
                                message=f"scan failed: {type(exc).__name__}"))
            self.state.audit.record("system", "scan_failed", scan_id, new=ScanStatus.FAILED.value,
                                    justification=traceback.format_exception_only(type(exc), exc)[-1][:500])
            return None

    # ------------------------------------------------------------------ generic jobs
    def submit_job(self, kind: str, subject: str, user: str | None, fn: Callable[[JobContext], dict[str, Any]]) -> str:
        job_id = f"JOB-{secrets.token_hex(4).upper()}"
        with self._lifecycle_lock:
            self._ensure_accepting()
            with self.state.db.session() as s:
                s.add(Job(id=job_id, kind=kind, subject=subject, status=JobStatus.RUNNING.value,
                          started_by=user, steps=[]))
            self.state.audit.record(user or "system", f"start_{kind}", subject, extra={"job_id": job_id})
            self.pool.submit(self._run_job, job_id, fn)
        return job_id

    def _run_job(self, job_id: str, fn: Callable[[JobContext], dict[str, Any]]) -> None:
        ctx = JobContext(self.state, job_id)
        try:
            result = fn(ctx)
            status, error = JobStatus.COMPLETED.value, None
        except Exception as exc:  # noqa: BLE001 - job failure is recorded and shown
            log.exception("job %s failed", job_id)
            result, status, error = None, JobStatus.FAILED.value, f"{type(exc).__name__}: {exc}"[:2000]
            ctx.step("failed", error or "", status="error")
        with self.state.db.session() as s:
            job = s.get(Job, job_id)
            job.status, job.result, job.error, job.completed_at = status, result, error, _now()

    def shutdown(self) -> None:
        with self._lifecycle_lock:
            self._accepting = False
        self.pool.shutdown(wait=True, cancel_futures=True)
