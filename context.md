# NumericVerifier — Baseline Project Context

## 1. Project Purpose
Build an end-to-end **post-generation numeric verification system** for finance-style LLM answers.

The system:
- takes a question and financial evidence
- generates or accepts an LLM answer
- extracts numeric claims
- verifies them against evidence
- produces verification signals
- outputs a final decision: ACCEPT / REPAIR / FLAG
- generates a full audit-style report

This baseline must work **without ML and without OpenAI**.
ML and OpenAI must be pluggable later.

---

## 2. High-Level Architecture (MANDATORY)
The implementation must follow this pipeline strictly:

User Question + Financial Evidence
→ Candidate Answer (user-provided for baseline)
→ Numeric Claim Detection
→ Normalization Layer
→ Evidence Grounding
→ Verification Engines
   - Lookup-based check
   - Execution-based check
   - Constraint-based check
→ Verifier Signals (risk features, not decisions)
→ Rule-based Decision (baseline)
→ Final Decision Output + Audit Report

NO ML is used for decision in baseline.
NO OpenAI calls in baseline.
Design must allow plugging them in later.

---

## 3. Tech Stack (Fixed)
- Language: Python 3.10+
- Backend framework: FastAPI
- ML (later): scikit-learn (not in baseline)
- LLM (later): OpenAI (stub only)
- Storage: local files (JSON, CSV)
- OS compatibility: macOS

---

## 4. Repository Structure (STRICT)
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── verify.py
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── verifier/
│   │   │   ├── types.py
│   │   │   ├── extract.py
│   │   │   ├── normalize.py
│   │   │   ├── evidence.py
│   │   │   ├── grounding.py
│   │   │   ├── engines/
│   │   │   │   ├── lookup.py
│   │   │   │   ├── execution.py
│   │   │   │   └── constraints.py
│   │   │   ├── signals.py
│   │   │   ├── decision_rules.py
│   │   │   └── report.py
│   │   ├── eval/
│   │   │   └── logging.py
│   │   └── tests/
│   ├── requirements.txt
│   └── README.md
├── examples/
│   ├── accept_case.json
│   ├── repair_case.json
│   └── flag_case.json
└── context.md

---

## 5. API Contract (Baseline)

### GET /health
Returns:
{ "status": "ok" }

---

### POST /verify-only
Runs the full verification pipeline on a provided candidate answer.

Request:
{
  "question": "string",
  "evidence": {
    "type": "text" | "table",
    "content": "string OR table JSON"
  },
  "candidate_answer": "string",
  "options": {
    "tolerance": 0.01,
    "log_run": true
  }
}

Response:
{
  "decision": "ACCEPT | REPAIR | FLAG",
  "rationale": "plain English explanation",
  "signals": { ... },
  "claims": [ ... ],
  "grounding": [ ... ],
  "verification": { ... },
  "report": { ... full audit report ... }
}

---

## 6. Core Data Types (verifier/types.py)
Implement dataclasses for:
- NumericClaim
- EvidenceItem
- GroundingMatch
- VerificationResult
- VerifierSignals
- Decision
- AuditReport

All must be JSON-serializable.

---

## 7. Numeric Claim Extraction
Extract numeric claims from candidate_answer:
- integers, decimals
- comma-separated numbers
- negative numbers incl (123)
- percentages
- currency tokens
- scale tokens (K, M, B, thousand, million)

Each claim must include:
- raw text
- parsed numeric value
- character span
- detected unit/scale token (if any)

---

## 8. Normalization Layer
Normalize numeric claims:
- remove commas
- convert brackets to negative
- expand K/M/B
- percent stored as both 10 and 0.10
- keep original surface form

---

## 9. Evidence Ingestion
Support:
- Text evidence (string)
- Table evidence:
{
  "columns": [...],
  "rows": [...],
  "units": { column_name: unit }
}

Parse numeric cells to floats.

---

## 10. Evidence Grounding
Match claims to evidence:
- Text: numeric match with tolerance
- Table: cell match with tolerance

If multiple matches found:
- mark ambiguous
- reduce confidence

---

## 11. Verification Engines

### 11.1 Lookup Engine
- Supported if grounded match exists within tolerance

### 11.2 Execution Engine
Recompute:
- percent change
- totals
- ratios

If operands missing, mark as unverifiable.

### 11.3 Constraint Engine
Check:
- scale mismatch (millions vs absolute)
- period mismatch (basic heuristic via text)

---

## 12. Verifier Signals
Compute:
- unsupported_claims_count
- coverage_ratio
- recomputation_fail_count
- max_relative_error
- mean_relative_error
- scale_mismatch_count
- period_mismatch_count
- ambiguity_count

Signals describe **risk**, not decisions.

---

## 13. Decision Logic (Baseline)
Implement deterministic rules:

ACCEPT if:
- no unsupported claims
- no scale/period mismatch
- recomputation failures = 0
- coverage_ratio >= threshold

REPAIR if:
- evidence coverage is good
- arithmetic or scale issues exist
- errors appear correctable

FLAG if:
- low coverage
- ambiguity high
- unsupported claims high

Decision must include rationale.

---

## 14. Reporting
Generate an audit report containing:
- inputs
- extracted claims
- grounding matches
- per-claim verification results
- signals
- decision + rationale
- metadata (timestamp, tolerance)

Must be saved optionally to disk.

---

## 15. Evaluation Logging (ML-Ready)
When log_run=true:
- append run to runs/logs.jsonl
- append signals to runs/signals.csv

This dataset will later be used in Google Colab
to train the ML acceptance model.

---

## 16. OpenAI Integration (NOT IMPLEMENTED YET)
Create stubs only:
- llm/provider.py
- methods: generate_answer(), repair_answer()

No OpenAI calls in baseline.
Design must allow plug-in later.

---

## 17. ML Integration (NOT IMPLEMENTED YET)
Create stubs only:
- ml/decision_model.py
- load joblib if exists
- fallback to rule-based decision

No training or inference in baseline.

---

## 18. Tests (Required)
Add unit tests for:
- numeric extraction
- normalization
- percent change computation
- totals
- grounding ambiguity
- decision logic

Add 1 integration test for /verify-only.

---

## 19. Examples (Required)
Provide 3 example JSON files:
- accept_case.json
- repair_case.json
- flag_case.json

Each must demonstrate a different decision.

---

## 20. Definition of Done
The project is complete when:
- Backend runs on Mac
- /verify-only works end-to-end
- All examples return correct decisions
- signals.csv is generated
- No OpenAI key required
- ML-ready logging exists
- Tests pass

