# NumericVerifier — Evaluation Results (P&L-Only Refactor)

**Execution:** Real HTTP requests to `http://127.0.0.1:8000`. P&L evaluation cases from `examples/pnl_eval_cases.json`. No fabricated outputs.

---

## P&L Evaluation Table (paste into Excel / Google Sheets)

Copy the block below; paste into a spreadsheet; use Tab as column delimiter.

```
Case_ID	Scenario_Type	Question	Evidence_Table	Endpoint_Used	Expected_Human_Decision	Actual_System_Decision	Key_Actual_Signals	Correctness_Label	Notes
P001	Identity correct	What was gross profit in 2022?	{"columns":["Line Item","2022","2023"],"rows":[["Revenue","100","120"],["COGS","40","50"],["Gross Profit","60","70"]],"units":{}}	/verify-only	ACCEPT	ACCEPT	coverage=1.00	Correct	All claims are grounded and verified. No scale or period mismatches. All recomputations and P&L checks successful. Coverage meets threshold.
P002	Identity wrong but repairable	What was gross profit in 2022?	{"columns":["Line Item","2022"],"rows":[["Revenue","100"],["COGS","40"],["Gross Profit","50"]],"units":{}}	/verify-only	REPAIR	REPAIR	pnl_identity_fail>0; coverage=1.00	Correct	Good evidence coverage (100.0%), but P&L issues: P&L identity failures. Errors appear correctable.
P003	YoY missing baseline	What was the YoY growth from 2021 to 2022?	{"columns":["Line Item","2022","2023"],"rows":[["Revenue","100","120"],["COGS","40","50"],["Gross Profit","60","70"]],"units":{}}	/verify-only	FLAG	FLAG	unsupported>0; pnl_missing_baseline>0; pnl_period_strict_mismatch>0; coverage=0.00	Correct	YoY or baseline period requested but missing in evidence. Requires review.
P004	Margin check correct	What was gross margin in 2022?	{"columns":["Line Item","2022"],"rows":[["Revenue","100"],["COGS","40"],["Gross Profit","60"]],"units":{}}	/verify-only	ACCEPT	FLAG	unsupported>0; coverage=0.00	Over-conservative	Issues detected: low coverage (0.0%), many unsupported claims (1). Requires review.
P005	Synonym-heavy table (Sales, Cost of revenue, SG&A)	What was sales in 2022?	{"columns":["Line Item","2022","2023"],"rows":[["Sales","100","120"],["Cost of revenue","40","50"],["Gross Profit","60","70"],["SG&A","15","18"],["Operating Income","45","52"]],"units":{}}	/verify-only	ACCEPT	ACCEPT	coverage=1.00	Correct	All claims are grounded and verified. No scale or period mismatches. All recomputations and P&L checks successful. Coverage meets threshold.
P006	Non-P&L table	What is the value?	{"columns":["Category","Count"],"rows":[["A","10"],["B","20"]],"units":{}}	/verify-only	FLAG	FLAG	coverage=0.00	Correct	Evidence is not a P&L / Income Statement table.
```

**Note:** P004 (Margin check correct) is marked **Over-conservative**: the system correctly computes gross margin (60%) but does not yet ground percentage claims to computed margins, so the claim is treated as unverified → FLAG. This is conservative (finance safety first).

---

## Summary Statistics (P&L Suite)

| Metric | Value |
|--------|--------|
| **Total test cases** | 6 |
| **% Correct decisions** | 83.3% (5/6) |
| **% Over-permissive** | 0.0% |
| **% Over-conservative** | 16.7% (1/6) — P004 |

**Improvements (P&L-only refactor):**

- **YoY baseline strictness:** P003 — question asks YoY 2021→2022 but table has only 2022/2023 → **FLAG** with `pnl_missing_baseline_count` and rationale "YoY or baseline period requested but missing in evidence." ✅
- **Accounting identity correctness:** P001 (identity correct → ACCEPT), P002 (identity wrong → REPAIR with `pnl_identity_fail_count`). ✅
- **Period strict mismatch:** P003 also increments `pnl_period_strict_mismatch_count` when baseline is missing. ✅
- **Non-P&L gating:** P006 — non-P&L table → **FLAG** with "Evidence is not a P&L / Income Statement table." ✅
- **Synonym support:** P005 — Sales, Cost of revenue, SG&A → correct lookup and ACCEPT. ✅

---

## How to re-run

From project root, with backend running at `http://127.0.0.1:8000`:

```bash
# P&L cases only (default)
python3 run_evaluation_api.py

# Legacy test cases
python3 run_evaluation_api.py --legacy

# P&L + legacy
python3 run_evaluation_api.py --all
```

Redirect to file for a fresh table:

```bash
python3 run_evaluation_api.py > evaluation_output.tsv
```

To start the server (from project root, with app on path):

```bash
PYTHONPATH=backend python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or from `backend/`:

```bash
cd backend && python3 -m uvicorn app.main:app --reload
```
