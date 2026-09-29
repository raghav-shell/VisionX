"""Runtime checks for the security policy mounted by the application factory."""

from __future__ import annotations

import asyncio

from starlette.testclient import TestClient

from visionsentinel.api.app import create_app
from visionsentinel.api.settings import Settings
from visionsentinel.core.workspace import Workspace
from visionsentinel.governance.identity import create_user
from visionsentinel.contracts import Role
from visionsentinel.api.security import BodyLimit


def _client(tmp_path, **settings_overrides) -> TestClient:
    workspace = Workspace(tmp_path / "security").ensure()
    settings = Settings(
        allowed_hosts=["testserver"],
        extra_origins=["http://testserver"],
        secure_cookies=False,
        **settings_overrides,
    )
    app = create_app(settings=settings, workspace=workspace)
    create_user(app.state.vs.db, "analyst", "analystpassword", Role.ANALYST, "Lead Analyst")
    return TestClient(app, base_url="http://testserver")


def _login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "analyst", "password": "analystpassword"},
                           headers={"Origin": "http://testserver"})
    assert response.status_code == 200
    return {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf"]}


def test_configured_host_and_security_headers_are_enforced(tmp_path):
    client = _client(tmp_path)
    allowed = client.get("/api/system/info")
    assert allowed.status_code == 200
    assert allowed.headers["x-content-type-options"] == "nosniff"
    assert allowed.headers["x-frame-options"] == "DENY"
    assert allowed.headers["cache-control"] == "no-store"
    assert "content-security-policy" in allowed.headers

    rejected = client.get("/api/system/info", headers={"Host": "not-allowed.invalid"})
    assert rejected.status_code == 400
    assert rejected.headers["x-content-type-options"] == "nosniff"


def test_general_and_upload_limits_are_distinct_and_configured(tmp_path):
    client = _client(tmp_path, max_json_bytes=256, max_upload_bytes=4096)
    headers = _login(client)

    ordinary = client.post("/api/auth/logout", content=b"x" * 1024, headers=headers)
    assert ordinary.status_code == 413

    upload = client.post("/api/assets/upload", headers=headers,
                         files={"file": ("events.jsonl", b'{"record": 1}\n', "application/x-ndjson")},
                         data={"kind": "ledger", "name": "test ledger"})
    assert upload.status_code == 201

    oversized = client.post("/api/assets/upload", headers=headers,
                            files={"file": ("events.jsonl", b"x" * 5000, "application/octet-stream")},
                            data={"kind": "ledger"})
    assert oversized.status_code == 413


def test_streamed_body_is_limited_without_content_length(tmp_path):
    messages = []

    async def app(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return {"type": "http.request", "body": b"x" * 1024, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "path": "/api/auth/login", "headers": []}
    asyncio.run(BodyLimit(app, default_limit=256, upload_limit=4096)(scope, receive, send))
    assert messages[0]["status"] == 413


def test_cookie_policy_comes_from_settings(tmp_path):
    client = _client(tmp_path, session_cookie_path="/api", session_cookie_samesite="lax",
                     session_cookie_httponly=True)
    response = client.post("/api/auth/login", json={"username": "analyst", "password": "analystpassword"},
                           headers={"Origin": "http://testserver"})
    cookie = response.headers["set-cookie"].lower()
    assert "path=/api" in cookie
    assert "samesite=lax" in cookie
    assert "httponly" in cookie
    assert "secure" not in cookie
