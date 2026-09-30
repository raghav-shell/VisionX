"""Append-only, hash-chained, Ed25519-signed ledger with Merkle checkpoints and external anchors."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .. import SOFTWARE_ID
from .canonical import anchor_message, canonical_bytes, entry_hash, signing_message
from .keys import b64u, key_id
from .merkle import root_hex

GENESIS_PREV = "sha256:" + "0" * 64


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")



try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]
    import msvcrt


def _lock_exclusive(fh) -> None:
    """Block until this process holds the ledger's lock file exclusively."""
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_EX)
        return
    fh.seek(0)
    while True:  # LK_LOCK gives up after ~10 s; keep waiting, as flock does
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            return
        except OSError:
            continue


def _unlock(fh) -> None:
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_UN)
        return
    fh.seek(0)
    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

class LedgerWriter:
    """Thread- and process-safe appender (flock on a sidecar lock file)."""

    def __init__(self, path: Path, key: Ed25519PrivateKey, *, purpose: str = "inference", checkpoint_every: int = 64,
                 anchor_path: Path | None = None, anchor_key: Ed25519PrivateKey | None = None) -> None:
        self.path = Path(path)
        self.key = key
        self.anchor_key = anchor_key or key
        self.purpose = purpose
        self.checkpoint_every = checkpoint_every
        self.anchor_path = anchor_path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lockfile = self.path.with_suffix(self.path.suffix + ".lock")
        with self._locked():
            if not self.path.exists() or self.path.stat().st_size == 0:
                self._hashes: list[str] = []
                self.ledger_id = f"{purpose}-{uuid.uuid4().hex[:12]}"
                self._append_locked("header", {"purpose": purpose, "software": SOFTWARE_ID,
                                               "checkpoint_interval": checkpoint_every, "created": utc_now()})
            else:
                self._load()

    # ------------------------------------------------------------------ internals
    def _locked(self):
        writer = self

        class _Guard:
            def __enter__(self_inner):
                writer._lock.acquire()
                writer._fh = open(writer._lockfile, "a+")  # noqa: SIM115
                _lock_exclusive(writer._fh)
                return self_inner

            def __exit__(self_inner, *exc):
                _unlock(writer._fh)
                writer._fh.close()
                writer._lock.release()
        return _Guard()

    def _load(self) -> None:
        self._hashes = []
        self.ledger_id = ""
        with open(self.path, "rb") as fh:
            for raw in fh:
                if raw.strip():
                    rec = json.loads(raw)
                    self.ledger_id = rec["ledger"]
                    self._hashes.append(entry_hash(rec))

    def _append_locked(self, kind: str, body: dict[str, Any]) -> dict:
        seq = len(self._hashes)
        rec = {"v": 1, "ledger": self.ledger_id, "seq": seq, "prev": self._hashes[-1] if self._hashes else GENESIS_PREV,
               "ts": utc_now(), "nonce": b64u(os.urandom(16)), "kind": kind, "body": body, "key_id": key_id(self.key)}
        rec["sig"] = b64u(self.key.sign(signing_message(rec)))
        line = canonical_bytes(rec) + b"\n"
        with open(self.path, "ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        self._hashes.append(entry_hash(rec))
        return rec

    # ------------------------------------------------------------------ public API
    @property
    def size(self) -> int:
        return len(self._hashes)

    def append(self, kind: str, body: dict[str, Any]) -> dict:
        canonical_bytes(body)  # validate (no floats, bounded depth) before signing
        with self._locked():
            self._load()
            rec = self._append_locked(kind, body)
            if self.checkpoint_every and (len(self._hashes) % self.checkpoint_every == 0):
                self._checkpoint_locked()
            return rec

    def checkpoint(self) -> dict:
        with self._locked():
            self._load()
            return self._checkpoint_locked()

    def _checkpoint_locked(self) -> dict:
        size = len(self._hashes)
        root = root_hex(self._hashes)
        rec = self._append_locked("checkpoint", {"tree_size": size, "root": root})
        if self.anchor_path is not None:
            anchor = {"ledger": self.ledger_id, "tree_size": size, "root": root, "ts": utc_now(),
                      "key_id": key_id(self.anchor_key)}
            anchor["sig"] = b64u(self.anchor_key.sign(anchor_message(anchor)))
            self.anchor_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.anchor_path, "ab") as fh:
                fh.write(canonical_bytes(anchor) + b"\n")
        return rec
