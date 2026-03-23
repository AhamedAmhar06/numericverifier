# NumericVerifier System Overview

## Purpose

NumericVerifier is a P&L-scoped numeric verification system that determines whether a candidate answer to a financial question is supported by structured table evidence. It produces a three-class decision: **ACCEPT**, **REPAIR**, or **FLAG**.

## Pipeline Architecture

```
HTTP POST /verify-only or /verify
        │
        ▼
  ┌─────────────┐
  │  API Layer   │  backend/app/api/verify.py
  │  (Pydantic)  │  Validates request schema
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │ Domain Router│  backend/app/verifier/router.py
  │              │  Single entry: route_and_verify()
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │ Domain Gate  │  backend/app/verifier/domain.py
  │              │  classify_table_type() → pnl | unknown
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │ P&L Parser   │  backend/app/verifier/pnl_parser.py
  │              │  parse_pnl_table() → PnLTable
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │ Extraction   │  backend/app/verifier/extract.py
  │              │  extract_numeric_claims(text) → List[NumericClaim]
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │Normalization │  backend/app/verifier/normalize.py
  │              │  normalize_claims() — currently pass-through
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │  Evidence    │  backend/app/verifier/evidence.py
  │  Ingestion   │  ingest_evidence() → List[EvidenceItem]
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │  Grounding   │  backend/app/verifier/grounding.py
  │              │  ground_claims() → List[GroundingMatch]
  └──────┬──────┘
         ▼
  ┌────────────────────────────────────────────┐
  │         Verification Engines               │
  │  ┌────────┐ ┌────────────┐ ┌────────────┐ │
  │  │ Lookup │ │Constraints │ │P&L Exec.   │ │
  │  │        │ │            │ │            │ │
  │  │lookup  │ │scale/period│ │identity/   │ │
  │  │.py     │ │checks      │ │margin/YoY  │ │
  │  └────────┘ └────────────┘ └────────────┘ │
  └──────┬─────────────────────────────────────┘
         ▼
  ┌──────────────┐
  │   Signals    │  backend/app/verifier/signals.py
  │              │  compute_signals() → VerifierSignals (14 fields)
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │  Decision    │  decision_rules.py / ml/decision_model.py
  │              │  decide() → Decision(ACCEPT|REPAIR|FLAG)
  └──────┬──────┘
         ▼
  ┌──────────────┐
  │   Report     │  backend/app/verifier/report.py
  │              │  generate_report() → AuditReport
  └──────┬──────┘
         ▼
       Response JSON
```

## Input Schema

### POST /verify-only

```json
{
  "question": "string",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Line Item", "2022", "2023"],
      "rows": [["Revenue", "100", "120"], ["COGS", "40", "50"]],
      "units": {}
    }
  },
  "candidate_answer": "string",
  "options": {
    "tolerance": 0.01,
    "log_run": true
  }
}
```

### POST /verify

Same as above but without `candidate_answer`; the system generates one via the external language service.

## Output Schema

```json
{
  "decision": "ACCEPT | REPAIR | FLAG",
  "rationale": "string",
  "signals": { "...14 signal fields..." },
  "claims": [ "...extracted numeric claims..." ],
  "grounding": [ "...grounding matches..." ],
  "verification": [ "...per-claim verification results..." ],
  "report": { "...full audit report..." },
  "domain": { "table_type": "pnl", "confidence": 0.75 },
  "engine_used": "pnl",
  "llm_used": false,
  "llm_fallback_reason": null
}
```

## Core Data Types (backend/app/verifier/types.py)

- **NumericClaim**: raw_text, parsed_value (float), char_span, unit, scale_token
- **EvidenceItem**: value (float), source, location, context
- **GroundingMatch**: claim, evidence, distance, relative_error, ambiguous
- **VerificationResult**: claim, grounded, grounding_match, lookup_supported, execution_supported, execution_result, execution_error, constraint_violations (List[str])
- **VerifierSignals**: 14 numeric fields (schema v2) including P&L-specific counts
- **Decision**: decision (str), rationale (str)
- **AuditReport**: full audit with timestamp

## Signal Schema (v2)

| Signal | Type | Description |
|--------|------|-------------|
| unsupported_claims_count | int | Claims not grounded in evidence |
| coverage_ratio | float | Fraction of value claims supported |
| recomputation_fail_count | int | Failed arithmetic re-checks |
| max_relative_error | float | Worst relative error across grounded claims |
| mean_relative_error | float | Average relative error |
| scale_mismatch_count | int | Claims with scale disagreement |
| period_mismatch_count | int | Claims referencing wrong period |
| ambiguity_count | int | Claims with multiple evidence matches |
| schema_version | int | Always 2 |
| pnl_table_detected | int | 0 or 1 |
| pnl_identity_fail_count | int | Accounting identity violations |
| pnl_margin_fail_count | int | Margin range violations |
| pnl_missing_baseline_count | int | YoY baseline missing |
| pnl_period_strict_mismatch_count | int | Strict period disagreement |

## Known Gaps (Pre-Improvement)

1. **normalize.py is a pass-through**: All normalization happens inside extract.py. No Decimal precision, no BPS support, no approximate-hedge tolerance widening, no table-level scale detection.
2. **EvidenceItem is flat**: No row_label, col_label, period, or canonical_line_item fields. Context is always row[0] regardless of layout.
3. **Grounding is numeric-only**: No unit-type filtering, no period bonus, no line-item matching. Ambiguity flagged but not scored.
4. **constraint_violations are raw strings**: Signals count violations by substring matching ("scale mismatch" in v.lower()), which is fragile.
5. **No repair module**: REPAIR decision is produced but no corrected answer is generated or re-verified.
6. **Execution engine lacks semantic constraints**: P&L checks run on the table itself, not on claims. No growth/margin formula library tied to claim semantics.
7. **No structured evaluation framework**: Existing eval scripts are ad-hoc; no ablation infrastructure.
8. **ML uses schema_version as a feature**: Should be metadata only.
