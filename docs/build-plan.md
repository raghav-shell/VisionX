# Build and submission plan

[Documentation home](README.md) · [Readiness review](sih-readiness.md) · [Development guide](handbook/13-development.md)

This plan prioritizes a reliable, reviewable hackathon submission. Workstreams are suggested responsibilities, not new commitments assigned to individual contributors. Sequence the work by evidence needed, and preserve a working demo throughout.

## P0 · Make the presentation path reproducible

| Work item | Deliverable | Acceptance evidence |
| --- | --- | --- |
| Freeze a submission candidate | Recorded commit, dependencies, profiles, synthetic assets, and environment. | A fresh checkout can reproduce the documented startup path. |
| Rehearse authentication and governance | Distinct analyst/approver sessions and one end-to-end decision. | Pending relaxation, refusal of self-approval, independent resolution, audit history. |
| Align packaging | A reviewed frontend/API deployment recipe consistent with the chosen runtime. | Build/transfer/start on the target platform with no missing `frontend/out` assumption. |
| Prepare a fallback | Completed scan, portable report, benchmark files, and public verification inputs. | Presenter can continue honestly if new execution or the backend is unavailable. |

Keep role checks and evidence integrity intact while fixing usability. A successful demo obtained by bypassing authentication or suppressing failures does not meet these gates.

## P1 · Close known evaluation gaps

Investigate `duplicate_flood` and `semantic_shift` against their declared expected signals. For `systematic_mislabel`, determine why the fitness gate fails before changing detector thresholds. Keep old artifacts for comparison and preserve the observation unit.

For each fix, retain the manifest/seed, before-and-after result, false-positive examples, and a matching clean or benign-shift control. Freeze calibration before held-out evaluation. Update benchmark JSON and Markdown from the same generated report; do not manually polish numbers.

## P1 · Prove the deployment boundary

Test the model-worker isolation status on the target OS. Measure workload behavior under the intended host network controls, including native runtimes where relevant. Verify shutdown/restart reconciliation and restoration into a separate workspace. Record time and peak resources for named workloads before adding hardware or latency claims.

Security evidence should identify the test, platform, revision, observed result, and residual risk. Prefer specific statements over a single “secure” badge.

## P2 · Strengthen the reviewer experience

Use the handbook to connect claims to source, tests, and artifacts. Refresh screenshot provenance when UI or sample results change. Confirm the demo makes a missing capability understandable and that the distinction between original report results and later governance decisions remains clear.

Broader held-out corpora, sample-level metrics with compatible labels/scores, and multi-user deployment engineering follow the immediate submission gates. Do not imply those capabilities already exist.

## Suggested workstreams

| Workstream | Focus | Handoff |
| --- | --- | --- |
| Assurance and evaluation | Detector misses, fitness gates, clean controls, provenance verification. | Reproducible artifacts with scientific interpretation. |
| Workspace and presentation | Review flow, sample evidence, screenshot refresh, presenter rehearsal. | A timed route with observable evidence and fallbacks. |
| Integration and operations | API contracts, job recovery, packaging, CI, backup/restore. | Repeatable startup and retained verification results. |
| Shared review | Readiness assessment, claim wording, submission checklist. | Agreement between documentation and observed behavior. |

## Definition of done

A submission candidate is ready for team sign-off when the documented demo runs on the recorded machine, every claimed result has retained evidence, remaining failures are disclosed, integrity checks can be repeated, and the presenter can explain the assessment boundary. The team should update [readiness](sih-readiness.md) after each gate, rather than treating this plan as proof that the gate has passed.
