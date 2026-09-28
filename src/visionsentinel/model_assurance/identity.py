"""Model identity: artifact/parameter digests and architecture fingerprints.

Deterministic checks. Artifact identity (bytes) is separated from parameter identity (canonical
parameter digest: sorted names, dtypes, shapes, bytes) so that a harmless re-serialisation is
distinguished from a substitution, and both are separated from *behaviour* (see the behavioural
fingerprint detector).
"""

from __future__ import annotations

import difflib
from collections import Counter
from typing import Any

from ..contracts import (
    AssetType,
    AttackSupport,
    CalibrationRequirement,
    Capability,
    DetectorMode,
    DetectorSpec,
    EvidenceKind,
    Layer,
    ProposedFinding,
    RuntimeClass,
    Severity,
    SupportLevel,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult
from ..core.hashing import digest_json
from ..loaders.models import GraphSummary
from .common import MODEL_ASSUMPTIONS, candidate, reference, short, stat, table


def approved_set(ctx: DetectorContext) -> list[dict[str, Any]]:
    """Approved identities from the reference model and the trust root."""
    out: list[dict[str, Any]] = []
    ref = reference(ctx)
    if ref is not None:
        out.append({"source": f"reference model {ref.name}", "artifact": ref.artifact_digest,
                    "params": ref.param_digest, "preprocess": ref.cfg.digest if ref.preprocess_explicit else None,
                    "architecture": architecture_digest(ref.graph()) if ref.graph() else None})
    trust = ctx.optional_asset("trust_root")
    if trust is not None:
        for m in trust.approved_models:
            out.append({"source": f"trust root '{trust.name}' ({m.name})", "artifact": m.artifact_digest,
                        "params": m.param_digest, "preprocess": m.preprocess_digest,
                        "architecture": m.architecture_digest})
    return out


# ------------------------------------------------------------------------------------------ digests

class ArtifactDigest(Detector):
    spec = DetectorSpec(
        id="model.artifact_digest", version="1.0.0", title="Model artifact & parameter digest", layer=Layer.MODEL,
        summary="Compares the SHA-256 of the model artifact, its canonical parameter digest and its preprocessing "
                "digest with the approved reference and trust-root bindings.",
        required=[Capability.MODEL_ARTIFACT],
        required_any=[[Capability.REFERENCE_MODEL, Capability.REFERENCE_MODEL_DIGEST]],
        optional=[Capability.MODEL_PARAMETERS, Capability.PREPROCESSING_CONFIG],
        modes=[DetectorMode(name="artifact+parameters", description="artifact and canonical parameter digests",
                            needs=[Capability.MODEL_PARAMETERS]),
               DetectorMode(name="artifact-only", description="artifact digest only (parameters not accessible)",
                            degraded=True, support_override=[
                                AttackSupport(attack_class="model_substitution", level=SupportLevel.FULL)])],
        supports=[AttackSupport(attack_class="model_substitution", level=SupportLevel.FULL),
                  AttackSupport(attack_class="model_weight_tampering", level=SupportLevel.PARTIAL,
                                note="detects that parameters differ, not how"),
                  AttackSupport(attack_class="config_binding_violation", level=SupportLevel.PARTIAL,
                                note="preprocessing digest against approved bindings")],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.CRYPTO_CHECK],
        limitations=["Identity is only as good as the approved digests; approving a malicious model makes it 'match'.",
                     "A digest mismatch says the artifact is different, not whether the difference is harmful."],
        access_assumptions=MODEL_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        cand = candidate(ctx)
        approved = approved_set(ctx)
        params = cand.param_digest if ctx.mode == "artifact+parameters" else None
        art_match = next((a for a in approved if a["artifact"] == cand.artifact_digest), None)
        param_match = next((a for a in approved if params and a["params"] == params), None)
        rows = [[a["source"], short(a["artifact"]), short(a["params"]), short(a["preprocess"])] for a in approved]
        rows.append(["candidate (observed)", short(cand.artifact_digest), short(params),
                     short(cand.cfg.digest) if cand.preprocess_explicit else "not declared"])
        ev = table(ctx, "Digest comparison", "Approved identities versus the observed artifact.",
                   ["identity", "artifact sha256", "parameter digest", "preprocess digest"], rows,
                   kind=EvidenceKind.CRYPTO_CHECK, extra={"observed": {"artifact": cand.artifact_digest,
                                                                        "params": params,
                                                                        "preprocess": cand.cfg.digest}})
        res = DetectorResult(samples_processed=1, artifacts={"artifact_match": art_match is not None,
                                                             "param_match": param_match is not None})
        res.section = {"identity": {"candidate": cand.describe(), "approved": approved,
                                    "artifact_match": art_match is not None, "param_match": param_match is not None,
                                    "isolation": getattr(cand, "isolation", None)}}
        common = dict(asset_type=AssetType.MODEL, asset_id=cand.name, evidence=[ev], access_assumptions=MODEL_ASSUMPTIONS,
                      limitations=self.spec.limitations, deterministic=True, calibrated=True, confidence=1.0)
        if art_match:
            res.findings.append(ProposedFinding(
                attack_class="model_substitution", subject="identity:artifact", severity=Severity.INFO,
                title="Model artifact matches the approved digest",
                reason=(f"The artifact SHA-256 {short(cand.artifact_digest)}… equals the approved digest from "
                        f"{art_match['source']}; the deployed file is byte-identical to the approved model."),
                recommended_action="None.", **common))
        elif param_match:
            res.findings.append(ProposedFinding(
                attack_class="model_substitution", subject="identity:artifact", severity=Severity.MEDIUM,
                title="Model re-serialised: different bytes, identical parameters",
                reason=(f"The artifact SHA-256 {short(cand.artifact_digest)}… matches no approved artifact, but its "
                        f"canonical parameter digest equals the one approved by {param_match['source']}; the weights "
                        "are unchanged and the difference lies in serialisation or metadata."),
                tags={"parameters": "identical"}, recommended_action="Confirm the re-export was authorised and "
                "register the new artifact digest.", **common))
        else:
            res.findings.append(ProposedFinding(
                attack_class="model_substitution", subject="identity:artifact", severity=Severity.HIGH,
                title="Model artifact is not an approved artifact",
                reason=(f"The artifact SHA-256 {short(cand.artifact_digest)}… matches none of the "
                        f"{len(approved)} approved identities"
                        + (f", and its parameter digest {short(params)}… differs from every approved parameter set"
                           if params else " (parameters were not accessible for a parameter-level comparison)") + "."),
                tags={"parameters": "different" if params else "unknown"},
                recommended_action="Do not deploy. Obtain the approved artifact or run an approval review.", **common))
        approved_pre = {a["preprocess"] for a in approved if a["preprocess"]}
        if cand.preprocess_explicit and approved_pre and cand.cfg.digest not in approved_pre:
            res.findings.append(ProposedFinding(
                attack_class="config_binding_violation", subject="identity:preprocess", severity=Severity.HIGH,
                title="Preprocessing configuration differs from the approved binding",
                reason=(f"The declared preprocessing digest {short(cand.cfg.digest)}… is not among the approved "
                        f"preprocessing digests; resize or normalisation differences change model behaviour."),
                recommended_action="Restore the approved preprocessing configuration.", **common))
        return res


# ------------------------------------------------------------------------------------------ architecture

def canonical_architecture(graph: GraphSummary) -> dict[str, Any]:
    """Name-independent structure: ops in order with attributes, parameter shapes and edge wiring."""
    if graph.kind == "parameter-shapes":
        return {"kind": graph.kind, "parameters": sorted([k, list(v)] for k, v in graph.parameters.items())}
    if graph.kind == "torchscript-graph":
        return {"kind": graph.kind, "ops": [o["op"] for o in graph.ops],
                "parameters": sorted(list(v) for v in graph.parameters.values())}
    ids: dict[str, str] = {}
    for i, inp in enumerate(graph.inputs):
        ids[inp["name"]] = f"in{i}"
    nodes = []
    for k, op in enumerate(graph.ops):
        refs = []
        for name in op["inputs"]:
            if name in graph.parameters:
                refs.append("p" + "x".join(str(d) for d in graph.parameters[name]))
            else:
                refs.append(ids.get(name, "?"))
        for j, out in enumerate(op["outputs"]):
            ids[out] = f"t{k}.{j}"
        nodes.append([op["op"], sorted(op["attrs"].items()), refs])
    return {"kind": graph.kind, "inputs": [i["shape"] for i in graph.inputs],
            "outputs": [o["shape"] for o in graph.outputs], "nodes": nodes}


def architecture_digest(graph: GraphSummary | None) -> str | None:
    return digest_json(canonical_architecture(graph)) if graph is not None else None


def architecture_diff(ref: GraphSummary, cand: GraphSummary) -> dict[str, Any]:
    rops = [o["op"] for o in ref.ops]
    cops = [o["op"] for o in cand.ops]
    added = Counter(cops) - Counter(rops)
    removed = Counter(rops) - Counter(cops)
    segments = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=rops, b=cops, autojunk=False).get_opcodes():
        if tag != "equal":
            after = rops[i1 - 1] if i1 > 0 else "input"
            segments.append({"change": tag, "after": after, "reference": rops[i1:i2], "candidate": cops[j1:j2]})
    rshapes = sorted(tuple(v) for v in ref.parameters.values())
    cshapes = sorted(tuple(v) for v in cand.parameters.values())
    return {
        "reference_nodes": len(rops), "candidate_nodes": len(cops), "added": dict(added), "removed": dict(removed),
        "segments": segments[:20],
        "reference_parameters": sum(int(_prod(s)) for s in rshapes),
        "candidate_parameters": sum(int(_prod(s)) for s in cshapes),
        "parameter_shapes_changed": rshapes != cshapes,
        "io_changed": ([i["shape"] for i in ref.inputs] != [i["shape"] for i in cand.inputs]
                       or [o["shape"] for o in ref.outputs] != [o["shape"] for o in cand.outputs]),
    }


def _prod(shape: tuple[int, ...]) -> int:
    out = 1
    for d in shape:
        out *= int(d)
    return out


def _fmt_counts(c: dict[str, int]) -> str:
    return ", ".join(f"{op} ×{n}" for op, n in sorted(c.items())) or "none"


class ArchitectureFingerprint(Detector):
    spec = DetectorSpec(
        id="model.architecture", version="1.0.0", title="Architecture fingerprint", layer=Layer.MODEL,
        summary="Hashes a name-independent canonical form of the computational graph (operators, attributes, wiring, "
                "parameter shapes) and explains any difference from the approved architecture.",
        required_any=[[Capability.MODEL_GRAPH, Capability.MODEL_PARAMETERS],
                      [Capability.REFERENCE_MODEL, Capability.REFERENCE_MODEL_DIGEST]],
        modes=[DetectorMode(name="graph", description="full graph canonicalisation", needs=[Capability.MODEL_GRAPH]),
               DetectorMode(name="parameter-shapes", description="parameter-shape fingerprint only", degraded=True)],
        supports=[AttackSupport(attack_class="model_graph_modification", level=SupportLevel.FULL)],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.DIFF, EvidenceKind.STATISTIC],
        limitations=["Structure only: identical architectures with different weights are the weight/behaviour "
                     "detectors' concern.",
                     "Parameter-shape fingerprints cannot see parameter-free operators (e.g. an added Sigmoid)."],
        access_assumptions=MODEL_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
        references=["Bober-Irizar et al. (2023) Architectural Backdoors in Neural Networks. CVPR."],
    )

    def run(self, ctx: DetectorContext) -> DetectorResult:
        cand = candidate(ctx)
        cgraph = cand.graph()
        if cgraph is None:
            return DetectorResult(abstained="the candidate format exposes neither a graph nor parameter shapes")
        if ctx.mode == "parameter-shapes" and cgraph.kind != "parameter-shapes":
            cgraph = GraphSummary(kind="parameter-shapes", parameters=cgraph.parameters)
        cdig = architecture_digest(cgraph)
        ref = reference(ctx)
        rgraph = ref.graph() if ref is not None else None
        if rgraph is not None and rgraph.kind != cgraph.kind:
            rgraph = GraphSummary(kind="parameter-shapes", parameters=rgraph.parameters)
            cgraph = GraphSummary(kind="parameter-shapes", parameters=cgraph.parameters)
            cdig = architecture_digest(cgraph)
        approved = {a["architecture"] for a in approved_set(ctx) if a["architecture"]}
        rdig = architecture_digest(rgraph) if rgraph is not None else None
        if rdig:
            approved.add(rdig)
        res = DetectorResult(samples_processed=len(cgraph.ops) or len(cgraph.parameters))
        if not approved:
            return DetectorResult(abstained="no approved architecture fingerprint is available for comparison")
        op_counts = dict(Counter(o["op"] for o in cgraph.ops))
        res.section = {"architecture": {"candidate_digest": cdig, "approved": sorted(approved), "kind": cgraph.kind,
                                        "op_counts": op_counts, "nodes": len(cgraph.ops),
                                        "parameters": sum(_prod(v) for v in cgraph.parameters.values())}}
        common = dict(asset_type=AssetType.MODEL, asset_id=cand.name, access_assumptions=MODEL_ASSUMPTIONS,
                      limitations=self.spec.limitations, deterministic=True, calibrated=True, confidence=1.0,
                      attack_class="model_graph_modification", subject="architecture")
        if cdig in approved:
            res.findings.append(ProposedFinding(
                severity=Severity.INFO, title="Architecture matches the approved fingerprint",
                reason=(f"The canonical {cgraph.kind} of the candidate ({len(cgraph.ops)} operators, "
                        f"{len(cgraph.parameters)} parameter tensors) hashes to {short(cdig)}…, identical to the approved "
                        "architecture."),
                evidence=[stat(ctx, "Architecture fingerprint", "Canonical structure digest.",
                               {"digest": cdig, "operators": op_counts})], recommended_action="None.", **common))
            return res
        evidence = []
        if rgraph is not None:
            diff = architecture_diff(rgraph, cgraph)
            res.section["architecture"]["diff"] = diff
            evidence.append(table(ctx, "Architecture difference", "Operator sequence alignment against the reference.",
                                  ["change", "after operator", "reference", "candidate"],
                                  [[s["change"], s["after"], " → ".join(s["reference"]) or "—",
                                    " → ".join(s["candidate"]) or "—"] for s in diff["segments"]],
                                  kind=EvidenceKind.DIFF, extra={"summary": diff}))
            reason = (f"Reference contains {diff['reference_nodes']} computational nodes; the candidate contains "
                      f"{diff['candidate_nodes']}. Unexpected nodes: {_fmt_counts(diff['added'])}. Missing nodes: "
                      f"{_fmt_counts(diff['removed'])}. Parameters: {diff['reference_parameters']:,} → "
                      f"{diff['candidate_parameters']:,}"
                      + ("; the input/output signature changed" if diff["io_changed"] else "") + ".")
        else:
            reason = (f"The candidate's canonical {cgraph.kind} hashes to {short(cdig)}…, which matches none of the "
                      f"{len(approved)} approved architecture fingerprints; no reference graph is available to "
                      "explain the difference.")
        evidence.append(stat(ctx, "Architecture fingerprints", "Candidate versus approved digests.",
                             {"candidate": cdig, "approved": sorted(approved)}))
        res.findings.append(ProposedFinding(
            severity=Severity.HIGH, title="Computational graph differs from the approved architecture", reason=reason,
            evidence=evidence, recommended_action="Treat as an unapproved model; inspect the added operators for a "
            "grafted trigger path.", **common))
        return res
