# 09 · Security and governance

[Handbook home](../README.md) · [Project README](../../README.md)

VisionX protects an assurance workflow through input boundaries, controlled execution, evidence integrity, and accountable review. It does not certify the operating system, physical acquisition chain, or the honesty of approved reference data.

## Accounts and authorization

| Role | Permissions in the governance model |
| --- | --- |
| VIEWER | Read assessments and authorized review data. |
| ANALYST | Viewer actions plus assessment submission, acknowledgment, ownership, comments, and decision requests. |
| APPROVER | Analyst actions plus independent approval or rejection. |
| ADMIN | Approver actions plus administrative account and trust-management operations. |

Role inheritance does not bypass the two-person rule. An administrator cannot decide their own pending request. Provision people as distinct accounts, rather than sharing one privileged login.

The API uses session cookies, password hashing, origin checks, mutation CSRF tokens, and rate limits. Login is origin-checked; subsequent authenticated mutations require the session's CSRF token. The localhost setup uses a deliberate insecure-cookie override for HTTP; deployments outside loopback require a separate HTTPS configuration review.

## Disposition decisions

The order is `ACCEPT → REVIEW → QUARANTINE`. Tightening applies immediately. Relaxing creates a pending decision that another APPROVER or ADMIN must decide. Requests require a supported reason code and a justification of 20–2,000 characters.

A deterministic HIGH or CRITICAL cryptographic/binding failure in the protected class set cannot be changed to ACCEPT. An independent approval cannot turn invalid records into trustworthy records. Duplicate pending requests and decisions on already resolved requests are refused.

### Audit trail

Governance records include actor, action, target, state transition, reason, and justification as applicable. The service appends signed, chained audit records alongside database state. Self-approval refusal is also audited. Review the ledger and trust material through [evidence and provenance](07-evidence-and-provenance.md).

### Sandbox and offline controls

Supported native model paths execute in a fresh Python worker with bounded, pickle-free communication. The worker attempts user/network namespace isolation, applies resource limits where supported, and installs Python audit restrictions. Namespace success and resource-limit support are platform-dependent; inspect the reported status rather than assuming Linux and macOS have identical containment.

The workload egress guard wraps Python socket/DNS operations and permits local communication. Native-code bypasses, other host processes, browser extensions, and the surrounding network remain outside that Python control. Host firewall and operating-system isolation need independent deployment validation. A failed model load should not be worked around by loading the same artifact unrestricted.

### Security review route

Read [threat model](../threat-model.md), inspect [model-loading tests](../../tests/security/test_model_loading.py), [input-safety tests](../../tests/security/test_input_safety.py), [API security tests](../../tests/security/test_api_security_runtime.py), [governance tests](../../tests/security/test_governance.py), and [ledger attack tests](../../tests/security/test_ledger_attacks.py). These are test assets, not a published claim that every test passed on every target host.

See [operations](12-operations.md) for incident preservation, key custody, and recovery. The exact decision rules are in [the governance service](../../src/visionsentinel/governance/service.py).

---

[08 · Previous](08-verification.md) · [10 · Next](10-configuration.md)
