# 14 · Demo rehearsal and delivery

[Handbook home](../README.md) · [Project README](../../README.md)

The presentation should show one complete chain of evidence: controlled input, execution, a finding, assessment limits, human review, and a portable result. Use synthetic data and a rehearsed machine configuration.

## Prepare the environment

Follow [getting started](01-getting-started.md), provision distinct accounts, and start the authenticated factory-launched API. Confirm the same source revision and profiles on the presentation machine. Validate the scenario catalogue before the session.

Run **Targeted Label Flip Attack** through the backend and retain its completed scan. Verify that the selected finding is suitable for a disposition relaxation; protected cryptographic failures cannot be accepted. Prepare a second browser session for the approver and sign in before the live demonstration if the presentation format permits.

## Rehearse the evidence route

| Stop | Show | Explain |
| --- | --- | --- |
| Overview | Named scan, disposition, findings, and coverage | This is a completed controlled assessment. |
| Finding | Label-consistency observation and evidence | The result can be traced to a sample and detector. |
| Coverage | Partial and unavailable classes | Coverage reflects supplied evidence and access. |
| Governance | Pending relaxation and independent decision | The analyst cannot authorize their own relaxation. |
| Report/evaluation | Actual artifacts and benchmark outcomes | Integrity and detector effectiveness are separate claims. |

Use the [presenter script and judge answers](../demo-script.md) for exact wording, expected observations, and fallbacks. The [SIH demo runbook](../SIH_DEMO.md) contains the operational sequence.

## Backups and timing

Time a full rehearsal on the actual machine. No generic execution-time promise is published. Keep a completed server scan and a locally importable report in case a new run exceeds the allotted time. If the backend becomes unavailable, identify the fallback as local report review; do not imply that approval actions are occurring in a disconnected session.

Preserve the original report bundle and public verification material separately from screenshots. A screenshot demonstrates the interface, while the assessment artifacts support inspection and reproduction.

## Presentation exit check

A presenter should be able to explain the observed finding, one coverage gap, the current benchmark denominator, the independent approval rule, and one deployment limitation without relying on marketing language. Review [SIH readiness](../sih-readiness.md) before calling the submission ready.

---

[13 · Previous](13-development.md) · [15 · Next](15-faq-and-glossary.md)
