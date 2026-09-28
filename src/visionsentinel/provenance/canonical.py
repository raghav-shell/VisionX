"""Canonical JSON for signed payloads (RFC 8785 / JCS-compatible subset). Standard library only.

Objects with keys sorted by UTF-16 code units, no insignificant whitespace, UTF-8, strings escaped as JCS
requires. Floating-point numbers are *rejected* (design correction DC-6): their textual form differs across
languages, which would make independent verification brittle. Scores are carried as decimal strings.
"""

from __future__ import annotations

import hashlib
from typing import Any

LEDGER_DOMAIN = b"visionsentinel/ledger/v1\x00"
ENTRY_DOMAIN = b"visionsentinel/entry/v1\x00"
ANCHOR_DOMAIN = b"visionsentinel/anchor/v1\x00"
MAX_SAFE_INT = 2**53 - 1


class CanonicalError(ValueError):
    pass


def _string(s: str) -> str:
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20:
            out.append(f"\\u{o:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _encode(value: Any, depth: int) -> str:
    if depth > 32:
        raise CanonicalError("nesting too deep")
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INT:
            raise CanonicalError("integer outside the IEEE-754 safe range")
        return str(value)
    if isinstance(value, float):
        raise CanonicalError("floats are not allowed in signed payloads; use decimal strings")
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(v, depth + 1) for v in value) + "]"
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise CanonicalError("object keys must be strings")
        keys = sorted(value, key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(_string(k) + ":" + _encode(value[k], depth + 1) for k in keys) + "}"
    raise CanonicalError(f"type {type(value).__name__} is not allowed in signed payloads")


def canonical_bytes(value: Any) -> bytes:
    return _encode(value, 0).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signing_message(record: dict) -> bytes:
    unsigned = {k: v for k, v in record.items() if k != "sig"}
    return LEDGER_DOMAIN + canonical_bytes(unsigned)


def entry_hash(record: dict) -> str:
    return "sha256:" + sha256_hex(ENTRY_DOMAIN + canonical_bytes(record))


def anchor_message(anchor: dict) -> bytes:
    return ANCHOR_DOMAIN + canonical_bytes({k: v for k, v in anchor.items() if k != "sig"})
