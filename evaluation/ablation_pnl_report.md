# Ablation Report (P&L-only)

Baseline: **full_rules** (accuracy=42.59%, false_accept=0.00%)

| Config | Accuracy | False Accept | FLAG Recall | Acc Delta | FA Delta |
|--------|----------|--------------|-------------|-----------|----------|
| full_rules | 42.59% | 0.00% | 0.00% | +0.00% | +0.00% |
| no_constraints | 42.59% | 0.00% | 0.00% | +0.00% | +0.00% |
| no_execution | 33.33% | 0.00% | 0.00% | -9.26% | +0.00% |
| no_lookup | 42.59% | 0.00% | 0.00% | +0.00% | +0.00% |
| no_repair | 42.59% | 0.00% | 0.00% | +0.00% | +0.00% |
| ml_full | 42.59% | 0.00% | 0.00% | +0.00% | +0.00% |

## Deltas

- false ACCEPT: increase = worse
- gold ACCEPT: decrease = worse
- FLAG recall: decrease = worse
- latency: reported in ms

