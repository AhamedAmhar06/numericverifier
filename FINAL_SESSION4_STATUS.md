# FINAL SESSION 4 STATUS — LLM-Assisted Ingestion Layer

**Date:** 2026-03-29
**Feature:** P&L Row Label Ingestion Confidence Layer

---

## What Was Implemented

### New file: `backend/app/verifier/ingestion.py`

An ingestion confidence layer that runs before `pnl_parser.parse_pnl_table()` and returns metadata about how well the input table row labels map to canonical P&L line items.

**Function signature:**
```python
def assess_ingestion(
    table_dict: dict,
    llm_available: Optional[bool] = None,
    confidence_threshold: float = 0.5,
) -> dict
```

**Return shape:**
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

---

## How It Works

### Rule-Based Path (always runs)
1. Extract row labels (first column of each row)
2. Normalize: lowercase, strip punctuation, collapse whitespace
3. Match against `_SYNONYMS` dict from `pnl_parser.py` (two passes: exact, then longest substring)
4. Compute `coverage = matched / total_labels`

### LLM-Assisted Path (optional)
Triggered when ALL of the following are true:
- `llm_available=True` OR `OPENAI_API_KEY` env var is set
- `coverage < confidence_threshold` (default 0.5)
- There are unmatched rows

When triggered:
1. Builds a prompt listing unmatched row labels
2. Calls OpenAI `gpt-3.5-turbo` to map each label to a canonical key
3. Validates response — only accepts known canonical keys
4. Returns suggestions in `llm_suggestions`, updates `coverage` and sets `mode="llm_assisted"`

---

## Integration Points

### `backend/app/verifier/router.py`
- `assess_ingestion(content)` called before `parse_pnl_table(content)` in `route_and_verify()`
- Result stored as `ingestion_meta` and included in response as `"ingestion"` key

### Frontend
- `DecisionPanel.tsx` renders ingestion metadata as a formatted JSON card
- `VerifyResponse.ingestion` typed as `IngestionResult` interface

---

## Tests

**File:** `tests/test_assess_ingestion.py` (7 tests, all passing)

| Test | What it verifies |
|------|----------------|
| `test_full_coverage_rule_based` | Standard Apple FY2023 data → 100% coverage, rule_based |
| `test_low_coverage_no_llm` | Unknown labels → low coverage, no LLM triggered |
| `test_empty_table` | Empty rows → zero coverage, no errors |
| `test_partial_coverage` | Mixed known/unknown rows → partial coverage |
| `test_result_shape` | All required keys present, types correct |
| `test_synonym_variations` | Alternate synonyms (EBIT, Total revenue, etc.) map correctly |
| `test_llm_not_triggered_when_coverage_high` | LLM not called when coverage ≥ threshold |

---

## Design Decisions

- **Additive, non-breaking**: ingestion layer only adds metadata; it does not change pnl_parser behavior or the pipeline output
- **Single source of truth for synonyms**: imports `_SYNONYMS` directly from `pnl_parser.py`
- **Explicit override**: passing `llm_available=False` disables LLM even if `OPENAI_API_KEY` is set (prevents test pollution)
- **Graceful degradation**: LLM failures are logged and silently ignored; rule_based result returned

---

## Limitations

- LLM path not integration-tested (requires live OpenAI key)
- No evaluation of LLM mapping accuracy on real-world financial tables
- `confidence_threshold=0.5` is heuristic — not empirically tuned
- LLM model hardcoded to `gpt-3.5-turbo`; no user-configurable model selection
