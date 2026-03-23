# Contribution Checklist

Maps each research contribution to implementation, tests, and evaluation evidence.

## 1. Claim-Centric Numeric Verification

- **Implementation:** `backend/app/verifier/extract.py` (regex-based claim extraction), `backend/app/verifier/types.py` (NumericClaim dataclass)
- **Tests:** `tests/test_normalize.py`, `backend/app/tests/test_extract.py`
- **Evidence:** Each claim is individually grounded, verified, and reported in the API response (`claims`, `verification` arrays).

## 2. Context-Aware Decimal Normalization

- **Implementation:** `backend/app/verifier/normalize.py` (Decimal-based normalization, BPS, scale, currency, approximate hedges, table-level scale detection)
- **Types:** `NumericClaim` extended with `value_decimal`, `unit_type`, `scale_label`, `currency`, `period`, `tolerance_abs`, `tolerance_rel`, `approximate`
- **Tests:** `tests/test_normalize.py` (25 tests covering scale K/M/B, percent, BPS, currency, period, approximate, table-level scale, Decimal precision, negatives)
- **Evidence:** Evaluation metrics show improved arithmetic accuracy from context-aware parsing.

## 3. Context-Aware Grounding

- **Implementation:** `backend/app/verifier/grounding.py` (composite scoring: numeric proximity + period match + unit match + line item match)
- **Types:** `GroundingMatch` extended with `confidence`, `confidence_margin`
- **Tests:** `tests/test_grounding.py` (12 tests: exact match, period bonus, line item bonus, unit type hard fail, ambiguity, confidence margin)
- **Evidence:** Reduced ambiguous grounding and improved period-correct grounding in evaluation.

## 4. Semantically Constrained Execution Engine

- **Implementation:** `backend/app/verifier/engines/finance_formulas.py` (yoy_growth, margin, identity checks), `backend/app/verifier/engines/pnl_execution.py` (claim-level semantic execution)
- **Types:** `VerificationResult.execution_confidence` (high/medium/low)
- **Tests:** `tests/test_execution_semantics.py` (14 tests: formulas, claim-level execution, identity, growth, margin, missing period)
- **Evidence:** Ablation study shows accuracy delta when execution engine is disabled.

## 5. Deterministic Repair + Re-Verify Loop

- **Implementation:** `backend/app/verifier/repair.py` (4 repair strategies: grounded replacement, recomputation, scale correction, margin recomputation)
- **Router integration:** `options.enable_repair = True` triggers repair loop with `max_repair_depth=1`
- **Tests:** `tests/test_repair_loop.py` (6 tests: value replacement, no-change, execution replacement, metadata, multiple claims, integration)
- **Evidence:** Repair success rate metric in evaluation; ablation comparison (rules_full vs rules_no_repair).

## 6. Typed Violation Codes + Signal Hygiene

- **Implementation:** `backend/app/verifier/types.py` (Violation dataclass, V_SCALE_MISMATCH, V_PERIOD_MISMATCH, etc.), `backend/app/verifier/signals.py` (counting by Violation.code)
- **Tests:** `tests/test_signals.py` (11 tests: coverage, scale/period/PNL strict counting, temporal exclusion, legacy fallback)
- **Evidence:** Signals are now deterministically derived from typed codes, eliminating substring fragility.

## 7. Signal-Based Decision Model (Rules + ML)

- **Implementation:** `backend/app/verifier/decision_rules.py` (rule-based), `backend/app/ml/decision_model.py` (ML with hard gates and calibration)
- **Training:** `scripts/train_ml_decision_v2.py` (imputer, scaler, CV, CalibratedClassifierCV, 13 features)
- **Tests:** `backend/app/tests/test_decision.py`
- **Evidence:** `runs/ml_metrics_v2.json`, ablation comparison (rules_full vs ml_full), `docs/ml_model_report.md`

## 8. Evaluation Framework + Ablation Study

- **Dataset:** `evaluation/cases_v2.json` (80+ cases across 8 categories)
- **Runner:** `evaluation/run_eval.py` (accuracy, false accept rate, repair success, per-class F1, latency)
- **Ablation:** `evaluation/run_ablation.py` (6 configurations)
- **Outputs:** `evaluation/results_summary.json`, `evaluation/confusion_matrix.csv`, `evaluation/metrics.md`, `evaluation/ablation_results.csv`, `evaluation/ablation_report.md`

## 9. Documentation

- `docs/system_overview.md` -- Pipeline architecture and known gaps
- `docs/request_examples.md` -- Valid API request examples
- `docs/ml_model_report.md` -- Model selection, safety objective, training pipeline
- `docs/contribution_checklist.md` -- This file
- `docs/how_to_run.md` -- Reproduction instructions
