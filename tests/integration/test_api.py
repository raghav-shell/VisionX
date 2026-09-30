"""Integration tests for FastAPI endpoints: auth, system, scans, assets, governance, attacklab, evidence."""

from __future__ import annotations

import hashlib
import asyncio
import json
import time

import pytest
from starlette.testclient import TestClient

from visionsentinel.api.app import create_app
from visionsentinel.api.routers import scans as scans_router
from visionsentinel.api.settings import Settings
from visionsentinel.core.workspace import Workspace
from visionsentinel.storage import Scan, ScanEvent
from visionsentinel.contracts import Disposition, JobStatus, ScanStatus
from visionsentinel.engine.registry import default_registry


@pytest.fixture
def api_client(tmp_path):
    from visionsentinel.contracts import Role
    from visionsentinel.governance.identity import create_user

    ws = Workspace(tmp_path / "api_ws").ensure()
    settings = Settings(
        allowed_hosts=["testserver", "localhost", "127.0.0.1"],
        extra_origins=["http://testserver"],
        secure_cookies=False,
        session_ttl_minutes=60,
        demo_mode=True,
    )
    app = create_app(settings=settings, workspace=ws)
    # Seed default users
    create_user(app.state.vs.db, "analyst", "analystpassword", Role.ANALYST, "Lead Analyst")
    create_user(app.state.vs.db, "approver", "approverpassword", Role.APPROVER, "Assurance Officer")
    return TestClient(app, base_url="http://testserver")


def test_api_unauthenticated_info(api_client):
    res = api_client.get("/api/system/info")
    assert res.status_code == 200
    data = res.json()
    assert data["product"] == "VisionX"
    assert "version" in data


def test_workspace_metadata_uses_live_contracts(api_client):
    response = api_client.get("/api/system/metadata", headers={"X-VisionX-Demo": "1"})
    assert response.status_code == 200
    metadata = response.json()
    from visionsentinel.contracts import SCAN_ASSET_INPUTS, AssetKind, Disposition, JobStatus, Role, ScanStatus
    from visionsentinel.governance import REASON_CODES

    assert {item["value"] for item in metadata["asset_kinds"]} == {item.value for item in AssetKind}
    assert [(item["field"], tuple(item["compatible_kinds"])) for item in metadata["asset_inputs"]] == [
        (item.field, tuple(sorted(kind.value for kind in item.kinds))) for item in SCAN_ASSET_INPUTS
    ]
    assert metadata["statuses"]["scan"] == [item.value for item in ScanStatus]
    assert metadata["statuses"]["job"] == [item.value for item in JobStatus]
    assert metadata["statuses"]["disposition"] == [item.value for item in Disposition]
    assert metadata["governance"]["reason_codes"] == list(REASON_CODES)
    assert metadata["roles"] == [{"value": item.value, "rank": item.rank} for item in Role]


def test_demo_header_allows_read_only_workspace_access(api_client):
    demo_headers = {"X-VisionX-Demo": "1"}

    assert api_client.get("/api/auth/me", headers=demo_headers).json()["user"] == {
        "username": "visionx-demo",
        "display_name": "VisionX demo viewer",
        "role": "VIEWER",
    }
    assert api_client.get("/api/scans", headers=demo_headers).status_code == 200
    assert api_client.get("/api/assets", headers=demo_headers).status_code == 200
    assert api_client.get("/api/system/profiles", headers=demo_headers).status_code == 200

    # The demo header never grants mutation access or a CSRF token.
    assert api_client.post("/api/scans", headers=demo_headers, json={}).status_code == 401
    assert api_client.get("/api/scans").status_code == 401


def test_jobs_api_lists_filters_and_returns_detail(api_client):
    login = api_client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "analystpassword"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200
    runner = api_client.app.state.vs.runner
    job_id = runner.submit_job("api-test", "job-api", "analyst", lambda ctx: {"ok": True})

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        detail = api_client.get(f"/api/jobs/{job_id}")
        assert detail.status_code == 200
        if JobStatus(detail.json()["status"]).terminal:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("job did not complete")

    response = api_client.get("/api/jobs", params={"started_by": "analyst", "limit": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["id"] == job_id
    assert api_client.get(f"/api/jobs/{job_id}").json()["result"] == {"ok": True}
    assert api_client.get("/api/jobs/unknown-job").status_code == 404


def test_scan_event_stream_uses_persisted_contract_and_terminal_status(api_client):
    detector_id = default_registry().ids()[0]
    with api_client.app.state.vs.db.session() as session:
        session.add(Scan(id="SCN-SSE-SEALED", name="sealed", status=ScanStatus.SEALED.value, profile="baseline", request={}))
        session.add(ScanEvent(scan_id="SCN-SSE-SEALED", seq=1, t_ms=12, level="stage", message="planned", detector_id=None))
        session.add(ScanEvent(scan_id="SCN-SSE-SEALED", seq=2, t_ms=34, level="info", message="detector complete", detector_id=detector_id))
        session.add(Scan(id="SCN-SSE-FAILED", name="failed", status=ScanStatus.FAILED.value, profile="baseline", request={}))
        session.add(ScanEvent(scan_id="SCN-SSE-FAILED", seq=1, t_ms=1, level="error", message="scan failed: RuntimeError", detector_id=None))

    headers = {"X-VisionX-Demo": "1"}
    with api_client.stream("GET", "/api/scans/SCN-SSE-SEALED/events", headers=headers) as response:
        assert response.status_code == 200
        body = response.read().decode()
    assert detector_id in body
    assert f'"detector_id":"{detector_id}"' in body
    assert '"stage":' not in body
    assert '"detector":' not in body
    assert '"status":"SEALED"' in body

    with api_client.stream("GET", "/api/scans/SCN-SSE-FAILED/events", headers=headers) as response:
        assert '"status":"FAILED"' in response.read().decode()
    assert api_client.get("/api/scans/SCN-SSE-MISSING/events", headers=headers).status_code == 404


def test_scan_event_stream_reconnect_and_malformed_last_event_id(api_client):
    with api_client.app.state.vs.db.session() as session:
        session.add(Scan(id="SCN-SSE-RECONNECT", name="reconnect", status=ScanStatus.SEALED.value,
                         profile="baseline", request={}))
        session.add_all([
            ScanEvent(scan_id="SCN-SSE-RECONNECT", seq=1, t_ms=1, level="stage", message="one"),
            ScanEvent(scan_id="SCN-SSE-RECONNECT", seq=2, t_ms=2, level="info", message="two"),
        ])

    headers = {"X-VisionX-Demo": "1", "Last-Event-ID": "not-an-id"}
    with api_client.stream("GET", "/api/scans/SCN-SSE-RECONNECT/events", headers=headers) as response:
        malformed_body = response.read().decode()
    assert malformed_body.index('"seq":1') < malformed_body.index('"seq":2')
    assert malformed_body.count("event: scan_complete") == 1

    headers["Last-Event-ID"] = "3"
    with api_client.stream("GET", "/api/scans/SCN-SSE-RECONNECT/events", headers=headers) as response:
        reconnected_body = response.read().decode()
    assert reconnected_body == ""


def test_scan_event_stream_ends_safely_when_scan_disappears(api_client):
    scan_id = "SCN-SSE-DISAPPEARS"
    with api_client.app.state.vs.db.session() as session:
        session.add(Scan(id=scan_id, name="disappears", status=ScanStatus.RUNNING.value,
                         profile="baseline", request={}))
        session.add(ScanEvent(scan_id=scan_id, seq=1, t_ms=1, level="stage", message="planned"))

    class RequestStub:
        headers = {"last-event-id": "0"}
        calls = 0

        async def is_disconnected(self):
            self.calls += 1
            if self.calls == 2:
                with api_client.app.state.vs.db.session() as session:
                    session.delete(session.get(Scan, scan_id))
            return False

    async def collect():
        response = await scans_router.scan_events_stream(scan_id, RequestStub(), api_client.app.state.vs)
        return [chunk async for chunk in response.body_iterator]

    body = "".join(asyncio.run(collect()))
    assert body.index('"seq":1') < body.index("event: scan_unavailable")
    assert body.count("event: scan_unavailable") == 1
    assert "database" not in body.lower()
    assert "sql" not in body.lower()


def test_scan_event_stream_stops_immediately_on_disconnect(api_client):
    with api_client.app.state.vs.db.session() as session:
        session.add(Scan(id="SCN-SSE-DISCONNECT", name="disconnect", status=ScanStatus.RUNNING.value,
                         profile="baseline", request={}))

    class DisconnectingRequest:
        headers = {"last-event-id": "0"}
        calls = 0

        async def is_disconnected(self):
            self.calls += 1
            return True

    request = DisconnectingRequest()

    async def collect():
        response = await scans_router.scan_events_stream("SCN-SSE-DISCONNECT", request, api_client.app.state.vs)
        return [chunk async for chunk in response.body_iterator]

    assert asyncio.run(collect()) == []
    assert request.calls == 1


def test_scan_event_stream_polls_at_centralized_interval(api_client, monkeypatch):
    with api_client.app.state.vs.db.session() as session:
        session.add(Scan(id="SCN-SSE-POLL", name="poll", status=ScanStatus.RUNNING.value,
                         profile="baseline", request={}))

    intervals = []

    async def sleep(interval):
        intervals.append(interval)

    monkeypatch.setattr(scans_router.asyncio, "sleep", sleep)

    class DisconnectAfterPoll:
        headers = {"last-event-id": "0"}
        calls = 0

        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 2

    request = DisconnectAfterPoll()

    async def collect():
        response = await scans_router.scan_events_stream("SCN-SSE-POLL", request, api_client.app.state.vs)
        return [chunk async for chunk in response.body_iterator]

    assert asyncio.run(collect()) == []
    assert intervals == [scans_router.SCAN_EVENTS_POLL_INTERVAL_SECONDS]


def test_api_auth_flow_and_rbac(api_client):
    # 1. Login with analyst credentials
    login_res = api_client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "analystpassword"},
        headers={"Origin": "http://testserver"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "csrf" in login_data
    csrf = login_data["csrf"]
    assert "vs_session" in api_client.cookies

    # 2. Check /api/auth/me
    me_res = api_client.get("/api/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["username"] == "analyst"
    assert me_data["user"]["role"] == "ANALYST"

    # 3. Access system status with authenticated session
    status_res = api_client.get("/api/system/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["engine"]["detectors"] >= 8
    assert "trust_root" in status_data

    # 4. Access catalog & profiles
    cat_res = api_client.get("/api/system/catalog")
    assert cat_res.status_code == 200
    assert len(cat_res.json()["attack_classes"]) >= 10

    prof_res = api_client.get("/api/system/profiles")
    assert prof_res.status_code == 200
    assert len(prof_res.json()["profiles"]) >= 4

    # 5. Access scenarios
    scen_res = api_client.get("/api/attacklab/scenarios")
    assert scen_res.status_code == 200
    assert scen_res.json()["total"] >= 5

    # 6. Logout
    logout_res = api_client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
    )
    assert logout_res.status_code == 200

    # 7. Verify session dropped
    after_me = api_client.get("/api/auth/me")
    assert after_me.status_code == 401


def test_admin_user_lifecycle_never_exposes_password_hashes(api_client):
    from visionsentinel.contracts import Role
    from visionsentinel.governance.identity import create_user

    create_user(api_client.app.state.vs.db, "admin", "adminpassword", Role.ADMIN, "Platform Admin")
    login = api_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "adminpassword"},
        headers={"Origin": "http://testserver"},
    )
    headers = {"Origin": "http://testserver", "X-CSRF-Token": login.json()["csrf"]}

    created = api_client.post("/api/admin/users", headers=headers, json={
        "username": "operator", "password": "operatorpassword", "role": "VIEWER", "display_name": "Read Operator",
    })
    assert created.status_code == 201
    assert created.json()["user"] == {
        "username": "operator", "display_name": "Read Operator", "role": "VIEWER", "disabled": False,
        "created_at": created.json()["user"]["created_at"],
    }
    assert "password" not in json.dumps(created.json()).lower()

    assert api_client.get("/api/admin/users", headers=headers).status_code == 200
    changed = api_client.patch("/api/admin/users/operator/role", headers=headers, json={"role": "ANALYST"})
    assert changed.json()["user"]["role"] == "ANALYST"
    assert api_client.post("/api/admin/users/operator/disable", headers=headers).json()["user"]["disabled"] is True

    denied = api_client.post(
        "/api/auth/login", json={"username": "operator", "password": "operatorpassword"},
        headers={"Origin": "http://testserver"},
    )
    assert denied.status_code == 401
    assert api_client.post("/api/admin/users/operator/enable", headers=headers).json()["user"]["disabled"] is False
    reset = api_client.post("/api/admin/users/operator/reset-password", headers=headers, json={"password": "newoperatorpassword"})
    assert reset.status_code == 200
    assert api_client.post(
        "/api/auth/login", json={"username": "operator", "password": "newoperatorpassword"},
        headers={"Origin": "http://testserver"},
    ).status_code == 200

    analyst_login = api_client.post(
        "/api/auth/login", json={"username": "analyst", "password": "analystpassword"},
        headers={"Origin": "http://testserver"},
    )
    analyst_headers = {"Origin": "http://testserver", "X-CSRF-Token": analyst_login.json()["csrf"]}
    assert api_client.get("/api/admin/users", headers=analyst_headers).status_code == 403


def test_csrf_rejection_on_mutation(api_client):
    # Login
    login_res = api_client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "analystpassword"},
        headers={"Origin": "http://testserver"},
    )
    assert login_res.status_code == 200

    # Attempt mutation with invalid CSRF token
    bad_res = api_client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": "invalid_csrf_token", "Origin": "http://testserver"},
    )
    assert bad_res.status_code == 403
    assert "CSRF" in bad_res.json()["detail"]


def test_governance_mutations_require_authentication_and_role(api_client):
    assert api_client.post("/api/findings/missing/acknowledge").status_code == 401

    from visionsentinel.contracts import Role
    from visionsentinel.governance.identity import create_user

    create_user(api_client.app.state.vs.db, "viewer", "viewerpassword", Role.VIEWER, "Read Only")
    login = api_client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "viewerpassword"},
        headers={"Origin": "http://testserver"},
    )
    csrf = login.json()["csrf"]
    response = api_client.post(
        "/api/findings/missing/acknowledge",
        headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
    )
    assert response.status_code == 403


def test_web_routes_reject_raw_server_paths(api_client):
    """Browser clients may select registered assets, never arbitrary host paths."""
    login = api_client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "analystpassword"},
        headers={"Origin": "http://testserver"},
    )
    csrf = login.json()["csrf"]
    headers = {"X-CSRF-Token": csrf, "Origin": "http://testserver"}

    scan = api_client.post(
        "/api/scans",
        json={"name": "raw-path-attempt", "dataset": "/etc/passwd"},
        headers=headers,
    )
    assert scan.status_code == 422
    assert "imported asset identifier" in scan.json()["detail"]

    drift = api_client.post(
        "/api/drift/analyze",
        json={"incoming_data": "/etc/passwd"},
        headers=headers,
    )
    assert drift.status_code == 422
    assert "imported asset identifier" in drift.json()["detail"]

    provenance = api_client.post(
        "/api/provenance/verify",
        json={"ledger_path": "/etc/passwd"},
        headers=headers,
    )
    assert provenance.status_code == 422


def test_origin_check_rejection(api_client):
    # Login
    login_res = api_client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "analystpassword"},
        headers={"Origin": "http://evil-attacker.com"},
    )
    assert login_res.status_code == 403


def test_attacklab_run_and_governance_workflow(api_client):
    # 1. Login as Analyst
    login_res = api_client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "analystpassword"},
        headers={"Origin": "http://testserver"},
    )
    assert login_res.status_code == 200
    analyst_csrf = login_res.json()["csrf"]

    # 2. Run an AttackLab scenario
    run_res = api_client.post(
        "/api/attacklab/scenarios/label_flip_targeted/run",
        json={"profile": "selftest"},
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert run_res.status_code == 202
    queued = run_res.json()
    assert queued["status"] == JobStatus.QUEUED.value
    job_id = queued["job_id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        job_res = api_client.get(f"/api/jobs/{job_id}")
        assert job_res.status_code == 200
        job = job_res.json()
        if JobStatus(job["status"]).terminal:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Attack Lab job did not reach a terminal state")
    assert job["status"] == JobStatus.COMPLETED.value
    run_data = job["result"]
    assert run_data["scenario_id"] == "label_flip_targeted"
    assert run_data["detected_expected_signals"] is True
    scan_id = run_data["scan_id"]

    # 3. Check Scan details and findings
    scan_res = api_client.get(f"/api/scans/{scan_id}")
    assert scan_res.status_code == 200
    assert scan_res.json()["status"] in ("SEALED", "COMPLETED_WITH_FINDINGS")

    findings_res = api_client.get(f"/api/scans/{scan_id}/findings")
    assert findings_res.status_code == 200
    findings = findings_res.json()["findings"]
    assert len(findings) > 0

    # The download must be the exact report.json whose digest is listed in the signed manifest.
    report = api_client.get(f"/api/scans/{scan_id}/report.json")
    manifest = api_client.get(f"/api/scans/{scan_id}/bundle/manifest.json")
    assert report.status_code == 200 and manifest.status_code == 200
    report_entry = next(item for item in manifest.json()["files"] if item["file"] == "report.json")
    assert report_entry["sha256"] == "sha256:" + hashlib.sha256(report.content).hexdigest()
    assert api_client.post(f"/api/scans/{scan_id}/report/verify", json={}).json()["verified"] is True
    target_finding = findings[0]
    finding_id = target_finding["id"]
    immutable_before = target_finding.copy()

    acknowledge = api_client.post(
        f"/api/findings/{finding_id}/acknowledge",
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert acknowledge.status_code == 200
    assert acknowledge.json()["governance"]["state"]["acknowledged_by"] == "analyst"
    repeated_acknowledge = api_client.post(
        f"/api/findings/{finding_id}/acknowledge",
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert repeated_acknowledge.status_code == 200

    assigned = api_client.post(
        f"/api/findings/{finding_id}/owner",
        json={"owner": "approver"},
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["governance"]["state"]["owner"] == "approver"
    reassigned = api_client.post(
        f"/api/findings/{finding_id}/owner",
        json={"owner": "analyst"},
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["governance"]["state"]["owner"] == "analyst"
    missing_owner = api_client.post(
        f"/api/findings/{finding_id}/owner",
        json={"owner": "missing-user"},
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert missing_owner.status_code == 400

    comment = api_client.post(
        f"/api/findings/{finding_id}/comment",
        json={"text": "Reviewed with the analyst and recorded the evidence."},
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert comment.status_code == 200
    invalid_comment = api_client.post(
        f"/api/findings/{finding_id}/comment",
        json={"text": ""},
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert invalid_comment.status_code == 400

    history = api_client.get(f"/api/findings/{finding_id}/history")
    assert history.status_code == 200
    history_actions = {event["action"] for event in history.json()["events"]}
    assert {"acknowledge", "assign_owner", "comment"}.issubset(history_actions)
    other_finding_id = next(item["id"] for item in findings if item["id"] != finding_id)
    other_history = api_client.get(f"/api/findings/{other_finding_id}/history")
    assert other_history.status_code == 200
    assert all(event["action"] not in history_actions for event in other_history.json()["events"])

    immutable_after = api_client.get(f"/api/scans/{scan_id}/findings").json()["findings"]
    assert next(item for item in immutable_after if item["id"] == finding_id) == immutable_before

    # Findings persistence uses FindingState for governance and the sealed result for detector data.
    finding_list = api_client.get(f"/api/findings?scan_id={scan_id}&limit=1")
    assert finding_list.status_code == 200
    assert finding_list.json()["total"] == len(findings)
    assert len(finding_list.json()["findings"]) == 1
    assert finding_list.json()["findings"][0]["finding_id"] in {item["id"] for item in findings}
    severity = target_finding["severity"]
    filtered = api_client.get(f"/api/findings?scan_id={scan_id}&severity={severity}&offset=0&limit=1")
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1
    assert all(item["severity"] == severity for item in filtered.json()["findings"])
    assert api_client.get("/api/findings?scan_id=missing-scan").json() == {"total": 0, "findings": []}

    detail_before = api_client.get(f"/api/findings/{finding_id}")
    assert detail_before.status_code == 200
    detail_before = detail_before.json()
    original_recommendation = detail_before["immutable"]["recommended_disposition"]
    assert detail_before["governance"]["state"]["disposition"] == original_recommendation
    assert detail_before["governance"]["decisions"]["latest"] is None

    contributor_res = api_client.get(f"/api/scans/{scan_id}/contributors")
    assert contributor_res.status_code == 200
    assert contributor_res.json()["scan_id"] == scan_id
    assert contributor_res.json()["total"] == len(contributor_res.json()["contributors"])

    drift_res = api_client.get(f"/api/scans/{scan_id}/drift")
    assert drift_res.status_code == 200
    assert {item["detector_id"] for item in drift_res.json()["detectors"]}
    provenance_res = api_client.get(f"/api/scans/{scan_id}/provenance")
    assert provenance_res.status_code == 200
    assert {item["detector_id"] for item in provenance_res.json()["detectors"]}
    # 4. Request disposition downgrade (e.g. REVIEW -> ACCEPT)
    dec_req_res = api_client.post(
        f"/api/findings/{finding_id}/decision",
        json={
            "target_disposition": Disposition.ACCEPT.value,
            "reason_code": "ACCEPTED_RISK",
            "justification": "Verified by field team to be an acceptable operational variation.",
        },
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert dec_req_res.status_code == 201
    dec_data = dec_req_res.json()
    decision_id = dec_data["id"]
    assert dec_data["sensitive"] is True
    assert dec_data["status"] == "PENDING"
    decision_detail = api_client.get(f"/api/governance/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["id"] == decision_id
    assert decision_detail.json()["current_disposition"] == dec_data["current_disposition"]
    decision_list = api_client.get(f"/api/governance/decisions?status={dec_data['status']}&limit=1")
    assert decision_list.status_code == 200
    assert decision_list.json()["total"] >= 1
    assert all(item["status"] == dec_data["status"] for item in decision_list.json()["decisions"])

    # 5. Analyst cannot self-approve sensitive downgrade (two-person rule enforcement)
    self_approve_res = api_client.post(
        f"/api/governance/decisions/{decision_id}/approve",
        json={"justification": "Attempting self-approval"},
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    # Analyst lacks APPROVER role or self-approval is rejected
    assert self_approve_res.status_code in (400, 403)

    # 6. Login as second user (Approver)
    login_appr = api_client.post(
        "/api/auth/login",
        json={"username": "approver", "password": "approverpassword"},
        headers={"Origin": "http://testserver"},
    )
    assert login_appr.status_code == 200
    approver_csrf = login_appr.json()["csrf"]

    # 7. Approver successfully approves the decision
    approve_res = api_client.post(
        f"/api/governance/decisions/{decision_id}/approve",
        json={"justification": "Independent senior officer approval after inspecting field evidence."},
        headers={"X-CSRF-Token": approver_csrf, "Origin": "http://testserver"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"
    assert approve_res.json()["decided_by"] == "approver"
    effective_disposition = approve_res.json()["current_disposition"]

    detail_after = api_client.get(f"/api/findings/{finding_id}")
    assert detail_after.status_code == 200
    detail_after = detail_after.json()
    assert detail_after["immutable"]["recommended_disposition"] == original_recommendation
    assert detail_after["governance"]["state"]["disposition"] == effective_disposition
    assert detail_after["governance"]["decisions"]["latest"]["status"] == approve_res.json()["status"]

    # 8. Check Audit Trail with cryptographic verification
    audit_res = api_client.get("/api/governance/audit?verify=true")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["total"] >= 3
    if audit_data["verification"]:
        assert audit_data["verification"]["intact"] is True
