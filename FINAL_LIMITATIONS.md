# FINAL LIMITATIONS — Session 4

**Date:** 2026-03-29

---

## Backend Limitations

### 1. `units` field must be a dict
Passing `"units": "millions USD"` (string) to any verify endpoint causes a 500 error:
```
AttributeError: 'str' object has no attribute 'values'
```
in `pnl_parser.py` line ~492. Always use `"units": {}` or `"units": {"FY2023": "millions USD"}`.

### 2. Scale token ambiguity
The claim "Apple revenue was $383,285 million" parses the scale token "million" and multiplies:
`383285 * 1,000,000 = 383,285,000,000,000`. This fails grounding because the table has `383285`.
Fix: omit the scale word in candidate answers, or use exact values matching the table units.

### 3. LLM fallback is a stub
Without `OPENAI_API_KEY`, `/verify` uses a deterministic stub that extracts numeric values from the evidence table. This is not an actual language model response.

### 4. Ingestion LLM path untested
The `llm_assisted` mode in `assess_ingestion()` requires a live OpenAI API key to test. No integration test covers it. The implementation is correct by design but unverified empirically.

### 5. pnl_parser hardcodes English P&L terminology
Non-English financial tables (French, German, etc.) will have near-zero synonym coverage.

---

## Frontend Limitations

### 1. Default API URL
`http://localhost:8001` is the default. Must set `VITE_API_BASE_URL` in `.env` for any other environment.

### 2. No frontend tests
No unit tests, no integration tests, no accessibility audit.

### 3. No auth
The frontend makes unauthenticated requests. Suitable for local dev only.

### 4. Evidence format validation
The frontend's `parseEvidenceInput()` in `parser.ts` accepts JSON and CSV, but validation errors may give cryptic messages for some malformed inputs.

---

## ML Model Limitations

### 1. Training data scope
V6.1 trained on synthetic + TAT-QA-derived signals. Real-world edge cases (footnoted tables, adjusted EPS, GAAP/non-GAAP differences) may yield unexpected decisions.

### 2. No online learning
Model is static (trained once). Errors from production use do not feed back into model updates.

### 3. Threshold sensitivity
The ACCEPT/REPAIR/FLAG boundary was calibrated on an 84-case eval set. Precision/recall tradeoffs on larger or more diverse datasets are unknown.

---

## What Is Safe to Claim in Dissertation

- The full verification pipeline is functional and produces deterministic results for well-formed P&L table inputs
- ML model V6.1 achieves 91.67% accuracy on the 84-case evaluation set (evidence in `runs/ml_metrics_v6_1.json`)
- The ingestion layer is implemented, integrated, and unit-tested (7 tests, all passing)
- The frontend builds without errors and routes requests correctly to `/verify-only` vs `/verify`
- 204 backend tests pass after all Session 4 changes

## What Is NOT Safe to Claim

- LLM-assisted ingestion accuracy or quality (not evaluated)
- Real-world deployment readiness (no load testing, no security review)
- Generalizability beyond English-language P&L tables with standard line item names
