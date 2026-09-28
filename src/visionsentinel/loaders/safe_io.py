"""Security boundary for untrusted files: path confinement, bounded reads, bounded JSON."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from ..core.errors import LoaderError, ResourceLimitError, UnsafeInputError
from ..core.limits import ResourceLimits

_WINDOWS_DRIVE = tuple(f"{c}:" for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


def normalise_member_name(name: str) -> str:
    """Validate a relative name from an annotation file or archive and return it POSIX-normalised.

    Rejects absolute paths, drive letters, NUL bytes, ``..`` components and empty names. Backslashes
    are treated as separators (datasets authored on Windows) and then validated like any other name.
    """
    if not isinstance(name, str) or not name:
        raise UnsafeInputError("empty or non-string path")
    if "\x00" in name:
        raise UnsafeInputError(f"path contains NUL byte: {name[:64]!r}")
    candidate = name.replace("\\", "/")
    if candidate.startswith("/") or candidate.startswith(_WINDOWS_DRIVE):
        raise UnsafeInputError(f"absolute path not allowed: {name[:128]!r}")
    parts = [p for p in PurePosixPath(candidate).parts if p not in ("", ".")]
    if not parts:
        raise UnsafeInputError(f"empty path: {name[:128]!r}")
    if any(p == ".." for p in parts):
        raise UnsafeInputError(f"path traversal not allowed: {name[:128]!r}")
    if any(len(p) > 255 for p in parts) or len(candidate) > 4096:
        raise UnsafeInputError("path component too long")
    return "/".join(parts)


def resolve_within(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root`` and prove the result (after symlinks) stays inside ``root``."""
    clean = normalise_member_name(relative)
    root_resolved = root.resolve()
    target = (root_resolved / clean).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise UnsafeInputError(f"path escapes dataset root (symlink or traversal): {relative[:128]!r}")
    return target


def ensure_regular_file(path: Path, max_bytes: int) -> int:
    try:
        st = path.stat()
    except FileNotFoundError:
        raise LoaderError(f"file not found: {path.name}") from None
    if not stat.S_ISREG(st.st_mode):
        raise UnsafeInputError(f"not a regular file: {path.name}")
    if st.st_size > max_bytes:
        raise ResourceLimitError(f"{path.name}: {st.st_size} bytes exceeds limit of {max_bytes}")
    return st.st_size


def read_bounded(path: Path, max_bytes: int) -> bytes:
    ensure_regular_file(path, max_bytes)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise UnsafeInputError(f"cannot open {path.name} safely: {exc.strerror}") from exc
    with os.fdopen(fd, "rb") as fh:
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ResourceLimitError(f"{path.name}: exceeds limit of {max_bytes} bytes")
    return data


def _check_structure(obj: Any, max_depth: int, max_elements: int) -> None:
    stack: list[tuple[Any, int]] = [(obj, 1)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > max_elements:
            raise ResourceLimitError(f"JSON has more than {max_elements} elements")
        if depth > max_depth:
            raise ResourceLimitError(f"JSON nesting deeper than {max_depth}")
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)


def load_json_bounded(path: Path, limits: ResourceLimits) -> Any:
    return parse_json_bounded(read_bounded(path, limits.max_json_bytes), limits, name=path.name)


def parse_json_bounded(data: bytes, limits: ResourceLimits, *, name: str = "<json>") -> Any:
    if len(data) > limits.max_json_bytes:
        raise ResourceLimitError(f"{name}: JSON exceeds {limits.max_json_bytes} bytes")
    try:
        obj = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ResourceLimitError(f"{name}: JSON nesting too deep") from exc
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LoaderError(f"{name}: malformed JSON: {exc}") from exc
    _check_structure(obj, limits.max_json_depth, limits.max_json_elements)
    return obj


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-standard JSON constant {value}")


def safe_text(value: Any, max_len: int = 256) -> str | None:
    """Coerce an untrusted metadata value to a bounded single-line string."""
    if value is None:
        return None
    text = str(value)
    text = "".join(ch for ch in text if ch.isprintable())
    return text[:max_len] if text else None
