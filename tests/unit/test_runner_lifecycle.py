"""Startup reconciliation and local runner lifecycle invariants."""

from __future__ import annotations

from visionsentinel.api.runner import JobRunner, recover_interrupted_work
from visionsentinel.api.settings import Settings
from visionsentinel.api.state import AppState
from visionsentinel.contracts import JobStatus, ScanStatus
from visionsentinel.core.errors import RunnerUnavailableError
from visionsentinel.core.workspace import Workspace
from visionsentinel.storage import AuditEvent, Job, Scan, ScanEvent


def _state(tmp_path):
    workspace = Workspace(tmp_path / "lifecycle").ensure()
    return AppState.create(Settings(allowed_hosts=["testserver"]), workspace)


def test_recovery_reconciles_active_work_and_is_idempotent(tmp_path):
    state = _state(tmp_path)
    with state.db.session() as session:
        session.add(Scan(id="SCN-RECOVER", name="interrupted", status=ScanStatus.RUNNING.value,
                         profile="baseline", request={}))
        session.add(Scan(id="SCN-DONE", name="sealed", status=ScanStatus.SEALED.value,
                         profile="baseline", request={}))
        session.add(Job(id="JOB-RECOVER", kind="test", subject="subject", status=JobStatus.RUNNING.value,
                        steps=[]))
        session.add(Job(id="JOB-DONE", kind="test", subject="subject", status=JobStatus.COMPLETED.value,
                        steps=[]))

    assert recover_interrupted_work(state) == {"scans": 1, "jobs": 1}
    with state.db.session() as session:
        scan = session.get(Scan, "SCN-RECOVER")
        job = session.get(Job, "JOB-RECOVER")
        assert scan.status == ScanStatus.FAILED.value
        assert scan.completed_at is not None
        assert session.query(ScanEvent).filter(ScanEvent.scan_id == scan.id).count() == 1
        assert job.status == JobStatus.FAILED.value
        assert job.completed_at is not None
        assert len(job.steps) == 1
        audit_actions = {event.action for event in session.query(AuditEvent).all()}
        assert {"recover_scan", "recover_job"} <= audit_actions
    assert recover_interrupted_work(state) == {"scans": 0, "jobs": 0}
    with state.db.session() as session:
        assert session.query(ScanEvent).filter(ScanEvent.scan_id == "SCN-RECOVER").count() == 1
        assert session.get(Scan, "SCN-DONE").status == ScanStatus.SEALED.value
        assert session.get(Job, "JOB-DONE").status == JobStatus.COMPLETED.value


def test_runner_rejects_new_work_after_shutdown(tmp_path):
    state = _state(tmp_path)
    runner = JobRunner(state)
    runner.shutdown()
    try:
        runner.submit_job("test", "subject", None, lambda _ctx: {})
    except RunnerUnavailableError:
        pass
    else:
        raise AssertionError("runner accepted work after shutdown")


def test_app_lifespan_owns_runner_shutdown_and_database_disposal(tmp_path):
    from fastapi.testclient import TestClient

    from visionsentinel.api.app import create_app

    workspace = Workspace(tmp_path / "app").ensure()
    app = create_app(Settings(allowed_hosts=["testserver"]), workspace)
    runner_calls: list[str] = []
    db_calls: list[str] = []
    app.state.vs.runner.shutdown = lambda: runner_calls.append("shutdown")
    app.state.vs.db.dispose = lambda: db_calls.append("dispose")
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/api/system/info").status_code == 200
    assert runner_calls == ["shutdown"]
    assert db_calls == ["dispose"]
