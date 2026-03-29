# NumericVerifier — Deprecated / Old Artifacts

> These files are historical artifacts from earlier model versions and development iterations.
> They are safe to ignore for dissertation submission. Do NOT delete them — they document the evolution.

---

## Old Notebooks

| File | Why Deprecated |
|------|----------------|
| `ml_decision_model.ipynb` | Trains V2 RandomForest model. V6.1 is the final model. Retained for provenance but not shown in viva. |

---

## Old Model Versions (V2 through V6)

All superseded by V6.1 XGBClassifier. See `runs/model_registry.json` for full deprecation reasons.

| Artifact | Version | Algorithm | Why Deprecated |
|----------|---------|-----------|----------------|
| `runs/decision_model_v2.joblib` | V2 | RandomForest | Tautological — labels derived from same rules used for evaluation |
| `runs/feature_schema_v2.json` | V2 | — | See above |
| `runs/label_mapping_v2.json` | V2 | — | See above |
| `runs/ml_metrics_v2.json` | V2 | — | See above |
| `runs/decision_model_v3.joblib` | V3 | LogisticRegression | Tautological — trained and tested on same evaluation protocol signals |
| `runs/feature_schema_v3.json` | V3 | — | See above |
| `runs/label_mapping_v3.json` | V3 | — | See above |
| `runs/ml_metrics_v3.json` | V3 | — | See above |
| `runs/decision_model_v4.joblib` | V4 | LogisticRegression | Superseded by V4b (zero-variance features removed) |
| `runs/feature_schema_v4.json` | V4 | — | See above |
| `runs/label_mapping_v4.json` | V4 | — | See above |
| `runs/ml_metrics_v4.json` | V4 | — | See above |
| `runs/label_encoder_v4.joblib` | V4 | — | Old label encoder format |
| `runs/decision_model_v4b.joblib` | V4b | LogisticRegression | Superseded by V5 GBM |
| `runs/feature_schema_v4b.json` | V4b | — | See above |
| `runs/decision_model_v5.joblib` | V5 | GBM | Superseded by V5b, then V6 |
| `runs/feature_schema_v5.json` | V5 | — | See above |
| `runs/ml_metrics_v5.json` | V5 | — | See above |
| `runs/label_encoder_v5.joblib` | V5 | — | Old label encoder format |
| `runs/decision_model_v5b.joblib` | V5b | GBM | Superseded by V6 |
| `runs/feature_schema_v5b.json` | V5b | — | See above |
| `runs/decision_model_v6.joblib` | V6 | XGBClassifier | Superseded by V6.1 (balanced training data) |
| `runs/feature_schema_v6.json` | V6 | — | See above |
| `runs/ml_metrics_v6.json` | V6 | — | See above |

**Note:** `runs/label_mapping_v5.json` is STILL ACTIVE — used by V6.1 (same label encoding).

---

## Old Datasets / Signal Files

| File | Why Deprecated |
|------|----------------|
| `runs/signals.csv` | Runtime log signals (old format) — not training data |
| `runs/signals_v2.csv` | Runtime log signals (V2 format) — not training data |
| `evaluation/signals_v4_accept.csv` | V4 ACCEPT training signals |
| `evaluation/signals_v4_complete.csv` | V4 complete training set |
| `evaluation/signals_v4_flag.csv` | V4 FLAG training signals |
| `evaluation/signals_v5_accept.csv` | V5 ACCEPT training signals |
| `evaluation/signals_v5_ambiguous.csv` | V5 ambiguous cases |
| `evaluation/signals_v5_complete.csv` | V5 complete training set |
| `evaluation/signals_v5_flag.csv` | V5 FLAG training signals |
| `evaluation/signals_v6_complete.csv` | V6 complete training set — superseded by V6.1 |
| `evaluation/signals_pnl_dev.csv` | TAT-QA P&L dev split signals |
| `evaluation/signals_pnl_test.csv` | TAT-QA P&L test split signals |
| `evaluation/signals_pnl_train.csv` | TAT-QA P&L train split signals |
| `evaluation/tatqa_pnl_gold_dev_signals.csv` | TAT-QA gold dev signals |
| `evaluation/tatqa_pnl_gold_test_signals.csv` | TAT-QA gold test signals |
| `evaluation/tatqa_pnl_gold_train_signals.csv` | TAT-QA gold train signals |
| `evaluation/tatqa_pnl_llm_signals.csv` | TAT-QA LLM-generated signals |
| `evaluation/tier3_ambiguous_LABELED.csv` | Tier-3 labeled ambiguous cases |
| `evaluation/tier3_ambiguous_UNLABELED.csv` | Tier-3 unlabeled |
| `evaluation/tier3_tatqa_ambiguous_UNLABELED.csv` | TAT-QA tier-3 unlabeled |

**Active:** Only `evaluation/signals_v6_1_complete.csv` and `evaluation/signals_tatqa_accept_v6.csv`.

---

## Old Evaluation Outputs

| File | Why Deprecated |
|------|----------------|
| `evaluation/ml_v4_findings.json` | V4 model analysis |
| `evaluation/ml_v5_findings.json` | V5 model analysis |
| `evaluation/evaluation_after_change_a.json` | Intermediate evaluation snapshot |
| `evaluation/evaluation_final_baseline.json` | Pre-V6 baseline |
| `evaluation/error_injection_metrics.json` | Error injection metrics (may be V4/V5 era) |
| `evaluation/sample_audit_log_TC1.json` | Sample audit log — illustrative only |
| `evaluation/results_summary.json` | Undated summary — likely pre-V6 |
| `evaluation/confusion_matrix_rules_*.csv` | Rules ablation confusion matrices — useful for ablation analysis but tied to earlier models |

---

## Old Plots (for deprecated models)

| File | Why |
|------|-----|
| `evaluation/plots/confusion_matrix_v5.png` | V5 model |
| `evaluation/plots/confusion_matrix_v5b.png` | V5b model |
| `evaluation/plots/confusion_matrix_v6.png` | V6 model |
| `evaluation/plots/feature_importance_v5.png` | V5 model |
| `evaluation/plots/feature_importance_v6.png` | V6 model |
| `evaluation/plots/learning_curve_v5.png` | V5 model |
| `evaluation/plots/learning_curve_v6.png` | V6 model |
| `evaluation/plots/permutation_importance_v5.png` | V5 model |
| `evaluation/plots/permutation_importance_v6.png` | V6 model |
| `evaluation/plots/shap_flag_v6.png` | V6 SHAP analysis |
| `evaluation/plots/signal_separation_v5.png` | V5 signal analysis |
| `evaluation/plots/signal_separation_v6.png` | V6 signal analysis |

**Active plots:** Only `*_v6_1.png` files.

---

## Old Docs / Summaries

| File | Notes |
|------|-------|
| `EVALUATION_RESULTS.md` | May reference old model versions |
| `NUMERIC_VERIFIER_FULL_TECHNICAL_AUDIT.md` | Pre-Session 4 audit |
| `PROJECT_REVIEW_AND_USER_GUIDE.md` | May reference old architecture |
| `context.md` | Development context notes |
| `docs/evaluation.md` | May reference old eval numbers |
| `docs/evaluation_report.md` | Old evaluation report |
| `docs/ml_context.md` | ML development context |
| `docs/pnl_extension_context.md` | P&L extension context |
| `docs/llm_integration_context.md` | LLM integration context |
| `docs/final_summary.md` | Pre-Session 4 summary |

**Active docs:** `FINAL_*.md` files at repo root are the authoritative references.
