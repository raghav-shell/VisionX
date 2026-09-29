"""Asset management endpoints: list, import, upload, describe and delete assets in workspace."""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import desc, select

from ...contracts import Role
from ...core.errors import LoaderError, UnsafeInputError
from ...storage import Asset, AuditEvent, Scan
from ..assets import KINDS, import_path, safe_name
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _asset_view(a: Asset) -> dict:
    details = dict(a.details or {})
    return {
        "id": a.id,
        "kind": a.kind,
        "name": a.name,
        "digest": a.digest,
        "details": details,
        "lifecycle": details.get("lifecycle", "ACTIVE"),
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _tree_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def _is_referenced(asset_id: str, state: AppState) -> bool:
    """Conservatively prevent deletion of anything referenced by a scan request."""
    with state.db.session() as s:
        return any(asset_id in (scan.request or {}).values() for scan in s.scalars(select(Scan)).all())


@router.get("", dependencies=[Depends(require(Role.VIEWER))])
def list_assets(
    kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    lifecycle: str | None = Query(default="ACTIVE", pattern="^(ACTIVE|ARCHIVED)$"),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as s:
        q = select(Asset).order_by(desc(Asset.created_at))
        if kind:
            q = q.filter(Asset.kind == kind.lower())
        rows = s.scalars(q).all()
        if lifecycle:
            rows = [r for r in rows if (r.details or {}).get("lifecycle", "ACTIVE") == lifecycle]
        total = len(rows)
        return {"total": total, "assets": [_asset_view(r) for r in rows[offset:offset + limit]]}


@router.get("/kinds", dependencies=[Depends(require(Role.VIEWER))])
def asset_kinds() -> dict:
    return {"kinds": [{"id": kind, "label": kind.replace("_", " ").title()} for kind in KINDS]}


@router.get("/status", dependencies=[Depends(require(Role.VIEWER))])
def asset_status(state: AppState = Depends(get_state)) -> dict:
    active = archived = 0
    by_kind: dict[str, int] = {}
    with state.db.session() as s:
        rows = s.scalars(select(Asset)).all()
    for a in rows:
        if (a.details or {}).get("lifecycle", "ACTIVE") == "ARCHIVED":
            archived += 1
        else:
            active += 1
        by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
    used = _tree_bytes(state.workspace.assets)
    quota = state.settings.max_asset_storage_bytes
    return {"quota_bytes": quota, "used_bytes": used, "available_bytes": max(quota - used, 0),
            "over_quota": used > quota, "active_assets": active, "archived_assets": archived, "by_kind": by_kind}


@router.get("/{asset_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_asset(asset_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        a = s.get(Asset, asset_id)
        if a is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"asset {asset_id!r} not found")
        return _asset_view(a)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    kind: str = Form(...),
    name: str | None = Form(default=None),
    principal: Principal = Depends(mutation(Role.ANALYST)),
    state: AppState = Depends(get_state),
) -> dict:
    if kind not in KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid kind {kind!r}; choose one of {', '.join(KINDS)}")

    if _tree_bytes(state.workspace.assets) >= state.settings.max_asset_storage_bytes:
        raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "workspace asset quota exhausted; archive or remove assets")
    temp_dir = state.workspace.root / "tmp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"upload_{secrets.token_hex(8)}_{safe_name(file.filename or 'upload')}"

    # Read bounded
    max_bytes = state.settings.max_upload_bytes
    total_read = 0
    try:
        with temp_file.open("wb") as dst:
            while chunk := await file.read(64 * 1024):
                total_read += len(chunk)
                if total_read > max_bytes:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"upload exceeds limit of {max_bytes / (1024*1024):.0f} MB",
                    )
                if _tree_bytes(state.workspace.assets) + total_read > state.settings.max_asset_storage_bytes:
                    raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE,
                                        "upload would exceed the configured workspace asset quota")
                dst.write(chunk)

        asset_name = name or file.filename or "upload"
        asset = import_path(
            state.db,
            state.workspace,
            temp_file,
            kind=kind,
            name=asset_name,
            copy=True,
        )
        state.audit.record(
            principal.username,
            "upload_asset",
            asset.id,
            extra={"kind": asset.kind, "name": asset.name, "bytes": total_read},
        )
        return _asset_view(asset)
    finally:
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)


@router.get("/{asset_id}/history", dependencies=[Depends(require(Role.VIEWER))])
def asset_history(asset_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        if s.get(Asset, asset_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"asset {asset_id!r} not found")
        events = s.scalars(select(AuditEvent).where(AuditEvent.target == asset_id).order_by(desc(AuditEvent.ts))).all()
    return {"asset_id": asset_id, "events": [{"timestamp": e.ts.isoformat(), "actor": e.actor,
            "action": e.action, "old_state": e.old_state, "new_state": e.new_state,
            "reason_code": e.reason_code} for e in events]}


@router.post("/{asset_id}/archive")
def archive_asset(asset_id: str, principal: Principal = Depends(mutation(Role.ANALYST)),
                  state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        asset = s.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"asset {asset_id!r} not found")
        details = dict(asset.details or {})
        if details.get("lifecycle", "ACTIVE") == "ARCHIVED":
            return _asset_view(asset)
        details["lifecycle"] = "ARCHIVED"
        asset.details = details
    state.audit.record(principal.username, "archive_asset", asset_id, old="ACTIVE", new="ARCHIVED")
    return _asset_view(asset)


@router.post("/{asset_id}/restore")
def restore_asset(asset_id: str, principal: Principal = Depends(mutation(Role.ANALYST)),
                  state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        asset = s.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"asset {asset_id!r} not found")
        details = dict(asset.details or {})
        details["lifecycle"] = "ACTIVE"
        asset.details = details
    state.audit.record(principal.username, "restore_asset", asset_id, old="ARCHIVED", new="ACTIVE")
    return _asset_view(asset)


@router.delete("/{asset_id}")
def delete_asset(asset_id: str, principal: Principal = Depends(mutation(Role.ADMIN)),
                 state: AppState = Depends(get_state)) -> dict:
    if _is_referenced(asset_id, state):
        raise HTTPException(status.HTTP_409_CONFLICT, "asset is referenced by a scan and cannot be deleted")
    with state.db.session() as s:
        asset = s.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"asset {asset_id!r} not found")
        source = Path(asset.path).resolve()
        owned_root = (state.workspace.assets / asset_id).resolve()
        if not source.is_relative_to(owned_root):
            raise HTTPException(status.HTTP_409_CONFLICT, "only workspace-owned imported assets can be deleted")
        quarantine = state.workspace.root / "deleted_assets" / asset_id
        quarantine.parent.mkdir(parents=True, exist_ok=True)
        if owned_root.exists():
            shutil.move(str(owned_root), str(quarantine))
        s.delete(asset)
    state.audit.record(principal.username, "delete_asset", asset_id, old="ARCHIVED", new="RECOVERABLE_DELETE")
    return {"deleted": asset_id, "recovery_path": str(quarantine.relative_to(state.workspace.root))}
