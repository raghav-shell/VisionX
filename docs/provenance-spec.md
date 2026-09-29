# Provenance specification

Ledger records use canonical JSON under the `visionsentinel/ledger/v1` domain and are Ed25519 signed. Each record includes a previous-entry hash; checkpoint roots use RFC 6962 tree construction. Anchors are independently signed under `visionsentinel/anchor/v1`.

The trust root is versioned JSON containing public keys, roles, validity windows, revocation state, and approved model bindings. Private keys never appear in the trust root.

Operational sequence: retain anchors outside the workstation; export them at shift boundaries; verify ledger + trust root + anchor with the independent verifier; investigate the first broken record; recover from the last known-good backup; preserve the corrupted copy; then create a new, audited ledger segment. Never edit a damaged ledger in place.
