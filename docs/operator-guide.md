# Operator guide

1. Start the service and provision distinct analyst and approver accounts.
2. Upload assets and inspect digest/type validation and remaining storage quota.
3. Select only active assets; archived assets are intentionally rejected by scans.
4. Submit a scan, review its negotiated plan and coverage before interpreting findings.
5. Open a finding's evidence drawer; raw evidence links are integrity-checked on read.
6. For a sensitive relaxation, request a disposition change with a substantive justification. A different approver must decide it.
7. Download and verify report artifacts. Export anchors to offline custody.

If a ledger fails verification: stop relying on it, preserve it read-only, verify against the external anchor, restore a last known-good copy, rotate a suspected key, revoke it in the trust root, and record the incident in governance.
