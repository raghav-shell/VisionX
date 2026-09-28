"""Trust root: public keys and approved model bindings. Standard library only (used by the verifier).

    {
      "version": 1,
      "name": "...",
      "keys": [{"key_id": "ed25519:<16 hex>", "public_key": "<base64 raw 32 bytes>", "roles": ["ledger", ...],
                "not_before": "<ISO 8601>", "not_after": null, "revoked": false, "comment": ""}],
      "approved_models": [{"name": "...", "artifact_digest": "sha256:...", "param_digest": "sha256:...",
                           "preprocess_digest": "sha256:...", "architecture_digest": "sha256:...",
                           "approved_by": "...", "approved_at": "<ISO 8601>"}]
    }
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MAX_TRUST_ROOT_BYTES = 1024 * 1024


class TrustRootError(ValueError):
    pass


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class TrustedKey:
    key_id: str
    public_key: bytes
    roles: tuple[str, ...]
    not_before: datetime | None = None
    not_after: datetime | None = None
    revoked: bool = False
    comment: str = ""

    def valid_at(self, when: datetime) -> bool:
        if self.revoked:
            return False
        if self.not_before and when < self.not_before:
            return False
        return not (self.not_after and when > self.not_after)


@dataclass(frozen=True)
class ApprovedModel:
    name: str
    artifact_digest: str
    param_digest: str | None = None
    preprocess_digest: str | None = None
    architecture_digest: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None


@dataclass
class TrustRoot:
    name: str
    keys: dict[str, TrustedKey] = field(default_factory=dict)
    approved_models: list[ApprovedModel] = field(default_factory=list)
    digest: str = ""

    def approved_artifact(self, digest: str) -> ApprovedModel | None:
        return next((m for m in self.approved_models if m.artifact_digest == digest), None)

    def approved_params(self, digest: str | None) -> ApprovedModel | None:
        if not digest:
            return None
        return next((m for m in self.approved_models if m.param_digest == digest), None)

    def approved_preprocess(self) -> set[str]:
        return {m.preprocess_digest for m in self.approved_models if m.preprocess_digest}


def key_id_for(public_key: bytes) -> str:
    return "ed25519:" + hashlib.sha256(public_key).hexdigest()[:16]


def parse_trust_root(data: bytes) -> TrustRoot:
    if len(data) > MAX_TRUST_ROOT_BYTES:
        raise TrustRootError("trust root exceeds size limit")
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustRootError(f"trust root is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise TrustRootError("trust root must be an object with version 1")
    root = TrustRoot(name=str(doc.get("name", "trust root"))[:200],
                     digest="sha256:" + hashlib.sha256(data).hexdigest())
    for k in doc.get("keys", []):
        try:
            pub = base64.b64decode(k["public_key"], validate=True)
            if len(pub) != 32:
                raise TrustRootError(f"key {k.get('key_id')!r}: Ed25519 public keys are 32 bytes")
            kid = k.get("key_id") or key_id_for(pub)
            if kid != key_id_for(pub):
                raise TrustRootError(f"key id {kid!r} does not match its public key")
            root.keys[kid] = TrustedKey(kid, pub, tuple(k.get("roles", [])), _ts(k.get("not_before")),
                                        _ts(k.get("not_after")), bool(k.get("revoked", False)),
                                        str(k.get("comment", ""))[:200])
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, TrustRootError):
                raise
            raise TrustRootError(f"malformed key entry: {exc}") from exc
    for m in doc.get("approved_models", []):
        if not isinstance(m, dict) or not str(m.get("artifact_digest", "")).startswith("sha256:"):
            raise TrustRootError("approved model entries need an artifact_digest")
        root.approved_models.append(ApprovedModel(
            name=str(m.get("name", "approved"))[:200], artifact_digest=m["artifact_digest"],
            param_digest=m.get("param_digest"), preprocess_digest=m.get("preprocess_digest"),
            architecture_digest=m.get("architecture_digest"), approved_by=m.get("approved_by"),
            approved_at=m.get("approved_at")))
    return root


def load_trust_root(path: Path) -> TrustRoot:
    return parse_trust_root(Path(path).read_bytes()[: MAX_TRUST_ROOT_BYTES + 1])


def build_trust_root_document(name: str, keys: list[dict], approved_models: list[dict]) -> dict:
    return {"version": 1, "name": name, "keys": keys, "approved_models": approved_models}
