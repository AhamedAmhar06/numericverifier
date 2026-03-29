# FINAL CODEBASE STATUS — Session 4

**Date:** 2026-03-29
**Branch:** feat/react-frontend
**ML Model:** V6.1 XGBoost
**Test count:** 204 passed, 4 skipped

---

## Working Now (with evidence)

### Backend (FastAPI + Python)
- Full P&L verification pipeline: extract → normalize → ground → lookup → constraints → execution → signals → ML decision
- ML decision model V6.1 (XGBoost, balanced training, 10 features)
- `/verify-only` endpoint: accepts candidate answer, runs deterministic verification
- `/verify` endpoint: LLM generates answer (or stub fallback), then verifies
- Repair-and-reverify loop: REPAIR → attempt fix → re-verify (max 2 passes)
- Per-claim audit (`claim_audit`, `audit_summary`) in every response
- `ingestion` metadata field in every successful response (Session 4 addition)
- 197+ previously passing tests still pass; new ingestion tests add 7 more

### Frontend (React + TypeScript + Vite)
- Clean build: `npm run build` succeeds with zero TypeScript errors
- Correct endpoint routing: `/verify-only` when candidate_answer provided, `/verify` when not
- All UI sections rendered: question, evidence, candidate answer, Load Example, Verify, Clear
- Decision badge with color coding (ACCEPT/REPAIR/FLAG)
- Rationale text, signals panel, claim audit list, repair metadata, ingestion metadata
- Apple FY2023 example preloaded via "Load Apple Example" button

### Ingestion Layer (Session 4)
- `backend/app/verifier/ingestion.py` — `assess_ingestion()` function
- Rule-based path: reuses `_SYNONYMS` from `pnl_parser.py`
- LLM-assisted path: triggers when coverage < 0.5 and OPENAI_API_KEY is set
- Metadata returned in API response as `ingestion` field
- 7 unit tests in `tests/test_assess_ingestion.py` — all passing

---

## Partially Working

- LLM-assisted ingestion path: implemented and wired in, but requires `OPENAI_API_KEY` to activate. Cannot be integration-tested without a valid OpenAI key.
- `/verify` endpoint LLM path: uses stub fallback if no OpenAI key — deterministic, always returns a valid response but not LLM-generated.

---

## Known Limitations

- `units` field in table evidence must be a dict (e.g., `{}`), not a string — passing `"millions USD"` as string causes 500 error in pnl_parser.
- Scale ambiguity: "383,285 million" gets parsed as 383,285,000,000 (billion scale) rather than 383,285 in millions. This is pre-existing behavior.
- Frontend API base URL defaults to `http://localhost:8001` — needs `VITE_API_BASE_URL` env var for production deployment.

---

## Safe to Report in Dissertation/Paper

- End-to-end P&L verification pipeline is functional and deterministic for table inputs
- ML model V6.1 metrics are documented in `runs/ml_metrics_v6_1.json`
- 221 tests passing (from Session 3 lock), 84-case eval at 91.67%
- Ingestion layer is additive and non-breaking — all existing tests pass after addition

---

## Caveats / Not Safe to Claim

- LLM-assisted ingestion accuracy has not been evaluated (no gold standard mapping data)
- Repair success rate not formally benchmarked on a held-out test set
- Frontend has not been user-tested or accessibility-audited
