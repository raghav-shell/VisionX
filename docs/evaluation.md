# Evaluation protocol

`visionsentinel benchmark` writes `benchmarks/latest.json` and `benchmarks/latest.md`. Both artifacts are generated from the same `BenchmarkReport`, so scenario counts, evaluation tiers, outcomes, eligibility, and metric values are not maintained manually in separate documents.

The report derives positive-control and negative-control counts from the checked-in manifests and records which scenarios were eligible for scientific metrics. Invalid manifests, generation failures, invalid ground truth, fitness failures, and scan execution failures are excluded from metric denominators. A valid detector miss remains an observation for scenario-level TPR.

TPR is explicitly scenario-level: the observation is whether a valid positive-control scenario detected its manifest-declared expected signal. The clean-control metric is reported as material alerts per clean sample because the current evidence does not establish sample-level one-to-one false-alarm matching; it must not be interpreted as conventional sample-classification FPR. Its confidence interval is therefore unavailable unless compatible observation units are supplied.

AUROC is reported only when compatible labelled continuous score vectors contain both classes. Undefined, invalid, or unavailable metrics are serialized as `null` and rendered as **not estimated**; they are never replaced by zero or one.

To make a scientific detector claim, add adjudicated clean and benign-shift controls per detector family, freeze calibration before held-out evaluation, retain false-positive examples with adjudication, and publish counts and confidence intervals whose denominators match the stated observation unit.
