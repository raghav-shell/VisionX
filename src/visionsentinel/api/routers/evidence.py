"""Evidence store endpoints: retrieve content-addressed evidence blobs with integrity verification."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...contracts import Role
from ...core.errors import EvidenceIntegrityError, UnsafeInputError
from ...evidence.store import sniff_media_type
from ..deps import get_state, require
from ..state import AppState

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


def _read_verified(state: AppState, digest: str) -> bytes:
    """Read a blob, re-checking its SHA-256 against the digest it is addressed by."""
    try:
        path = state.store.path_for(digest)
    except UnsafeInputError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"evidence {digest!r} not found in store")
    try:
        return state.store.get(digest)
    except EvidenceIntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"evidence blob tampered on disk: {exc}") from exc


@router.get("/{digest}/raw", dependencies=[Depends(require(Role.VIEWER))])
def get_raw_evidence(digest: str, state: AppState = Depends(get_state)) -> Response:
    """Retrieve a raw content-addressed blob, verifying SHA-256 integrity on read."""
    raw_bytes = _read_verified(state, digest)
    return Response(
        content=raw_bytes,
        media_type=sniff_media_type(raw_bytes),
        headers={
            # Content-addressed, so it never changes; private because it is served only to signed-in users.
            "Cache-Control": "private, max-age=31536000, immutable",
            "ETag": f'"{digest}"',
        },
    )


@router.get("/{digest}", dependencies=[Depends(require(Role.VIEWER))])
def get_evidence_meta(digest: str, state: AppState = Depends(get_state)) -> dict:
    raw_bytes = _read_verified(state, digest)
    return {"digest": digest, "media_type": sniff_media_type(raw_bytes), "size_bytes": len(raw_bytes), "verified": True}
