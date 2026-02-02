## 1) Project goal (5 lines)

NumericVerifier is a backend system that verifies numeric claims in answers to finance-style questions against provided evidence (primarily tables).  
It can either accept a user-provided answer or generate one via an LLM, then run a deterministic verification pipeline.  
The pipeline extracts numeric claims, grounds them in the evidence, recomputes implied quantities, and computes risk signals.  
Based on those signals, it outputs a decision: **ACCEPT**, **REPAIR**, or **FLAG**, plus a full audit report.  
The same signals are logged to build datasets for training an ML decision model that may later replace or augment rules.

---

## 2) Current architecture (ASCII diagram)

High-level runtime architecture:

```
Client (curl / UI / tests)
        |
        v
   FastAPI app (backend/app/main.py)
        |
        +-- /health        → health router
        |
        +-- /verify-only   → verification router (user-provided answer)
        |
        +-- /verify        → verification router (LLM-generated answer)
                    |
                    v
            LLM provider (backend/app/llm/provider.py)
                    |
                    v
          OpenAI API (if OPENAI_API_KEY set) / Stub (otherwise)

Verification pipeline (inside /verify-only and /verify):

Question + Evidence + Candidate Answer
        |
        v
  extract_numeric_claims (extract.py)
        |
        v
  normalize_claims (normalize.py)
        |
        v
  ingest_evidence (evidence.py)
        |
        v
  ground_claims (grounding.py)
        |
        v
  verification engines (engines/lookup.py, execution.py, constraints.py)
        |
        v
  compute_signals (signals.py)
        |
        v
  make_decision (decision_rules.py)
        |
        v
  generate_report (report.py)
        |
        v
  log_run / log_signals (eval/logging.py → runs/logs.jsonl, runs/signals.csv)
```

---

## 3) Folder tree (2 levels deep)

Repository root:

```
.
├── backend/
│   ├── app/
│   ├── README.md
│   ├── requirements.txt
│   └── test_examples.py
├── examples/
├── runs/
├── generate_evaluation_report.py
├── llm_integration_context.md
├── ml_context.md
├── ml_decision_model.ipynb
├── PROJECT_REVIEW_AND_USER_GUIDE.md
├── EVALUATION_RESULTS.md
└── run_evaluation_api.py
```

Backend (2 levels under `backend/app`):

```
backend/app/
├── api/
│   ├── health.py
│   └── verify.py
├── core/
│   ├── config.py
│   └── logging.py
├── eval/
│   └── logging.py
├── llm/
│   ├── __init__.py
│   └── provider.py
├── ml/
│   ├── __init__.py
│   └── decision_model.py
├── tests/
│   ├── test_decision.py
│   ├── test_execution.py
│   ├── test_extract.py
│   ├── test_grounding.py
│   ├── test_integration.py
│   └── test_normalize.py
└── verifier/
    ├── decision_rules.py
    ├── evidence.py
    ├── extract.py
    ├── grounding.py
    ├── normalize.py
    ├── report.py
    ├── signals.py
    ├── types.py
    └── engines/
        ├── constraints.py
        ├── execution.py
        └── lookup.py
```

---

## 4) API

### 4.1 Endpoints overview

- **GET `/health`** — health check.
- **GET `/`** — root; returns a simple JSON message.
- **POST `/verify-only`** — run full verification pipeline on a **user-provided** candidate answer.
- **POST `/verify`** — generate an answer via the LLM (or stub) from question + table evidence, then run the same verification pipeline.

Only **`POST /verify`** calls the LLM provider (`generate_llm_answer` in `backend/app/llm/provider.py`). `POST /verify-only` never calls the LLM.

### 4.2 `GET /health`

**Request:** none  
**Response example:**

```json
{
  "status": "ok"
}
```

### 4.3 `GET /`

**Request:** none  
**Response example:**

```json
{
  "message": "NumericVerifier API"
}
```

### 4.4 `POST /verify-only` (user-provided answer)

**Request schema (Pydantic `VerifyRequest`):**

```json
{
  "question": "What was the total revenue for Q1 2024?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Quarter", "Revenue"],
      "rows": [
        ["Q1 2024", "5000000"],
        ["Q2 2024", "5500000"]
      ],
      "units": {
        "Revenue": "dollars"
      }
    }
  },
  "candidate_answer": "The total revenue for Q1 2024 was $5,000,000.",
  "options": {
    "tolerance": 0.01,
    "log_run": true
  }
}
```

- `evidence.type`: `"text"` or `"table"`.
- `evidence.content`: string (for text) or table JSON (`columns` / `rows` / `units`).
- `options.tolerance`: numeric tolerance for comparisons.
- `options.log_run`: whether to log to `runs/`.

**Response shape (conceptual):**

```json
{
  "decision": "ACCEPT | REPAIR | FLAG",
  "rationale": "plain-English explanation",
  "signals": {
    "unsupported_claims_count": 0,
    "coverage_ratio": 1.0,
    "recomputation_fail_count": 0,
    "max_relative_error": 0.0,
    "mean_relative_error": 0.0,
    "scale_mismatch_count": 0,
    "period_mismatch_count": 0,
    "ambiguity_count": 0
  },
  "claims": [ /* list of NumericClaim dicts */ ],
  "grounding": [ /* list of GroundingMatch dicts */ ],
  "verification": [ /* list of VerificationResult dicts */ ],
  "report": { /* AuditReport dict; full audit */ }
}
```

### 4.5 `POST /verify` (LLM-generated answer + verification)

**Request schema (Pydantic `VerifyWithLLMRequest`):**

```json
{
  "question": "What is the percent change in revenue from Q1 to Q2?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Period", "Revenue"],
      "rows": [
        ["Q1", "10"],
        ["Q2", "15"]
      ],
      "units": {
        "Revenue": "dollars"
      }
    }
  },
  "options": {
    "tolerance": 0.01,
    "log_run": false
  }
}
```

Notes:
- `evidence.type` **must** be `"table"`; text evidence is rejected for this endpoint.
- `candidate_answer` is **not** provided by the client; it is generated server-side.

**Flow:**

1. `generate_llm_answer(question, evidence.content)` is called.
2. Generated answer (or stub) is passed into the same pipeline as `/verify-only`.

**Response shape:**

Same as `/verify-only`, with an additional top-level field:

```json
{
  "decision": "ACCEPT | REPAIR | FLAG",
  "rationale": "...",
  "signals": { /* as above */ },
  "claims": [ ... ],
  "grounding": [ ... ],
  "verification": [ ... ],
  "report": { ... },
  "generated_answer": "LLM (or stub) answer text"
}
```

---

## 5) Verification pipeline

### 5.1 Extraction (numeric claim detection)

File: `backend/app/verifier/extract.py`  
Function: `extract_numeric_claims(text: str) -> List[NumericClaim]`

Responsibilities:
- Scan answer text for numeric patterns, including:
  - integers and decimals (`123`, `123.45`)
  - comma-separated numbers (`1,234,567`)
  - negative numbers, including parentheses notation (`(500)`)
  - percentages (`10%`, `12.5%`)
  - currency forms (`$5,000`, `5000 dollars`)
  - scale tokens (`5M`, `3 million`, `2.5K`, etc.)
- Produce `NumericClaim` dataclasses with:
  - `raw_text`
  - `parsed_value` (float, with scale expanded and percent converted to decimal)
  - `char_span` (start, end indices)
  - `unit` (e.g. `"percent"`, `"dollar"`)
  - `scale_token` (e.g. `\"K\"`, `\"million\"`).

Normalization (`normalize_claims` in `normalize.py`) currently preserves claims, relying mostly on extraction to handle commas, scales, and percents.

### 5.2 Grounding (lookup against evidence)

Files:
- `verifier/evidence.py` — `ingest_evidence` for text/table.
- `verifier/grounding.py` — `ground_claims`.

Evidence ingestion:
- Text:
  - Extracts numbers from the text and wraps them as `EvidenceItem` with `context` set to surrounding text.
- Table:
  - Reads `columns`, `rows`, `units`.
  - Creates `EvidenceItem` for each numeric cell; `location` is `row:<i>,col:<j>`.
  - `context` is set to the first column in the row (e.g. `"Q1 2024"`) to support period checks.

Grounding:
- Attempt to match each `NumericClaim` to one or more `EvidenceItem`s within a numeric tolerance.
- Returns `GroundingMatch` with:
  - `distance` (absolute difference),
  - `relative_error`,
  - `ambiguous` flag (if multiple matches).

### 5.3 Execution engine (recomputation)

File: `verifier/engines/execution.py`  
Function: `verify_execution(claim, grounding_match, all_claims, evidence_items, answer_text)`

Supported recomputation patterns (heuristic):
- **Percent change**
  - Detect via `claim.unit == "percent"` or keywords (`"change"`, `"increase"`, `"decrease"`, `"growth"`, `"%"`, etc.).
  - Compute percent change for candidate operand pairs using:
    - `compute_percent_change(old, new) = ((new - old) / old) * 100`.
  - Compare recomputed percent vs claimed percent (stored as decimal in signals, but compared in percentage points).
  - If recomputed value is within a tolerance (e.g., ≤ max(0.1, tol × 100)), set `execution_supported=True`; otherwise, record `execution_error`.

- **Totals / sums**
  - Look for keywords (`"total"`, `"sum"`, `"combined"`, `"together"`).
  - Try subsets of other claim values as operands; if any subset sum matches the claim within tolerance, mark as supported.

- **Ratios**
  - Look for keywords (`"ratio"`, `"per"`, `"divided"`, `"/"`).
  - Try ratios between claims and see if they match any evidence value within tolerance.

If the engine detects a computation intent but cannot recompute, it records an `execution_error`. These errors drive `recomputation_fail_count` in signals.

### 5.4 Constraints (scale/period/etc.)

File: `verifier/engines/constraints.py`  
Function: `verify_constraints(claim, grounding_match, all_claims, evidence_items)`

Checks:
- **Scale mismatch**
  - Compare claim scale tokens (e.g. `M`, `million`, `K`, `thousand`) to magnitude of evidence values.
  - If the claim suggests millions but evidence magnitude suggests thousands (or vice versa), add a `"Scale mismatch"` violation.

- **Period mismatch**
  - Use a simple keyword list (`\"2023\"`, `\"2024\"`, `\"Q1\"`, `\"Q2\"`, month names, etc.).
  - Compare time-related keywords in `claim.raw_text` vs `grounding_match.evidence.context` (e.g. `"Q1 2024"` from table row label).
  - If both contain period indicators but they do not overlap, add a `"Period mismatch"` violation.

Constraint violations are stored in `VerificationResult.constraint_violations` and contribute to `scale_mismatch_count` and `period_mismatch_count` in signals.

### 5.5 Decision policy (ACCEPT / REPAIR / FLAG)

File: `verifier/decision_rules.py`  
Function: `make_decision(signals: VerifierSignals, verification_results: List[VerificationResult]) -> Decision`

Signals used:
- `unsupported_claims_count`
- `coverage_ratio`
- `recomputation_fail_count`
- `scale_mismatch_count`
- `period_mismatch_count`
- `ambiguity_count`

Fixed policy:

- **ACCEPT** if:
  - `unsupported_claims_count == 0`
  - `scale_mismatch_count == 0`
  - `period_mismatch_count == 0`
  - `recomputation_fail_count == 0`
  - `coverage_ratio >= coverage_threshold` (from settings, default 0.8).

- **REPAIR** if:
  - `coverage_ratio >= 0.6` (good coverage), and
  - at least one of:
    - `scale_mismatch_count > 0`
    - `period_mismatch_count > 0`
    - `recomputation_fail_count > 0`
  - and `unsupported_claims_count` is relatively small (`<= 30%` of total results).

- **FLAG** (default) if:
  - `coverage_ratio` is below threshold, or
  - ambiguity high, or
  - unsupported claims high.

Separately, **input validation** in `validate_candidate_answer` short-circuits to **FLAG** when:
- Candidate answer has **no numeric values**, or
- Question explicitly asks for a percentage but the answer contains **no percent claim**.

---

## 6) Logging

File: `backend/app/eval/logging.py`

### 6.1 `runs/logs.jsonl`

- Writer: `log_run(report: AuditReport, extra: Dict[str, Any] = None)`.
- For each verification run:
  - Serializes `AuditReport` via `report.to_dict()`:
    - `timestamp`
    - `question`
    - `candidate_answer`
    - `evidence_type`
    - `tolerance`
    - `claims` (list of claim dicts)
    - `grounding` (list of grounding match dicts)
    - `verification` (list of verification result dicts, including execution results/errors)
    - `signals` (dict)
    - `decision` (dict with `decision` + `rationale`)
  - Optionally merges `extra` (e.g. `{"generated_answer": "..."}`
    for the `/verify` endpoint).
  - Appends as one JSON object per line.

### 6.2 `runs/signals.csv`

- Writer: `log_signals(signals: VerifierSignals, decision: str)`.
- For each run, appends a single CSV row.
- Columns are taken from `VerifierSignals.to_dict()` plus `decision`.

**Exact columns** (from header in `runs/signals.csv`):

- `unsupported_claims_count`
- `coverage_ratio`
- `recomputation_fail_count`
- `max_relative_error`
- `mean_relative_error`
- `scale_mismatch_count`
- `period_mismatch_count`
- `ambiguity_count`
- `decision`

These are the features + label used by the ML notebook.

---

## 7) Tests

Location: `backend/app/tests/`

### 7.1 How to run tests

From `backend/`:

```bash
python -m pytest app/tests/ -v
```

Or individual files, e.g.:

```bash
python -m pytest app/tests/test_integration.py -v
```

### 7.2 Test files and behaviors

- `test_extract.py`
  - Validates **numeric extraction**:
    - integers, decimals, comma-separated numbers
    - negative numbers (including parentheses)
    - scale tokens (K/M/B, words)
    - percent extraction (unit = \"percent\").

- `test_normalize.py`
  - Checks that normalization preserves claim values and does not drop claims.

- `test_grounding.py`
  - Tests **ground_claims** with:
    - exact matches,
    - matches within tolerance,
    - ambiguous matches (multiple equal values),
    - table evidence.

- `test_execution.py`
  - Unit tests for `compute_percent_change`, `compute_total`, `compute_ratio`.
  - Integration test for `verify_execution` on a percent-change sentence to ensure it runs without crashing and handles percent recomputation.

- `test_decision.py`
  - Checks **decision rules**:
    - ACCEPT when signals are all \"good\".
    - REPAIR when coverage is good but issues (recomputation/scale/period) exist.
    - FLAG when coverage is low and ambiguity/unsupported claims are high.

- `test_integration.py`
  - Uses `TestClient` against the FastAPI app.
  - Covers:
    - `/health` basic sanity.
    - `/verify-only` with:
      - table evidence (ACCEPT-style case),
      - text evidence,
      - percent-change table (ACCEPT/REPAIR/FLAG behaviors depending on input).

These tests validate extraction, normalization, grounding, execution, decisions, and basic API integration, but they are not exhaustive for all the evaluation scenarios in `EVALUATION_RESULTS.md`.

---

## 8) ML notebook

Artifacts:
- Notebook: `ml_decision_model.ipynb`
- Context doc: `ml_context.md`
- Backend stub: `backend/app/ml/decision_model.py` (for later integration).

### 8.1 Where it is and what it does

- `ml_decision_model.ipynb` (project root) implements a **multiclass classifier** that predicts the final decision (**ACCEPT / REPAIR / FLAG**) from verifier-generated numeric signals.
- It is intended to replace or augment the rule-based `make_decision` logic, but currently runs offline only.

### 8.2 Features it uses

From `ml_context.md` and the notebook:

**Input features (columns in `signals.csv`):**

- `unsupported_claims_count`
- `coverage_ratio`
- `recomputation_fail_count`
- `max_relative_error`
- `mean_relative_error`
- `scale_mismatch_count`
- `period_mismatch_count`
- `ambiguity_count`

No raw text, no question/evidence/answer are used as features (to avoid leakage).

### 8.3 Labels it expects

- Label column: `decision` (string) with values:
  - `"ACCEPT"`
  - `"REPAIR"`
  - `"FLAG"`

The notebook encodes them (e.g. ACCEPT→0, REPAIR→1, FLAG→2) for modeling.

### 8.4 How it loads `signals.csv`

In the notebook:
- Uses `pandas.read_csv(Path(\"runs\") / \"signals.csv\")` (or equivalent) to load the dataset.
- Drops non-feature columns except `decision`.
- Splits into train/validation (stratified), scales features, trains models (Logistic Regression, Random Forest).
- Exports:
  - `decision_model.joblib` (trained model),
  - `feature_schema.json` (ordered feature list),
  - evaluation summary (metrics + confusion matrix) for future backend integration.

---

## 9) Known current failure modes (from evaluation table)

Source: `EVALUATION_RESULTS.md` — 15 live API test cases (`run_evaluation_api.py`).

### 9.1 Over-permissive scenarios

Cases where the system was **too lenient** compared to human expectation:

- **E007 – Period mismatch**
  - Scenario: Period context differs (evidence row labeled `Q1 2024`, value `2023`; answer states \"value for 2023 was 2023\").  
  - Expected human decision: **FLAG** (period mismatch should fully reject).  
  - Actual system decision: **REPAIR** with `period_mismatch_count > 0` and `coverage_ratio = 1.0`.  
  - Interpretation: Period mismatch is treated as repairable when coverage is high, which may be too permissive for some use cases.

- **E008 – Missing baseline data (year-over-year growth)**
  - Scenario: Question asks for YoY growth, but evidence only contains current-year quarters (no explicit prior year). Answer claims a specific growth rate.  
  - Expected human decision: **REPAIR** (or possibly FLAG, due to missing baseline).  
  - Actual system decision: **ACCEPT** with full coverage and no recomputation failures.  
  - Interpretation: The system treats the absolute percent claim as consistent with observed values, without checking for presence of a true prior-year baseline, leading to over-permissive acceptance.

### 9.2 Over-conservative scenarios

Cases where the system was **too strict** versus human expectation:

- **E001 – Correct lookup (Q1 revenue)**
  - Scenario: Candidate answer exactly matches a value present in the table.  
  - Expected: **ACCEPT** (simple correct lookup).  
  - Actual: **FLAG** with `unsupported_claims_count > 0` and `coverage_ratio = 0.5`.  
  - Possible reason: Partial coverage due to how claims/evidence are paired; the rules default to FLAG when coverage < threshold.

- **E003 – Correct total (3 + 7 = 10)**
  - Scenario: Total over Q1 and Q2 is correct.  
  - Expected: **ACCEPT**.  
  - Actual: **FLAG** with zero coverage and unsupported claims.  
  - Possible reason: Execution engine’s total recomputation heuristic did not successfully match the sum to operands, so the claim appears unsupported.

- **E005 – Incorrect total treated as FLAG instead of REPAIR**
  - Scenario: Total is wrong, but evidence coverage is good and off-by-amount is straightforward.  
  - Expected human decision: **REPAIR** (correctable arithmetic error).  
  - Actual system decision: **FLAG**, driven by `unsupported_claims_count` and `coverage_ratio = 0.0`.  
  - Interpretation: When totals are not recognized by the execution engine, the system tends to drop to FLAG rather than REPAIR, making it more conservative than intended.

Overall, these failure modes are driven by:
- Sensitivity of **coverage_ratio** and **unsupported_claims_count** in the rule-based decision.
- Limited robustness of heuristics for:
  - total recomputation,
  - detecting baseline context for YoY questions,
  - distinguishing hard period mismatches (should FLAG) from softer issues (REPAIR).

