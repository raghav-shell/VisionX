# Report format and verification

[Documentation home](README.md) · [Verification guide](handbook/08-verification.md)

A report is a portable assessment record. Its integrity checks support custody of that record; they do not certify detector accuracy or automatically incorporate later governance decisions.

## Bundle contents

| File | Content |
| --- | --- |
| `report.json` | Envelope with schema `visionsentinel/report/v1`, generation time, software version, and the structured result. |
| `report.html` | Offline human-readable result. |
| `coverage.md` | Assessed, partial, unassessed, failed, and unsupported attack classes with reasons. |
| `manifest.json` | Schema `visionsentinel/report-manifest/v1`, scan ID, result digest, file names/hashes/sizes, software version, and optional signer/signature. |

Result data includes the assessment's inputs, profile, plan, executions, findings, coverage, and available reproduction metadata. Preserve supplied seed, version, dependency, and platform details when comparing runs. Large evidence blobs may remain in the workspace evidence store rather than inside JSON.

## Signing

`write_report` signs the manifest when it receives a signing key. The CLI makes this explicit with `scan --sign-with /path/to/report-key.pem`. API scan and Attack Lab paths supply the workspace report key. An unsigned manifest provides file hashes without authenticated signer identity.

The manifest signature uses a domain-separated canonical representation. Do not reformat, edit, or replace bundle content before verification. Treat public-key custody as a separate prerequisite from having a signature field.

## Verification paths

The Python interface `visionsentinel.reporting.verify_manifest(report_dir, public_key)` re-hashes listed files and checks the manifest signature when raw Ed25519 public-key bytes are supplied. It returns a list of problems. Without a public key, it checks hashes only.

For stored server reports, `POST /api/scans/{scan_id}/report/verify` uses the active workspace report public key and optionally compares `expected_digest`. Historical reports signed before rotation require the appropriate historical trusted key for independent checking; the active-key endpoint does not resolve every historical trust case.

The workspace's **Open report** action parses and displays JSON. It does not independently verify the bundle signature. Describe backend verification, local parsing, and independent verification distinctly in a presentation.

A different result digest can reflect different inputs, policy, environment, or run content; it is not by itself a compromise verdict. Compare equivalent assets/profiles and inspect the differences. Source: [report implementation](../src/visionsentinel/reporting/report.py).
