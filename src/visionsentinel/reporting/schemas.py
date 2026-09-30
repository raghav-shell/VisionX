"""JSON Schema export: domain contracts (generated from the Pydantic models) plus ledger and trust-root formats."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import Finding, ScanResult
from ..core.profiles import Profile

LEDGER_RECORD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "visionsentinel/ledger-record/v1",
    "title": "VisionSentinel ledger record",
    "type": "object",
    "additionalProperties": False,
    "required": ["v", "ledger", "seq", "prev", "ts", "nonce", "kind", "body", "key_id", "sig"],
    "properties": {
        "v": {"const": 1},
        "ledger": {"type": "string", "maxLength": 128},
        "seq": {"type": "integer", "minimum": 0},
        "prev": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
        "ts": {"type": "string", "format": "date-time"},
        "nonce": {"type": "string", "pattern": "^[A-Za-z0-9_-]{22}$"},
        "kind": {"enum": ["header", "inference", "checkpoint", "audit"]},
        "body": {"type": "object"},
        "key_id": {"type": "string", "pattern": "^ed25519:[0-9a-f]{16}$"},
        "sig": {"type": "string", "pattern": "^[A-Za-z0-9_-]{86}$"},
    },
}

TRUST_ROOT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "visionsentinel/trust-root/v1",
    "title": "VisionSentinel trust root",
    "type": "object",
    "required": ["version", "keys"],
    "properties": {
        "version": {"const": 1},
        "name": {"type": "string"},
        "keys": {"type": "array", "items": {
            "type": "object", "required": ["public_key", "roles"],
            "properties": {"key_id": {"type": "string"}, "public_key": {"type": "string"},
                           "roles": {"type": "array", "items": {"enum": ["ledger", "audit", "anchor", "report"]}},
                           "not_before": {"type": ["string", "null"]}, "not_after": {"type": ["string", "null"]},
                           "revoked": {"type": "boolean"}, "comment": {"type": "string"}}}},
        "approved_models": {"type": "array", "items": {
            "type": "object", "required": ["artifact_digest"],
            "properties": {k: {"type": ["string", "null"]} for k in
                           ("name", "artifact_digest", "param_digest", "preprocess_digest", "architecture_digest",
                            "approved_by", "approved_at")}}},
    },
}


def export_schemas(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    docs = {"finding.schema.json": Finding.model_json_schema(),
            "scan-result.schema.json": ScanResult.model_json_schema(),
            "profile.schema.json": Profile.model_json_schema(),
            "ledger-record.schema.json": LEDGER_RECORD_SCHEMA,
            "trust-root.schema.json": TRUST_ROOT_SCHEMA}
    paths = []
    for name, doc in docs.items():
        p = out / name
        p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(p)
    return paths
