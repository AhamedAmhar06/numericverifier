# NumericVerifier — Report Alignment Guide

> What the dissertation/report should say for each component. Exact phrasing suggestions.

---

## Model

**Safe phrasing:**
> "The final ML decision model (V6.1) is an XGBClassifier trained on 364 labeled cases (200 FLAG, 148 ACCEPT, 16 REPAIR) using 10 signal features. Five-fold stratified cross-validation yields a mean accuracy of 98.90% (SD = 0.0104). On a held-out test set, the model achieves 98.18% accuracy with FLAG recall of 98.50% and ACCEPT recall of 99.32%. The overfit gap is 1.42%, and no feature leakage was detected."

**Required caveat:**
> "REPAIR recall of 100% is based on only 16 cases and is not statistically robust. The training data consists of synthetic perturbation cases and TAT-QA gold standard cases; generalization to diverse real-world financial statements has not been empirically validated."

---

## System Architecture

**Safe phrasing:**
> "NumericVerifier implements a multi-stage verification pipeline: (1) numeric claim extraction from candidate answers, (2) normalization of scale and units, (3) evidence grounding against table data, (4) three verification engines (direct lookup, constraint checking, P&L recomputation), (5) signal aggregation into a 10-dimensional feature vector, and (6) ML-based decision classification (ACCEPT/FLAG/REPAIR) with hard safety gates. A repair-and-reverify loop allows deterministic correction of repairable errors."

---

## Evaluation

**What you CAN claim:**
- V6.1 intrinsic metrics (CV, test accuracy, recall) from `runs/ml_metrics_v6_1.json`
- Ablation study shows each engine contributes to overall accuracy (ablation_results.csv)
- Apple FY2023 real-world evaluation (20 cases, including adversarial)
- Microsoft real-world test case
- Hard questions evaluation (10 cases)
- Model evolution from tautological V2/V3 to non-tautological V6.1

**What you CANNOT claim without caveat:**
- That V6.1 achieves 91.67% on the 84-case eval (that was V5; V6.1 was not re-evaluated on the exact same 84-case set)
- That the model generalizes to production financial data (no production deployment)
- Precision/recall tradeoffs on datasets larger than the 364 training cases

---

## Frontend

**Safe phrasing:**
> "A React/TypeScript single-page application provides an interactive interface for the verification pipeline. The frontend automatically routes requests to the appropriate API endpoint, displays decision badges with color coding, and renders per-claim audit details, signal values, and ingestion metadata. The application builds with zero TypeScript compilation errors."

**Required caveat:**
> "The frontend has not been user-tested, accessibility-audited, or deployed to a production environment. No automated frontend tests exist."

---

## Ingestion Layer (Session 4)

**Safe phrasing:**
> "An ingestion confidence layer assesses how well input table row labels map to canonical P&L line items using a synonym dictionary. When rule-based coverage falls below a configurable threshold, an LLM-assisted path (using GPT-3.5-turbo) attempts to map unrecognized labels to canonical categories. The layer is additive and does not alter the verification pipeline's behavior — it returns metadata about ingestion confidence alongside the verification result."

**Required caveat:**
> "The LLM-assisted mapping path is implemented but has not been empirically validated with a live API call in a controlled evaluation. The rule-based path is unit-tested (7 tests, all passing). The confidence threshold (0.5) is heuristic and not empirically tuned."

---

## Test Suite

**Safe phrasing:**
> "The system includes 234 passing unit and integration tests (4 skipped) covering claim extraction, normalization, grounding, execution semantics, signal computation, ML decision making, repair loops, ingestion assessment, and API endpoint behavior."

---

## What Old Numbers to Avoid

| Old Claim | Correct Value | Source |
|-----------|---------------|--------|
| "221 tests passing" | 234 pass, 4 skip | pytest run 2026-03-29 |
| "204 tests passing" | 234 pass, 4 skip | pytest run 2026-03-29 |
| "units must be a dict" | Fixed — accepts both dict and string | Code fix 2026-03-29 |
| "V5 is current" | V6.1 is current | runs/model_registry.json |
| "91.67% accuracy" | 98.18% test / 98.90% CV (V6.1) | runs/ml_metrics_v6_1.json |
