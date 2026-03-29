# NumericVerifier — Final Active Project Map

> Dissertation/viva reference. Only currently active files listed.
> Generated: 2026-03-29 | Branch: feat/react-frontend | Tests: 234 pass, 4 skip

---

## A. FINAL ACTIVE BACKEND FILES

| Path | Purpose | Why Active | Show in Report? |
|------|---------|------------|-----------------|
| `backend/app/main.py` | FastAPI app factory, CORS, route registration | Entry point for uvicorn | Yes — system architecture |
| `backend/app/api/verify.py` | `/verify-only` and `/verify` endpoints | Both API endpoints | Yes — API design |
| `backend/app/api/health.py` | `/health` endpoint | Deployment readiness check | Mention only |
| `backend/app/verifier/router.py` | `route_and_verify()` — orchestrates full pipeline | Central pipeline coordinator | Yes — core architecture |
| `backend/app/verifier/extract.py` | `extract_numeric_claims()` from candidate answer | Pipeline stage 1 | Yes |
| `backend/app/verifier/normalize.py` | `normalize_claims()` — scale/unit normalization | Pipeline stage 2 | Yes |
| `backend/app/verifier/evidence.py` | `ingest_evidence()` — parse table into EvidenceItems | Pipeline stage 3 | Yes |
| `backend/app/verifier/grounding.py` | `ground_claims()` — match claims to evidence | Pipeline stage 4 | Yes |
| `backend/app/verifier/engines/lookup.py` | `verify_lookup()` — direct value matching | Verification engine 1 | Yes |
| `backend/app/verifier/engines/constraints.py` | `verify_constraints()` — period/scale/identity checks | Verification engine 2 | Yes |
| `backend/app/verifier/engines/execution.py` | Shared execution utilities | Supporting engine code | Mention only |
| `backend/app/verifier/engines/pnl_execution.py` | `execute_claim_against_table()`, `run_pnl_checks()` | Verification engine 3 (P&L recomputation) | Yes |
| `backend/app/verifier/engines/finance_formulas.py` | P&L formula definitions (gross margin = revenue - COGS, etc.) | Used by pnl_execution | Yes |
| `backend/app/verifier/signals.py` | `compute_signals()` — aggregate verification into signal vector | ML feature vector | Yes |
| `backend/app/verifier/decision_rules.py` | `make_decision()` — rule-based decision fallback | Fallback when ML off | Yes |
| `backend/app/ml/decision_model.py` | `decide()` — ML decision (XGBoost V6.1) with hard safety gates | ML decision layer | Yes — key contribution |
| `backend/app/verifier/repair.py` | `attempt_repair()` — deterministic answer correction | Repair-and-reverify loop | Yes |
| `backend/app/verifier/report.py` | `generate_report()` — structured report generation | Output formatting | Mention only |
| `backend/app/verifier/audit.py` | `build_claim_audit()`, `build_audit_summary()` | Per-claim traceability | Yes |
| `backend/app/verifier/types.py` | Dataclasses: VerifierSignals, VerificationResult, Decision, etc. | Type definitions | Yes |
| `backend/app/verifier/domain.py` | `classify_table_type()` — P&L detection | Domain routing | Yes |
| `backend/app/verifier/pnl_parser.py` | `parse_pnl_table()` — structured P&L extraction with synonyms | P&L parsing core | Yes |
| `backend/app/verifier/ingestion.py` | `assess_ingestion()` — row label coverage + LLM mapping | Session 4 feature | Yes |
| `backend/app/core/config.py` | Settings: tolerance, thresholds | Configuration | Mention only |
| `backend/app/core/logging.py` | Logging setup | Infrastructure | No |
| `backend/app/eval/logging.py` | `log_run()`, `log_signals()` — audit trail to runs/ | Evaluation logging | Mention only |
| `backend/app/llm/provider.py` | `generate_llm_answer()` — OpenAI integration or stub fallback | LLM answer generation | Yes |
| `backend/app/ingestion/csv_pnl_parser.py` | CSV file ingestion for P&L tables | File upload support | Mention only |
| `backend/app/ingestion/excel_pnl_parser.py` | Excel file ingestion for P&L tables | File upload support | Mention only |

---

## B. FINAL ACTIVE FRONTEND FILES

| Path | Purpose | Show in Report? |
|------|---------|-----------------|
| `frontend/src/App.tsx` | Root component, state management, endpoint routing | Yes |
| `frontend/src/components/InputPanel.tsx` | Question/evidence/answer inputs, Load Example, Verify, Clear | Yes |
| `frontend/src/components/DecisionPanel.tsx` | Decision badge, rationale, repair/ingestion metadata | Yes |
| `frontend/src/components/AuditSignalsPanel.tsx` | Signals grid, coverage bar, claim audit list | Yes |
| `frontend/src/lib/api.ts` | API client — routes `/verify-only` vs `/verify` | Yes |
| `frontend/src/lib/constants.ts` | Apple FY2023 example data | Mention only |
| `frontend/src/lib/parser.ts` | CSV/JSON evidence parser | Mention only |
| `frontend/src/types/api.ts` | TypeScript types matching backend response | Yes |
| `frontend/dist/` | Production build output (exists and verified) | Yes — deployment evidence |

---

## C. FINAL ACTIVE MODEL FILES

| Path | Purpose | Show in Report? |
|------|---------|-----------------|
| `runs/decision_model_v6_1.joblib` | V6.1 XGBClassifier trained model artifact | Yes — primary artifact |
| `runs/feature_schema_v6_1.json` | 10-feature schema for V6.1 | Yes |
| `runs/ml_metrics_v6_1.json` | CV, test accuracy, recall metrics for V6.1 | Yes — primary evidence |
| `runs/label_mapping_v5.json` | Label encoding (ACCEPT=0, FLAG=1, REPAIR=2) | Yes |
| `runs/model_registry.json` | Full model evolution history (V2 through V6.1) | Yes — evolution narrative |

---

## D. FINAL ACTIVE DATA / SIGNAL FILES

| Path | Purpose | Show in Report? |
|------|---------|-----------------|
| `evaluation/signals_v6_1_complete.csv` | Training signals for V6.1 (364 rows) | Yes — training data |
| `evaluation/signals_tatqa_accept_v6.csv` | TAT-QA gold ACCEPT cases used in V6.1 training | Yes — data provenance |
| `evaluation/base_cases_tatqa_pnl_dev.json` | TAT-QA P&L dev set base cases | Mention only |
| `evaluation/base_cases_tatqa_pnl_test.json` | TAT-QA P&L test set base cases | Mention only |
| `evaluation/base_cases_tatqa_pnl_train.json` | TAT-QA P&L train set base cases | Mention only |
| `evaluation/cases_v2.json` | V2+ perturbation/human-labeled cases | Mention only |
| `evaluation/error_injected_cases.json` | Synthetic error injection cases | Yes — evaluation methodology |

---

## E. FINAL ACTIVE EVALUATION FILES

| Path | Purpose | Show in Report? |
|------|---------|-----------------|
| `evaluation/apple_real_world_test.json` | Apple FY2023 real-world eval (20 cases) | Yes |
| `evaluation/apple_llm_eval_20_results.json` | Apple LLM eval results | Yes |
| `evaluation/llm_evaluation_apple_20cases.json` | Apple 20-case LLM eval | Yes |
| `evaluation/llm_evaluation_apple_20cases_adversarial.json` | Adversarial Apple 20-case eval | Yes |
| `evaluation/llm_hard_questions_10cases.json` | Hard questions eval (10 cases) | Yes |
| `evaluation/microsoft_realworld_test.json` | Microsoft real-world eval | Yes |
| `evaluation/ablation_results.csv` | Ablation study results (engine removal) | Yes — contribution analysis |
| `evaluation/ablation_pnl_results.csv` | P&L-specific ablation results | Yes |
| `evaluation/confusion_matrix.csv` | Final confusion matrix | Yes |
| `evaluation/confusion_matrix_ml_full.csv` | ML full confusion matrix | Yes |
| `evaluation/results_summary_ml_full.json` | ML evaluation summary | Yes |
| `evaluation/results_summary_rules_full.json` | Rules evaluation summary | Yes |
| `evaluation/results_summary_rules_no_*.json` | Ablation results (no_constraints, no_execution, no_lookup, no_repair) | Yes |
| `evaluation/gold_verification_metrics.json` | Gold standard metrics | Yes |
| `evaluation/baseline_comparison.json` | Baseline comparison results | Yes |

### Plots for V6.1

| Path | Show in Report? |
|------|-----------------|
| `evaluation/plots/confusion_matrix_v6_1.png` | Yes |
| `evaluation/plots/feature_importance_v6_1.png` | Yes |
| `evaluation/plots/learning_curve_v6_1.png` | Yes |
| `evaluation/plots/permutation_importance_v6_1.png` | Yes |

---

## F. FINAL ACTIVE TEST FILES

| Path | Purpose |
|------|---------|
| `tests/test_api_verify_only.py` | API endpoint tests |
| `tests/test_assess_ingestion.py` | Ingestion layer tests (7 tests) |
| `tests/test_evidence_ingestion.py` | Evidence ingestion tests |
| `tests/test_execution_semantics.py` | Execution engine semantic tests |
| `tests/test_grounding.py` | Grounding tests |
| `tests/test_ingestion.py` | Additional ingestion tests |
| `tests/test_normalize.py` | Normalization tests |
| `tests/test_pnl_parser.py` | P&L parser tests |
| `tests/test_repair_loop.py` | Repair-and-reverify loop tests |
| `tests/test_signals.py` | Signals computation tests |
| `backend/app/tests/test_decision.py` | ML decision model tests |
| `backend/app/tests/test_execution.py` | Execution engine tests |
| `backend/app/tests/test_extract.py` | Claim extraction tests |
| `backend/app/tests/test_grounding.py` | Grounding unit tests |
| `backend/app/tests/test_integration.py` | Integration tests |
| `backend/app/tests/test_normalize.py` | Normalization unit tests |

**Total: 234 passed, 4 skipped** (verified 2026-03-29)

---

## G. FINAL ACTIVE NOTEBOOK / DEMO FILE

| Path | Status |
|------|--------|
| `ml_decision_model.ipynb` | Old V2 training notebook — DEPRECATED for demo |
| `notebooks/FINAL_V6_1_Demo.ipynb` | **Created** — V6.1 demo notebook for viva (see Step 8) |
