# NumericVerifier — Project Review & User Guide

This document explains **how to run the project**, **what inputs to give**, and **how to review what works**. It is written for humans reviewing or using the system.

---

## 1. What This Project Does

**NumericVerifier** is a backend that:

1. **Takes** a question and evidence (text or table).
2. **Optionally** uses an LLM to generate an answer, or **you** provide the answer.
3. **Verifies** numeric claims in the answer against the evidence (lookup, recomputation, constraints).
4. **Returns** a decision: **ACCEPT**, **REPAIR**, or **FLAG**, plus signals and a full audit-style report.

So: it checks whether numbers in an answer are correct and consistent with the evidence.

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
| `evidence` | Yes | Either **text** or **table** (see formats below). |
| `candidate_answer` | Yes | The answer you want verified (must contain numbers to verify). |
| `options` | No | `{"tolerance": 0.01, "log_run": true}` — tolerance for numeric comparison; `log_run` to write to `runs/logs.jsonl`. |

**Evidence formats:**

**1. Text evidence**

```json
"evidence": {
  "type": "text",
  "content": "The company reported revenue of 5000000 dollars in Q1 2024."
}
```

**2. Table evidence**

```json
"evidence": {
  "type": "table",
  "content": {
    "columns": ["Quarter", "Revenue"],
    "rows": [
      ["Q1 2024", "5000000"],
      ["Q2 2024", "5500000"]
    ],
    "units": { "Revenue": "dollars" }
  }
}
```

**Example full request (verify-only):**

```json
{
  "question": "What was the total revenue for Q1 2024?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Quarter", "Revenue"],
      "rows": [["Q1 2024", "5000000"], ["Q2 2024", "5500000"]],
      "units": { "Revenue": "dollars" }
    }
  },
  "candidate_answer": "The total revenue for Q1 was 5,000,000 dollars.",
  "options": { "tolerance": 0.01, "log_run": false }
}
```

**What you get back:** `decision` (ACCEPT/REPAIR/FLAG), `rationale`, `signals`, `claims`, `grounding`, `verification`, `report`.

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

**What you get back:** Same as verify-only, **plus** `generated_answer` (the LLM’s answer that was verified).

**Note:** If `OPENAI_API_KEY` is not set (in environment or in `backend/.env`), the server uses **stub mode**: it returns a placeholder answer and still runs verification on that placeholder. So you can run and test without an API key.

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
| `accept_case.json` | Question + table + answer that matches evidence → expect **ACCEPT**. |
| `repair_case.json` | Answer with a numeric claim that can be checked (e.g. growth %) → may get **REPAIR** if there’s a mismatch. |
| `flag_case.json` | Answer that doesn’t match evidence → expect **FLAG**. |

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

- `recomputation_fail_count` — Recomputed value didn’t match the answer (e.g. said 20% but data says 50%).
- `period_mismatch_count` — Answer referred to a different period than the evidence.
- `unsupported_claims_count` — Claims that couldn’t be grounded or recomputed.
- `coverage_ratio` — Fraction of claims that were supported by evidence/recomputation.

So: **to see what works**, run a few requests (via docs or curl), then look at:

1. **decision** and **rationale** — Do they match your expectation (e.g. correct answer → ACCEPT, wrong percent → REPAIR, no numbers → FLAG)?
2. **signals** — Do they reflect the kind of error you introduced (e.g. wrong percent → `recomputation_fail_count` > 0)?
3. **claims** and **verification** — Do the extracted numbers and recomputed values look correct?

---

## 6. Optional: LLM / Stub Mode and Logging

- **LLM mode:** Set `OPENAI_API_KEY` in your environment or in `backend/.env`. The server logs **“Backend running in LLM mode”** at startup; **POST /verify** then uses the real OpenAI API.
- **Stub mode:** No key (or empty key). Server logs **“Backend running in stub mode”**; **POST /verify** still runs but uses a placeholder answer (no real LLM call).
- **Logging:** If `options.log_run` is `true`, each run is appended to `runs/logs.jsonl` (and signals to `runs/signals.csv`). Path is relative to the project root. Use this to review runs later.

---

## 7. Running the Automated Tests

From the **backend** folder:

```bash
python -m pytest app/tests/test_integration.py -v
```

This runs integration tests that cover:

- Health check.
- Verify-only with table and text evidence.
- **Case A:** Correct arithmetic (e.g. 50% from 10→15) → ACCEPT.
- **Case B:** Incorrect arithmetic (e.g. 20% instead of 50%) → REPAIR, `recomputation_fail_count` > 0.
- **Case C:** Vague answer (no numbers) → FLAG.
- **Case D:** Period mismatch → `period_mismatch_count` > 0, FLAG or REPAIR.

If these pass, the main flow (verify-only and verification logic) is working as intended.

---

## 8. Quick Reference — Inputs Summary

| Goal | Endpoint | Required body |
|------|----------|----------------|
| Verify an answer you have | **POST /verify-only** | `question`, `evidence`, `candidate_answer`; optional `options`. |
| Generate answer with LLM and verify it | **POST /verify** | `question`, `evidence` (table only); optional `options`. |
| Check server is up | **GET /health** | (none) |

Evidence: **text** = `{"type": "text", "content": "..."}`. **Table** = `{"type": "table", "content": {"columns": [...], "rows": [...], "units": {...}}}`.

---

## 9. Project Review Summary

| Aspect | Notes |
|--------|--------|
| **Purpose** | Verify numeric claims in answers against given evidence; optional LLM answer generation. |
| **Run** | `cd backend` → `pip install -r requirements.txt` → `python3 -m uvicorn app.main:app --reload`. |
| **Try it** | Open http://localhost:8000/docs and use **POST /verify-only** or **POST /verify** with the example inputs above. |
| **Inputs** | Always: `question` + `evidence`. For verify-only add `candidate_answer`; for verify the server generates it. |
| **Outputs** | `decision` (ACCEPT/REPAIR/FLAG), `rationale`, `signals`, `claims`, `verification`, `report`; verify also returns `generated_answer`. |
| **What to review** | Decision and rationale for a few hand-crafted cases; signals and claims in the JSON response; optional logs in `runs/logs.jsonl`. |

This document gives you everything needed to **run the project**, **choose and send the right inputs**, and **review what works** manually or via tests.
