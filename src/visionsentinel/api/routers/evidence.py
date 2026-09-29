"""Evidence store endpoints: retrieve content-addressed evidence blobs with integrity verification."""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...contracts import Role
from ...core.errors import EvidenceIntegrityError
from ..deps import get_state, require
from ..state import AppState

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/{digest}/raw", dependencies=[Depends(require(Role.VIEWER))])
def get_raw_evidence(digest: str, state: AppState = Depends(get_state)) -> Response:
    """Retrieve raw content-addressed blob, verifying SHA-256 integrity on read."""
    try:
        raw_bytes = state.store.get_bytes(digest)
    except EvidenceIntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"evidence blob tampered on disk: {exc}") from exc
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"evidence {digest!r} not found in store")

    # Determine media type by prefix or suffix
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif raw_bytes.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif raw_bytes.strip().startswith(b"{") or raw_bytes.strip().startswith(b"["):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return Response(
        content=raw_bytes,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{digest}"',
        },
    )


@router.get("/{digest}", dependencies=[Depends(require(Role.VIEWER))])
def get_evidence_meta(digest: str, state: AppState = Depends(get_state)) -> dict:
    try:
        meta = state.store.describe(digest)
        return meta
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"evidence {digest!r} not found in store")
