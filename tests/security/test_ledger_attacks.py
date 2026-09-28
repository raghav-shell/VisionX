"""Ledger tampering: every attack in the threat model must be detected and reported precisely."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from visionsentinel.provenance.canonical import CanonicalError, canonical_bytes, signing_message
from visionsentinel.provenance.inference import InferenceRecorder
from visionsentinel.provenance.keys import b64u, generate_key, trust_entry
from visionsentinel.provenance.ledger import LedgerWriter
from visionsentinel.provenance.merkle import inclusion_proof, leaf_hash, merkle_root, verify_inclusion
from visionsentinel.provenance.trust import build_trust_root_document, parse_trust_root
from visionsentinel.provenance.verifier import main as verify_main
from visionsentinel.provenance.verifier import verify_ledger

APPROVED_MODEL = "sha256:" + "a" * 64


class FakeModel:
    artifact_digest = APPROVED_MODEL
    class_names = ["tank", "truck", "car"]

    class cfg:  # noqa: N801 - mimics PreprocessConfig
        digest = "sha256:" + "b" * 64

    def predict_proba(self, images):
        s = images.reshape(len(images), -1).mean(1, keepdims=True) / 255.0
        return np.hstack([s, 1 - s, np.full_like(s, 0.1)]) / 1.1


@pytest.fixture()
def ledger(tmp_path):
    key = generate_key()
    doc = build_trust_root_document("test", [trust_entry(key, ["ledger", "anchor"])],
                                    [{"name": "m", "artifact_digest": APPROVED_MODEL,
                                      "preprocess_digest": FakeModel.cfg.digest}])
    (tmp_path / "trust.json").write_text(json.dumps(doc))
    writer = LedgerWriter(tmp_path / "ledger.jsonl", key, checkpoint_every=16, anchor_path=tmp_path / "anchors.jsonl")
    rec = InferenceRecorder(FakeModel(), writer)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    rng = np.random.default_rng(0)
    for i in range(50):
        data = rng.integers(0, 255, 64, dtype=np.uint8).tobytes()
        (inputs / f"in-{i:03d}.bin").write_bytes(data)
        rec.record(data, f"in-{i:03d}.bin", np.frombuffer(data, np.uint8).reshape(4, 4, 4)[..., :3].copy())
    writer.checkpoint()
    trust = parse_trust_root((tmp_path / "trust.json").read_bytes())
    return {"path": tmp_path / "ledger.jsonl", "trust": trust, "anchors": tmp_path / "anchors.jsonl", "key": key,
            "inputs": inputs, "root": tmp_path}


def _lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def _write(path: Path, recs: list[dict]) -> None:
    path.write_bytes(b"".join(canonical_bytes(r) + b"\n" for r in recs))


def _status(report) -> dict[int, str]:
    return {r.seq: r.status for r in report.records}


def test_intact_ledger_verifies_completely(ledger):
    rep = verify_ledger(ledger["path"], ledger["trust"], anchors=ledger["anchors"], inputs=ledger["inputs"])
    assert rep.intact and not rep.bindings
    assert set(_status(rep).values()) == {"VALID"}
    assert rep.checkpoints and all(c["consistent"] for c in rep.checkpoints)
    assert rep.anchors and all(a["status"] == "CONSISTENT" for a in rep.anchors)


def test_modified_record_fails_and_breaks_continuity(ledger):
    recs = _lines(ledger["path"])
    target = next(r for r in recs if r["seq"] == 20)
    target["body"]["output"]["label"] = "car"
    _write(ledger["path"], recs)
    rep = verify_ledger(ledger["path"], ledger["trust"], anchors=ledger["anchors"])
    st = _status(rep)
    assert st[20] == "FAILED" and all(st[s] == "VALID" for s in range(20))
    assert st[21] == "UNTRUSTED" and st[max(st)] == "UNTRUSTED"
    failed = next(r for r in rep.records if r.seq == 20)
    assert "record_modification" in failed.classes and "signature does not verify" in failed.reasons[0]
    assert "continuity was lost at sequence 20" in next(r for r in rep.records if r.seq == 21).reasons[0]
    assert rep.rewritten and not rep.intact


def test_deleted_record_is_a_gap_with_broken_link(ledger):
    recs = [r for r in _lines(ledger["path"]) if r["seq"] != 20]
    _write(ledger["path"], recs)
    rep = verify_ledger(ledger["path"], ledger["trust"])
    rec21 = next(r for r in rep.records if r.seq == 21)
    assert rec21.status == "FAILED" and "record_deletion" in rec21.classes
    assert any("previous hash does not match record 19" in x for x in rec21.reasons)
    assert rep.gaps == [[20, 20]]
    assert _status(rep)[22] == "UNTRUSTED"


def test_reordered_records_are_reported_as_reordering_not_deletion(ledger):
    recs = _lines(ledger["path"])
    i = next(k for k, r in enumerate(recs) if r["seq"] == 20)
    recs[i], recs[i + 1] = recs[i + 1], recs[i]
    _write(ledger["path"], recs)
    rep = verify_ledger(ledger["path"], ledger["trust"])
    assert not rep.gaps
    for seq in (20, 21):
        r = next(x for x in rep.records if x.seq == seq)
        assert r.status == "FAILED" and "record_reorder" in r.classes


def test_replayed_record_is_detected_without_tainting_the_authentic_chain(ledger):
    recs = _lines(ledger["path"])
    recs.append(dict(next(r for r in recs if r["seq"] == 10)))
    _write(ledger["path"], recs)
    rep = verify_ledger(ledger["path"], ledger["trust"])
    replay = rep.records[-1]
    assert replay.status == "FAILED" and replay.classes == ["record_replay"]
    assert "exact replay" in replay.reasons[0]
    assert all(r.status == "VALID" for r in rep.records[:-1])
    assert rep.replays and not rep.intact


def test_truncation_is_invisible_to_the_chain_but_caught_by_the_anchor(ledger):
    recs = _lines(ledger["path"])
    _write(ledger["path"], recs[:-10])
    chain_only = verify_ledger(ledger["path"], ledger["trust"])
    assert chain_only.intact, "tail truncation leaves a valid chain; only an external anchor can reveal it"
    anchored = verify_ledger(ledger["path"], ledger["trust"], anchors=ledger["anchors"])
    assert anchored.truncated and not anchored.intact
    assert any(a["status"] == "TRUNCATED" for a in anchored.anchors)


def test_key_holder_rewriting_history_is_caught_by_the_external_anchor(ledger):
    from visionsentinel.provenance.canonical import entry_hash
    recs = _lines(ledger["path"])
    prev = None
    for r in recs:
        if r["seq"] == 20:
            r["body"]["output"]["label"] = "car"
        if prev is not None and r["seq"] >= 20:
            r["prev"] = prev
        if r["seq"] >= 20:
            r["sig"] = b64u(ledger["key"].sign(signing_message(r)))
        prev = entry_hash(r)
    # the insider also drops in-ledger checkpoints that would contradict the rewrite
    recs = [r for r in recs if r["kind"] != "checkpoint" or r["seq"] < 20]
    for k in range(1, len(recs)):
        recs[k]["seq"] = k
        recs[k]["prev"] = entry_hash(recs[k - 1])
        recs[k]["sig"] = b64u(ledger["key"].sign(signing_message(recs[k])))
    _write(ledger["path"], recs)
    rep = verify_ledger(ledger["path"], ledger["trust"])
    assert all(r.status == "VALID" for r in rep.records), "a key holder can produce a self-consistent chain"
    rep = verify_ledger(ledger["path"], ledger["trust"], anchors=ledger["anchors"])
    assert (rep.rewritten or rep.truncated) and not rep.intact


def test_corrupted_signature_fails(ledger):
    recs = _lines(ledger["path"])
    r = next(x for x in recs if x["seq"] == 5)
    sig = bytearray(base64.urlsafe_b64decode(r["sig"] + "=="))
    sig[0] ^= 0x01
    r["sig"] = b64u(bytes(sig))
    _write(ledger["path"], recs)
    rep = verify_ledger(ledger["path"], ledger["trust"])
    assert _status(rep)[5] == "FAILED" and _status(rep)[6] == "UNTRUSTED"


def test_record_signed_by_unknown_key_is_forgery(ledger):
    recs = _lines(ledger["path"])
    r = next(x for x in recs if x["seq"] == 7)
    attacker = generate_key()
    r["key_id"] = trust_entry(attacker, ["ledger"])["key_id"]
    r["sig"] = b64u(attacker.sign(signing_message(r)))
    _write(ledger["path"], recs)
    rep = verify_ledger(ledger["path"], ledger["trust"])
    rec = next(x for x in rep.records if x.seq == 7)
    assert rec.status == "FAILED" and "signature_forgery" in rec.classes and "unknown key" in rec.reasons[0]


def test_revoked_key_invalidates_its_records(ledger, tmp_path):
    doc = json.loads((ledger["root"] / "trust.json").read_text())
    doc["keys"][0]["revoked"] = True
    trust = parse_trust_root(json.dumps(doc).encode())
    rep = verify_ledger(ledger["path"], trust)
    assert all(r.status == "FAILED" and "revoked" in r.reasons[0] for r in rep.records[:1])


def test_unapproved_model_is_a_binding_violation_even_when_validly_signed(ledger):
    writer = LedgerWriter(ledger["path"], ledger["key"], checkpoint_every=0)
    body = dict(_lines(ledger["path"])[1]["body"])
    body["model_digest"] = "sha256:" + "c" * 64
    writer.append("inference", body)
    rep = verify_ledger(ledger["path"], ledger["trust"])
    assert rep.records[-1].status == "VALID"
    assert [b["class"] for b in rep.bindings] == ["model_binding_violation"]


def test_replaced_input_is_detected(ledger):
    (ledger["inputs"] / "in-004.bin").write_bytes(b"\x00" * 64)
    rep = verify_ledger(ledger["path"], ledger["trust"], inputs=ledger["inputs"])
    assert [b["class"] for b in rep.bindings] == ["input_substitution"]
    assert "in-004.bin" in rep.bindings[0]["detail"]


def test_cli_exit_codes_and_report_text(ledger, capsys):
    args = [str(ledger["path"]), "--trust-root", str(ledger["root"] / "trust.json"), "--anchor", str(ledger["anchors"])]
    assert verify_main(args) == 0
    assert "LEDGER INTACT" in capsys.readouterr().out
    recs = _lines(ledger["path"])
    recs[3]["body"]["output"]["label"] = "tank"
    _write(ledger["path"], recs)
    assert verify_main(args) == 1
    out = capsys.readouterr().out
    assert "Record 3: FAILED" in out and "Record 4: UNTRUSTED" in out


def test_canonical_form_rejects_floats_and_is_order_independent():
    assert canonical_bytes({"b": 1, "a": [True, None, "x"]}) == canonical_bytes({"a": [True, None, "x"], "b": 1})
    assert canonical_bytes({"a": "é\n\u0001"}) == '{"a":"é\\n\\u0001"}'.encode()
    with pytest.raises(CanonicalError):
        canonical_bytes({"score": 0.5})
    with pytest.raises(CanonicalError):
        canonical_bytes({"n": 2**60})


@pytest.mark.parametrize("n", [1, 2, 3, 7, 16, 33])
def test_merkle_inclusion_proofs(n):
    leaves = [f"leaf-{i}".encode() for i in range(n)]
    root = merkle_root(leaves)
    assert (n != 1) or root == leaf_hash(leaves[0])
    for i in range(n):
        assert verify_inclusion(leaves[i], i, n, inclusion_proof(i, leaves), root)
    assert not verify_inclusion(b"forged", 0, n, inclusion_proof(0, leaves), root)


def test_verifier_runs_without_pydantic_numpy_or_the_dashboard(ledger):
    code = ("import sys\n"
            "for m in ('pydantic','numpy','fastapi','sqlalchemy','PIL','torch','onnx'): sys.modules[m] = None\n"
            "from visionsentinel.provenance.verifier import main\n"
            f"raise SystemExit(main([{str(ledger['path'])!r}, '--trust-root', {str(ledger['root'] / 'trust.json')!r}]))\n")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)  # noqa: S603
    assert proc.returncode == 0, proc.stderr
    assert "LEDGER INTACT" in proc.stdout
