"""Startup reconciliation and local runner lifecycle invariants."""

from __future__ import annotations

import threading

from visionsentinel.api.runner import JobRunner, recover_interrupted_work
from visionsentinel.api.settings import Settings
from visionsentinel.api.state import AppState
from visionsentinel.contracts import JobStatus, ScanStatus
from visionsentinel.core.errors import RunnerUnavailableError
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
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


def _shutdown_after_cancelling_queue(runner, release: threading.Event, finished: threading.Event) -> None:
    original_shutdown = runner.pool.shutdown

    def controlled_shutdown(*, wait=True, cancel_futures=False):
        original_shutdown(wait=False, cancel_futures=cancel_futures)
        release.set()
        assert finished.wait(10)

    runner.pool.shutdown = controlled_shutdown
    runner.shutdown()


def test_shutdown_reconciles_cancelled_queued_job_and_preserves_completed_job(tmp_path):
    state = _state(tmp_path)
    runner = JobRunner(state)
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    queued_started = threading.Event()

    def blocking_job(_ctx):
        started.set()
        release.wait(10)
        finished.set()
        return {"completed": True}

    def queued_job(_ctx):
        queued_started.set()
        return {"should_not_run": True}

    completed_id = runner.submit_job("blocking", "completed", None, blocking_job)
    assert started.wait(10)
    cancelled_id = runner.submit_job("queued", "cancelled", None, queued_job)
    _shutdown_after_cancelling_queue(runner, release, finished)

    with state.db.session() as session:
        assert session.get(Job, completed_id).status == JobStatus.COMPLETED.value
        assert session.get(Job, cancelled_id).status == JobStatus.FAILED.value
        assert not queued_started.is_set()
        assert session.query(AuditEvent).filter(AuditEvent.target == cancelled_id).count() >= 1


def test_shutdown_reconciles_cancelled_queued_scan_and_preserves_completed_scan(tmp_path):
    state = _state(tmp_path)
    runner = JobRunner(state)
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    queued_started = threading.Event()

    def fake_execute(scan_id, _request):
        started.set()
        release.wait(10)
        with state.db.session() as session:
            session.get(Scan, scan_id).status = ScanStatus.SEALED.value
        finished.set()

    def unexpected_execute(_scan_id, _request):
        queued_started.set()

    runner.execute_scan = fake_execute
    completed_id = runner.submit_scan(ScanRequest(name="completed"), None)
    assert started.wait(10)
    runner.execute_scan = unexpected_execute
    cancelled_id = runner.submit_scan(ScanRequest(name="cancelled"), None)
    _shutdown_after_cancelling_queue(runner, release, finished)

    with state.db.session() as session:
        assert session.get(Scan, completed_id).status == ScanStatus.SEALED.value
        assert session.get(Scan, cancelled_id).status == ScanStatus.FAILED.value
        assert not queued_started.is_set()
        assert session.query(AuditEvent).filter(AuditEvent.target == cancelled_id).count() >= 1


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


def test_app_construction_does_not_recover_persisted_work_until_lifespan(tmp_path):
    from visionsentinel.api.app import create_app

    workspace = Workspace(tmp_path / "startup-boundary").ensure()
    seed = AppState.create(Settings(allowed_hosts=["testserver"]), workspace)
    with seed.db.session() as session:
        session.add(Scan(id="SCN-STARTUP", name="interrupted", status=ScanStatus.RUNNING.value,
                         profile="baseline", request={}))
        session.add(Job(id="JOB-STARTUP", kind="test", subject="subject", status=JobStatus.RUNNING.value,
                        steps=[]))
    seed.db.dispose()

    app = create_app(Settings(allowed_hosts=["testserver"]), workspace)
    with app.state.vs.db.session() as session:
        assert session.get(Scan, "SCN-STARTUP").status == ScanStatus.RUNNING.value
        assert session.get(Job, "JOB-STARTUP").status == JobStatus.RUNNING.value

    app.state.vs.db.dispose()


def test_app_lifespan_recovers_active_work_before_serving_and_is_idempotent(tmp_path):
    from fastapi.testclient import TestClient

    from visionsentinel.api.app import create_app

    workspace = Workspace(tmp_path / "startup-recovery").ensure()
    seed = AppState.create(Settings(allowed_hosts=["testserver"]), workspace)
    with seed.db.session() as session:
        session.add(Scan(id="SCN-LIFESPAN", name="interrupted", status=ScanStatus.RUNNING.value,
                         profile="baseline", request={}))
        session.add(Scan(id="SCN-TERMINAL", name="sealed", status=ScanStatus.SEALED.value,
                         profile="baseline", request={}))
        session.add(Job(id="JOB-LIFESPAN", kind="test", subject="subject", status=JobStatus.RUNNING.value,
                        steps=[]))
        session.add(Job(id="JOB-TERMINAL", kind="test", subject="subject", status=JobStatus.COMPLETED.value,
                        steps=[]))
    seed.db.dispose()

    app = create_app(Settings(allowed_hosts=["testserver"]), workspace)
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/api/system/info").status_code == 200
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/api/system/info").status_code == 200

    with app.state.vs.db.session() as session:
        assert session.get(Scan, "SCN-LIFESPAN").status == ScanStatus.FAILED.value
        assert session.get(Job, "JOB-LIFESPAN").status == JobStatus.FAILED.value
        assert session.get(Scan, "SCN-TERMINAL").status == ScanStatus.SEALED.value
        assert session.get(Job, "JOB-TERMINAL").status == JobStatus.COMPLETED.value
        assert session.query(ScanEvent).filter(ScanEvent.scan_id == "SCN-LIFESPAN").count() == 1
