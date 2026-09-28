"""Coverage statement, computed from detector declarations and what actually executed.

Nothing here is typed by hand: an attack class is ASSESSED only if a detector that declares FULL
support for it completed in a mode that preserves FULL support; PARTIALLY_ASSESSED if only partial
support completed; FAILED_TO_EXECUTE if the only detectors that could have assessed it crashed;
NOT_ASSESSED if they could not run (access, budget, preconditions, abstention); UNSUPPORTED if no
registered detector addresses it at all.
"""

from __future__ import annotations

from ..contracts import (
    ATTACK_CLASSES,
    CAPABILITY_INFO,
    Capability,
    CoverageRow,
    CoverageState,
    CoverageStatement,
    DetectorExecution,
    DetectorSpec,
    ExecutionState,
    Negotiation,
    SupportLevel,
)

RECOMMENDATION: dict[Capability, str] = {
    Capability.DATASET_IMAGES: "Supply the dataset images.",
    Capability.DATASET_LABELS: "Supply image-level labels for the dataset.",
    Capability.DATASET_ANNOTATIONS: "Supply bounding-box annotations.",
    Capability.DATASET_METADATA: "Supply source/batch/sensor/timestamp metadata (manifest or metadata.csv).",
    Capability.CONTRIBUTOR_METADATA: "Attribute every sample to its contributor.",
    Capability.MODEL_ARTIFACT: "Supply the deployed model artifact.",
    Capability.MODEL_PREDICT: "Grant prediction access to the model.",
    Capability.MODEL_LOGITS: "Grant access to per-class scores, not only top-1 labels.",
    Capability.MODEL_GRAPH: "Grant access to the model graph (ONNX/TorchScript).",
    Capability.MODEL_PARAMETERS: "Grant access to model parameters.",
    Capability.MODEL_ACTIVATIONS: "Grant white-box access to internal activations.",
    Capability.MODEL_GRADIENTS: "Grant white-box, differentiable access (enables gradient-based trigger reconstruction).",
    Capability.REFERENCE_MODEL: "Supply the approved reference model artifact.",
    Capability.REFERENCE_MODEL_DIGEST: "Register the approved model digest in the trust root.",
    Capability.REFERENCE_FINGERPRINT: "Supply the approved model's stored behavioural fingerprint.",
    Capability.REFERENCE_DATASET: "Supply a trusted clean reference dataset.",
    Capability.PROBE_DATASET: "Supply a clean, labelled probe corpus.",
    Capability.SUSPECT_INPUTS: "Supply the operational inputs suspected of carrying a trigger.",
    Capability.INFERENCE_LEDGER: "Supply the signed inference ledger.",
    Capability.LEDGER_TRUST_ROOT: "Supply the trust root (public keys and approved bindings).",
    Capability.LEDGER_ANCHOR: "Supply the externally held Merkle anchor file.",
    Capability.INFERENCE_INPUTS: "Supply the raw inputs referenced by the inference records.",
    Capability.PREPROCESSING_CONFIG: "Supply the preprocessing configuration used at inference.",
    Capability.OPERATIONAL_DATA: "Supply a batch of incoming operational images.",
    Capability.SEMANTIC_ENCODER: "Install a vendored foundation encoder or supply the approved reference model.",
}

DONE = (ExecutionState.COMPLETED, ExecutionState.COMPLETED_DEGRADED)


def compute_coverage(specs: list[DetectorSpec], plan: list[Negotiation], executions: list[DetectorExecution]
                     ) -> CoverageStatement:
    neg = {n.detector_id: n for n in plan}
    exe = {e.detector_id: e for e in executions}
    rows: list[CoverageRow] = []
    for info in ATTACK_CLASSES.values():
        supporters = [s for s in specs if any(a.attack_class == info.id for a in s.supports)]
        if not supporters:
            rows.append(CoverageRow(
                attack_class=info.id, layer=info.layer, title=info.title, state=CoverageState.UNSUPPORTED,
                reason=info.unsupported_reason or "No registered detector addresses this attack class.",
                recommended_evidence=list(info.recommended_evidence)))
            continue
        full, partial, failed, idle_reasons = [], [], [], []
        missing: set[Capability] = set()
        for spec in supporters:
            e = exe.get(spec.id)
            n = neg.get(spec.id)
            if e is None:
                continue
            if e.state in DONE:
                level = next((a.level for a in e.assessed_classes if a.attack_class == info.id), None)
                if level == SupportLevel.FULL:
                    full.append(spec.id)
                elif level == SupportLevel.PARTIAL:
                    partial.append(spec.id)
                else:
                    idle_reasons.append(f"{spec.id} ran in mode '{e.mode}', which does not assess this class")
                    preferred = next((m for m in spec.modes if not m.degraded), None)
                    if preferred is not None:
                        missing.update(preferred.needs)
            elif e.state == ExecutionState.ERROR:
                failed.append(spec.id)
            else:
                why = "; ".join(e.reasons) if e.reasons else e.state.value.lower()
                idle_reasons.append(f"{spec.id}: {why}")
                if n:
                    missing.update(n.missing)
        if full:
            state = CoverageState.ASSESSED
            reason = "Assessed by " + ", ".join(full) + (f"; partial support also from {', '.join(partial)}" if partial else "")
        elif partial:
            state = CoverageState.PARTIALLY_ASSESSED
            degraded = [pid for pid in partial if exe[pid].state == ExecutionState.COMPLETED_DEGRADED]
            reason = ("Only partial support completed: " + ", ".join(partial)
                      + (f" (degraded mode: {', '.join(f'{d} [{exe[d].mode}]' for d in degraded)})" if degraded else ""))
            for pid in degraded:
                spec = next(s for s in supporters if s.id == pid)
                preferred = next((m for m in spec.modes if not m.degraded), None)
                if preferred is not None:
                    missing.update(preferred.needs)
        elif failed:
            state = CoverageState.FAILED_TO_EXECUTE
            reason = "Detector(s) that should have assessed this class failed: " + ", ".join(
                f"{f} ({exe[f].error_type}: {exe[f].error_message})" for f in failed)
        else:
            state = CoverageState.NOT_ASSESSED
            reason = "Not assessed — " + " | ".join(idle_reasons) if idle_reasons else "Not assessed."
        if failed and state in (CoverageState.ASSESSED, CoverageState.PARTIALLY_ASSESSED):
            reason += f". Note: {', '.join(failed)} failed to execute."
        required = sorted(missing, key=lambda c: c.value)
        rows.append(CoverageRow(
            attack_class=info.id, layer=info.layer, title=info.title, state=state, detectors=full + partial,
            failed_detectors=failed, reason=reason,
            required_access=required if state != CoverageState.ASSESSED else [],
            recommended_evidence=[RECOMMENDATION[c] for c in required] if state != CoverageState.ASSESSED else []))
    count = {s: sum(1 for r in rows if r.state == s) for s in CoverageState}
    return CoverageStatement(rows=rows, total=len(rows), assessed=count[CoverageState.ASSESSED],
                             partial=count[CoverageState.PARTIALLY_ASSESSED], not_assessed=count[CoverageState.NOT_ASSESSED],
                             failed=count[CoverageState.FAILED_TO_EXECUTE], unsupported=count[CoverageState.UNSUPPORTED])


def capability_title(c: Capability) -> str:
    return CAPABILITY_INFO[c].title
