# VisionSentinel benchmark

## Protocol

Calibration and held-out families are reported separately. A false-positive rate or AUROC is only reported when a negative-control denominator and score vector were supplied; it is never assumed to be zero.

## Scenario results

| Family | Scenario | Tier | TPR (95% CI) | FPR (95% CI) | AUROC (95% CI) | Fitness |
|---|---|---|---|---|---|---|
| clean_control | clean_baseline | evaluation | 0.000 [0.000, 0.000] | 0.003 [0.000, 0.014] | not estimated | PASS |
| operational_covariate_shift | drift_illumination | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | PASS |
| duplicate_flood | duplicate_flood | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | PASS |
| label_flip | label_flip_targeted | evaluation | 1.000 [0.206, 1.000] | not estimated | not estimated | PASS |
| record_modification | ledger_tamper | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | PASS |
| model_substitution | model_swap | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | PASS |
| model_weight_tampering | modified_weights | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | PASS |
| localized_trigger | patch_poison | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | PASS |
| operational_semantic_shift | semantic_shift | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | PASS |
| systematic_mislabel | systematic_mislabel | evaluation | 0.000 [0.000, 0.793] | not estimated | not estimated | FAIL |

## Limits

The current shipped attack scenarios are positive controls. Add adjudicated clean / benign-shift controls for each detector before quoting FPR or AUROC in a competition claim.
