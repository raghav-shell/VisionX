# Known limitations

- Detector findings are risk indicators; they cannot prove intent or absence of compromise.
- Unsupported modalities, encrypted containers, missing references, and withheld model access reduce coverage explicitly.
- External anchors are required to detect a validly signed ledger-tail truncation.
- Workspace key rotation preserves historical public trust entries but cannot undo signatures made by a compromised key before revocation.
- The benchmark includes clean-control material-alert measurement, but it does not provide a conventional sample-level FPR or AUROC until compatible sample labels and continuous score vectors are available.
- Local SQLite is suitable for a single offline workstation; multi-node deployments need an operational database and managed backup process.

- The current Dockerfile expects a static frontend export, while the current Next.js configuration runs a server with API rewrites. Packaging needs alignment and an offline rehearsal.
- Platform-specific sandbox controls must be inspected on the target machine; a Python egress guard is not whole-host network isolation.
- Local report import does not verify signatures. The backend report check uses the active workspace key; historical reports require the corresponding trusted historical public key for independent verification.

See the [readiness review](sih-readiness.md) for evidence and remaining release gates.
