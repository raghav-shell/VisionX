# VisionX synthetic test pack

Use this only for testing; it is not an operational benchmark.

## Contents
- training_mixed: 108? The actual inventory.json is authoritative; it contains mostly-clean multi-contributor samples plus duplicate flooding, duplicate-label conflicts, trigger patches and OOD-like samples.
- reference_clean: trusted clean reference.
- operational_shift: deliberately shifted incoming batch.
- suspect_inputs: clean + trigger-patched inputs.

Ground-truth `.truth.json` files are intentionally OUTSIDE each dataset directory. Do not feed them to detectors.

## Suggested commands

Data assurance:
```bash
visionsentinel scan --dataset training_mixed --profile baseline --name synthetic-data-test --out reports/synthetic-data-test
```

Data + reference + drift:
```bash
visionsentinel scan --dataset training_mixed --reference-dataset reference_clean --incoming operational_shift --profile strict --name synthetic-full-data-test --out reports/synthetic-full-data-test
```

With a compatible model:
```bash
visionsentinel scan --dataset training_mixed --probe reference_clean --suspect-inputs suspect_inputs --model YOUR_MODEL.onnx --profile strict --name synthetic-model-test --out reports/synthetic-model-test
```

Exact findings depend on current profiles, thresholds, encoders, access and scientific prerequisites.
