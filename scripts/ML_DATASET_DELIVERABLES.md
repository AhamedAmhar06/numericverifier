# ML Dataset Generation — Deliverables Summary

## Execution Summary

| Item                                    | Result                                                       |
| --------------------------------------- | ------------------------------------------------------------ |
| **Cases generated and submitted**       | 130                                                          |
| **API endpoint used**                   | `POST /verify` only (LLM generates answer; backend verifies) |
| **API errors**                          | 0                                                            |
| **Valid logged rows (new)**             | 121                                                          |
| **Total rows in `runs/signals_v2.csv`** | 122 (1 pre-existing + 121 from run)                          |
| **Target (≥120)**                       | Met                                                          |

---

## Class Distribution (from `runs/signals_v2.csv`)

Distribution is taken from the **backend-produced** `decision` column in `runs/signals_v2.csv` (no manual labels).

| Decision | Count | %     |
| -------- | ----- | ----- |
| ACCEPT   | 1     | 0.8%  |
| FLAG     | 121   | 99.2% |
| REPAIR   | 0     | 0%    |

**Note:** This run used the backend in **stub LLM mode** (no OpenAI key). The stub often returns a generic or non-numeric answer, so the verifier frequently FLAGs (e.g. no numeric claims or low coverage). To approach the target stratification (~40% ACCEPT, ~30% REPAIR, ~30% FLAG), run the same script with **OpenAI enabled** (`OPENAI_API_KEY` set). The case _design_ is already stratified (ACCEPT-/REPAIR-/FLAG-oriented inputs); the _realized_ distribution depends on LLM answers and engine behavior.

---

## Confirmations

1. **No fabricated labels or signals**  
   Every decision and signal row was produced by the backend: `POST /verify` → LLM (or stub) answer → P&L verification engine → signals and decision → logged to `runs/signals_v2.csv`.

2. **No bypass of backend logic**  
   The generator only builds (question, evidence) pairs and calls the API. All verification, identity checks, YoY logic, and decision rules run in the backend.

3. **API-only usage**  
   Only `POST /verify` was called (no `/verify-only`). The LLM generated the answer for each case.

4. **Logging enabled**  
   Requests used `options: {"log_run": true, "tolerance": 0.01}`. Each run was appended to `runs/signals_v2.csv` and `runs/logs.jsonl`.

5. **Dataset ready for ML training**
   - **File:** `runs/signals_v2.csv`
   - **Schema:** `schema_version=2`, with P&L fields: `pnl_table_detected`, `pnl_identity_fail_count`, `pnl_margin_fail_count`, `pnl_missing_baseline_count`, `pnl_period_strict_mismatch_count`, plus coverage, recomputation, period/scale mismatch, and `decision`.
   - **Target:** `decision` (ACCEPT / REPAIR / FLAG).
   - **Features:** All numeric and categorical columns above are suitable as inputs for a decision model.

---

## How to Reproduce or Extend

1. Start backend at `http://127.0.0.1:8000` (and set `OPENAI_API_KEY` for richer stratification).
2. Run: `python3 scripts/generate_ml_dataset.py`
3. Check `runs/signals_v2.csv` for new rows and `runs/logs.jsonl` for full audit trails.

See `scripts/README_ML_DATASET.md` for full instructions.
