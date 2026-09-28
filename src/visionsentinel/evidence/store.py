"""Content-addressed evidence storage.

``SHA-256(content) → evidence/sha256/<aa>/<hex>``. Writes are atomic and idempotent (identical
evidence is stored once). Every read re-hashes the content and refuses to return bytes whose digest
does not match the address, so tampered evidence can never be rendered as if it were genuine.
Only formats that VisionSentinel generates itself are accepted: PNG and JSON.
"""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..contracts import BlobRef
from ..core.errors import EvidenceIntegrityError, UnsafeInputError
from ..core.hashing import canonical_json_bytes, sha256_hex

_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MEDIA_TYPES = ("image/png", "application/json")
MAX_BLOB_BYTES = 32 * 1024 * 1024


def sniff_media_type(data: bytes) -> str:
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    try:
        json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnsafeInputError("evidence blob is neither PNG nor JSON") from exc
    return "application/json"


class EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        (self.root / "sha256").mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        m = _DIGEST.match(digest)
        if not m:
            raise UnsafeInputError(f"malformed evidence digest {digest[:80]!r}")
        hexd = m.group(1)
        return self.root / "sha256" / hexd[:2] / hexd

    def put_bytes(self, data: bytes, media_type: str) -> BlobRef:
        if media_type not in MEDIA_TYPES:
            raise UnsafeInputError(f"evidence media type {media_type!r} is not allowed")
        if len(data) > MAX_BLOB_BYTES:
            raise UnsafeInputError("evidence blob exceeds size limit")
        if sniff_media_type(data) != media_type:
            raise UnsafeInputError(f"evidence content does not match declared type {media_type}")
        digest = "sha256:" + sha256_hex(data)
        target = self.path_for(digest)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, target)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise
        return BlobRef(digest=digest, media_type=media_type, size_bytes=len(data))

    def put_json(self, obj: Any) -> BlobRef:
        return self.put_bytes(canonical_json_bytes(obj), "application/json")

    def put_png(self, image: np.ndarray) -> BlobRef:
        arr = np.asarray(image)
        if arr.dtype != np.uint8:
            arr = np.clip(arr * (255.0 if arr.max(initial=0) <= 1.0 else 1.0), 0, 255).astype(np.uint8)
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="PNG", optimize=False, compress_level=6)
        return self.put_bytes(buf.getvalue(), "image/png")

    def get(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if not path.is_file():
            raise EvidenceIntegrityError(f"evidence {digest} is missing from the store")
        data = path.read_bytes()
        if "sha256:" + sha256_hex(data) != digest:
            raise EvidenceIntegrityError(f"evidence {digest} failed digest verification (content altered)")
        return data

    def verify(self, digest: str) -> bool:
        try:
            self.get(digest)
            return True
        except EvidenceIntegrityError:
            return False

    def media_type(self, digest: str) -> str:
        return sniff_media_type(self.get(digest))


class MemoryBlobSink:
    """In-memory sink used by unit tests and dry runs."""

    def __init__(self) -> None:
        self.blobs: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, data: bytes, media_type: str) -> BlobRef:
        digest = "sha256:" + sha256_hex(data)
        self.blobs[digest] = (data, media_type)
        return BlobRef(digest=digest, media_type=media_type, size_bytes=len(data))

    def put_json(self, obj: Any) -> BlobRef:
        return self.put_bytes(canonical_json_bytes(obj), "application/json")

    def put_png(self, image: np.ndarray) -> BlobRef:
        buf = io.BytesIO()
        Image.fromarray(np.asarray(image, dtype=np.uint8)).save(buf, format="PNG")
        return self.put_bytes(buf.getvalue(), "image/png")
