# 07 · Evidence and provenance

[Handbook home](../README.md) · [Project README](../../README.md)

Evidence explains an observation. Provenance records where it came from and whether the associated records still satisfy their integrity checks. These are complementary: a valid signature does not make an incorrect observation scientifically true.

## Evidence custody

Evidence blobs are addressed by content digest. Findings can carry statistics, tables, contact-sheet descriptions, comparisons, heatmaps, or cryptographic observations. The evidence graph connects assessment objects for investigation; it is not itself a proof that every claim is correct.

On retrieval, stored blob content is checked against its address. A mismatch is an integrity failure that should be preserved and investigated. Portable report JSON may contain summaries and blob references without all raw media. Retain the evidence store if reviewers need those assets later.

## Signed ledgers

An inference ledger binds record contents through canonicalization, signatures, and previous-entry hashes. Merkle checkpoints summarize ledger history. Trust roots hold public keys, authorized roles, validity/revocation information, and approved model bindings. They must be obtained through trusted custody, not accepted solely because they accompanied a suspect ledger.

| Check | What it supports | What it cannot establish alone |
| --- | --- | --- |
| Record signature | The record matches content signed by a trusted key under the verifier's rules | The signer was honest or the host uncompromised. |
| Hash chain | The supplied sequence has valid predecessor links | An externally unknown tail was not removed. |
| Merkle checkpoint | Consistency with the recorded tree root | The root itself was independently retained. |
| External anchor | Comparison against a separately held checkpoint | Trustworthiness of the acquisition process. |
| Input/model binding | Agreement with declared digests and approved bindings | Accuracy of the resulting prediction. |

## Keep audit and inference separate

The governance audit records user actions and decision history. An inference ledger records model-related events and bindings. They share cryptographic mechanisms but answer different questions. Verifying the local audit ledger does not automatically verify every imported inference ledger.

## Review sequence

1. Identify the ledger and the public trust root used to verify it.
2. Supply any independently retained anchor and referenced input files.
3. Review the first invalid or missing binding and its downstream effects.
4. Preserve the original data and verifier output. Do not repair a broken chain by editing it in place.
5. Record any recovery or trust-root change through the governance/operations process.

Workspace private keys live under `keys/`; only public trust material belongs in a shareable verification package. Signed report manifests are a separate artifact described in [verification](08-verification.md).

Sources: [provenance specification](../provenance-spec.md), [evidence store](../../src/visionsentinel/evidence/store.py), and [verifier implementation](../../src/visionsentinel/provenance/verifier.py).

---

[06 · Previous](06-detectors-and-profiles.md) · [08 · Next](08-verification.md)
