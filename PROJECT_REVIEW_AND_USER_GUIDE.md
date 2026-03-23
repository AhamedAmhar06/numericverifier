# NumericVerifier — Project Review & User Guide

This document explains **how to run the project**, **what inputs to give**, and **how to review what works**. It is written for humans reviewing or using the system.

---

## 1. What This Project Does

**NumericVerifier** is a **P&L / Income Statement–specific** backend that:

1. **Takes** a question and evidence. For verification, evidence **must be a table** (P&L layout). Text evidence or non-P&L tables return **FLAG**.
2. **Optionally** uses an LLM to generate an answer (`POST /verify`), or **you** provide the answer (`POST /verify-only`).
3. **Verifies** numeric claims against the evidence: lookup, P&L accounting identities (e.g. Gross Profit = Revenue − COGS), margin checks, and YoY baseline strictness.
4. **Returns** a decision: **ACCEPT**, **REPAIR**, or **FLAG**, plus signals (including P&L-specific ones), domain, engine_used, and a full audit-style report.

So: it checks whether numbers in an answer are correct and consistent with **P&L table** evidence, with strict handling of YoY baselines and period mismatches.

---

## 2. How to Run the Project

### Prerequisites

- **Python 3.9+** (3.10+ recommended)
- Terminal (macOS/Linux or similar)

### Step 1: Open the backend folder

```bash
cd path/to/numericverifier/backend
```

(Use your actual path, e.g. `cd "/Users/ahamedamhar/Development - campus/numericverifier/backend"`.)

### Step 2: Use a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Start the server

```bash
python3 -m uvicorn app.main:app --reload
```

You should see something like:

- `Uvicorn running on http://127.0.0.1:8000`
- A log line: **"Backend running in stub mode"** (no API key) or **"Backend running in LLM mode"** (if `OPENAI_API_KEY` is set)

### Step 5: Confirm it’s running

- In a browser open: **http://localhost:8000**  
  You should see: `{"message":"NumericVerifier API"}`.
- Open: **http://localhost:8000/docs**  
  You get the interactive API docs (Swagger UI) where you can try endpoints with sample inputs.

---

## 3. What Inputs to Give — Two Ways to Use the API

There are **two main endpoints**. You always send **question** and **evidence**; the difference is whether **you** provide the answer or the **LLM** does.

---

### Option A: You provide the answer — `POST /verify-only`

**Use this when:** you already have a candidate answer (e.g. from another system or a human) and want it verified.

**Inputs:**

| Field | Required | Description |
|-------|----------|-------------|
| `question` | Yes | The question being answered (e.g. "What was the total revenue for Q1 2024?") |
| `evidence` | Yes | **Table** required for verification. If `type` is not `"table"` or the table is not a P&L, the decision is **FLAG**. |
| `candidate_answer` | Yes | The answer you want verified (must contain numbers to verify). |
| `options` | No | `{"tolerance": 0.01, "log_run": true}` — tolerance for numeric comparison; `log_run` to write to `runs/logs.jsonl`. |

**Evidence formats (P&L-only scope):**

- **Text evidence:** If you send `"type": "text"`, the verifier returns **FLAG** with rationale "P&L verifier requires table evidence."
- **Table evidence:** Must be a **P&L / Income Statement** table. Supported layouts:
  - **Layout A (preferred):** First column = line items (Revenue, COGS, Gross Profit, etc.), other columns = periods (e.g. 2022, 2023).
  - **Layout B:** Columns = Period, Line Item, Value.

If the table is not classified as P&L (e.g. random columns like Category, Count), the decision is **FLAG** with "Evidence is not a P&L / Income Statement table."

**Example P&L table (Layout A):**

```json
"evidence": {
  "type": "table",
  "content": {
    "columns": ["Line Item", "2022", "2023"],
    "rows": [
      ["Revenue", "100", "120"],
      ["COGS", "40", "50"],
      ["Gross Profit", "60", "70"]
    ],
    "units": {}
  }
}
```

**Example full request (verify-only, P&L Layout A):**

```json
{
  "question": "What was revenue in 2022?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Line Item", "2022", "2023"],
      "rows": [
        ["Revenue", "100", "120"],
        ["COGS", "40", "50"],
        ["Gross Profit", "60", "70"]
      ],
      "units": {}
    }
  },
  "candidate_answer": "Revenue was 100.",
  "options": { "tolerance": 0.01, "log_run": false }
}
```

**What you get back:** `decision` (ACCEPT/REPAIR/FLAG), `rationale`, `signals`, `claims`, `grounding`, `verification`, `report`, `domain` (e.g. `{"table_type": "pnl", "confidence": ...}`), `engine_used` (e.g. `"pnl"`).

---

### Option B: LLM generates the answer — `POST /verify`

**Use this when:** you only have a question and table evidence; the backend will call the LLM to generate an answer, then verify it.

**Inputs:**

| Field | Required | Description |
|-------|----------|-------------|
| `question` | Yes | The question (e.g. "What is the percent change in revenue from Q1 to Q2?") |
| `evidence` | Yes | **Must be table** (text not supported for this endpoint). Same table format as above. |
| `options` | No | Same as verify-only (`tolerance`, `log_run`). |

**No `candidate_answer`** — the server generates it via the LLM (or stub if no API key).

**Example full request (verify with LLM):**

```json
{
  "question": "What is the percent change in revenue from Q1 to Q2?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Period", "Revenue"],
      "rows": [["Q1", "10"], ["Q2", "15"]],
      "units": { "Revenue": "dollars" }
    }
  },
  "options": { "tolerance": 0.01, "log_run": false }
}
```

**What you get back:** Same as verify-only, **plus** `generated_answer`, `llm_used` (true/false), and `llm_fallback_reason` (set if the LLM was not used, e.g. quota/network failure).

**Note:** If `OPENAI_API_KEY` is not set (environment only; keys are never read from repo files), the server uses **stub mode**: it returns a placeholder answer and still runs verification. Logs will indicate "stub" or "fallback" and the reason.

---

## 4. How to Try It — Practical Ways to Give Inputs

### A. Using the built-in API docs (easiest)

1. Start the server (see Section 2).
2. Open **http://localhost:8000/docs**.
3. Click **POST /verify-only** or **POST /verify**.
4. Click **“Try it out”**.
5. Paste one of the example JSON bodies below into the request body.
6. Click **“Execute”**.

You’ll see the full response (decision, rationale, signals, claims, etc.) and can change inputs and re-run.

### B. Using curl from the terminal

**Health check:**

```bash
curl http://localhost:8000/health
```

**Verify-only** (using the project’s example file):

```bash
curl -X POST "http://localhost:8000/verify-only" \
  -H "Content-Type: application/json" \
  -d @../examples/accept_case.json
```

(From the `backend` folder; adjust the path to `examples/` if needed.)

**Verify (LLM-generated answer):**

```bash
curl -X POST "http://localhost:8000/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the percent change in revenue from Q1 to Q2?",
    "evidence": {
      "type": "table",
      "content": {
        "columns": ["Period", "Revenue"],
        "rows": [["Q1", "10"], ["Q2", "15"]],
        "units": { "Revenue": "dollars" }
      }
    },
    "options": { "log_run": false }
  }'
```

### C. Example JSON files in the repo

In the **`examples/`** folder (at project root):

| File | Purpose |
|------|--------|
| `accept_case.json` | Question + P&L table + answer that matches evidence → expect **ACCEPT**. |
| `repair_case.json` | Answer with a numeric claim that can be checked → may get **REPAIR** if there’s a mismatch. |
| `flag_case.json` | Answer that doesn’t match evidence → expect **FLAG**. |
| `pnl_eval_cases.json` | P&L evaluation suite (6 cases): identity correct/repair, YoY missing baseline, margin, synonym table, non-P&L. Used by `run_evaluation_api.py` by default. |

Use these as templates: change `question`, `evidence`, or `candidate_answer` and send to **POST /verify-only** to see how the decision and signals change.

---

## 5. How to Interpret the Output — “What Works”

### Decision and rationale

- **ACCEPT** — Numeric claims are grounded in evidence and (where applicable) recomputation agrees; coverage is sufficient.
- **REPAIR** — Some issues (e.g. wrong percent, scale/period mismatch) but evidence coverage is decent; suggests the answer could be corrected.
- **FLAG** — No numbers in the answer, or low coverage, or many unsupported claims; needs human review.

The **rationale** field explains in plain language why that decision was chosen.

### Signals (in the response and in logs)

Signals describe *what* was wrong, not the decision itself:

- `recomputation_fail_count` — Recomputed value didn’t match the answer.
- `period_mismatch_count` — Answer referred to a different period than the evidence.
- `unsupported_claims_count` — Claims that couldn’t be grounded or recomputed.
- `coverage_ratio` — Fraction of claims that were supported by evidence/recomputation.
- **P&L-specific (schema v2):** `pnl_table_detected` (0/1), `pnl_identity_fail_count`, `pnl_margin_fail_count`, `pnl_missing_baseline_count`, `pnl_period_strict_mismatch_count`. If YoY is asked but the baseline period is missing in the table → `pnl_missing_baseline_count` > 0 and decision **FLAG**.

So: **to see what works**, run a few requests (via docs or curl), then look at:

1. **decision** and **rationale** — Do they match your expectation (e.g. correct answer → ACCEPT, wrong percent → REPAIR, no numbers → FLAG)?
2. **signals** — Do they reflect the kind of error you introduced (e.g. wrong percent → `recomputation_fail_count` > 0)?
3. **claims** and **verification** — Do the extracted numbers and recomputed values look correct?

---

## 6. Optional: LLM / Stub Mode and Logging

- **LLM mode:** Set `OPENAI_API_KEY` in your environment or in `backend/.env`. The server logs **“Backend running in LLM mode”** at startup; **POST /verify** then uses the real OpenAI API.
- **Stub mode:** No key (or empty key). Server logs **“Backend running in stub mode”**; **POST /verify** still runs but uses a placeholder answer (no real LLM call).
- **Logging:** If `options.log_run` is `true`, each run is appended to `runs/logs.jsonl` (and signals to `runs/signals.csv` or `runs/signals_v2.csv` for schema v2). Logs include `domain`, `engine_used`, `llm_used`, and `llm_fallback_reason`. Path is relative to the project root.

---

## 7. Running the Automated Tests

From the **project root** (with venv activated):

```bash
python -m pytest backend/app/tests -v
```

Or from the **backend** folder:

```bash
python -m pytest app/tests -v
```

Integration tests cover P&L-only scope:

- Health check.
- Verify-only with P&L table → ACCEPT/REPAIR/FLAG as appropriate.
- Text evidence → **FLAG** (P&L verifier requires table evidence).
- **P&L identity correct** (e.g. Gross Profit = Revenue − COGS) → ACCEPT.
- **P&L identity wrong** (table row disagrees with identity) → REPAIR, `pnl_identity_fail_count` > 0.
- **YoY missing baseline** (question asks 2021→2022 but table has only 2022/2023) → **FLAG**, `pnl_missing_baseline_count` > 0.
- **Vague answer** (no numerics) → FLAG.
- **Non-P&L table** (e.g. Category, Count) → FLAG.
- **Margin check** and **synonym-heavy table** (Sales, Cost of revenue, SG&A) → ACCEPT when correct.

If these pass, the P&L verification pipeline is working as intended.

---

## 8. Quick Reference — Inputs Summary

| Goal | Endpoint | Required body |
|------|----------|----------------|
| Verify an answer you have | **POST /verify-only** | `question`, `evidence`, `candidate_answer`; optional `options`. |
| Generate answer with LLM and verify it | **POST /verify** | `question`, `evidence` (table only); optional `options`. |
| Check server is up | **GET /health** | (none) |

Evidence: **Table only** for verification; must be P&L layout. **Table** = `{"type": "table", "content": {"columns": [...], "rows": [...], "units": {...}}}`. Text or non-P&L table → FLAG.

---

## 9. Project Review Summary

| Aspect | Notes |
|--------|--------|
| **Purpose** | P&L / Income Statement–specific verification of numeric claims against table evidence; optional LLM answer generation. |
| **Run** | `cd backend` → `pip install -r requirements.txt` → `python3 -m uvicorn app.main:app --reload`. Or from root: `PYTHONPATH=backend python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. |
| **Try it** | Open http://localhost:8000/docs and use **POST /verify-only** or **POST /verify** with P&L table evidence. |
| **Inputs** | Always: `question` + `evidence` (table, P&L layout). For verify-only add `candidate_answer`; for verify the server generates it. |
| **Outputs** | `decision`, `rationale`, `signals` (incl. P&L fields), `claims`, `verification`, `report`, `domain`, `engine_used`; verify also returns `generated_answer`, `llm_used`, `llm_fallback_reason`. |
| **Evaluation** | P&L cases in `examples/pnl_eval_cases.json`. Run `python3 run_evaluation_api.py` (server must be up). See `EVALUATION_RESULTS.md`. |
| **What to review** | Decision and rationale for P&L cases; YoY baseline strictness; identity/margin signals; logs in `runs/logs.jsonl` with domain and engine_used. |

This document gives you everything needed to **run the project**, **choose and send the right inputs**, and **review what works** manually or via tests.
