# Evaluation protocol

`visionsentinel benchmark` writes `benchmarks/latest.json` and `benchmarks/latest.md`. Results retain scenario, attack family, calibration/evaluation/held-out tier, TPR and Wilson interval, detector notes, and fitness status.

The shipped scenario suite is positive-control evidence. It does not have an adjudicated clean-control denominator, so FPR and AUROC are marked **not estimated** rather than reported as zero or one. To make a scientific detector claim, add clean and benign-shift controls per detector family, freeze calibration before held-out evaluation, retain false-positive examples with adjudication, and publish counts/confidence intervals.
