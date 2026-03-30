# ML Dataset Generation (P&L Verification Signals)

## Purpose

Generate a **finance-specific dataset** of verification signals for training a decision model. All labels and signals come from the backend; this script only generates inputs and calls the API.

## Rules (no violations)

- **No fabricated labels or signals** — backend produces all decisions and signals.
- **POST /verify only** — LLM generates answers; verification engine produces signals.
- **Logging enabled** — each run is logged to `runs/signals_v2.csv` and `runs/logs.jsonl`.

## Prerequisites

1. **Backend running** at `http://localhost:8877`:

   ```bash
   cd backend && python3 -m uvicorn app.main:app --reload --port 8877
   ```

   Or from project root:

   ```bash
   PYTHONPATH=backend python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8877
   ```

2. **OpenAI LLM enabled** (optional but recommended for diverse answers):

   - Set `OPENAI_API_KEY` in the environment (or in `backend/.env`).
   - If not set, the backend uses a stub answer; you still get valid signals and decisions.

3. **Logging** — backend defaults `log_run=True` for `/verify`; signals append to `runs/signals_v2.csv`.

## Run

From project root:

```bash
python3 scripts/generate_ml_dataset.py
```

The script will:

1. Check that the backend is reachable (exit with clear message if not).
2. Build a pool of **≥120 cases** (target 130) with stratification:
   - **~40% ACCEPT-oriented**: P&L tables with valid identities, clear period references.
   - **~30% REPAIR-oriented**: One identity or arithmetic error (e.g. wrong Gross Profit row).
   - **~30% FLAG-oriented**: YoY with missing baseline, non-P&L table, or period not in table.
3. Call **POST /verify** for each case (LLM generates answer; P&L engine verifies and logs).
4. Report: cases submitted, API errors, **decision distribution**, and **new rows** in `runs/signals_v2.csv`.

## Output

- **runs/signals_v2.csv** — one row per run (schema_version=2, P&L fields, `decision`).
- **runs/logs.jsonl** — full audit per run (claims, grounding, verification, domain, llm_used, etc.).

## Deliverables (after successful run)

- **Case count**: ≥120 cases submitted.
- **Class distribution**: Summary of ACCEPT / REPAIR / FLAG from API responses.
- **No manual labeling**: All decisions and signals from backend only.
- **Dataset ready for ML**: `signals_v2.csv` with numeric and categorical features plus `decision` target.

## Stopping condition

The script stops when all cases in the pool have been submitted. It reports whether **new rows ≥ 120** in `signals_v2.csv` and exits with code 0 only if target met and no API errors.
