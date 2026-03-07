# Ablation Study Report

Baseline: **rules_full** (accuracy=84.52%, false_accept=19.44%)

| Config | Accuracy | False Accept | Repair Success | Acc Delta | FA Delta |
|--------|----------|--------------|----------------|-----------|----------|
| rules_full | 84.52% | 19.44% | 0.00% | +0.00% | +0.00% |
| rules_no_execution | 84.52% | 19.44% | 0.00% | +0.00% | +0.00% |
| rules_no_constraints | 75.00% | 58.33% | 0.00% | -9.52% | +38.89% |
| rules_no_lookup | 84.52% | 19.44% | 0.00% | +0.00% | +0.00% |
| rules_no_repair | 84.52% | 19.44% | 0.00% | +0.00% | +0.00% |
| ml_full | 84.52% | 36.11% | 0.00% | +0.00% | +16.67% |

## Observations

- Disabling lookup reduces grounding coverage and accuracy.
- Disabling constraints removes period/scale checks, potentially increasing false accepts.
- Disabling execution removes P&L identity and formula checks.
- Disabling repair prevents automatic correction of recoverable errors.
- ML mode uses the trained classifier after hard safety gates.
