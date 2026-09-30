# 15 · FAQ and glossary

[Handbook home](../README.md) · [Project README](../../README.md)

Use these answers to keep technical reviews and judge discussions consistent with the implementation.

## Frequently asked questions

**Is VisionX a training or inference platform?** It assesses supplied data, models, and records. Attack Lab may train small synthetic models to create controlled scenarios; that is not a production model-serving capability.

**Why do some commands say VisionSentinel?** VisionX is the product/workspace name. `visionsentinel` is the Python package and primary CLI; `visionx` is an alias.

**Does ASSESSED mean safe?** No. It means suitable checks completed under their declared conditions. Unknown attack variants and detector misses remain possible.

**Can it run offline?** The assessment workflow is designed for local operation after dependencies and required assets are provisioned. The Python egress guard and self-test do not certify the entire host or native stack. Docker packaging currently has a frontend static-export mismatch.

**Why are model checks missing?** A compatible model, preprocessing, references, runtime dependency, access permission, or budget may be absent. Read the plan and detector reasons before changing settings.

**Can we claim 75% accuracy?** The checked-in result is 6/8 eligible positive scenarios detecting their expected signal. That is scenario-level TPR under a small controlled protocol, not model accuracy or general sample-level detection accuracy.

**Is the clean-control ratio a false-positive rate?** It is material detector alerts per clean sample. The current evidence does not establish one-to-one sample classification needed for conventional FPR. AUROC is also not estimated.

**Does Open report verify a signature?** No. It parses and displays local JSON. Verify the manifest with trusted public key material and check ledger integrity separately.

**Can an administrator bypass approval?** Role rank does not allow the requester to approve or reject their own pending request. Protected deterministic cryptographic failures cannot be changed to ACCEPT.

**Does key rotation make old signatures invalid automatically?** Rotation and revocation have specific trust semantics. They cannot undo content signed before a compromise was identified. Retain historical public keys and evaluate the relevant verification policy.

**Can we add another contributor?** Update the README team cards with the person's agreed name, profile, and actual project contributions. Keep repository contributor credit separate from dataset-source attribution.

## Glossary

| Term | Meaning in VisionX |
| --- | --- |
| Anchor | Independently retained checkpoint reference used when verifying ledger history. |
| Attack Lab | Controlled, seeded scenario generation and evaluation. |
| Capability | A form of available or policy-withheld access needed by a detector. |
| Coverage | Per-attack-class assessment status derived from detector support and execution. |
| Disposition | Policy/governance recommendation: ACCEPT, REVIEW, or QUARANTINE. |
| Evidence digest | Content identifier used to detect changed evidence bytes. |
| Fitness gate | Check that a scenario has valid inputs/ground truth before detector metrics are counted. |
| Profile | Versioned configuration of analysis, access, budgets, detectors, and risk rules. |
| Report manifest | Artifact list with file hashes and, when configured, a signature. |
| Scenario-level TPR | Fraction of eligible positive scenarios detecting the expected signal. |
| Trust root | Public trust information used to evaluate keys, roles, and approved bindings. |
| Two-person rule | Requirement that a sensitive relaxation be decided by another authorized identity. |

If the question concerns a particular run, retain its ID, profile, input digests, execution state, and report rather than answering from a screenshot alone.

---

[14 · Previous](14-demo-guide.md) · [Review readiness](../sih-readiness.md)
