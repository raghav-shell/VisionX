from __future__ import annotations

import threading
import time

from visionsentinel.api.runner import JobRunner
from visionsentinel.api.settings import Settings
from visionsentinel.api.state import AppState
from visionsentinel.contracts import JobKind, JobStatus
from visionsentinel.core.workspace import Workspace
from visionsentinel.storage import Job


def _state(tmp_path):
    workspace = Workspace(tmp_path / "jobs").ensure()
    return AppState.create(Settings(allowed_hosts=["testserver"]), workspace)


def _wait_for_terminal(state, job_id: str) -> Job:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with state.db.session() as session:
            job = session.get(Job, job_id)
            if job is not None and JobStatus(job.status).terminal:
                return job
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def test_job_is_persisted_before_worker_progress_and_result(tmp_path):
    state = _state(tmp_path)
    runner = JobRunner(state)
    entered = threading.Event()
    release = threading.Event()

    def operation(ctx):
        ctx.step("prepare")
        entered.set()
        assert release.wait(timeout=30)
        ctx.step("complete")
        return {"value": "persisted"}

    try:
        job_id = runner.submit_job(JobKind.ATTACK_LAB.value, "subject", "analyst", operation)
        assert entered.wait(timeout=30)
        with state.db.session() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert JobStatus(job.status) in {JobStatus.QUEUED, JobStatus.RUNNING}
            assert [step["name"] for step in job.steps] == ["prepare"]
        release.set()
        job = _wait_for_terminal(state, job_id)
        assert job.status == JobStatus.COMPLETED.value
        assert [step["name"] for step in job.steps] == ["prepare", "complete"]
        assert job.result == {"value": "persisted"}
        assert job.completed_at is not None
    finally:
        release.set()
        runner.shutdown()


def test_failed_job_is_safe_and_worker_remains_usable(tmp_path):
    state = _state(tmp_path)
    runner = JobRunner(state)

    def fails(ctx):
        ctx.step("started")
        raise RuntimeError("private path should not be persisted")

    try:
        failed_id = runner.submit_job(JobKind.ATTACK_LAB.value, "failure", "analyst", fails)
        failed = _wait_for_terminal(state, failed_id)
        assert failed.status == JobStatus.FAILED.value
        assert failed.error == "RuntimeError"
        assert "private path" not in (failed.error or "")
        assert failed.completed_at is not None
        with state.db.session() as session:
            assert session.get(Job, failed_id).steps[-1]["status"] == "error"

        succeeded_id = runner.submit_job(JobKind.ATTACK_LAB.value, "success", "analyst", lambda _ctx: {"ok": True})
        succeeded = _wait_for_terminal(state, succeeded_id)
        assert succeeded.status == JobStatus.COMPLETED.value
    finally:
        runner.shutdown()
