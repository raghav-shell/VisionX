"""Asset management endpoints: list, import, upload, describe and delete assets in workspace."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from ...contracts import Role
from ...core.errors import LoaderError, UnsafeInputError
from ...storage import Asset
from ..assets import KINDS, import_path, register, safe_name
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/assets", tags=["assets"])


class AssetImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str | None = None
    copy_source: bool = Field(default=True)


def _asset_view(a: Asset) -> dict:
    return {
        "id": a.id,
        "kind": a.kind,
        "name": a.name,
        "path": a.path,
        "digest": a.digest,
        "details": a.details,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("", dependencies=[Depends(require(Role.VIEWER))])
def list_assets(
    kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as s:
        q = select(Asset).order_by(desc(Asset.created_at))
        if kind:
            q = q.filter(Asset.kind == kind.lower())
        total = s.query(Asset).count()
        rows = s.scalars(q.offset(offset).limit(limit)).all()
        return {"total": total, "assets": [_asset_view(r) for r in rows]}


@router.get("/{asset_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_asset(asset_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        a = s.get(Asset, asset_id)
        if a is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"asset {asset_id!r} not found")
        return _asset_view(a)


@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_asset(
    body: AssetImportBody,
    principal: Principal = Depends(mutation(Role.ANALYST)),
    state: AppState = Depends(get_state),
) -> dict:
    src = Path(body.source_path)
    if not src.exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"source path {body.source_path!r} does not exist")
    try:
        asset = import_path(
            state.db,
            state.workspace,
            src,
            kind=body.kind,
            name=body.name,
            copy=body.copy_source,
        )
        state.audit.record(
            principal.username,
            "import_asset",
            asset.id,
            extra={"kind": asset.kind, "name": asset.name, "digest": asset.digest},
        )
        return _asset_view(asset)
    except (LoaderError, UnsafeInputError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


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
