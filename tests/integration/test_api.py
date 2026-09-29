"""Integration tests for FastAPI endpoints: auth, system, scans, assets, governance, attacklab, evidence."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from visionsentinel.api.app import create_app
from visionsentinel.api.settings import Settings
from visionsentinel.core.workspace import Workspace
from visionsentinel.storage import Database, Scan, ScanEvent, User
from visionsentinel.contracts import ScanStatus
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
    assert run_res.status_code == 200
    run_data = run_res.json()
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
    target_finding = findings[0]
    finding_id = target_finding["id"]

    # 4. Request disposition downgrade (e.g. REVIEW -> ACCEPT)
    dec_req_res = api_client.post(
        f"/api/findings/{finding_id}/decision",
        json={
            "target_disposition": "ACCEPT",
            "reason_code": "ACCEPTED_RISK",
            "justification": "Verified by field team to be an acceptable operational variation.",
        },
        headers={"X-CSRF-Token": analyst_csrf, "Origin": "http://testserver"},
    )
    assert dec_req_res.status_code == 201
    dec_data = dec_req_res.json()
    decision_id = dec_data["decision_id"]
    assert dec_data["requires_second_user"] is True
    assert dec_data["status"] == "PENDING"

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
    assert approve_res.json()["approved_by"] == "approver"
    assert approve_res.json()["effective_disposition"] == "ACCEPT"

    # 8. Check Audit Trail with cryptographic verification
    audit_res = api_client.get("/api/governance/audit?verify=true")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["total"] >= 3
    if audit_data["verification"]:
        assert audit_data["verification"]["intact"] is True
