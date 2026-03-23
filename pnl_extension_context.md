# NumericVerifier — P&L-Only Refactor (Authoritative Context)

You are an AI engineering agent modifying an existing FastAPI codebase called NumericVerifier.

## Non-negotiable goal
Refactor the project so the “finance niche” is explicit and strong:

✅ The system becomes **P&L / Income Statement–specific**, end-to-end.  
✅ The existing generic pipeline must be replaced by a **P&L-first** pipeline.  
✅ Keep the API usable and runnable locally on macOS.  
✅ LLM integration must use the existing OpenAI setup via environment variable (**do NOT hardcode keys**).  
✅ After refactor, run tests + run evaluation script and regenerate evaluation artifacts.

---

## 0) Success criteria (Definition of Done)

### Runtime / API
- `python3 -m uvicorn app.main:app --reload` starts cleanly.
- Swagger UI works at `/docs`.
- `POST /verify-only` works end-to-end for **P&L tables only**.
- `POST /verify` works end-to-end:
  - If OpenAI quota/credits exist → real LLM answer is used.
  - If OpenAI fails (429/insufficient_quota/network/etc.) → fallback to stub answer AND log clearly.

### P&L correctness behaviors
- Detect P&L tables (domain gating).
- Apply P&L accounting identity verification:
  - Gross Profit = Revenue − COGS
  - Operating Income = Gross Profit − Operating Expenses
  - Net Income = Operating Income − Taxes − Interest (only if present)
  - Gross Margin = Gross Profit / Revenue
  - Operating Margin = Operating Income / Revenue
- YoY growth baseline must exist:
  - If question asks YoY and baseline period is missing → MUST `FLAG`.

### Signals & logging
- Runs still log to `runs/logs.jsonl`.
- Signals continue to append per run, but **schema changes must not overwrite old data** (see CSV rules).
- Logs must include:
  - `domain` (table_type + confidence)
  - `engine_used` (e.g., `"pnl"` or `"none"`)
  - `llm_used` and `llm_fallback_reason` (if any)

### Tests + evaluation
- All tests pass (updated for new scope).
- Add new P&L-specific tests.
- Run `run_evaluation_api.py` and regenerate `EVALUATION_RESULTS.md` using new P&L eval cases.

---

## 1) Current project structure you must work within
- Backend is FastAPI.
- Existing endpoints (keep these stable):
  - `POST /verify-only`: verify a provided candidate answer
  - `POST /verify`: generate answer using LLM then verify

It is allowed to add optional fields to response (e.g., `domain`, `engine_used`, `llm_used`).

---

## 2) New architecture (THIS REPLACES EXISTING PIPELINE)

### New pipeline (both endpoints ultimately call the same router/verifier)

Inputs:
- `question`
- `evidence` (MUST be `type="table"` for this refactor)
- `candidate_answer` (verify-only) OR generated answer (verify)

Hard scope rules (apply to BOTH endpoints):
- If `evidence.type != "table"` → decision = `FLAG` with rationale: "P&L verifier requires table evidence."
- If table_type != `"pnl"` → decision = `FLAG` with rationale: "Evidence is not a P&L / Income Statement table."

Pipeline steps (P&L mode only):
1) Evidence ingestion (table)
2) P&L table classification (gate)
   - output: `table_type = "pnl" | "unknown"` and `confidence`
3) P&L semantic parsing into structured form:
   - map line-items to canonical keys (revenue, cogs, gross_profit, opex, op_income, taxes, interest, net_income)
   - support common synonyms (sales, turnover, cost of revenue, SG&A, operating profit, profit after tax, etc.)
4) Numeric claim extraction from answer (reuse existing extraction)
5) Grounding against evidence (still needed)
6) P&L execution engine runs domain-specific checks:
   - accounting identities
   - margin checks (if margin asked/claimed)
   - YoY baseline existence (strict)
7) Generate signals (existing + new pnl_* signals)
8) Decision rules (updated and stricter in P&L mode)
9) Logging to `runs/`

---

## 2.1 Domain Router (REQUIRED for future niches)

Create: `backend/app/verifier/router.py`

Purpose:
- Single deterministic place that chooses which domain engine runs.
- This is NOT an LLM. It is deterministic routing.
- Later you can add more domain engines (balance sheet, cashflow, etc.) without touching endpoints.

Required function:
- `route_and_verify(question, evidence, candidate_answer, options) -> VerifyResponse`

Where:
- `evidence` is the full evidence object from the API (`{"type":"table","content":...}`).

Routing rule (v1):
- If `classify_table_type(evidence.content)` returns `"pnl"` → run P&L pipeline.
- Else → return `FLAG` with rationale: "Evidence is not a P&L / Income Statement table."

Both endpoints (`/verify-only`, `/verify`) must call this router.

---

## 2.2 Supported P&L table layouts (STRICT)

Only support these P&L formats:

### Layout A (preferred)
- First column = line-item labels (Revenue, COGS, etc.)
- Other columns = periods (2022, 2023 / Q1, Q2 / FY2023)

Example:
columns: ["Line Item", "2022", "2023"]
rows:
  ["Revenue", "100", "120"]
  ["COGS", "40", "50"]
  ["Gross Profit", "60", "70"]

### Layout B (allowed only if detected clearly)
- columns: ["Period", "Line Item", "Value"]

If the table does not match supported layouts → decision = `FLAG` with clear rationale.

---

## 2.3 Signals CSV schema versioning (DO NOT BREAK EXISTING DATA)

Signals are used as training data later, so schema stability matters.

Rules:
- Introduce `schema_version` as an integer feature (fixed = 2 for this refactor).
- If `runs/signals.csv` exists and already matches schema_version=2 header → append to `runs/signals.csv`.
- If `runs/signals.csv` exists but is old schema → write new rows to `runs/signals_v2.csv` (new header).
- Never overwrite old signals files.

---

## 2.4 Strict YoY + period handling (P&L mode)

Rules:
- If question asks YoY or references a baseline period not present in parsed P&L periods:
  - increment `pnl_missing_baseline_count`
  - MUST return decision = `FLAG` (not ACCEPT/REPAIR)

- If strict period mismatch is detected in P&L mode (question references period A but answer/grounding uses period B):
  - increment `pnl_period_strict_mismatch_count`
  - MUST return decision = `FLAG`

---

## 2.5 Required P&L evaluation suite (new)

Create a new eval cases file:
- `examples/pnl_eval_cases.jsonl` (one JSON per line) OR `examples/pnl_eval_cases.json` (list)

Must include at least these cases:
1) Identity correct → ACCEPT
2) Identity wrong but repairable → REPAIR
3) YoY missing baseline → FLAG
4) Margin check correct → ACCEPT
5) Synonym-heavy table (Sales/Turnover, Cost of revenue, SG&A) → ACCEPT
6) Non-P&L table → FLAG

Update `run_evaluation_api.py` to run these P&L cases (and optionally legacy cases updated to P&L).

Regenerate `EVALUATION_RESULTS.md`.

---

## 3) Implementation tasks (do in this order)

### 3.1 Add P&L domain classifier (gate)
Create: `backend/app/verifier/domain.py`

- `classify_table_type(evidence_table) -> DomainContext`
- `DomainContext` fields:
  - `table_type: "pnl" | "unknown"`
  - `confidence: float`
  - `matched_terms: List[str]` (for explainability/logging)

Heuristics:
- scan row labels + headers for canonical P&L line items:
  - revenue, sales, turnover
  - cogs, cost of sales, cost of revenue
  - gross profit
  - operating expenses, SG&A
  - operating income / operating profit / EBIT
  - taxes, income tax
  - interest
  - net income / net profit / profit after tax
- Require a conservative minimum confidence threshold.
- Prefer false-negative (unknown) over false-positive.

### 3.2 Add P&L table parser (line-item mapper)
Create: `backend/app/verifier/pnl_parser.py`

Responsibilities:
- Support Layout A and Layout B.
- Normalize line item labels (lowercase, strip punctuation, remove extra spaces).
- Map synonyms to canonical keys:
  - revenue: "revenue", "sales", "turnover", "total revenue"
  - cogs: "cogs", "cost of sales", "cost of revenue"
  - gross_profit: "gross profit", "gross income"
  - operating_expenses: "operating expenses", "opex", "sg&a", "selling general administrative"
  - operating_income: "operating income", "operating profit", "ebit"
  - taxes: "tax", "taxes", "income tax"
  - interest: "interest", "interest expense"
  - net_income: "net income", "net profit", "profit after tax", "profit"

Output (structured):
- canonical values by period:
  - `periods: List[str]`
  - `items: Dict[str, Dict[str, float]]`  # items[key][period] = value
- keep provenance for logging/debug:
  - original row label matched for each key

### 3.3 Add P&L execution engine
Create: `backend/app/verifier/engines/pnl_execution.py`

Must implement domain checks:
- Identity checks (when operands exist for the same period):
  - gross_profit = revenue - cogs
  - operating_income = gross_profit - operating_expenses
  - net_income = operating_income - taxes - interest  (only subtract components that exist)
- Margin checks (when asked or when a margin claim exists):
  - gross_margin = gross_profit / revenue
  - operating_margin = operating_income / revenue
- YoY baseline existence check:
  - if question asks YoY growth between periods, verify both periods exist in parsed table periods

Integration requirements:
- Must integrate with existing VerificationResult structures:
  - set `execution_supported=True/False`
  - populate `execution_result` when a computation was performed
  - add constraint violations such as:
    - `"pnl_identity_mismatch"`
    - `"pnl_margin_mismatch"`
    - `"missing_yoy_baseline"`

### 3.4 Update constraints for P&L strictness
Update: `backend/app/verifier/engines/constraints.py`

Add P&L strict constraints:
- strict period coverage:
  - if question references year/quarter X and parsed P&L has no X → `"missing_period_in_evidence"`
- strict mismatch:
  - if claim/grounding context uses different period than question → `"pnl_period_strict_mismatch"`
- YoY baseline:
  - if YoY requested and baseline missing → `"missing_yoy_baseline"`

### 3.5 Update signals (schema v2)
Update: `backend/app/verifier/signals.py`

Add these fields:
- `schema_version` (fixed int = 2)
- `pnl_table_detected` (0/1)
- `pnl_identity_fail_count`
- `pnl_margin_fail_count`
- `pnl_missing_baseline_count`
- `pnl_period_strict_mismatch_count`

CSV output rules:
- If existing `runs/signals.csv` header matches schema_version=2 → append there.
- If existing `runs/signals.csv` is old → append to `runs/signals_v2.csv` with the v2 header.
- Never overwrite old signals files.

### 3.6 Update decision logic (P&L mode)
Update: `backend/app/verifier/decision_rules.py`

In P&L mode:
- If `pnl_table_detected == 0` → `FLAG`
- If `pnl_missing_baseline_count > 0` → `FLAG`
- If `pnl_period_strict_mismatch_count > 0` → `FLAG`
- If coverage is good AND (`pnl_identity_fail_count > 0` OR `pnl_margin_fail_count > 0`) → `REPAIR`
- Otherwise keep the existing overall structure, but prefer finance safety (more conservative than generic).

### 3.7 Update pipeline integration via router
Update: `backend/app/api/verify.py`

- Both endpoints must call `route_and_verify(...)` from `backend/app/verifier/router.py`.
- `/verify-only`:
  - must use provided `candidate_answer`
- `/verify`:
  - generate answer using LLM provider first (or stub fallback)
  - pass generated answer to router

Response/report must include:
- `domain`: `{ "table_type": "pnl" | "unknown", "confidence": float }`
- `engine_used`: `"pnl"` or `"none"`
- `llm_used`: true/false
- `llm_fallback_reason`: string or null

### 3.8 LLM provider requirements
Update: `backend/app/llm/provider.py`

Requirements:
- Use `OPENAI_API_KEY` from environment only.
- Do NOT read keys from repo files directly.
- If OpenAI request fails (429/quota/network):
  - log warning with reason
  - return stub answer
  - ensure `llm_used=false` and `llm_fallback_reason` is set

---

## 4) Test plan (must implement)

Add/update tests in `backend/app/tests/`:

### 4.1 P&L detection test
- Provide a valid P&L table → assert `table_type=="pnl"`
- Provide a random table → assert router returns `FLAG`

### 4.2 Identity checks
Use a clean P&L table (single period) or two periods:

Example (single period):
- Revenue=100, COGS=40, Gross Profit=60
- Opex=10, Operating Income=50
- Taxes=5, Interest=5, Net Income=40

Tests:
- Correct answer → ACCEPT
- Wrong gross profit or net income → REPAIR (with `pnl_identity_fail_count>0`)

### 4.3 YoY baseline strictness
- Question asks: "YoY growth 2021 to 2022"
- Evidence has only 2022 and 2023
- Must return:
  - decision = FLAG
  - `pnl_missing_baseline_count>0`

### 4.4 Legacy tests
Any legacy test using non-P&L evidence must be updated:
- either convert to P&L-style tables
- OR assert it now FLAGs (non-P&L)

---

## 5) Evaluation artifacts (must be regenerated)
After implementation:
- Start backend
- Run: `python run_evaluation_api.py`
- Update `EVALUATION_RESULTS.md`
- Include summary stats: correct / over-permissive / over-conservative
- Specifically highlight improvements in:
  - strict period mismatch handling
  - YoY baseline strictness
  - identity/margin checks (new)

---

## 6) Deliverables
STOP ONLY WHEN ALL DONE:

- Code compiles and server runs
- tests pass
- `examples/pnl_eval_cases.*` exists
- evaluation report regenerated
- project guide updated to reflect P&L-only scope:
  - update `PROJECT_REVIEW_AND_USER_GUIDE.md` accordingly
- logs include domain + engine_used + llm_used fields
- signals CSV schema v2 created safely without overwriting old data