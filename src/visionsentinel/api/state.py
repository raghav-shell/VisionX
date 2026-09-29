"""Application state: workspace, database, keys, governance, evidence store and the job runner."""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from ..contracts import ScanResult
from ..core.workspace import Workspace
from ..evidence.store import EvidenceStore
from ..governance import AuditTrail, GovernanceService
from ..provenance.ledger import LedgerWriter
from ..provenance.workspace_keys import WorkspaceKeys, ensure_keys
from ..storage import Database, Scan
from .security import RateLimiter
from .settings import Settings


@dataclass
class ResultCache:
    size: int = 8
    _items: OrderedDict = field(default_factory=OrderedDict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, path: Path) -> ScanResult:
        key = str(path)
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        result = ScanResult.model_validate(json.loads(Path(path).read_text()))
        with self._lock:
            self._items[key] = result
            while len(self._items) > self.size:
                self._items.popitem(last=False)
        return result


@dataclass
class AppState:
    settings: Settings
    workspace: Workspace
    db: Database
    keys: WorkspaceKeys
    audit: AuditTrail
    governance: GovernanceService
    store: EvidenceStore
    limiter: RateLimiter
    results: ResultCache
    runner: "object" = None

    @classmethod
    def create(cls, settings: Settings, workspace: Workspace) -> "AppState":
        workspace.ensure()
        db = Database(workspace.database_url)
        keys = ensure_keys(workspace)
        ledger = LedgerWriter(keys.audit_ledger, keys.audit, purpose="audit", checkpoint_every=32,
                              anchor_path=keys.audit_anchor)
        audit = AuditTrail(db, ledger)
        return cls(settings=settings, workspace=workspace, db=db, keys=keys, audit=audit,
                   governance=GovernanceService(db, audit), store=EvidenceStore(workspace.evidence),
                   limiter=RateLimiter(), results=ResultCache())

    def result(self, scan_id: str) -> ScanResult | None:
        with self.db.session() as s:
            scan = s.get(Scan, scan_id)
            path = scan.result_path if scan else None
        return self.results.get(Path(path)) if path and Path(path).is_file() else None

    @property
    def origins(self) -> set[str]:
        out = set(self.settings.extra_origins)
        return out
