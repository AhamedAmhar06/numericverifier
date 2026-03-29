# FINAL E2E VALIDATION — Session 4

**Date:** 2026-03-29
**Backend:** `USE_ML_DECIDER=true uvicorn app.main:app --host 127.0.0.1 --port 8765`
**ML Model:** V6.1 XGBoost

---

## Health Check

```
GET /health → {"status":"ok"}
```

---

## Flow A: POST /verify-only (with candidate answer)

**Request:**
```json
{
  "question": "What was Apple net sales in FY2023?",
  "evidence": {
    "type": "table",
    "content": {
      "title": "Apple FY2023 Income Statement",
      "columns": ["", "FY2023", "FY2022"],
      "rows": [
        ["Net sales", "383,285", "394,328"],
        ["Cost of sales", "214,137", "223,546"],
        ["Gross margin", "169,148", "170,782"],
        ["Operating expenses", "54,847", "51,345"],
        ["Operating income", "114,301", "119,437"],
        ["Income taxes", "29,749", "19,300"],
        ["Net income", "96,995", "99,803"]
      ],
      "units": {}
    }
  },
  "candidate_answer": "Apple net sales were $383,285 in FY2023.",
  "tolerance": 0.01
}
```

**Response (key fields):**
```json
{
  "decision": "ACCEPT",
  "rationale": "All claims are grounded and verified. No scale or period mismatches. All recomputations and P&L checks successful. Coverage meets threshold.",
  "ingestion": {
    "mode": "rule_based",
    "coverage": 1.0,
    "matched_rows": ["Net sales", "Cost of sales", "Gross margin", "Operating expenses", "Operating income", "Income taxes", "Net income"],
    "unmapped_rows": [],
    "llm_suggestions": {},
    "confidence": 1.0
  }
}
```

**Status:** PASS — ACCEPT decision, ingestion metadata present with 100% coverage.

---

## Flow B: POST /verify (LLM generates answer)

**Request:**
```json
{
  "question": "What was Apple gross margin in FY2023?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["", "FY2023", "FY2022"],
      "rows": [["Net sales", "383,285", ...], ["Gross margin", "169,148", ...], ...],
      "units": {}
    }
  },
  "tolerance": 0.01
}
```

**Response (key fields):**
```json
{
  "decision": "ACCEPT",
  "rationale": "All claims are grounded and verified. No scale or period mismatches...",
  "signals": {
    "coverage_ratio": 1.0,
    "grounding_confidence_score": 0.925,
    "claim_count": 1
  },
  "ingestion": {
    "mode": "rule_based",
    "coverage": 1.0
  }
}
```

**Status:** PASS — LLM (or stub) generated "169,148" for gross margin, ACCEPT decision.

---

## Ingestion Layer Direct Test

```python
from app.verifier.ingestion import assess_ingestion
result = assess_ingestion({
    'columns': ['', 'FY2023'],
    'rows': [
        ['Net sales', '383285'],
        ['Cost of sales', '214137'],
        ['Gross margin', '169148'],
    ]
})
```

**Output:**
```json
{
  "mode": "rule_based",
  "coverage": 1.0,
  "matched_rows": ["Net sales", "Cost of sales", "Gross margin"],
  "unmapped_rows": [],
  "llm_suggestions": {},
  "confidence": 1.0
}
```

**Status:** PASS

---

## Known Issue: units as string causes 500

Passing `"units": "millions USD"` (string) to `/verify-only` causes:
```
AttributeError: 'str' object has no attribute 'values'
```
in `pnl_parser.py`. The `units` field must be a dict (e.g., `{}`).
This is a pre-existing limitation of the pnl_parser, not introduced in Session 4.

---

## Frontend Build

```
tsc -b && vite build
✓ 37 modules transformed.
dist/index.html   0.40 kB
dist/assets/*.js  154.71 kB
✓ built in 537ms
```

**Status:** PASS — zero TypeScript errors, zero Vite warnings.
