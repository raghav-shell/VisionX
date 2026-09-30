"""Workspace signing keys and trust root (created on first use, never overwritten)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..core.workspace import Workspace
from .keys import generate_key, load_private_key, save_private_key, trust_entry
from .trust import build_trust_root_document

ROLES = {"ledger": ["ledger", "anchor"], "audit": ["audit", "anchor"], "report": ["report"]}


@dataclass
class WorkspaceKeys:
    ledger: Ed25519PrivateKey
    audit: Ed25519PrivateKey
    report: Ed25519PrivateKey
    trust_root: Path

    @property
    def audit_ledger(self) -> Path:
        return self.trust_root.parent.parent / "ledgers" / "audit.jsonl"

    @property
    def audit_anchor(self) -> Path:
        return self.trust_root.parent.parent / "ledgers" / "audit.anchors.jsonl"


def ensure_keys(ws: Workspace) -> WorkspaceKeys:
    ws.ensure()
    keys = {}
    for name in ROLES:
        path = ws.keys / f"{name}.pem"
        keys[name] = load_private_key(path) if path.exists() else _create(path)
    trust = ws.keys / "trust.json"
    if not trust.exists():
        doc = build_trust_root_document("VisionSentinel workspace trust root",
                                        [trust_entry(keys[n], ROLES[n], f"workspace {n} key") for n in ROLES], [])
        trust.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return WorkspaceKeys(keys["ledger"], keys["audit"], keys["report"], trust)


def _create(path: Path) -> Ed25519PrivateKey:
    key = generate_key()
    save_private_key(key, path)
    return key


def approve_models(trust_path: Path, entries: list[dict]) -> None:
    """Add approved-model bindings to the workspace trust root (idempotent by artifact digest)."""
    doc = json.loads(trust_path.read_text(encoding="utf-8"))
    known = {m["artifact_digest"] for m in doc.get("approved_models", [])}
    for e in entries:
        if e["artifact_digest"] not in known:
            doc.setdefault("approved_models", []).append(e)
    trust_path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
