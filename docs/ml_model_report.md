# ML Decision Model Report

## Objective

Train a supervised classifier to predict ACCEPT / REPAIR / FLAG from verifier signals. The primary safety objective is to **minimize false ACCEPT** (a case incorrectly accepted when it should be flagged or repaired).

## Feature Space

The model uses **13 numeric features** derived from the verification pipeline signals (schema v2). The `schema_version` field is excluded from the feature vector and used only as a metadata assertion.

| Feature | Description |
|---------|-------------|
| unsupported_claims_count | Claims not grounded in evidence |
| coverage_ratio | Fraction of value claims supported |
| recomputation_fail_count | Failed arithmetic re-checks |
| max_relative_error | Worst relative error |
| mean_relative_error | Average relative error |
| scale_mismatch_count | Scale disagreements |
| period_mismatch_count | Period disagreements |
| ambiguity_count | Ambiguous grounding matches |
| pnl_table_detected | P&L table present (0/1) |
| pnl_identity_fail_count | Accounting identity violations |
| pnl_margin_fail_count | Margin range violations |
| pnl_missing_baseline_count | Missing YoY baseline |
| pnl_period_strict_mismatch_count | Strict period mismatch |

No raw text, evidence content, or candidate answers are used as features.

## Training Pipeline

1. **Imputation:** `SimpleImputer(strategy="constant", fill_value=0)` ensures missing signal values default to zero.
2. **Scaling:** `StandardScaler` normalizes features to zero mean and unit variance.
3. **Models evaluated:** Logistic Regression (multinomial, balanced class weights) and Random Forest (100 estimators, balanced class weights).
4. **Selection criterion:** Best 5-fold stratified cross-validation macro F1.
5. **Calibration:** `CalibratedClassifierCV(method="sigmoid", cv=3)` applied to the selected model to produce calibrated probability estimates.
6. **Data split:** 80/20 stratified train/validation.

## Safety Design

- **Hard safety gates** in `decision_model.py` ensure that critical P&L violations (missing baseline, period strict mismatch, non-P&L table) always return FLAG regardless of the classifier output.
- **Calibrated probabilities** enable threshold-based decision making if needed to further reduce false ACCEPT rate.
- **Class weighting** (balanced) prevents the model from favoring the majority class at the expense of FLAG recall.

## Artifacts

- `runs/decision_model_v2.joblib` -- Calibrated pipeline
- `runs/feature_schema_v2.json` -- Feature order (13 features)
- `runs/label_mapping_v2.json` -- Index-to-label mapping
- `runs/ml_metrics_v2.json` -- Metrics, CV scores, dataset hash, sklearn version

## Retraining

Run `python scripts/train_ml_decision_v2.py` to retrain from `runs/signals_v2.csv`. Artifacts in `runs/` are overwritten. The backend loads the updated model on next startup when `USE_ML_DECIDER=true`.

---

## v3 Model (P&L-only, Safety-First)

**Objective:** Minimize False ACCEPT subject to FLAG recall >= 0.95.

**Training:**
- Logistic Regression only (no Random Forest)
- Pipeline: `SimpleImputer(strategy="median")` -> `StandardScaler` -> `LogisticRegression`
- `CalibratedClassifierCV(method="sigmoid", cv=3)`
- Train on `evaluation/signals_pnl_train.csv`
- Tune threshold on `evaluation/signals_pnl_dev.csv`
- Final report on `evaluation/signals_pnl_test.csv` only

**Threshold rationale:** Search over P(FLAG) thresholds; select the one that achieves FLAG recall >= 0.95 while minimizing False ACCEPT rate.

**Artifacts:**
- `runs/decision_model_v3.joblib` -- Pipeline + threshold + label encoder
- `runs/feature_schema_v3.json`
- `runs/label_mapping_v3.json`
- `runs/ml_metrics_v3.json`

**Usage:** Set `ML_MODEL_VERSION=v3` (and `USE_ML_DECIDER=true`) to load v3. Default remains v2.
