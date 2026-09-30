# Implementation status

[Documentation home](README.md) · [Readiness review](sih-readiness.md) · [Build plan](build-plan.md)

This is a source-backed inventory of VisionX, reviewed on 30 September 2026 against the code at `e09a94e`. “Implemented” means the code path exists; it is not a blanket claim of deployment validation or universal detection effectiveness.

## Implemented capabilities

| Capability | Implementation evidence | How to inspect it | Boundary |
| --- | --- | --- | --- |
| Dataset assurance | [Data detectors](../src/visionsentinel/data_assurance/) | Run the label-flip scenario; inspect findings and coverage. | Heuristic/calibrated signals have domain and reference requirements. |
| Model assurance | [Model detectors](../src/visionsentinel/model_assurance/) and [loaders](../src/visionsentinel/loaders/models/) | Supply candidate/reference models and inspect identity and behavior checks. | Backdoor analyses need compatible access, dependencies, and calibration. |
| Drift analysis | [Drift package](../src/visionsentinel/drift/) | Compare operational and reference data; read interpretation. | A shift does not establish malicious intent. |
| Inference provenance | [Ledger verifier](../src/visionsentinel/provenance/verifier.py) | Verify signed records with trust root and external anchor. | Trust custody and anchors are necessary for stronger historical claims. |
| Capability negotiation | [Detector contract](../src/visionsentinel/core/detector.py) | Inspect plan, execution, and coverage separately. | ASSESSED describes completed checks, not absence of attacks. |
| Evidence and reporting | [Evidence package](../src/visionsentinel/evidence/) and [reporting](../src/visionsentinel/reporting/) | Inspect digests, evidence graph, report files, and manifest. | Local JSON display is not cryptographic verification. |
| Human governance | [Governance service](../src/visionsentinel/governance/service.py) | Request a relaxation and resolve it from an independent account. | Host compromise and collusion remain outside this control. |
| Asset and job lifecycle | [Asset APIs](../src/visionsentinel/api/routers/assets.py) and [runner](../src/visionsentinel/api/runner.py) | Import/inspect assets; observe persistent jobs and restart recovery. | Single-workstation architecture, not distributed scheduling. |
| Browser workspace | [Workspace components](../frontend/src/components/workspace/) | Review actual server scans or locally imported reports. | Some views require backend state; landing figures are illustrative. |
| Attack Lab and evaluation | [Runner](../src/visionsentinel/attacklab/runner.py), [scenarios](../scenarios/), [benchmark](../benchmarks/latest.md) | Validate manifests and reproduce outcomes. | Current controlled corpus is small and includes misses/exclusions. |

## Recorded evidence

The checked-in benchmark contains 10 scenarios. Eight positive cases are eligible for expected-signal measurement; six succeeded. `duplicate_flood` and `semantic_shift` missed the declared expected signal. `systematic_mislabel` failed a fitness gate. The clean control produced two material alerts over 400 samples; AUROC is not estimated.

The README screenshots were captured from the production frontend with a generated label-flip report, not from fabricated dashboard values. Their [capture notes](images/screenshots/README.md) document the local import and environment. This single run is separate from the full checked-in benchmark.

## Work still required

- Align the Docker static-dashboard recipe with the current Next.js server configuration and rehearse offline transfer.
- Resolve benchmark misses and invalid scenario fitness with appropriate regression controls.
- Expand held-out clean/benign-shift evidence before stronger statistical claims.
- Record hardware, timings, resources, and platform isolation for the actual demonstration machine.
- Rehearse authenticated governance and restoration from retained artifacts on the submission revision.

## Non-goals and claim boundaries

VisionX does not provide a security certification, production model training/serving, guaranteed backdoor elimination, or host-wide network isolation. No validated customer deployment, universal accuracy number, or hardware throughput promise is asserted here.

Use this inventory to identify the code and evidence behind a claim. Use the [readiness review](sih-readiness.md) to decide what still needs verification before presenting it.
