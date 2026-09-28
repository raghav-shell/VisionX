"""Provenance detectors: ledger integrity and inference bindings (wrapping the standalone verifier)."""

from __future__ import annotations

from collections import defaultdict

from ..contracts import (
    AssetType,
    AttackSupport,
    CalibrationRequirement,
    Capability,
    DetectorMode,
    DetectorSpec,
    Evidence,
    EvidenceKind,
    Layer,
    ProposedFinding,
    RuntimeClass,
    SampleRef,
    Severity,
    SupportLevel,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult
from .verifier import VerificationReport, verify_ledger

PROV_ASSUMPTIONS = ["The trust root (public keys, approved bindings) is authentic and was obtained out of band.",
                    "Private signing keys have not been compromised (see the unsupported 'signing-key compromise' class)."]

CLASS_TEXT = {
    "record_modification": ("record(s) fail signature or hash-chain verification", "altered after signing"),
    "record_deletion": ("record(s) missing from the sequence", "deleted"),
    "record_reorder": ("record(s) out of order", "reordered"),
    "record_replay": ("duplicated / replayed record(s)", "replayed"),
    "signature_forgery": ("record(s) signed by an unknown, revoked or unauthorised key", "forged"),
}


def ledger_report(ctx: DetectorContext) -> VerificationReport:
    if "ledger_report" not in ctx.shared:
        ctx.shared["ledger_report"] = verify_ledger(ctx.asset("ledger_path"), ctx.asset("trust_root"),
                                                    anchors=ctx.optional_asset("anchor_path"),
                                                    inputs=ctx.optional_asset("inference_inputs_path"))
    return ctx.shared["ledger_report"]


def _crypto_evidence(ctx: DetectorContext, title: str, summary: str, rows: list[list]) -> Evidence:
    return Evidence(id=ctx.evidence_id(title), kind=EvidenceKind.CRYPTO_CHECK, title=title, summary=summary,
                    data={"columns": ["line", "sequence", "status", "reasons", "entry hash", "key"], "rows": rows[:300],
                          "truncated": max(0, len(rows) - 300)})


class LedgerIntegrity(Detector):
    spec = DetectorSpec(
        id="provenance.ledger_integrity", version="1.0.0", title="Inference ledger integrity", layer=Layer.PROVENANCE,
        summary="Verifies every record's Ed25519 signature, the SHA-256 hash chain, sequence continuity, nonces, "
                "in-ledger Merkle checkpoints and — when supplied — externally held anchors.",
        required=[Capability.INFERENCE_LEDGER, Capability.LEDGER_TRUST_ROOT], optional=[Capability.LEDGER_ANCHOR],
        modes=[DetectorMode(name="anchored", description="chain, checkpoints and external anchors",
                            needs=[Capability.LEDGER_ANCHOR]),
               DetectorMode(name="chain-only", description="chain and in-ledger checkpoints (tail truncation invisible)",
                            degraded=True, support_override=[
                                AttackSupport(attack_class=c, level=SupportLevel.FULL) for c in
                                ("record_modification", "record_deletion", "record_reorder", "record_replay",
                                 "signature_forgery")])],
        supports=[AttackSupport(attack_class=c, level=SupportLevel.FULL) for c in
                  ("record_modification", "record_deletion", "record_reorder", "record_replay", "record_truncation",
                   "signature_forgery")],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.CRYPTO_CHECK, EvidenceKind.GRAPH],
        limitations=["Without an external anchor, removing records from the end of the ledger cannot be detected.",
                     "Anyone holding the signing key can write new, valid records; anchors bound the damage."],
        access_assumptions=PROV_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
        references=["RFC 8032 (Ed25519)", "RFC 6962 (Merkle hash trees)", "RFC 8785 (JSON canonicalisation)"],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        rep = ledger_report(ctx)
        res = DetectorResult(samples_processed=len(rep.records))
        chain = [{"line": r.line, "seq": r.seq, "kind": r.kind, "status": r.status, "reasons": r.reasons,
                  "entry_hash": r.entry_hash, "key_id": r.key_id, "ts": r.ts,
                  "body": {k: r.body.get(k) for k in ("input_digest", "input_ref", "model_digest", "preprocess_digest",
                                                      "output_digest", "tree_size", "root")} if r.body else {},
                  "output": (r.body or {}).get("output", {}).get("label") if isinstance((r.body or {}).get("output"), dict) else None}
                 for r in rep.records]
        res.section = {"ledger": {"ledger_id": rep.ledger_id, "counts": rep.counts, "intact": rep.intact,
                                  "trust_root": rep.trust_root, "checkpoints": rep.checkpoints, "anchors": rep.anchors,
                                  "gaps": rep.gaps, "replays": rep.replays, "first_break": rep.first_break,
                                  "records": chain[-2000:]}}
        res.artifacts = {"report": rep}
        if ctx.mode == "chain-only":
            res.assessed_override = [a for a in self.spec.supports if a.attack_class != "record_truncation"]
            res.notes.append("no external anchor supplied: truncation of the ledger tail is not assessed")
        common = dict(asset_type=AssetType.INFERENCE_LEDGER, asset_id=rep.ledger_id or "ledger",
                      access_assumptions=PROV_ASSUMPTIONS, limitations=self.spec.limitations, deterministic=True,
                      calibrated=True, confidence=1.0)
        failed = [r for r in rep.records if r.status == "FAILED"]
        by_class: dict[str, list] = defaultdict(list)
        for r in failed:
            for c in dict.fromkeys(r.classes):
                by_class[c].append(r)
        untrusted = [r for r in rep.records if r.status == "UNTRUSTED"]
        for cls, recs in by_class.items():
            head, verb = CLASS_TEXT.get(cls, (cls, "altered"))
            first = recs[0]
            reason = (f"{len(recs)} {head}: the first is record {first.seq} (line {first.line}) — "
                      f"{'; '.join(first.reasons)}."
                      + (f" {len(untrusted)} subsequent record(s) cannot be trusted because chain continuity was lost at "
                         f"sequence {rep.first_break}." if untrusted and cls == next(iter(by_class)) else ""))
            rows = [[r.line, r.seq, r.status, "; ".join(r.reasons), r.entry_hash, r.key_id] for r in recs + untrusted[:50]]
            res.findings.append(ProposedFinding(
                attack_class=cls, subject=f"ledger:{cls}", severity=Severity.HIGH,
                title=f"Ledger {verb}: {len(recs)} record(s) failed verification",
                reason=reason, evidence=[_crypto_evidence(ctx, f"Failed records ({cls})", "Per-record verification "
                                                          "results.", rows)],
                affected_samples=[SampleRef(sample_id=f"seq:{r.seq}", note=r.reasons[0] if r.reasons else None)
                                  for r in recs[:200]], affected_count=len(recs),
                recommended_action="Treat every affected and untrusted record as unverified; restore the ledger from a "
                                   "trusted copy and investigate who had write access.", **common))
        if rep.truncated or rep.rewritten:
            bad = [a for a in rep.anchors if a["status"] in ("TRUNCATED", "MISMATCH")]
            bad_cp = [c for c in rep.checkpoints if not c["consistent"]]
            cls = "record_truncation" if rep.truncated else "record_modification"
            detail = "; ".join(a.get("detail", a["status"]) for a in bad) or \
                "; ".join(f"checkpoint at sequence {c['seq']} does not match history" for c in bad_cp)
            res.findings.append(ProposedFinding(
                attack_class=cls, subject="ledger:anchor", severity=Severity.HIGH,
                title="Ledger truncated relative to its external anchor" if rep.truncated else
                "Ledger history differs from its Merkle checkpoints",
                reason=f"Merkle verification failed: {detail}.",
                evidence=[Evidence(id=ctx.evidence_id("anchors"), kind=EvidenceKind.CRYPTO_CHECK,
                                   title="Checkpoints and anchors", summary="RFC 6962 roots recomputed from the ledger.",
                                   data={"checkpoints": rep.checkpoints, "anchors": rep.anchors})],
                recommended_action="Recover the missing or rewritten records from backup and compare with the anchor.",
                **common))
        if not res.findings:
            c = rep.counts
            res.findings.append(ProposedFinding(
                attack_class="record_modification", subject="ledger:verified", severity=Severity.INFO,
                title=f"Ledger verified: {c['VALID']} records, chain intact",
                reason=(f"All {c['VALID']} records carry valid Ed25519 signatures from trusted keys, link by SHA-256 to "
                        f"their predecessors with contiguous sequence numbers and unique nonces; "
                        f"{len(rep.checkpoints)} Merkle checkpoint(s) match the history"
                        + (f" and {sum(1 for a in rep.anchors if a['status'] == 'CONSISTENT')} external anchor(s) are "
                           "consistent." if rep.anchors else "; no external anchor was supplied, so tail truncation was "
                           "not assessed.")),
                evidence=[Evidence(id=ctx.evidence_id("summary"), kind=EvidenceKind.CRYPTO_CHECK,
                                   title="Verification summary", summary="Counts, checkpoints and anchors.",
                                   data={"counts": c, "checkpoints": rep.checkpoints, "anchors": rep.anchors,
                                         "trust_root": rep.trust_root})],
                recommended_action="None.", **common))
        return res


class InferenceBinding(Detector):
    spec = DetectorSpec(
        id="provenance.binding", version="1.0.0", title="Inference binding verification", layer=Layer.PROVENANCE,
        summary="Checks that every inference record names an approved model artifact and preprocessing configuration "
                "and — when the raw inputs are supplied — that each input still matches its recorded digest.",
        required=[Capability.INFERENCE_LEDGER, Capability.LEDGER_TRUST_ROOT, Capability.REFERENCE_MODEL_DIGEST],
        optional=[Capability.INFERENCE_INPUTS],
        modes=[DetectorMode(name="with-inputs", description="model, configuration and input bindings",
                            needs=[Capability.INFERENCE_INPUTS]),
               DetectorMode(name="bindings-only", description="model and configuration bindings", degraded=True,
                            support_override=[AttackSupport(attack_class="model_binding_violation", level=SupportLevel.FULL),
                                              AttackSupport(attack_class="config_binding_violation",
                                                            level=SupportLevel.FULL)])],
        supports=[AttackSupport(attack_class="model_binding_violation", level=SupportLevel.FULL),
                  AttackSupport(attack_class="config_binding_violation", level=SupportLevel.FULL),
                  AttackSupport(attack_class="input_substitution", level=SupportLevel.FULL)],
        depends_on=["provenance.ledger_integrity"], runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.CRYPTO_CHECK],
        limitations=["Bindings prove which artifacts were named, not that the named model actually ran; that relies on "
                     "the signer's execution environment."],
        access_assumptions=PROV_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        rep = ledger_report(ctx)
        res = DetectorResult(samples_processed=sum(1 for r in rep.records if r.kind == "inference"))
        if ctx.mode == "bindings-only":
            res.assessed_override = [a for a in self.spec.supports if a.attack_class != "input_substitution"]
        by_class: dict[str, list] = defaultdict(list)
        for b in rep.bindings:
            by_class[b["class"]].append(b)
        titles = {"model_binding_violation": "Inference records name an unapproved model",
                  "config_binding_violation": "Inference records use an unapproved preprocessing configuration",
                  "input_substitution": "Stored inputs no longer match their recorded digests"}
        for cls, items in by_class.items():
            res.findings.append(ProposedFinding(
                attack_class=cls, asset_type=AssetType.INFERENCE_LEDGER, asset_id=rep.ledger_id or "ledger",
                subject=f"binding:{cls}", severity=Severity.HIGH, confidence=1.0, title=titles[cls],
                reason=(f"{len(items)} inference record(s) fail the {cls.replace('_', ' ')} check; first: record "
                        f"{items[0]['seq']} — {items[0]['detail']}."),
                evidence=[Evidence(id=ctx.evidence_id(cls), kind=EvidenceKind.CRYPTO_CHECK, title="Binding failures",
                                   summary="Records whose bindings do not match the trust root or the stored inputs.",
                                   data={"columns": ["sequence", "record status", "detail"],
                                         "rows": [[b["seq"], b["record_status"], b["detail"]] for b in items[:300]]})],
                affected_samples=[SampleRef(sample_id=f"seq:{b['seq']}", note=b["detail"]) for b in items[:200]],
                affected_count=len(items), access_assumptions=PROV_ASSUMPTIONS, limitations=self.spec.limitations,
                deterministic=True, calibrated=True,
                recommended_action="Discard the affected outputs; establish which model and inputs were actually used."))
        if not res.findings:
            res.findings.append(ProposedFinding(
                attack_class="model_binding_violation", asset_type=AssetType.INFERENCE_LEDGER,
                asset_id=rep.ledger_id or "ledger", subject="binding:ok", severity=Severity.INFO, confidence=1.0,
                title="All inference records bind approved artifacts",
                reason=(f"Every one of {res.samples_processed} inference records names an approved model artifact and "
                        "preprocessing digest" + (" and matches its stored input." if ctx.mode == "with-inputs" else
                                                  "; raw inputs were not supplied, so input substitution was not assessed.")),
                evidence=[Evidence(id=ctx.evidence_id("ok"), kind=EvidenceKind.CRYPTO_CHECK, title="Binding summary",
                                   summary="Checked against the trust root.",
                                   data={"records": res.samples_processed, "trust_root": rep.trust_root})],
                access_assumptions=PROV_ASSUMPTIONS, limitations=self.spec.limitations, deterministic=True,
                calibrated=True, recommended_action="None."))
        return res
