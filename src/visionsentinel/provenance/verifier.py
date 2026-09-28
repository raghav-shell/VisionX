"""Independent ledger verifier. Depends only on the standard library and ``cryptography``.

    python -m visionsentinel.provenance.verifier ledger.jsonl --trust-root trust.json [--anchor anchors.jsonl]
                                                  [--inputs DIR] [--json]

For every line it reports VALID, FAILED (with the reason) or UNTRUSTED (the record's own signature may be
fine, but chain continuity from the genesis record was lost earlier). It detects edits, deletions, reordering,
replays, unknown/revoked keys, corrupted signatures, in-ledger checkpoint mismatches, truncation and history
rewriting against external anchors, unapproved model/preprocessing bindings and replaced inputs.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical import CanonicalError, anchor_message, entry_hash, signing_message
from .merkle import root_hex
from .trust import TrustRoot, TrustRootError, load_trust_root

GENESIS_PREV = "sha256:" + "0" * 64
MAX_LINE = 1 << 20
REQUIRED = ("v", "ledger", "seq", "prev", "ts", "nonce", "kind", "body", "key_id", "sig")


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@dataclass
class RecordStatus:
    line: int
    seq: int | None
    kind: str | None
    status: str  # VALID | FAILED | UNTRUSTED
    reasons: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    entry_hash: str | None = None
    key_id: str | None = None
    ts: str | None = None
    body: dict | None = None


@dataclass
class VerificationReport:
    ledger: str
    ledger_id: str | None
    trust_root: str
    verified_at: str
    records: list[RecordStatus] = field(default_factory=list)
    gaps: list[list[int]] = field(default_factory=list)
    replays: list[dict] = field(default_factory=list)
    checkpoints: list[dict] = field(default_factory=list)
    anchors: list[dict] = field(default_factory=list)
    bindings: list[dict] = field(default_factory=list)
    truncated: bool = False
    rewritten: bool = False
    first_break: int | None = None

    @property
    def counts(self) -> dict[str, int]:
        out = {"VALID": 0, "FAILED": 0, "UNTRUSTED": 0}
        for r in self.records:
            out[r.status] += 1
        return out

    @property
    def intact(self) -> bool:
        c = self.counts
        return (c["FAILED"] == 0 and c["UNTRUSTED"] == 0 and not self.truncated and not self.rewritten
                and not self.gaps and not self.replays and all(cp["consistent"] for cp in self.checkpoints)
                and all(a["status"] == "CONSISTENT" for a in self.anchors))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["counts"] = self.counts
        d["intact"] = self.intact
        for r in d["records"]:
            r.pop("body", None)
        return d


def _verify_sig(pub: bytes, message: bytes, sig: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(b64d(sig), message)
        return True
    except (InvalidSignature, ValueError):
        return False


def _ts(value: str) -> datetime | None:
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _check_key(trust: TrustRoot, key_id: str, role: str, when: datetime | None) -> tuple[bytes | None, str | None]:
    key = trust.keys.get(key_id)
    if key is None:
        return None, f"signed by unknown key {key_id}"
    if key.revoked:
        return None, f"signed by revoked key {key_id}"
    if role not in key.roles:
        return None, f"key {key_id} is not authorised for role '{role}'"
    if when is not None and not key.valid_at(when):
        return None, f"key {key_id} was not valid at {when.isoformat()}"
    return key.public_key, None


def verify_ledger(ledger: Path, trust: TrustRoot, *, anchors: Path | None = None, inputs: Path | None = None,
                  role: str | None = None) -> VerificationReport:
    report = VerificationReport(ledger=str(ledger), ledger_id=None, trust_root=trust.digest,
                                verified_at=datetime.now(timezone.utc).isoformat())
    lines = Path(ledger).read_bytes().split(b"\n")
    parsed: list[tuple[int, dict | None, str | None]] = []
    for n, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        if len(raw) > MAX_LINE:
            parsed.append((n, None, "line exceeds size limit"))
            continue
        try:
            rec = json.loads(raw.decode("utf-8"))
            if not isinstance(rec, dict) or any(k not in rec for k in REQUIRED):
                raise ValueError("missing required fields")
            parsed.append((n, rec, None))
        except (ValueError, UnicodeDecodeError) as exc:
            parsed.append((n, None, f"unparseable record: {exc}"))

    seen_seq: dict[int, str] = {}
    seen_nonce: dict[str, int] = {}
    seen_entry: dict[str, int] = {}
    chain: list[str] = []          # entry hashes of the continuous verified chain (index = seq)
    trusted_tip = GENESIS_PREV
    expected_seq = 0
    broken_at: int | None = None
    ledger_role = role

    for line, rec, err in parsed:
        if rec is None:
            report.records.append(RecordStatus(line, None, None, "FAILED", [err or "unparseable"], ["record_modification"]))
            broken_at = broken_at if broken_at is not None else -1
            continue
        seq = rec.get("seq") if isinstance(rec.get("seq"), int) else None
        st = RecordStatus(line, seq, rec.get("kind"), "VALID", key_id=rec.get("key_id"), ts=rec.get("ts"),
                          body=rec.get("body") if isinstance(rec.get("body"), dict) else None)
        if report.ledger_id is None:
            report.ledger_id = rec.get("ledger")
        elif rec.get("ledger") != report.ledger_id:
            st.reasons.append(f"belongs to ledger {rec.get('ledger')!r}, not {report.ledger_id!r}")
            st.classes.append("record_replay")
        if ledger_role is None and rec.get("kind") == "header" and isinstance(rec.get("body"), dict):
            ledger_role = rec["body"].get("purpose", "ledger")
        try:
            eh = entry_hash(rec)
            msg = signing_message(rec)
        except CanonicalError as exc:
            st.status, st.reasons = "FAILED", [f"not canonicalisable: {exc}"]
            st.classes.append("record_modification")
            report.records.append(st)
            broken_at = broken_at if broken_at is not None else (seq if seq is not None else -1)
            continue
        st.entry_hash = eh
        pub, key_err = _check_key(trust, str(rec.get("key_id")), "audit" if ledger_role == "audit" else "ledger",
                                  _ts(str(rec.get("ts"))))
        if key_err:
            st.reasons.append(key_err)
            st.classes.append("signature_forgery")
        elif not _verify_sig(pub, msg, str(rec.get("sig"))):
            st.reasons.append("signature does not verify: the record was altered or its signature corrupted")
            st.classes.append("record_modification")
        # replay: an entry, sequence number or nonce seen before
        if eh in seen_entry:
            st.reasons.append(f"exact replay of the record at line {seen_entry[eh]}")
            st.classes.append("record_replay")
            report.replays.append({"line": line, "seq": seq, "original_line": seen_entry[eh]})
        elif str(rec.get("nonce")) in seen_nonce:
            st.reasons.append(f"nonce reused from line {seen_nonce[str(rec.get('nonce'))]}")
            st.classes.append("record_replay")
            report.replays.append({"line": line, "seq": seq, "original_line": seen_nonce[str(rec.get("nonce"))]})
        elif seq is not None and seq in seen_seq:
            st.reasons.append(f"sequence number {seq} already used")
            st.classes.append("record_replay")
            report.replays.append({"line": line, "seq": seq})
        seen_entry.setdefault(eh, line)
        seen_nonce.setdefault(str(rec.get("nonce")), line)
        replay = "record_replay" in st.classes
        # ordering / continuity (a replayed duplicate is judged on its own and does not move the chain)
        if seq is None:
            st.reasons.append("missing or non-integer sequence number")
            st.classes.append("record_modification")
        elif not replay and seq > expected_seq:
            st.reasons.append(f"sequence gap: record(s) {expected_seq}–{seq - 1} missing before this one")
            st.classes.append("record_deletion")
            report.gaps.append([expected_seq, seq - 1])
        elif not replay and seq < expected_seq:
            st.reasons.append(f"out of order: sequence {seq} appears after {expected_seq - 1}")
            st.classes.append("record_reorder")
        prev_ok = rec.get("prev") == trusted_tip
        if not prev_ok and not replay and broken_at is None:
            st.reasons.append(f"previous hash does not match record {expected_seq - 1}")
            if not st.classes:
                st.classes.append("record_modification" if seq == expected_seq else "record_reorder")
        if st.classes:
            st.status = "FAILED"
            if broken_at is None and not (replay and len(set(st.classes)) == 1):
                broken_at = seq if seq is not None else -1
        elif broken_at is not None:
            st.status = "UNTRUSTED"
            st.reasons.append(
                f"cannot be trusted because chain continuity was lost at sequence {broken_at}" if not prev_ok else
                f"links correctly to its predecessor, but continuity from genesis was lost at sequence {broken_at}")
        if not replay and seq is not None and seq >= expected_seq:
            seen_seq.setdefault(seq, eh)
            if st.status == "VALID":
                chain.append(eh)
            trusted_tip = eh
            expected_seq = seq + 1
        elif not replay and seq is not None:
            seen_seq.setdefault(seq, eh)
        report.records.append(st)
        if rec.get("kind") == "checkpoint" and isinstance(rec.get("body"), dict):
            size = rec["body"].get("tree_size")
            ordered = [seen_seq.get(i) for i in range(size)] if isinstance(size, int) else []
            ok = bool(ordered) and all(ordered) and root_hex(ordered) == rec["body"].get("root")
            report.checkpoints.append({"line": line, "seq": seq, "tree_size": size, "consistent": ok,
                                       "root": rec["body"].get("root")})
            if not ok:
                report.rewritten = True
                st.status = "FAILED" if st.status == "VALID" else st.status
                st.reasons.append("checkpoint root does not match the Merkle root of the preceding history")

    # A "gap" whose records turn up later in the file is a reordering, not a deletion.
    real_gaps = []
    for lo, hi in report.gaps:
        if all(i in seen_seq for i in range(lo, hi + 1)):
            for st in report.records:
                if "record_deletion" in st.classes and st.seq == hi + 1:
                    st.classes = ["record_reorder" if c == "record_deletion" else c for c in st.classes]
                    st.reasons = [f"out of order: record(s) {lo}–{hi} appear later in the file" if r.startswith(
                        "sequence gap") else r for r in st.reasons]
        else:
            real_gaps.append([lo, hi])
    report.gaps = real_gaps
    report.first_break = broken_at
    all_hashes = [seen_seq[i] for i in sorted(seen_seq)]
    if anchors is not None:
        for n, raw in enumerate(Path(anchors).read_bytes().split(b"\n"), start=1):
            if not raw.strip():
                continue
            try:
                a = json.loads(raw.decode("utf-8"))
                size = int(a["tree_size"])
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                report.anchors.append({"line": n, "status": "UNPARSEABLE"})
                continue
            if a.get("ledger") != report.ledger_id:
                continue
            pub, key_err = _check_key(trust, str(a.get("key_id")), "anchor", _ts(str(a.get("ts"))))
            if key_err or not _verify_sig(pub, anchor_message(a), str(a.get("sig"))):
                report.anchors.append({"line": n, "tree_size": size, "status": "INVALID_SIGNATURE",
                                       "detail": key_err or "anchor signature does not verify"})
                continue
            prefix = [seen_seq.get(i) for i in range(size)]
            if size > len(all_hashes) or not all(prefix):
                report.truncated = True
                report.anchors.append({"line": n, "tree_size": size, "status": "TRUNCATED",
                                       "detail": f"anchor covers {size} records; the ledger holds {len(all_hashes)}"})
            elif root_hex(prefix) != a.get("root"):
                report.rewritten = True
                report.anchors.append({"line": n, "tree_size": size, "status": "MISMATCH",
                                       "detail": "history differs from the externally anchored Merkle root"})
            else:
                report.anchors.append({"line": n, "tree_size": size, "status": "CONSISTENT", "root": a.get("root")})

    # bindings: approved model / preprocessing, and raw inputs when supplied
    approved = {m.artifact_digest for m in trust.approved_models}
    approved_pre = trust.approved_preprocess()
    index: dict[str, Path] = {}
    if inputs is not None:
        for p in sorted(Path(inputs).rglob("*")):
            if p.is_file() and p.stat().st_size <= 64 * 1024 * 1024:
                index[p.name] = p
    for st in report.records:
        body = st.body or {}
        if st.kind != "inference":
            continue
        issues = []
        if approved and body.get("model_digest") not in approved:
            issues.append(("model_binding_violation", f"model {str(body.get('model_digest'))[:19]}… is not approved"))
        if approved_pre and body.get("preprocess_digest") not in approved_pre:
            issues.append(("config_binding_violation",
                           f"preprocessing {str(body.get('preprocess_digest'))[:19]}… is not approved"))
        ref = body.get("input_ref")
        if index and isinstance(ref, str):
            p = index.get(Path(ref).name)
            if p is None:
                issues.append(("input_substitution", f"input {ref!r} not found"))
            elif "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest() != body.get("input_digest"):
                issues.append(("input_substitution", f"input {ref!r} no longer matches its recorded digest"))
        for cls, detail in issues:
            report.bindings.append({"line": st.line, "seq": st.seq, "class": cls, "detail": detail,
                                    "record_status": st.status})
    return report


def render_text(report: VerificationReport) -> str:
    out = [f"ledger      {report.ledger}", f"ledger id   {report.ledger_id}", f"trust root  {report.trust_root}", ""]
    for r in report.records:
        label = f"Record {r.seq}" if r.seq is not None else f"Line {r.line}"
        if r.status == "VALID":
            out.append(f"{label}: signature valid, chain intact")
        else:
            out.append(f"{label}: {r.status}")
            out.extend(f"    {reason}" for reason in r.reasons)
    for cp in report.checkpoints:
        out.append(f"checkpoint @ seq {cp['seq']} (tree size {cp['tree_size']}): "
                   f"{'consistent' if cp['consistent'] else 'INCONSISTENT'}")
    for a in report.anchors:
        out.append(f"anchor line {a['line']}: {a['status']}" + (f" — {a['detail']}" if a.get("detail") else ""))
    for b in report.bindings:
        out.append(f"binding (record {b['seq']}): {b['class']} — {b['detail']}")
    c = report.counts
    out.append("")
    out.append(f"{c['VALID']} valid · {c['FAILED']} failed · {c['UNTRUSTED']} untrusted · "
               f"{'LEDGER INTACT' if report.intact else 'LEDGER INTEGRITY FAILED'}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="visionsentinel-verify", description="Verify a VisionSentinel ledger.")
    ap.add_argument("ledger", type=Path)
    ap.add_argument("--trust-root", type=Path, required=True)
    ap.add_argument("--anchor", type=Path)
    ap.add_argument("--inputs", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        trust = load_trust_root(args.trust_root)
    except (TrustRootError, OSError) as exc:
        print(f"error: trust root: {exc}", file=sys.stderr)
        return 2
    if not args.ledger.is_file():
        print(f"error: ledger {args.ledger} not found", file=sys.stderr)
        return 2
    report = verify_ledger(args.ledger, trust, anchors=args.anchor, inputs=args.inputs)
    print(json.dumps(report.to_dict(), indent=1) if args.json else render_text(report))
    return 0 if report.intact and not report.bindings else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
