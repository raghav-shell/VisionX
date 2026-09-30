from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from visionsentinel.api.app import create_app
from visionsentinel.api.assets import register
from visionsentinel.api.settings import Settings
from visionsentinel.contracts import AssetKind
from visionsentinel.core.workspace import Workspace


def _app(tmp_path: Path, *, direct_demo: bool, client: tuple[str, int] = ("127.0.0.1", 50000)) -> TestClient:
    workspace = Workspace(tmp_path / "workspace").ensure()
    settings = Settings(
        allowed_hosts=["127.0.0.1", "localhost"],
        extra_origins=["http://127.0.0.1:3000"],
        secure_cookies=False,
        direct_demo=direct_demo,
    )
    app = create_app(settings=settings, workspace=workspace)
    dataset = workspace.assets / "dataset"
    dataset.mkdir(parents=True)
    register(app.state.vs.db, AssetKind.DATASET.value, "demo dataset", dataset, asset_id="DATASET-DEMO")
    return TestClient(app, base_url="http://127.0.0.1:8000", client=client)


def test_normal_mode_rejects_anonymous_scan_mutation(tmp_path: Path) -> None:
    with _app(tmp_path, direct_demo=False) as client:
        response = client.post("/api/scans", headers={"Origin": "http://127.0.0.1:3000"},
                               json={"name": "normal", "profile": "baseline", "dataset": "DATASET-DEMO"})
    assert response.status_code == 401


def test_direct_demo_allows_loopback_assessment_and_reports_principal(tmp_path: Path) -> None:
    with _app(tmp_path, direct_demo=True) as client:
        session = client.get("/api/auth/me")
        queued = client.post("/api/scans", headers={"Origin": "http://127.0.0.1:3000"},
                             json={"name": "direct demo", "profile": "baseline", "dataset": "DATASET-DEMO"})
    assert session.status_code == 200
    assert session.json()["user"]["username"] == "visionx-demo-analyst"
    assert session.json()["user"]["role"] == "ANALYST"
    assert session.json()["direct_demo"] is True
    assert queued.status_code == 202


def test_direct_demo_cannot_use_admin_or_approval_mutations(tmp_path: Path) -> None:
    with _app(tmp_path, direct_demo=True) as client:
        admin = client.get("/api/admin/users")
        approve = client.post("/api/governance/decisions/unknown/approve", json={"justification": "demo"})
    assert admin.status_code == 401
    assert approve.status_code == 401


def test_direct_demo_rejects_non_loopback_client(tmp_path: Path) -> None:
    with _app(tmp_path, direct_demo=True, client=("192.0.2.10", 50000)) as client:
        response = client.post("/api/scans", headers={"Origin": "http://127.0.0.1:3000"},
                               json={"name": "remote", "profile": "baseline", "dataset": "DATASET-DEMO"})
    assert response.status_code == 403
