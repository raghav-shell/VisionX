"""Digest helpers. All digests are rendered as ``sha256:<hex>``."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .errors import ResourceLimitError

PREFIX = "sha256:"
_CHUNK = 1 << 20


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_digest(data: bytes) -> str:
    return PREFIX + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, *, max_bytes: int | None = None) -> str:
    """Stream a file into SHA-256, refusing files larger than ``max_bytes``."""
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise ResourceLimitError(f"{path.name}: exceeds size limit of {max_bytes} bytes")
            h.update(chunk)
    return PREFIX + h.hexdigest()


def _normalise(obj: Any) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return repr(obj)
        return obj
    if isinstance(obj, dict):
        return {str(k): _normalise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalise(v) for v in obj]
    return obj


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic JSON for digests of reports, profiles and scan results.

    Sorted keys, compact separators, UTF-8, non-finite floats rendered as strings. Signed ledger
    payloads use the stricter float-free canonical form in :mod:`visionsentinel.provenance.canonical`.
    """
    return json.dumps(_normalise(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest_json(obj: Any) -> str:
    return sha256_digest(canonical_json_bytes(obj))


def short(digest: str | None, n: int = 12) -> str:
    if not digest:
        return "—"
    return digest.removeprefix(PREFIX)[:n]
