# 02 · Core concepts

[Handbook home](../README.md) · [Project README](../../README.md)

VisionX assesses evidence about supplied assets. Its result combines observations, execution records, coverage, and a policy recommendation. These describe different things and must be interpreted separately.

## The objects in a review

| Object | Meaning | Review implication |
| --- | --- | --- |
| Asset | A registered dataset, model, ledger, trust root, or other supported input | Browser requests reference its ID, not a server path. |
| Profile | Validated detector parameters, budget, access restrictions, and risk policy | Record the profile and digest when comparing results. |
| Capability | An observed or policy-withheld form of access | A model file does not automatically grant gradients or activations. |
| Plan | Detector availability negotiated from capabilities and prerequisites | Explain unavailable checks before interpreting the findings. |
| Execution | What happened when a planned detector was reached | A runtime error is not an unassessed input or a successful check. |
| Finding | An observation with evidence, severity, assumptions, and limitations | Inspect its reason and corroboration before a decision. |
| Coverage | Per-attack-class assessment state | It is neither detection accuracy nor a global safety score. |
| Disposition | ACCEPT, REVIEW, or QUARANTINE under policy and governance | An ACCEPT result is limited to the assessed evidence. |
| Report | Portable result document and related artifacts | An opened JSON file is not automatically signature-verified. |

## Three state systems

**Availability** describes the plan: `READY`, `DEGRADED`, `UNAVAILABLE`, `ERROR`, or `BUDGET_EXCLUDED`. **Execution** describes the run: `COMPLETED`, `COMPLETED_DEGRADED`, `ABSTAINED`, `NOT_RUN`, or `ERROR`. **Coverage** summarizes attack classes: `ASSESSED`, `PARTIALLY_ASSESSED`, `NOT_ASSESSED`, `FAILED_TO_EXECUTE`, or `UNSUPPORTED`.

A check may be ready at planning time and fail during execution. A detector can run in degraded mode and provide partial evidence. Neither should be silently converted into a pass.

## An example

An imported label-flip scenario may produce REVIEW findings while model checks remain unavailable because no candidate model was supplied. That is a useful dataset assessment with a limited scope. It says nothing about the integrity of a model that was never provided.

## Two meanings of contributor

Dataset contributors are sources of samples inside an assessment; concentration of anomalies supports review, not an accusation of intent. Project contributors are the engineers credited in the README. These identities are unrelated.

The authoritative vocabulary is defined in [contract enums](../../src/visionsentinel/contracts/enums.py) and exposed to the frontend through `/api/system/metadata`.

---

[01 · Previous](01-getting-started.md) · [03 · Next](03-workspace.md)
