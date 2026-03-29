# NumericVerifier — Safe Claims for Dissertation

> These claims are verified from source files and can be stated in the dissertation without caveats.

---

## ML Model V6.1 — Verified Metrics

Source: `runs/ml_metrics_v6_1.json`

- V6.1 XGBClassifier achieves **98.18% test accuracy** on a held-out test set
- 5-fold stratified cross-validation mean: **98.90%** (std: 0.0104)
- CV fold scores: 100%, 100%, 98.63%, 98.63%, 97.22%
- FLAG recall: **98.50%** (on 200 FLAG training cases)
- ACCEPT recall: **99.32%** (on 148 ACCEPT training cases)
- Overfit gap: **1.42%** (train accuracy 99.61% vs test accuracy 98.18%)
- No leakage detected (leakage_detected: false)
- Model uses **10 features** (listed in `runs/feature_schema_v6_1.json`)
- Trained on **364 labeled cases** (200 FLAG, 148 ACCEPT, 16 REPAIR)

## Model Evolution — Verified from Registry

Source: `runs/model_registry.json`

- 7 model versions developed (V2 through V6.1)
- V2 and V3 were tautological (deprecated)
- V4/V4b used LogisticRegression with perturbation+human labels
- V5 introduced GBM with near_tolerance_flag + grounding_confidence_score
- V6 upgraded to XGBClassifier, added unverifiable_claim_count, dropped leaky features
- V6.1 balanced the training set (TAT-QA gold ACCEPT cases restored)

## Test Suite — Verified by Running

- **234 tests pass, 4 skipped** (pytest, verified 2026-03-29)
- Tests cover: extraction, normalization, grounding, execution, signals, decision, repair, ingestion, API, integration

## Frontend — Verified by Build

- React 18 + TypeScript 5 + Vite 5 build succeeds with **zero errors**
- `frontend/dist/` exists with production bundle
- Components: InputPanel, DecisionPanel, AuditSignalsPanel
- Correct API routing: `/verify-only` (with answer) vs `/verify` (LLM generates)

## Architecture — Verified from Code

- Pipeline: extract -> normalize -> ground -> lookup -> constraints -> execution -> signals -> ML decision
- Repair-and-reverify loop: max 2 passes
- Hard safety gates prevent ML from overriding critical violations
- Post-ML ACCEPT override for incomplete tables with all claims verified
- Ingestion layer returns row label coverage metadata (additive, non-breaking)

## Evaluation — Verified from Files

- Apple FY2023 20-case evaluation exists (`evaluation/llm_evaluation_apple_20cases.json`)
- Adversarial Apple evaluation exists (`evaluation/llm_evaluation_apple_20cases_adversarial.json`)
- Hard questions 10-case evaluation exists (`evaluation/llm_hard_questions_10cases.json`)
- Microsoft real-world test exists (`evaluation/microsoft_realworld_test.json`)
- Ablation study results exist (`evaluation/ablation_results.csv`)
- Confusion matrix for V6.1 exists (`evaluation/plots/confusion_matrix_v6_1.png`)

## Ingestion Layer — Verified from Code + Tests

- `assess_ingestion()` function implemented and integrated into pipeline
- 7 unit tests all passing
- Rule-based path reuses synonym dictionary from pnl_parser.py
- LLM-assisted path implemented (calls gpt-3.5-turbo for unmatched rows)
- Ingestion metadata returned in every successful API response
