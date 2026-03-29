# NumericVerifier — Final Model Trace

> Complete provenance for the active ML model. All numbers sourced directly from artifact files.

---

## Active Model: V6.1 XGBClassifier

| Property | Value | Source |
|----------|-------|--------|
| **Model artifact** | `runs/decision_model_v6_1.joblib` | File exists |
| **Feature schema** | `runs/feature_schema_v6_1.json` | File exists |
| **Label mapping** | `runs/label_mapping_v5.json` | Shared with V5/V6 |
| **Training signals** | `evaluation/signals_v6_1_complete.csv` | 364 rows |
| **CV metrics** | `runs/ml_metrics_v6_1.json` | File exists |

---

## Exact Metrics (from `runs/ml_metrics_v6_1.json`)

| Metric | Value |
|--------|-------|
| **Train accuracy** | 0.9961 (99.61%) |
| **Validation accuracy** | 0.9818 (98.18%) |
| **Test accuracy** | 0.9818 (98.18%) |
| **CV mean** | 0.9890 (98.90%) |
| **CV std** | 0.0104 |
| **CV scores** | [1.0, 1.0, 0.9863, 0.9863, 0.9722] |
| **FLAG recall** | 0.9850 (98.50%) |
| **ACCEPT recall** | 0.9932 (99.32%) |
| **REPAIR recall** | 1.0000 (100%) |
| **Overfit gap** | 0.0142 (1.42%) |
| **Leakage detected** | false |
| **Gate passed** | true |

---

## Training Data

| Property | Value |
|----------|-------|
| **Training rows** | 364 |
| **FLAG cases** | 200 |
| **ACCEPT cases** | 148 |
| **REPAIR cases** | 16 |
| **Label source** | perturbation_plus_cases_v2_plus_tatqa_gold |

### Data composition
- **Perturbation cases** (cases_v2.json): Synthetic error injection + human-labeled cases
- **TAT-QA gold ACCEPT cases** (signals_tatqa_accept_v6.csv): 100 ACCEPT cases from TAT-QA gold standard (with imputed confidence scores)
- **FLAG cap**: Capped at 200 to balance class distribution

---

## 10 Features (from `runs/feature_schema_v6_1.json`)

| # | Feature | Description |
|---|---------|-------------|
| 1 | `unsupported_claims_count` | Claims with no evidence support |
| 2 | `coverage_ratio` | Fraction of claims grounded in evidence |
| 3 | `max_relative_error` | Largest relative error across claims |
| 4 | `mean_relative_error` | Average relative error across claims |
| 5 | `scale_mismatch_count` | Claims with scale disagreement (K/M/B) |
| 6 | `ambiguity_count` | Ambiguous grounding matches |
| 7 | `pnl_identity_fail_count` | P&L identity check failures (e.g., revenue - COGS != gross margin) |
| 8 | `pnl_period_strict_mismatch_count` | Period mismatch violations |
| 9 | `grounding_confidence_score` | Weighted grounding confidence (0-1) |
| 10 | `unverifiable_claim_count` | Claims that cannot be verified against table |

### Dropped from V5
- `near_tolerance_flag` — leakage risk (too correlated with decision boundary)
- `claim_count` — leakage risk (correlates with case complexity, not correctness)

### Added vs V5b
- `unverifiable_claim_count` — captures claims that reference values not in the table

---

## Train/Val/Test Split

The training used sklearn's `train_test_split` with stratification on the label column. Based on the metrics file:
- Train set: ~254 rows (70%)
- Val/Test set: ~55 rows each (15%/15%)
- 5-fold stratified cross-validation on the train set

---

## Ablation Evidence

| File | Content |
|------|---------|
| `evaluation/ablation_results.csv` | Engine removal ablation (no_lookup, no_constraints, no_execution, no_repair) |
| `evaluation/ablation_pnl_results.csv` | P&L-specific ablation results |
| `evaluation/results_summary_rules_no_constraints.json` | Rules without constraints |
| `evaluation/results_summary_rules_no_execution.json` | Rules without execution |
| `evaluation/results_summary_rules_no_lookup.json` | Rules without lookup |
| `evaluation/results_summary_rules_no_repair.json` | Rules without repair |

---

## Plots for V6.1

| File | Shows |
|------|-------|
| `evaluation/plots/confusion_matrix_v6_1.png` | 3-class confusion matrix |
| `evaluation/plots/feature_importance_v6_1.png` | XGBoost feature importance |
| `evaluation/plots/learning_curve_v6_1.png` | Learning curve (train vs val) |
| `evaluation/plots/permutation_importance_v6_1.png` | Permutation importance |

---

## Model Evolution: Why V6.1 Replaced V6

From `runs/model_registry.json`:
> "balanced dataset -- TAT-QA gold ACCEPT cases restored (100), FLAG capped at 200"

V6 had an imbalanced training set that over-represented FLAG cases. V6.1 restored 100 TAT-QA gold ACCEPT cases and capped FLAG at 200, yielding a more balanced 200:148:16 (FLAG:ACCEPT:REPAIR) distribution.

## Why V6 Replaced V5

From `runs/model_registry.json`:
- Algorithm upgrade: GradientBoostingClassifier -> XGBClassifier
- New signal: `unverifiable_claim_count`
- Dropped: `near_tolerance_flag` (leakage), `claim_count` (leakage)
- Training expanded from 260 to 370 cases (V6) / 364 cases (V6.1)

---

## Hard Safety Gates (from `decision_model.py`)

The ML model is NEVER called when any of these conditions is true:
1. `pnl_missing_baseline_count > 0` — missing baseline data
2. `pnl_period_strict_mismatch_count > 0` — period mismatch violation
3. `pnl_table_detected == 0` — not a P&L table

These gates return FLAG unconditionally, ensuring the ML model cannot override critical safety checks.

---

## Post-ML ACCEPT Override (from `decision_model.py`)

When ML predicts REPAIR or FLAG but ALL of the following are true, the decision is overridden to ACCEPT:
- `unsupported_claims_count == 0`
- `coverage_ratio >= threshold`
- `pnl_missing_baseline_count == 0`
- `pnl_period_strict_mismatch_count == 0`
- `scale_mismatch_count == 0`
- `period_mismatch_count == 0`
- `recomputation_fail_count == 0`

This handles incomplete real-world tables where P&L identity checks fail due to missing rows (e.g., no G&A expense row), not because the answer is wrong.

---

## Caveats

1. **REPAIR recall of 100% is based on only 16 REPAIR cases** — not statistically robust. Report as "100% on 16 cases" with caveat about small sample size.
2. **TAT-QA ACCEPT cases use imputed confidence scores** — 100 ACCEPT cases from TAT-QA have `grounding_confidence_score` values that were imputed (not computed from the full pipeline). This is documented but should be noted as a limitation.
3. **Overfit gap is small (1.42%)** but the dataset is synthetic/semi-synthetic. Real-world generalization is not empirically validated beyond the Apple/Microsoft/hard-Q evaluations.
4. **No held-out test set from a different distribution** — all data comes from TAT-QA or synthetic perturbation. Cross-domain generalization is unknown.
