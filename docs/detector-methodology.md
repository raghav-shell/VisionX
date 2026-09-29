# Detector methodology

Each detector declares required capabilities before execution. The planner records `READY`, `DEGRADED`, or unavailable status, then coverage is derived from what actually ran. Findings are indicators with evidence and limitations, not automatic proof of compromise.

- Data assurance examines duplicate/near-duplicate structure, metadata anomalies, label consistency, localized triggers, and contributor concentration.
- Model assurance binds artifact, parameters, preprocessing, and graph identity; optional behavioural probes and trigger analyses require corresponding model access.
- Drift compares incoming data to a reference using interpretable image axes, semantic representations when available, and distribution tests.
- Provenance verifies canonical signed records, chain order, checkpoints, anchors, model bindings, and input bindings.

Thresholds live in versioned profiles. Calibration data must be separated from held-out attack families. See `evaluation.md` for the benchmark reporting policy.
