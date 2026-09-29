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

from ..contracts import AssetKind, AssetLifecycle, SCAN_ASSET_INPUTS, ScanAssetInput
from ..core.errors import LoaderError, UnsafeInputError, VisionSentinelError
from ..core.hashing import sha256_file
from ..core.limits import ResourceLimits
from ..core.workspace import Workspace
from ..loaders.archives import extract_archive
from ..loaders.datasets import open_dataset
from ..loaders.models import open_model
from ..storage import Asset, Database

KINDS = tuple(kind.value for kind in AssetKind)
_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


class AssetResolutionError(VisionSentinelError):
    """Base error for an asset that cannot be used for a requested input role."""


class AssetNotFoundError(AssetResolutionError):
    pass


class AssetCompatibilityError(AssetResolutionError):
    pass


class AssetUnavailableError(AssetResolutionError):
    pass


class AssetResolver:
    """Resolve registry IDs without allowing arbitrary or escaped filesystem paths."""

    def __init__(self, db: Database, workspace: Workspace) -> None:
        self.db = db
        self.workspace = workspace

    @staticmethod
    def _spec(field: str) -> ScanAssetInput:
        try:
            return next(spec for spec in SCAN_ASSET_INPUTS if spec.field == field)
        except StopIteration as exc:
            raise AssetCompatibilityError(f"{field} is not a registered scan asset input") from exc

    def resolve(self, asset_id: str | None, field: str) -> Path | None:
        if not asset_id:
            return None
        spec = self._spec(field)
        with self.db.session() as session:
            asset = session.get(Asset, asset_id)
            if asset is None:
                raise AssetNotFoundError(f"{field} must identify an imported asset identifier")
            try:
                kind = AssetKind(asset.kind)
            except ValueError as exc:
                raise AssetCompatibilityError(f"{field} references an unsupported asset kind") from exc
            if kind not in spec.kinds:
                expected = ", ".join(sorted(item.value for item in spec.kinds))
                raise AssetCompatibilityError(f"{field} requires an asset compatible with {expected}")
            details = asset.details or {}
            try:
                lifecycle = AssetLifecycle(details.get("lifecycle", AssetLifecycle.ACTIVE.value))
            except ValueError as exc:
                raise AssetUnavailableError(f"{field} references an asset with an invalid lifecycle") from exc
            if lifecycle is not AssetLifecycle.ACTIVE:
                raise AssetUnavailableError(f"{field} references an archived asset")
            stored_path = Path(asset.path)

        return self._validate_storage(stored_path, field)

    def resolve_request(self, request: object) -> dict[str, Path]:
        """Resolve all registry IDs represented by a web-shaped ScanRequest."""
        resolved: dict[str, Path] = {}
        for spec in SCAN_ASSET_INPUTS:
            value = getattr(request, spec.field)
            if value is not None:
                path = self.resolve(str(value), spec.field)
                if path is not None:
                    resolved[spec.field] = path
        return resolved

    def _validate_storage(self, stored_path: Path, field: str) -> Path:
        root = self.workspace.assets.resolve()
        if not stored_path.is_absolute() or any(part == ".." for part in stored_path.parts):
            raise AssetUnavailableError(f"{field} references unsafe asset storage")
        if any(part.is_symlink() for part in self._path_chain(stored_path, root)):
            raise AssetUnavailableError(f"{field} references unsafe asset storage")
        try:
            resolved = stored_path.resolve(strict=False)
        except OSError as exc:
            raise AssetUnavailableError(f"{field} asset storage cannot be resolved") from exc
        if resolved == root or not resolved.is_relative_to(root):
            raise AssetUnavailableError(f"{field} references storage outside the workspace")
        if not resolved.exists():
            raise AssetUnavailableError(f"{field} asset storage is unavailable")
        return resolved

    @staticmethod
    def _path_chain(path: Path, root: Path) -> list[Path]:
        chain: list[Path] = []
        current = path
        while True:
            chain.append(current)
            if current == root or current.parent == current:
                break
            current = current.parent
        return chain


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
    if kind == AssetKind.DATASET.value:
        ds = open_dataset(path, limits)
        return ds.digest, ds.summary()
    if kind == AssetKind.MODEL.value:
        m = open_model(path, limits)
        try:
            return m.artifact_digest, m.describe()
        finally:
            m.close()
    if kind == AssetKind.INPUTS.value:
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
    if source.is_file() and source.suffix.lower() in (".zip", ".tar", ".gz", ".tgz", ".xz", ".bz2") and kind in {
            AssetKind.DATASET.value, AssetKind.INPUTS.value}:
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
            if kind == AssetKind.MODEL.value and sidecar.is_file():
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
