"""Safe archive extraction (zip / tar).

Checks happen before and during extraction: member names are normalised and confined, links and
device files are refused, member count and total size are bounded, and the per-member compression
ratio is bounded. Declared sizes are not trusted: bytes are counted while streaming.
"""

from __future__ import annotations

import shutil
import stat
import tarfile
import zipfile
from pathlib import Path

from ..core.errors import LoaderError, ResourceLimitError, UnsafeInputError
from ..core.limits import ResourceLimits
from .safe_io import normalise_member_name, resolve_within

_CHUNK = 1 << 16


def _copy_bounded(src, dst_path: Path, budget: list[int], limit_member: int) -> None:
    written = 0
    with open(dst_path, "wb") as out:
        while chunk := src.read(_CHUNK):
            written += len(chunk)
            budget[0] -= len(chunk)
            if budget[0] < 0:
                raise ResourceLimitError("archive expands beyond the total size limit")
            if written > limit_member:
                raise ResourceLimitError(f"{dst_path.name}: member exceeds per-file size limit")
            out.write(chunk)


def extract_zip(archive: Path, dest: Path, limits: ResourceLimits) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile as exc:
        raise LoaderError(f"{archive.name}: not a valid zip archive") from exc
    names: list[str] = []
    with zf:
        members = zf.infolist()
        if len(members) > limits.max_archive_members:
            raise ResourceLimitError(f"archive has {len(members)} members (limit {limits.max_archive_members})")
        declared = sum(m.file_size for m in members)
        if declared > limits.max_archive_total_bytes:
            raise ResourceLimitError("archive declares more uncompressed data than allowed")
        for m in members:
            ftype = stat.S_IFMT((m.external_attr >> 16) & 0xFFFF)
            if ftype == stat.S_IFLNK:
                raise UnsafeInputError(f"archive member is a symbolic link: {m.filename[:128]!r}")
            if ftype and ftype not in (stat.S_IFREG, stat.S_IFDIR):
                raise UnsafeInputError(f"archive member is a special file: {m.filename[:128]!r}")
            clean = normalise_member_name(m.filename)
            if m.compress_size and m.file_size / max(m.compress_size, 1) > limits.max_compression_ratio:
                raise ResourceLimitError(f"{clean}: compression ratio exceeds {limits.max_compression_ratio:.0f}:1")
        budget = [limits.max_archive_total_bytes]
        for m in members:
            clean = normalise_member_name(m.filename)
            target = resolve_within(dest, clean)
            if m.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(m) as src:
                _copy_bounded(src, target, budget, limits.max_file_bytes)
            names.append(clean)
    return names


def extract_tar(archive: Path, dest: Path, limits: ResourceLimits) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        tf = tarfile.open(archive, mode="r:*")
    except tarfile.TarError as exc:
        raise LoaderError(f"{archive.name}: not a valid tar archive") from exc
    names: list[str] = []
    budget = [limits.max_archive_total_bytes]
    with tf:
        count = 0
        for m in tf:
            count += 1
            if count > limits.max_archive_members:
                raise ResourceLimitError(f"archive has more than {limits.max_archive_members} members")
            if m.issym() or m.islnk():
                raise UnsafeInputError(f"archive member is a link: {m.name[:128]!r}")
            if not (m.isfile() or m.isdir()):
                raise UnsafeInputError(f"archive member is a special file: {m.name[:128]!r}")
            clean = normalise_member_name(m.name)
            target = resolve_within(dest, clean)
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(m)
            if src is None:
                continue
            with src:
                _copy_bounded(src, target, budget, limits.max_file_bytes)
            names.append(clean)
    return names


def extract_archive(archive: Path, dest: Path, limits: ResourceLimits) -> list[str]:
    """Extract ``archive`` into an empty ``dest``; on any violation the partial output is removed."""
    if dest.exists() and any(dest.iterdir()):
        raise LoaderError(f"extraction target {dest} is not empty")
    name = archive.name.lower()
    try:
        if name.endswith(".zip"):
            return extract_zip(archive, dest, limits)
        if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.xz", ".tar.bz2")):
            return extract_tar(archive, dest, limits)
        raise LoaderError(f"unsupported archive type: {archive.name}", hint="use .zip or .tar[.gz|.xz|.bz2]")
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
