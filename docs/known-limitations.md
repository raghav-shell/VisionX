# Known limitations

- Detector findings are risk indicators; they cannot prove intent or absence of compromise.
- Unsupported modalities, encrypted containers, missing references, and withheld model access reduce coverage explicitly.
- External anchors are required to detect a validly signed ledger-tail truncation.
- Workspace key rotation preserves historical public trust entries but cannot undo signatures made by a compromised key before revocation.
- The shipped benchmark provides positive-control fitness, not a production-ready FPR/AUROC claim.
- Local SQLite is suitable for a single offline workstation; multi-node deployments need an operational database and managed backup process.
