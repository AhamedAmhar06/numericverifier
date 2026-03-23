# ML Decision Layer (P&L-only, Option A)

## Why ML does not see raw text

The ML decider receives only the **numeric signal vector** produced by the P&L verifier (e.g. `unsupported_claims_count`, `coverage_ratio`, `pnl_identity_fail_count`, etc.). It does not receive the question, the evidence table, or the LLM answer. This avoids data leakage, keeps the decision boundary in a small, auditable feature space, and ensures that the same signals always map to the same model input. Using raw text would also require different preprocessing and would be harder to defend under evaluation.

## Why hard rules remain

Certain conditions must always result in FLAG and must not be overridable by the model:

- **Missing YoY baseline** (`pnl_missing_baseline_count > 0`): The user asked for a comparison (e.g. YoY) but the evidence does not contain the baseline period. Answering would be unsupported.
- **Period strict mismatch** (`pnl_period_strict_mismatch_count > 0`): The question refers to a period that is not in the table or does not align; verification cannot be trusted.
- **Non-P&L table** (`pnl_table_detected == 0`): The pipeline is P&L-only; non-P&L evidence is out of scope and must be FLAG.

These are enforced **before** the model is called. The ML model is never invoked for these cases, so it cannot override them.

## What the model is allowed to decide

The model is used only in the **soft region**: when the run has passed the hard gates (P&L table, no missing baseline, no strict period mismatch). In that region, the model predicts ACCEPT, REPAIR, or FLAG from the signal vector. That output replaces the rule-based decision for that request. So the model decides the boundary between ACCEPT / REPAIR / FLAG when the hard safety conditions are already satisfied.

## Why this is safe and appropriate for finance verification

1. **High-risk cases are rule-bound:** Missing baseline and period mismatch always produce FLAG without consulting the model.
2. **Inputs are structured:** The model sees only signals, not free text, which reduces leakage and keeps behaviour auditable.
3. **Fallback:** If the model is missing or prediction fails, the backend falls back to the existing rule-based decision.
4. **Toggle:** `USE_ML_DECIDER=false` (default) disables the model entirely for deployment or evaluation.

This design is defensible for IPD and finance verification because safety-critical FLAGs are deterministic and the model only refines decisions in the remaining cases.
