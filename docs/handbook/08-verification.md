# 08 · Verification and reproducibility

[Handbook home](../README.md) · [Project README](../../README.md)

Verify the property you intend to rely on. A completed scan, an intact report, a valid ledger, and good detector performance are four separate claims.

## Four verification paths

| Claim | Check | Evidence to retain |
| --- | --- | --- |
| The assessment executed | Scan state, plan, executions, and coverage | Scan ID, report, errors, and profile digest. |
| The report files are intact | Manifest file hashes and signature with the expected public key | Original bundle, trusted public key, verification output. |
| The ledger is intact | Ledger verifier with trust root, anchors, and optional inputs | Ledger, public trust material, anchors, verifier output. |
| Detectors meet the declared protocol | Valid scenarios, clean controls, fitness gates, and benchmark outcomes | Generated benchmark JSON/Markdown and environment metadata. |

## Reports

`report.json`, `report.html`, and `coverage.md` are listed in `manifest.json`. A CLI report is signed only when `--sign-with` supplies a report-role key. API scan and Attack Lab paths write reports with the workspace report key.

The backend exposes `POST /api/scans/{scan_id}/report/verify` for stored reports. It verifies against the active workspace report key and can compare an expected digest. This is server-side verification, not independent verification by the browser. Historical reports after key rotation require the matching historical public key for independent verification; an active-key check is not a complete historical trust resolver.

For an exported bundle, `visionsentinel.reporting.verify_manifest(report_dir, public_key)` is the Python verification interface. Its public-key argument is the expected raw Ed25519 public key bytes. Omitting it checks file hashes only. Opening `report.json` in the workspace verifies neither the manifest nor its signer.

## Ledgers

```bash
visionsentinel verify /path/to/ledger.jsonl --trust-root /path/to/trust-root.json
```

Use `visionsentinel verify --help` for the anchor and input options supported by the installed revision. Retain the public trust root independently. Detecting a validly signed tail truncation requires an external reference such as an anchor.

## Evaluation

The checked-in benchmark has 10 scenarios: 9 positive controls and 1 clean control. One positive scenario failed fitness, leaving 8 eligible positive cases; 6 detected their expected signal. The clean control has 2 material alerts across 400 samples. Neither that alert ratio nor scenario-level detection can be relabeled as universal sample-classification accuracy.

```bash
visionsentinel attacklab validate
visionsentinel benchmark
visionsentinel selftest --airgap
```

Benchmark regeneration changes the checked-in artifacts and can return a nonzero status for failed acceptance checks. Preserve misses and invalid scenarios. Record dependency versions, platform, seed, and profile before comparing runs.

The self-test checks cryptographic primitives, registry/profiles, selected egress controls, and frontend references. Its success is not proof of complete host isolation. See [evaluation protocol](../evaluation.md), [report format](../report-format.md), and [security review](09-security-governance.md).

---

[07 · Previous](07-evidence-and-provenance.md) · [09 · Next](09-security-governance.md)
