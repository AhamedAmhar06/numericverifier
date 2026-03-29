# NumericVerifier — Unsafe Claims (Require Caveats)

> These claims SHOULD NOT be stated in the dissertation without appropriate caveats or qualifications.

---

## 1. "221 tests passing" (STALE NUMBER)

**Reality:** 234 tests pass as of 2026-03-29. The "221" number was from Session 3 and is now outdated. Always cite the current count.

## 2. "REPAIR recall is 100%"

**Reality:** REPAIR recall is 100% but based on only **16 REPAIR cases** in the training set. This is not statistically robust. Report as: "REPAIR recall of 100% on 16 cases (insufficient sample for statistical confidence)."

## 3. "The model generalizes to real-world financial statements"

**Reality:** Training data consists of:
- Synthetic perturbation cases (cases_v2.json)
- TAT-QA gold standard cases (academic dataset)

No real-world production deployment data exists. The Apple/Microsoft evaluations are manually constructed test cases, not live production data.

## 4. "TAT-QA ACCEPT cases are fully representative"

**Reality:** The 100 TAT-QA ACCEPT cases used in V6.1 training have **imputed grounding_confidence_score** values. These were not computed by running the full pipeline on TAT-QA tables — they were assigned heuristically. This should be noted as a limitation.

## 5. "LLM-assisted ingestion works in production"

**Reality:** The LLM-assisted path in `assess_ingestion()` is:
- Implemented and code-reviewed
- Unit-tested for the rule-based path
- **NOT integration-tested with a live OpenAI API call in this session**
- The code path exists but its accuracy on real financial tables with non-standard labels is unvalidated

Report as: "LLM-assisted ingestion is implemented but not empirically validated."

## 6. "Production-ready system"

**Reality:**
- No Dockerfile
- No deployed instance
- No load testing
- No security audit
- No authentication
- No monitoring/alerting
- Default API URL is localhost:8001

Report as: "Research prototype" or "proof-of-concept system."

## 7. "84-case evaluation accuracy of 91.67%"

**Caveat:** This is the V5 84-case eval accuracy. It should not be attributed to V6.1 without re-running the evaluation. V6.1 metrics are from `runs/ml_metrics_v6_1.json` (98.18% test accuracy on intrinsic test set).

## 8. "Frontend is fully functional"

**Caveats:**
- No automated frontend tests (no Jest/Vitest)
- No accessibility audit
- No user testing
- Responsive design not extensively tested on mobile
- No authentication or rate limiting

## 9. "Scale detection handles all cases"

**Reality:** The claim "Apple revenue was $383,285 million" gets parsed as $383,285,000,000 (billion scale) rather than as the table value of 383,285 in millions. Scale token parsing has known edge cases.

## 10. "Supports all P&L table formats"

**Reality:**
- Only English-language P&L terminology is supported
- Only Layout A (line items x periods) and Layout B (period, item, value) are supported
- Non-English tables, footnoted tables, GAAP vs non-GAAP tables, and segment-level P&L tables are not handled
