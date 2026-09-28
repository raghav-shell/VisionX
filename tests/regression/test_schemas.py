"""Committed JSON Schemas match the code; ledger records validate against the ledger schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from visionsentinel.provenance.keys import generate_key, trust_entry
from visionsentinel.provenance.ledger import LedgerWriter
from visionsentinel.provenance.trust import build_trust_root_document
from visionsentinel.reporting.schemas import LEDGER_RECORD_SCHEMA, TRUST_ROOT_SCHEMA, export_schemas

ROOT = Path(__file__).resolve().parents[2]


def test_committed_schemas_are_up_to_date(tmp_path):
    for p in export_schemas(tmp_path):
        committed = ROOT / "schemas" / p.name
        assert committed.exists(), f"schemas/{p.name} missing — run 'visionsentinel schemas'"
        assert json.loads(committed.read_text()) == json.loads(p.read_text()), f"schemas/{p.name} is stale"


def test_ledger_records_and_trust_roots_validate(tmp_path):
    key = generate_key()
    w = LedgerWriter(tmp_path / "l.jsonl", key, checkpoint_every=2, purpose="audit")
    for i in range(5):
        w.append("audit", {"action": "test", "n": i})
    for line in (tmp_path / "l.jsonl").read_text().splitlines():
        jsonschema.validate(json.loads(line), LEDGER_RECORD_SCHEMA)
    jsonschema.validate(build_trust_root_document("t", [trust_entry(key, ["audit"])], []), TRUST_ROOT_SCHEMA)
