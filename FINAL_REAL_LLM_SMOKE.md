# Real LLM Smoke Test Results

**Date:** 2026-03-29
**Branch:** claude/peaceful-goldberg (≡ main)
**OPENAI_API_KEY available:** NO

---

## Environment

| Variable | Status |
|----------|--------|
| `OPENAI_API_KEY` | Not set — stub mode active |
| `USE_ML_DECIDER` | true |
| xgboost | Not installed in current Python env — rule-based fallback used |

---

## Structural Smoke Tests (No API Key Required)

### Test 1: Stub Mode Fallback

**Input:** Any question
**LLM call:** `generate_llm_answer(...)` with no API key
**Expected:** `llm_used=False`, `llm_fallback_reason="OPENAI_API_KEY not set"`
**Result:** PASS

```
LLM stub mode works: True
reason: OPENAI_API_KEY not set
```

---

### Test 2: Correct Answer — ACCEPT

**Input:**
- Question: `"What was Apple gross margin in FY2023?"`
- Candidate: `"Apple gross margin in FY2023 was 169148 million."`
- Evidence: Apple P&L table (FY2023/FY2022/FY2021, in millions)

**Expected:** `ACCEPT`
**Result:** PASS

```
Decision: ACCEPT
Rationale: All claims are grounded and verified. No scale or period mismatches. All recomputations and P&L checks successful.
Domain: pnl (confidence: 0.333)
```

---

### Test 3: Wrong Answer — FLAG

**Input:**
- Question: `"What was Apple net income in FY2023?"`
- Candidate: `"Apple net income in FY2023 was 200000 million."` ← wrong (actual: 96,995M)
- Evidence: Apple P&L table

**Expected:** `FLAG`
**Result:** PASS

```
Decision: FLAG
Rationale: Issues detected: low coverage (0.0%), many unsupported claims (1). Requires review.
```

---

### Test 4: Non-P&L Evidence — FLAG

**Input:** Table without P&L structure
**Expected:** FLAG with "Evidence is not a P&L / Income Statement table."
**Result:** PASS

---

## Live LLM Test (API Key Required)

**Status:** NOT EXECUTED — `OPENAI_API_KEY` not available in this environment.

**What would be tested:** The `/verify` endpoint with `OPENAI_API_KEY` set calls `gpt-4o-mini` (temperature=0.0, max_tokens=100) to generate a candidate answer, then runs the full verification pipeline on it.

**Prior evidence of live LLM behavior:** See `FINAL_VERIFY_ENDPOINT_STATUS.md` and `FINAL_E2E_VALIDATION.md` for recorded results from sessions where the API key was available. The Apple FY2023 /verify test previously returned `decision=FLAG` (LLM generated "383,285" without units — expected behaviour).

**How to run live test:**
```bash
cd backend
echo "OPENAI_API_KEY=sk-..." > .env
USE_ML_DECIDER=true python3 -m uvicorn app.main:app --reload
# Then POST to http://localhost:8000/verify
```

---

## Conclusion

The `/verify` and `/verify-only` pipeline is **structurally working**. All three structural smoke tests pass. Live LLM behaviour is environment-dependent and requires `OPENAI_API_KEY` in `backend/.env`.

Test suite: **234 passed, 4 skipped** (confirmed in this session).
