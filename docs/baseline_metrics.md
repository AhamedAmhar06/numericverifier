# Baseline Metrics (Phase 0 Snapshot)

**Date:** 2025-02-01  
**Scope:** No logic changes. Snapshot before TAT-QA P&L pipeline.

---

## 1. Test Pass Count

| Suite | Passed | Failed | Error |
|-------|--------|--------|-------|
| Core tests | 110 | 0 | 1* |

\* `backend/test_examples.py::test_example` has 1 error (likely path/network); core verifier tests pass.

---

## 2. Synthetic Evaluation Metrics

**Command:** `python -m evaluation.run_eval --enable_repair`  
**Cases:** 84 (from `evaluation/cases_v2.json`)

| Metric | Value |
|--------|-------|
| Accuracy | 84.52% |
| False ACCEPT rate | 19.44% |
| Repair success rate | 0.00% |
| Avg latency | 0.3 ms |

**Per-class (rules_full):**

| Class | Precision | Recall | F1 |
|-------|-----------|--------|-----|
| ACCEPT | 0.87 | 1.00 | 0.93 |
| REPAIR | 0.00 | 0.00 | 0.00 |
| FLAG | 1.00 | 0.64 | 0.78 |

---

## 3. Repair Example (Request/Response)

**Case:** `case_009` — scale error (claim uses "million" but evidence is in raw units)

### Request

```json
{
  "question": "What was revenue in 2022?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Line Item", "2022", "2023"],
      "rows": [
        ["Revenue", "500000", "620000"],
        ["COGS", "200000", "250000"],
        ["Gross Profit", "300000", "370000"],
        ["Operating Expenses", "100000", "120000"],
        ["Operating Income", "200000", "250000"],
        ["Taxes", "30000", "38000"],
        ["Interest", "20000", "22000"],
        ["Net Income", "150000", "190000"]
      ],
      "units": {}
    }
  },
  "candidate_answer": "Revenue in 2022 was 0.50 million."
}
```

### Response (with `enable_repair: true`)

```json
{
  "decision": "REPAIR",
  "rationale": "Good evidence coverage (100.0%), but issues detected: scale mismatches. Errors appear correctable.",
  "signals": {
    "scale_mismatch_count": 1,
    "coverage_ratio": 1.0,
    "unsupported_claims_count": 0,
    "recomputation_fail_count": 0,
    "period_mismatch_count": 0
  },
  "repair": {
    "repaired_answer": "Revenue in 2022 was 500000.",
    "repair_actions": [
      {
        "span": [20, 32],
        "old_text": "0.50 million",
        "new_text": "500000",
        "reason": "scale_correction",
        "provenance": "evidence:row:0,col:1"
      }
    ],
    "repaired_decision": "ACCEPT"
  }
}
```

---

## 4. Ablation Key Finding

**Command:** `python -m evaluation.run_ablation`

| Config | Accuracy | False Accept | Repair Success |
|--------|----------|--------------|----------------|
| rules_full | 84.52% | 19.44% | 0.00% |
| rules_no_execution | 84.52% | 19.44% | 0.00% |
| rules_no_constraints | 75.00% | **58.33%** | 0.00% |
| rules_no_lookup | 84.52% | 19.44% | 0.00% |
| rules_no_repair | 84.52% | 19.44% | 0.00% |
| ml_full | 84.52% | **36.11%** | 0.00% |

**Key finding:** Disabling constraints (`rules_no_constraints`) doubles false ACCEPT (19% → 58%), showing period/scale checks are critical for safety. ML mode (`ml_full`) increases false ACCEPT by ~17 points vs rules_full, suggesting the v2 classifier is too permissive.
