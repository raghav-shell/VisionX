"""Seed derivation and runtime fingerprinting.

Every stochastic component draws from a generator derived from ``(scan seed, component label)``
so that adding a detector never shifts the random stream of another one.
"""

from __future__ import annotations

import hashlib
import os
import platform
import random
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np

DETERMINISM_NOTE = (
    "Seeds are fixed for Python, NumPy and PyTorch and every component draws from its own derived "
    "stream. Results are reproducible on the same library versions and thread count; byte-identical "
    "floating-point output across different CPUs, BLAS builds or thread counts is not guaranteed."
)

_TRACKED_LIBS = ("numpy", "scipy", "scikit-learn", "pillow", "pydantic", "cryptography", "onnx",
                 "onnxruntime", "torch", "fastapi", "sqlalchemy")


def derive_seed(root: int, *labels: object) -> int:
    material = "|".join([str(int(root)), *map(str, labels)]).encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") & ((1 << 63) - 1)


def rng_for(root: int, *labels: object) -> np.random.Generator:
    return np.random.default_rng(derive_seed(root, *labels))


def seed_everything(seed: int, *, torch_threads: int | None = None) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed % (2**32))
    settings: dict[str, Any] = {"python_hash_seed": os.environ.get("PYTHONHASHSEED", "unset")}
    try:
        import torch
    except ImportError:
        settings["torch"] = "not installed"
        return settings
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    if torch_threads:
        torch.set_num_threads(torch_threads)
    settings.update(torch_threads=torch.get_num_threads(), torch_deterministic=True)
    return settings


def library_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in _TRACKED_LIBS:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "not installed"
    return out


def git_commit(start: Path | None = None) -> str | None:
    """Read the checked-out commit from ``.git`` without spawning a process."""
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        git = parent / ".git"
        if not git.is_dir():
            continue
        try:
            head = (git / "HEAD").read_text(encoding="utf-8").strip()
            if not head.startswith("ref: "):
                return head
            ref = head[5:]
            ref_file = git / ref
            if ref_file.is_file():
                return ref_file.read_text(encoding="utf-8").strip()
            packed = git / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        return line.split(" ", 1)[0]
        except OSError:
            return None
        return None
    return None


def platform_info() -> tuple[str, str]:
    return sys.version.split()[0], f"{platform.system()} {platform.release()} {platform.machine()}"
