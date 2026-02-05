# ML Decision Model v2 (P&L-only)

## Role and limits

- **What the model does:** Predicts ACCEPT / REPAIR / FLAG from verifier signals only (no raw text, no question, no evidence).
- **When it is used:** Only in the "soft region" after hard safety gates. If any of the following are true, the system returns FLAG immediately and the model is **not** called:
  - `pnl_missing_baseline_count > 0` (YoY/baseline missing)
  - `pnl_period_strict_mismatch_count > 0` (period mismatch)
  - `pnl_table_detected == 0` (non-P&L)
- **Why no raw text:** Decisions are based solely on numeric signals produced by the P&L verifier. Using question or LLM output would introduce leakage and non-reproducibility; the design keeps inputs to the decider as structured, auditable signals only.
- **Why hard rules remain:** Finance verification requires that certain conditions (missing baseline, wrong period, non-P&L table) always result in FLAG. The ML model is not allowed to override these; it only decides in the remaining cases.
- **Safety:** This design is appropriate for finance verification because (1) high-risk cases are always FLAG by rule, (2) the model sees only signals, and (3) if the model is unavailable, the system falls back to the rule-based decision.

## Training

- **Dataset:** `runs/signals_v2.csv` (schema v2, P&L-only; each row from a real LLM + verifier run).
- **Features:** All signal columns in fixed order (see `feature_schema_v2.json`). No `decision` or derived rule logic as input.
- **Label:** `decision` (ACCEPT / REPAIR / FLAG), produced deterministically by `decision_rules.py` at data collection time.
- **Split:** Stratified 80/20 train/validation. Class weight balanced.
- **Models:** Multinomial Logistic Regression and Random Forest; best selected by macro F1.

## Artifacts

| File                       | Purpose                                        |
| -------------------------- | ---------------------------------------------- |
| `decision_model_v2.joblib` | Trained pipeline (StandardScaler + classifier) |
| `feature_schema_v2.json`   | Ordered feature list for inference             |
| `label_mapping_v2.json`    | Index ↔ ACCEPT/REPAIR/FLAG                     |
| `ml_metrics_v2.json`       | Metrics and confusion matrix                   |
| `ml_readme_v2.md`          | This file                                      |

## This run

- **Best model:** RandomForest
- **Macro F1:** 1.0000
- **Classes:** ['ACCEPT', 'FLAG', 'REPAIR']
- **Confusion matrix (val):**

```
  ACCEPT    FLAG  REPAIR
ACCEPT      22       0       0
  FLAG       0      17       0
REPAIR       0       0      11
```

## Runtime

- Set `USE_ML_DECIDER=true` to use the ML model after hard gates.
- Set `USE_ML_DECIDER=false` (default) for rule-based decision only.
- If the model file is missing or prediction fails, the backend falls back to rule-based decision.
- **Backend must have ML deps:** From `backend/`: `pip install -r requirements.txt` (includes joblib, numpy, scikit-learn) so the server can load `decision_model_v2.joblib`. Otherwise you will see "Decision path: rules (ML model not loaded)."
- **Logging:** Each request logs which path was used: `Decision path: rules (USE_ML_DECIDER=false)`, `Decision path: rules (ML model not loaded)`, `Decision path: hard-gate FLAG (no ML call)`, or `Decision path: ML (v2 model). decision=ACCEPT|REPAIR|FLAG`.
