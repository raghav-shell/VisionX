"""Workspace layout on disk.

Everything VisionSentinel writes at runtime lives below one root (``VISIONSENTINEL_HOME``,
default ``./var``) so that an air-gapped host can back it up, wipe it or mount it read-only for
review as a unit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_HOME = "VISIONSENTINEL_HOME"


def repo_root() -> Path:
    """The source checkout root (contains ``profiles/``), when running from a checkout."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "profiles").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


@dataclass(frozen=True)
class Workspace:
    root: Path

    @classmethod
    def default(cls) -> "Workspace":
        root = Path(os.environ.get(ENV_HOME) or (repo_root() / "var"))
        return cls(root.resolve())

    def ensure(self) -> "Workspace":
        for d in (self.evidence, self.cache, self.ledgers, self.keys, self.assets, self.reports,
                  self.scans, self.demo, self.attacklab):
            d.mkdir(parents=True, exist_ok=True)
        try:
            self.keys.chmod(0o700)
        except OSError:
            pass
        return self

    @property
    def evidence(self) -> Path:
        return self.root / "evidence"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def ledgers(self) -> Path:
        return self.root / "ledgers"

    @property
    def keys(self) -> Path:
        return self.root / "keys"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def scans(self) -> Path:
        return self.root / "scans"

    @property
    def demo(self) -> Path:
        return self.root / "demo"

    @property
    def attacklab(self) -> Path:
        return self.root / "attacklab"

    @property
    def database_url(self) -> str:
        return os.environ.get("VISIONSENTINEL_DATABASE_URL") or f"sqlite:///{self.root / 'visionsentinel.sqlite'}"
