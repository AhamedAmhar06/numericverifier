# Error Analysis: Real P&L Cases

Analysis of 12–16 representative cases from TAT-QA P&L evaluation.

---

## 5 Failures (Why)

Cases where the verifier incorrectly ACCEPTed, FLAGged, or REPAIRED.

| Case ID | Question | Gold | Decision | Why |
|---------|----------|------|----------|-----|
| (example) | What was Revenue in 2022? | 620000 | FLAG | Scale mismatch: evidence in thousands, answer in raw units |
| (example) | What was Gross Profit in Q4? | 90 | REPAIR | Verifier repaired to different format; gold expects exact |
| ... | ... | ... | ... | ... |

**Failure categories:**
1. **Scale mismatch** — Evidence uses K/M suffix; answer in raw or vice versa.
2. **Period mismatch** — Question asks FY20; table has 2020; strict match fails.
3. **Identity check** — P&L identity (Revenue - COGS = Gross Profit) fails due to rounding.
4. **Coverage** — Claim not grounded; unsupported_claims_count > 0.
5. **Ambiguity** — Multiple cells match; verifier flags or picks wrong one.

---

## 5 Repair Wins (Before/After)

Cases where repair correctly fixed an error.

| Case ID | Before | After | Repair Action |
|---------|--------|-------|---------------|
| (example) | FLAG (scale) | ACCEPT | "0.62 million" -> "620000" |
| (example) | FLAG (scale) | ACCEPT | "500K" -> "500000" |
| ... | ... | ... | ... |

**Repair success pattern:** Scale correction when evidence and answer use different units; repair aligns to evidence scale.

---

## 2 Ambiguity Cases

Cases where multiple valid interpretations exist.

| Case ID | Question | Ambiguity | Resolution |
|---------|----------|-----------|------------|
| (example) | What was operating income? | "Operating Income" vs "EBIT" row | Verifier picks first match |
| (example) | Revenue for 2022? | Two columns: "2022" and "FY2022" | Period strict match may reject |

---

## 2 Scale/Period Edge Cases

| Case ID | Issue | Outcome |
|---------|-------|---------|
| (example) | Table has "2022" and "FY22"; question says "2022" | Period strict mismatch if FY22 != 2022 |
| (example) | Evidence: "1,500" (with comma); answer: "1500" | Parse/normalization may differ |

---

## How to Populate

1. Run `python -m evaluation.run_tatqa_gold_eval` and `run_tatqa_llm_eval` (if LLM).
2. Inspect `tatqa_pnl_gold_*_results.jsonl` and `tatqa_pnl_llm_results.jsonl`.
3. Select 5 failures (decision != ACCEPT for gold, or ACCEPT for bad answer).
4. Select 5 repair wins (before=FLAG/REPAIR, after=ACCEPT, repaired matches gold).
5. Select 2 ambiguity and 2 scale/period edge cases.
6. Fill the tables above with real case IDs and summaries.
