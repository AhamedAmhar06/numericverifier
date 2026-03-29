# NumericVerifier — Final Evidence Pack

> One-page reference for viva preparation and dissertation writing.
> All numbers verified from source files on 2026-03-29.

---

## What to Show in Viva

| Item | Path / Command |
|------|----------------|
| **Demo notebook** | `notebooks/FINAL_V6_1_Demo.ipynb` |
| **Start backend** | `cd backend && USE_ML_DECIDER=true uvicorn app.main:app --port 8001` |
| **Start frontend** | `cd frontend && npm run dev` (or serve `frontend/dist/`) |
| **Key metric** | V6.1 CV 98.9%, test accuracy 98.18%, 234 tests pass |
| **API docs** | `http://localhost:8001/docs` (Swagger UI) |

---

## What to Cite in Report

### Model Evidence
| What | File |
|------|------|
| ML metrics | `runs/ml_metrics_v6_1.json` |
| Feature schema | `runs/feature_schema_v6_1.json` |
| Model registry | `runs/model_registry.json` |
| Training data | `evaluation/signals_v6_1_complete.csv` (364 rows) |

### Evaluation Evidence
| What | File |
|------|------|
| Apple 20-case eval | `evaluation/llm_evaluation_apple_20cases.json` |
| Apple adversarial eval | `evaluation/llm_evaluation_apple_20cases_adversarial.json` |
| Hard questions 10-case | `evaluation/llm_hard_questions_10cases.json` |
| Microsoft real-world | `evaluation/microsoft_realworld_test.json` |
| Ablation results | `evaluation/ablation_results.csv` |
| Baseline comparison | `evaluation/baseline_comparison.json` |
| Gold verification | `evaluation/gold_verification_metrics.json` |

### Plots (V6.1 only)
| What | File |
|------|------|
| Confusion matrix | `evaluation/plots/confusion_matrix_v6_1.png` |
| Feature importance | `evaluation/plots/feature_importance_v6_1.png` |
| Learning curve | `evaluation/plots/learning_curve_v6_1.png` |
| Permutation importance | `evaluation/plots/permutation_importance_v6_1.png` |

### Tests
- **234 passed, 4 skipped** across `tests/` and `backend/app/tests/`
- Run: `cd "/path/to/numericverifier" && python3 -m pytest tests/ backend/app/tests/ -q`

---

## Backend Files to Cite (Top 7)

| File | One-line Purpose |
|------|-----------------|
| `backend/app/verifier/router.py` | Pipeline orchestrator — extract, normalize, ground, verify, decide |
| `backend/app/ml/decision_model.py` | ML decision layer with hard safety gates + XGBoost V6.1 |
| `backend/app/verifier/engines/pnl_execution.py` | P&L recomputation engine (formula verification) |
| `backend/app/verifier/signals.py` | Signal vector computation (10 features for ML) |
| `backend/app/verifier/repair.py` | Deterministic repair-and-reverify loop |
| `backend/app/verifier/ingestion.py` | LLM-assisted row label mapping (Session 4) |
| `backend/app/verifier/pnl_parser.py` | P&L table parsing with synonym dictionary |

---

## Frontend Summary

- **Stack:** React 18 + TypeScript 5 + Vite 5
- **Build status:** PASSING (zero errors, `frontend/dist/` exists)
- **Components:** InputPanel, DecisionPanel, AuditSignalsPanel
- **Features:** Auto-routing (`/verify-only` vs `/verify`), decision badge, signals grid, claim audit, ingestion metadata

---

## What Old Files to Ignore

- **Old model artifacts:** `runs/decision_model_v{2,3,4,4b,5,5b,6}.joblib` — all superseded by V6.1
- **Old signals CSVs:** `evaluation/signals_v{4,5,6}_*.csv` — training data for deprecated models
- **Old notebook:** `ml_decision_model.ipynb` — trains V2, not V6.1
- **Old plots:** `evaluation/plots/*_v{5,5b,6}.png` — for deprecated models
- **Old docs:** `context.md`, `EVALUATION_RESULTS.md`, `NUMERIC_VERIFIER_FULL_TECHNICAL_AUDIT.md` — pre-Session 4

See `DEPRECATED_OR_OLD_ARTIFACTS.md` for the full inventory.
