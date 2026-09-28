"""Ed25519 key handling (standard ``cryptography`` primitives only; no custom cryptography)."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .trust import key_id_for


def generate_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def public_bytes(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(key: Ed25519PrivateKey) -> str:
    return key_id_for(public_bytes(key))


def save_private_key(key: Ed25519PrivateKey, path: Path, passphrase: bytes | None = None) -> Path:
    enc = (serialization.BestAvailableEncryption(passphrase) if passphrase else serialization.NoEncryption())
    data = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, enc)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return path


def load_private_key(path: Path, passphrase: bytes | None = None) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=passphrase)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"{path} is not an Ed25519 private key")
    return key


def trust_entry(key: Ed25519PrivateKey, roles: list[str], comment: str = "") -> dict:
    return {"key_id": key_id(key), "public_key": base64.b64encode(public_bytes(key)).decode(), "roles": roles,
            "not_before": datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat(), "not_after": None, "revoked": False,
            "comment": comment}


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
