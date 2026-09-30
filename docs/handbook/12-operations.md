# 12 · Operations, backup, and recovery

[Handbook home](../README.md) · [Project README](../../README.md)

Operate VisionX as a local assurance workstation with explicit custody of assets, keys, reports, and decisions. A successful demo does not replace a restore rehearsal or a deployment review.

## Start-of-session checks

1. Confirm the intended `VISIONSENTINEL_HOME` and API/frontend ports.
2. Check available disk space and the registered-asset quota before importing large data.
3. Verify profiles and run `visionsentinel selftest --airgap`; inspect individual checks and platform restrictions.
4. Confirm analyst and independent approver accounts, then open a known completed assessment.
5. Record the code revision, profile, environment, and retained public trust material for the review.

The factory-launched API uses secure cookies by default. The local HTTP recipe overrides that explicitly. Review reverse proxies, HTTPS, allowed hosts/origins, and cookie scope before exposing a service beyond loopback.

## Background work and shutdown

Scan and Attack Lab jobs persist lifecycle state. API startup reconciles interrupted work, and graceful shutdown coordinates the worker pool. Check the final job and scan status after restart; do not assume a queued or running job resumes successfully.

Use `Ctrl-C` for a local stop and allow it to finish. For a service deployment, provide a shutdown grace period appropriate to the workload and validate recovery on that host. Avoid duplicating an operation simply because its browser event stream disconnected.

## Backup procedure

Quiesce the application before copying the workspace so database state, referenced files, and signed ledgers belong to one consistent point. Preserve the entire workspace, including SQLite and any associated files, assets, reports, evidence, ledgers, and keys. Restrict access to backups containing private keys and sensitive media.

Record the revision, dependency environment, profile digests, backup time, and checksums. Retain public trust roots and anchors through independent custody. A checksum detects changed bytes; it does not authenticate an untrusted backup source.

Restore into a separate workspace first. Validate a known report, a ledger against its retained trust material, account access, and asset resolution before considering replacement of an operational workspace. This is a documented procedure to rehearse, not a claim that automated restore orchestration exists.

## Incident response

| Symptom | Immediate action | Investigation |
| --- | --- | --- |
| Evidence digest mismatch | Preserve the affected workspace and stop relying on that blob. | Compare with a known-good backup and the original report references. |
| Ledger verification failure | Preserve the ledger read-only. | Inspect the first failed record and verify with an external anchor. |
| Suspected key compromise | Restrict new signing and preserve audit evidence. | Revoke/rotate through reviewed administration; retain historical public keys. |
| Scan failed after restart | Inspect scan/job records before retrying. | Resolve the input, worker, or resource error; retain the failed attempt. |
| Storage quota exceeded | Review retention and archive policy. | Do not remove evidence that existing decisions depend on. |

Rotation does not undo signatures created before a compromise was identified. The report API verifies with the active workspace key; historical verification needs the matching trusted public key.

## Troubleshooting

**Workspace is local-only:** verify both service addresses and `VISIONX_API_ORIGIN`. **Login fails:** check credentials, cookie security, and allowed origin; keep `127.0.0.1`/`localhost` usage consistent. **No scans appear:** a fresh workspace is empty; run a scenario or import a local report. **Model checks are unavailable:** inspect access, dependencies, platform isolation, and preprocessing. **An assessment shows few covered classes:** match supplied inputs to detector prerequisites before changing the budget.

See [offline installation](../offline-install.md), [configuration](10-configuration.md), and [known limitations](../known-limitations.md).

---

[11 · Previous](11-api-reference.md) · [13 · Next](13-development.md)
