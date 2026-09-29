"""Workspace asset registry.

The API never accepts file-system paths from clients: assets enter the workspace through ``visionsentinel assets
import`` (operator on the host), through size-limited uploads with safe archive extraction, or through the demo
builder, and are referenced afterwards by identifier only.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import shutil
from pathlib import Path

from sqlalchemy import select

from ..core.errors import LoaderError, UnsafeInputError
from ..core.hashing import sha256_file
from ..core.limits import ResourceLimits
from ..core.workspace import Workspace
from ..loaders.archives import extract_archive
from ..loaders.datasets import open_dataset
from ..loaders.models import open_model
from ..storage import Asset, Database

KINDS = ("dataset", "model", "preprocess", "ledger", "anchor", "trust_root", "inputs", "fingerprint")
DATASET_ROLES = ("dataset", "reference_dataset", "probe_dataset", "suspect_inputs", "operational_data")
_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_name(name: str) -> str:
    return (_NAME.sub("_", name).strip(" .") or "asset")[:120]


def register(db: Database, kind: str, name: str, path: Path, *, digest: str | None = None,
             details: dict | None = None, asset_id: str | None = None) -> Asset:
    if kind not in KINDS:
        raise LoaderError(f"unknown asset kind {kind!r}; choose one of {', '.join(KINDS)}")
    aid = asset_id or f"{kind[:3].upper()}-{secrets.token_hex(4).upper()}"
    with db.session() as s:
        existing = s.get(Asset, aid)
        if existing is not None:
            existing.name, existing.path, existing.digest, existing.details = name, str(path), digest, details or {}
            return existing
        a = Asset(id=aid, kind=kind, name=safe_name(name), path=str(path), digest=digest, details=details or {})
        s.add(a)
    return a


def _describe(kind: str, path: Path, limits: ResourceLimits) -> tuple[str | None, dict]:
    if kind == "dataset":
        ds = open_dataset(path, limits)
        return ds.digest, ds.summary()
    if kind == "model":
        m = open_model(path, limits)
        try:
            return m.artifact_digest, m.describe()
        finally:
            m.close()
    if kind == "inputs":
        files = [p for p in path.rglob("*") if p.is_file()]
        h = hashlib.sha256()
        for p in sorted(files):
            h.update(p.name.encode() + sha256_file(p).encode())
        return "sha256:" + h.hexdigest(), {"files": len(files)}
    return sha256_file(path), {"bytes": path.stat().st_size}


def import_path(db: Database, ws: Workspace, source: Path, kind: str, name: str | None = None,
                limits: ResourceLimits | None = None, *, copy: bool = True) -> Asset:
    """Copy (or extract) ``source`` into the workspace, validate it with the matching loader and register it."""
    limits = limits or ResourceLimits()
    source = Path(source)
    if not source.exists():
        raise LoaderError(f"{source} does not exist")
    aid = f"{kind[:3].upper()}-{secrets.token_hex(4).upper()}"
    dest_root = ws.assets / aid
    if source.is_file() and source.suffix.lower() in (".zip", ".tar", ".gz", ".tgz", ".xz", ".bz2") and kind in (
            "dataset", "inputs"):
        extract_archive(source, dest_root, limits)
        dest = dest_root
        subdirs = [d for d in dest.iterdir()]
        if len(subdirs) == 1 and subdirs[0].is_dir():
            dest = subdirs[0]
    elif copy:
        dest_root.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            if any(p.is_symlink() for p in source.rglob("*")):
                raise UnsafeInputError(f"{source} contains symbolic links; refusing to import")
            dest = dest_root / source.name
            shutil.copytree(source, dest)
        else:
            dest = dest_root / source.name
            shutil.copy2(source, dest)
            sidecar = source.with_name(source.stem + ".preprocess.json")
            if kind == "model" and sidecar.is_file():
                shutil.copy2(sidecar, dest_root / sidecar.name)
    else:
        dest = source.resolve()
    try:
        digest, details = _describe(kind, dest, limits)
    except BaseException:
        if copy:
            shutil.rmtree(dest_root, ignore_errors=True)
        raise
    return register(db, kind, name or source.stem, dest, digest=digest, details=details, asset_id=aid)


def resolve(db: Database, asset_id: str | None, kinds: tuple[str, ...]) -> Path | None:
    if not asset_id:
        return None
    with db.session() as s:
        a = s.get(Asset, asset_id)
        if a is None or a.kind not in kinds:
            raise LoaderError(f"asset {asset_id!r} not found (expected kind {'/'.join(kinds)})")
        return Path(a.path)


def list_assets(db: Database, kind: str | None = None) -> list[Asset]:
    with db.session() as s:
        q = select(Asset).order_by(Asset.created_at.desc())
        if kind:
            q = q.where(Asset.kind == kind)
        return list(s.scalars(q))
