# 03 · Using the workspace

[Handbook home](../README.md) · [Project README](../../README.md)

The workspace supports two review modes. Use a backend session for uploads, scans, and governance. Use **Open report** to inspect a local `report.json` without uploading it. Local import does not grant backend permissions or independently verify signatures.

## Read an assessment

| View | What to inspect | Question to answer |
| --- | --- | --- |
| Overview | Triage findings, execution totals, and coverage summary | Where should review begin? |
| Findings | Observation, severity, disposition, and evidence inspector | What supports this finding? |
| Coverage | Assessment state and reasons for each attack class | What remains unknown? |
| Detectors | Planned and actual execution states | Did the checks complete as intended? |
| Evidence | Embedded summaries and links to findings | Can the observation be traced? |
| Assets | Supplied roles, formats, and digests | Are these the intended inputs? |
| Provenance | Ledger-related coverage and execution | Were record-integrity checks included? |
| Activity | Scan events and detector messages | How did the assessment progress? |
| Evidence graph | Backend relationships for a server scan | How do assets and findings connect? |
| Attack Lab | Backend scenario catalogue and run results | Can the case be reproduced? |

Backend-only views need a server scan and access to its persisted state. Large evidence blobs are not embedded in every portable JSON report. Do not assume local import carries the entire workspace.

## Submit and review

1. Sign in with an analyst account. Confirm the connection indicator identifies the server session.
2. Use **New assessment** to provide compatible registered assets and a backend-published profile. Upload through the supported form when needed.
3. Queue the assessment. Watch activity and wait for a terminal result before interpreting totals.
4. Open the most relevant finding. Read the observation, evidence, limitations, and required access.
5. Check the coverage gaps and detector errors. A finding cannot compensate for unrelated checks that never ran.
6. Record acknowledgment, ownership, and a substantive note. Request a disposition change only when the evidence supports it.

## Independent approval

Tightening a disposition can apply immediately. Relaxing it stays pending for another approver or administrator. Sign out, use the independent account, and inspect the request before approving or rejecting. The requester cannot decide their own request; protected cryptographic failures cannot be accepted.

The report preserves the original assessment. Subsequent governance state and audit events are separate records; review both when explaining a final operational decision.

## Practical controls

Use the light/dark toggle for the review environment and `Ctrl+K` or `⌘K` for workspace search. A locally opened report must be under the frontend's 15 MiB import limit. If a report cannot be opened, check its schema and required result fields rather than editing the evidence to make it load.

See [operations](12-operations.md) for interruptions and [verification](08-verification.md) before relying on report integrity.

---

[02 · Previous](02-core-concepts.md) · [04 · Next](04-architecture.md)
