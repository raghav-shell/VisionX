# 06 · Detectors, profiles, and coverage

[Handbook home](../README.md) · [Project README](../../README.md)

A detector declares the evidence it needs before it executes. The registry validates these declarations, and the planner combines them with observed capabilities, profile restrictions, scientific preconditions, and budget.

## Select the engagement

| Profile | Budget | Intended use |
| --- | --- | --- |
| `baseline` | STANDARD | General data, model identity/behavior, provenance, and drift review. |
| `strict` | DEEP | Deeper acceptance review; inherits baseline and adjusts contributor sensitivity. |
| `blackbox` | DEEP | Prediction-only engagement with graph, parameters, activations, and gradients withheld by policy. |
| `selftest` | DEEP | Deterministic exercises with reduced iteration counts for expensive checks. |

A stricter profile cannot manufacture missing inputs. `blackbox` intentionally withholds capabilities even if a supplied artifact could expose them. `selftest` is a reproducible exercise configuration, not a calibration certificate.

```bash
visionsentinel profiles list
visionsentinel profiles validate strict
visionsentinel detectors
```

Use `visionsentinel detectors --help` for inspecting one detector's declaration. Profile YAML rejects unknown fields; keep custom changes reviewable and record the resulting digest.

## Planning and execution

The planner checks required capabilities and any-of groups, scientific preconditions, budget, and execution mode. Missing access and policy-withheld access are distinguishable. The recorded plan is followed by an execution record with timing, processed samples, findings, reasons, and final state.

Coverage is computed from declared support and actual execution. A degraded detector can contribute partial coverage; an execution error must remain visible as a failure. Unsupported attack classes are explicitly represented rather than dropped from the denominator.

## Interpreting analytical findings

Data checks use different signals: duplicate structure, label consistency, geometry, metadata, outlier evidence, and trigger-like correlations. Model checks distinguish byte identity, graph/parameter differences, behavior, and access-dependent backdoor indicators. Drift describes distribution changes; provenance checks cryptographic and binding properties.

These signals have different uncertainty. Some checks are deterministic, while others use reference-data calibration, literature defaults, or uncalibrated heuristics. Read the threshold origin and limitation before interpreting confidence. A high confidence value is not a universal probability that a submission is malicious.

## Changing a detector

Define its supported classes and required access; implement explicit abstention and error paths; attach inspectable evidence; add suitable clean and attack controls; and verify coverage when inputs are missing. Do not fix a miss by rewriting the scenario's expected result without scientific justification.

See [detector methodology](../detector-methodology.md), [profiles](../../profiles/), [negotiation contract](../../src/visionsentinel/core/detector.py), and [development](13-development.md).

---

[05 · Previous](05-data-and-models.md) · [07 · Next](07-evidence-and-provenance.md)
