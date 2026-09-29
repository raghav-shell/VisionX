"""The registered-asset web boundary is registry-driven and path confined."""

from pathlib import Path

import pytest

from visionsentinel.contracts import AssetKind, AssetLifecycle, SCAN_ASSET_INPUTS
from visionsentinel.api.assets import (
    AssetCompatibilityError,
    AssetNotFoundError,
    AssetResolver,
    AssetUnavailableError,
)
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.storage import Asset, Database


def _resolver(tmp_path: Path) -> tuple[AssetResolver, Database, Workspace]:
    workspace = Workspace(tmp_path / "workspace").ensure()
    db = Database(workspace.database_url)
    return AssetResolver(db, workspace), db, workspace


def _asset(db: Database, workspace: Workspace, asset_id: str, kind: AssetKind, relative: str = "data") -> None:
    path = workspace.assets / asset_id / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("asset", encoding="utf-8")
    with db.session() as session:
        session.add(Asset(id=asset_id, kind=kind.value, name=asset_id, path=str(path), details={}))


def test_registry_covers_every_path_backed_scan_input_and_every_asset_kind() -> None:
    request_fields = {field for field, info in ScanRequest.model_fields.items()
                      if "Path" in str(info.annotation)}
    registry_fields = {spec.field for spec in SCAN_ASSET_INPUTS}
    assert request_fields - {"scan_id"} == registry_fields
    covered_kinds = {kind for spec in SCAN_ASSET_INPUTS for kind in spec.kinds}
    assert set(AssetKind) == covered_kinds


def test_resolver_accepts_only_semantically_compatible_kind(tmp_path: Path) -> None:
    resolver, db, workspace = _resolver(tmp_path)
    _asset(db, workspace, "MODEL-1", AssetKind.MODEL)
    assert resolver.resolve("MODEL-1", "model").name == "data"
    with pytest.raises(AssetCompatibilityError):
        resolver.resolve("MODEL-1", "dataset")


def test_resolver_rejects_archived_missing_and_escaped_storage(tmp_path: Path) -> None:
    resolver, db, workspace = _resolver(tmp_path)
    _asset(db, workspace, "DATA-1", AssetKind.DATASET)
    with db.session() as session:
        session.get(Asset, "DATA-1").details = {"lifecycle": AssetLifecycle.ARCHIVED.value}
    with pytest.raises(AssetUnavailableError):
        resolver.resolve("DATA-1", "dataset")

    with pytest.raises(AssetNotFoundError):
        resolver.resolve("missing", "dataset")

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with db.session() as session:
        session.add(Asset(id="DATA-2", kind=AssetKind.DATASET.value, name="escape", path=str(outside), details={}))
    with pytest.raises(AssetUnavailableError):
        resolver.resolve("DATA-2", "dataset")


def test_resolver_rejects_symlink_storage_even_when_target_is_inside(tmp_path: Path) -> None:
    resolver, db, workspace = _resolver(tmp_path)
    target = workspace.assets / "real" / "data"
    target.parent.mkdir(parents=True)
    target.write_text("asset", encoding="utf-8")
    link = workspace.assets / "link"
    link.symlink_to(target.parent, target_is_directory=True)
    with db.session() as session:
        session.add(Asset(id="DATA-LINK", kind=AssetKind.DATASET.value, name="link", path=str(link / "data"), details={}))
    with pytest.raises(AssetUnavailableError):
        resolver.resolve("DATA-LINK", "dataset")
