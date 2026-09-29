"""Lifecycle controls remain server-enforced, not merely dashboard affordances."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from visionsentinel.api.app import create_app
from visionsentinel.api.settings import Settings
from visionsentinel.contracts import Role
from visionsentinel.core.workspace import Workspace
from visionsentinel.governance.identity import create_user


@pytest.fixture
def api_client(tmp_path):
    ws = Workspace(tmp_path / "api_ws").ensure()
    app = create_app(settings=Settings(allowed_hosts=["testserver"], extra_origins=["http://testserver"],
                                       secure_cookies=False), workspace=ws)
    create_user(app.state.vs.db, "analyst", "analystpassword", Role.ANALYST, "Lead Analyst")
    return TestClient(app, base_url="http://testserver")


def _login(client, username="analyst", password="analystpassword"):
    response = client.post("/api/auth/login", json={"username": username, "password": password},
                           headers={"Origin": "http://testserver"})
    assert response.status_code == 200
    return {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf"]}


def test_asset_kind_status_and_lifecycle(api_client, tmp_path):
    headers = _login(api_client)
    kinds = api_client.get("/api/assets/kinds")
    assert kinds.status_code == 200
    assert any(x["id"] == "ledger" for x in kinds.json()["kinds"])

    upload = api_client.post("/api/assets/upload", headers=headers,
                             files={"file": ("events.jsonl", b'{"record": 1}\n', "application/x-ndjson")},
                             data={"kind": "ledger", "name": "test ledger"})
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["id"]
    assert api_client.get("/api/assets/status").json()["active_assets"] == 1

    archived = api_client.post(f"/api/assets/{asset_id}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["lifecycle"] == "ARCHIVED"
    assert api_client.get("/api/assets").json()["total"] == 0
    assert api_client.get("/api/assets", params={"lifecycle": "ARCHIVED"}).json()["total"] == 1
    assert api_client.get(f"/api/assets/{asset_id}/history").json()["events"][0]["action"] == "archive_asset"

    restored = api_client.post(f"/api/assets/{asset_id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["lifecycle"] == "ACTIVE"
