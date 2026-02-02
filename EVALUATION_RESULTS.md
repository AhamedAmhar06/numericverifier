# NumericVerifier — Evaluation Results (Live API)

**Execution:** Real HTTP requests to `http://127.0.0.1:8000`. No fabricated outputs.

---

## Evaluation Table (paste into Excel / Google Sheets)

Copy the block below; paste into a spreadsheet; use Tab as column delimiter.

```
Case_ID	Scenario_Type	Question	Evidence_Table	Endpoint_Used	Expected_Human_Decision	Actual_System_Decision	Key_Actual_Signals	Correctness_Label	Notes
E001	Correct numeric answer (lookup)	What was the revenue for Q1 2024?	{"columns":["Quarter","Revenue"],"rows":[["Q1 2024","5000000"],["Q2 2024","5500000"]],"units":{"Revenue":"dollars"}}	/verify-only	ACCEPT	FLAG	unsupported>0; coverage=0.50	Over-conservative	Issues detected: low coverage (50.0%), many unsupported claims (1). Requires review.
E002	Correct arithmetic (percent increase)	What is the percent change in revenue from Q1 to Q2?	{"columns":["Period","Revenue"],"rows":[["Q1","10"],["Q2","15"]],"units":{"Revenue":"dollars"}}	/verify-only	ACCEPT	ACCEPT	coverage=1.00	Correct	All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.
E003	Correct total computation	What is the total revenue for Q1 and Q2?	{"columns":["Quarter","Revenue"],"rows":[["Q1","3"],["Q2","7"]],"units":{"Revenue":"dollars"}}	/verify-only	ACCEPT	FLAG	unsupported>0; coverage=0.00	Over-conservative	Issues detected: low coverage (0.0%), many unsupported claims (1). Requires review.
E004	Incorrect arithmetic (wrong percent)	What is the percent change in revenue from Q1 to Q2?	{"columns":["Period","Revenue"],"rows":[["Q1","10"],["Q2","15"]],"units":{"Revenue":"dollars"}}	/verify-only	REPAIR	REPAIR	recomp_fail>0; coverage=1.00	Correct	Good evidence coverage (100.0%), but issues detected: recomputation failures. Errors appear correctable.
E005	Incorrect total	What is the total revenue for Q1 and Q2?	{"columns":["Quarter","Revenue"],"rows":[["Q1","100"],["Q2","200"]],"units":{"Revenue":"dollars"}}	/verify-only	REPAIR	FLAG	unsupported>0; coverage=0.00	Over-conservative	Issues detected: low coverage (0.0%), many unsupported claims (1). Requires review.
E006	Fabricated number	What was the revenue for Q1 2024?	{"columns":["Quarter","Revenue"],"rows":[["Q1 2024","5000000"],["Q2 2024","5500000"]],"units":{"Revenue":"dollars"}}	/verify-only	FLAG	FLAG	unsupported>0; coverage=0.00	Correct	Issues detected: low coverage (0.0%), many unsupported claims (2). Requires review.
E007	Period mismatch	What was the value for the period?	{"columns":["Period","Value"],"rows":[["Q1 2024","2023"],["Q2 2024","2024"]],"units":{}}	/verify-only	FLAG	REPAIR	period_mismatch>0; coverage=1.00	Over-permissive	Good evidence coverage (100.0%), but issues detected: period mismatches. Errors appear correctable.
E008	Missing baseline data	What was the year-over-year growth?	{"columns":["Quarter","Revenue"],"rows":[["Q1 2024","100"],["Q2 2024","150"]],"units":{"Revenue":"dollars"}}	/verify-only	REPAIR	ACCEPT	coverage=1.00	Over-permissive	All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.
E009	Vague / non-numeric answer	What is the percent change in revenue from Q1 to Q2?	{"columns":["Period","Revenue"],"rows":[["Q1","10"],["Q2","15"]],"units":{"Revenue":"dollars"}}	/verify-only	FLAG	FLAG	coverage=0.00	Correct	Candidate answer contains no numeric values; cannot verify.
E010	Mixed correct and incorrect claims	What were Q1 and Q2 revenues and the growth rate?	{"columns":["Quarter","Revenue"],"rows":[["Q1 2024","10"],["Q2 2024","15"]],"units":{"Revenue":"dollars"}}	/verify-only	REPAIR	REPAIR	recomp_fail>0; coverage=1.00	Correct	Good evidence coverage (100.0%), but issues detected: recomputation failures. Errors appear correctable.
E011	Number not present in table	What was profit in Q2?	{"columns":["Quarter","Revenue"],"rows":[["Q1 2024","5000000"],["Q2 2024","5500000"]],"units":{"Revenue":"dollars"}}	/verify-only	FLAG	FLAG	unsupported>0; coverage=0.00	Correct	Issues detected: low coverage (0.0%), many unsupported claims (1). Requires review.
E012	Rounding / tolerance edge	What was the revenue for Q1?	{"columns":["Quarter","Revenue"],"rows":[["Q1 2024","5000000.00"]],"units":{"Revenue":"dollars"}}	/verify-only	ACCEPT	ACCEPT	coverage=1.00	Correct	All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.
E013	LLM-generated answer (verify endpoint)	What is the percent change in revenue from Q1 to Q2?	{"columns":["Period","Revenue"],"rows":[["Q1","10"],["Q2","15"]],"units":{"Revenue":"dollars"}}	/verify	ACCEPT	ACCEPT	coverage=1.00	Correct	All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.
E014	Hedged answer (approximately)	What was the total revenue for Q1?	{"columns":["Quarter","Revenue"],"rows":[["Q1 2024","5000000"]],"units":{"Revenue":"dollars"}}	/verify-only	ACCEPT	ACCEPT	coverage=1.00	Correct	All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.
E015	Question asks for percent but answer has no percent	What is the percentage increase in revenue?	{"columns":["Period","Revenue"],"rows":[["Q1","10"],["Q2","15"]],"units":{"Revenue":"dollars"}}	/verify-only	FLAG	FLAG	unsupported>0; coverage=0.00	Correct	Question asks for a percentage but answer contains no percentage value.
```

**Note:** E007 Correctness_Label set to **Over-permissive** (expected FLAG, actual REPAIR; system was lenient).

---

## Summary Statistics

| Metric | Value |
|--------|--------|
| **Total test cases** | 15 |
| **% Correct decisions** | 66.7% (10/15) |
| **% Over-permissive** | 13.3% (2/15) — E007, E008 |
| **% Over-conservative** | 20.0% (3/15) — E001, E003, E005 |

**Most common failure mode (from signals):**
- **Low coverage / unsupported claims** (E001, E003, E005, E006, E011, E015): claim not grounded or total not recomputed → FLAG.
- **Recomputation failures** (E004, E010): wrong percent/total → REPAIR (correct).
- **Period mismatch** (E007): detected but decision REPAIR instead of FLAG → over-permissive.

---

## How to re-run

From project root, with backend running at `http://127.0.0.1:8000`:

```bash
python3 run_evaluation_api.py
```

Redirect to file for a fresh table:

```bash
python3 run_evaluation_api.py > evaluation_output.tsv
```
