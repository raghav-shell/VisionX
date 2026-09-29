# Threat model

VisionSentinel protects an offline assurance workstation, not a live perimeter. Inputs—datasets, models, archives, ledgers, anchors, and trust roots—are untrusted until validated and content-addressed.

## Trust boundaries

- Browser clients may submit asset identifiers, never server paths. Uploads are size-bounded, copied into the workspace, and parsed by type-specific safe loaders.
- The scanner has no outbound network path. The air-gap self-test and test-suite egress guard enforce this claim.
- The SQLite index is mutable operational state; sealed reports, evidence digests, signed audit records, and external anchors establish integrity claims.
- Operators and approvers are distinct roles. A sensitive disposition reduction needs a different approving identity.

## Attacker goals and controls

| Goal | Control | Residual risk |
|---|---|---|
| Supply a malicious archive/model | bounded parsing, archive traversal checks, format loaders, import copy | parser vulnerabilities remain possible |
| Alter evidence/report | SHA-256 evidence store, signed manifest, report verification | a compromised signing key can sign false content |
| Rewrite inference/audit history | hash chain, Ed25519 signatures, Merkle checkpoints, externally retained anchors | an unanchored tail can be removed |
| Bypass governance | RBAC, CSRF, same-origin enforcement, two-person rule, signed audit trail | colluding privileged users are not prevented |
| Misrepresent detector coverage | negotiated plan plus explicit unavailable/partial states | coverage is not proof of absence |

Do not put private keys, seed passwords, or raw operational media into a report bundle or source control.
