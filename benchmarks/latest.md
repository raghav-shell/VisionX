# VisionSentinel benchmark

## Protocol

Positive-control scenarios: 9. Negative-control scenarios: 1.
Eligible for scientific metrics: 9; excluded: 1.
Evaluation tiers: evaluation=10.
TPR unit: scenario; valid positive-control scenarios detecting their manifest-declared expected signal.
Reported clean-control metric: material_alerts_per_clean_sample; material detector findings divided by clean-control samples; not a sample-classification FPR.
Unavailable metrics are reported as not estimated, never as zero or one.

## Scenario results

| Family | Scenario | Tier | TPR (scenario) | Material alerts / clean sample | AUROC | Fitness |
|---|---|---|---|---|---|---|
| clean_control | clean_baseline | evaluation | not eligible | 0.005 | not estimated | PASS |
| operational_covariate_shift | drift_illumination | evaluation | 1.000 | not estimated | not estimated | PASS |
| duplicate_flood | duplicate_flood | evaluation | 0.000 | not estimated | not estimated | PASS |
| label_flip | label_flip_targeted | evaluation | 1.000 | not estimated | not estimated | PASS |
| record_modification | ledger_tamper | evaluation | 1.000 | not estimated | not estimated | PASS |
| model_substitution | model_swap | evaluation | 1.000 | not estimated | not estimated | PASS |
| model_weight_tampering | modified_weights | evaluation | 1.000 | not estimated | not estimated | PASS |
| localized_trigger | patch_poison | evaluation | 1.000 | not estimated | not estimated | PASS |
| operational_semantic_shift | semantic_shift | evaluation | 0.000 | not estimated | not estimated | PASS |
| systematic_mislabel | systematic_mislabel | evaluation | not eligible | not estimated | not estimated | FAIL |

## Outcome counts

| Outcome | Scenarios |
|---|---:|
| detector_miss | 3 |
| detector_success | 6 |
| fitness_failed | 1 |

## Limits

AUROC is not estimated because this run supplied no compatible labelled continuous score vectors containing both classes.
Clean-control alert rates are not interchangeable with conventional sample-level classification FPR.
Only one negative-control scenario was executed; its alert measurement does not generalize across attack families.
