# NumericVerifier — Full Technical Audit

Generated: 2026-02-23

This document is a code-first technical audit of the NumericVerifier backend located under `backend/app`. It inspects implementation details for the P&L verification pipeline (the /verify-only endpoint) and identifies strengths, weaknesses, and concrete improvements.

---

## 1. SYSTEM OVERVIEW

- Purpose
  - NumericVerifier verifies numeric claims (primarily financial P&L values) against provided evidence (tables or text). It aims to automate numeric fact-checking and surface verification signals.

- Problem it solves
  - Detects arithmetic, scale, and period inconsistencies; grounds values to table evidence; enforces accounting identities; and produces an explainable decision (ACCEPT / REPAIR / FLAG).

- Inputs
  - JSON POST requests with fields: `question` (string), `evidence` (object with `type` and `content`), `candidate_answer` (string). For P&L, `evidence.content` must be a dict with `columns` and `rows` (table layout A or B).

- Outputs
  - JSON object including: `decision`, `rationale`, `signals` (VerifierSignals v2), `claims`, `grounding`, `verification` (per-claim results), `report` (audit), and metadata (`engine_used`, `llm_used`).

---

## 2. END-TO-END REQUEST FLOW

Trace for `/verify-only` implemented in code:

1) Entry: `backend/app/api/verify.py` — `verify_only(request: VerifyRequest)` → calls `route_and_verify(...)`.

2) Router: `backend/app/verifier/router.py` — `route_and_verify(question, evidence, candidate_answer, options, llm_used, ...)`.

3) Pipeline steps inside `route_and_verify` (in order):
   1. Validate evidence type: `_evidence_type(evidence)` ensures `type == "table"`; else short-circuit FLAG via `_short_circuit_flag`.
   2. Classify table: `classify_table_type(content)` from `verifier/domain.py` determines `table_type` (must be `pnl`). Non-PnL → FLAG.
   3. Parse PnL: `parse_pnl_table(content)` in `verifier/pnl_parser.py` supports two layouts:
      - Layout A: first column = line item, following columns = periods (preferred).
      - Layout B: columns include Period, Line Item, Value.
      The parser maps synonyms to canonical keys (revenue, cogs, gross_profit, operating_expenses, operating_income, taxes, net_income, interest, etc.) and returns `PnLTable` with `periods` and `items`.
   4. Extract numeric claims from `candidate_answer`: `extract_numeric_claims(text)` in `verifier/extract.py` returns `NumericClaim` objects (parsed_value, scale_token, unit, char_span).
   5. Normalize claims: `normalize_claims(claims)` (thin wrapper in `verifier/normalize.py`).
   6. Ingest evidence items: `ingest_evidence({"type":"table","content":content})` in `verifier/evidence.py` converts table cells to `EvidenceItem` objects (value, source, location, context).
   7. Ground claims to evidence: `ground_claims(normalized_claims, evidence_items, tolerance)` in `verifier/grounding.py` → `GroundingMatch` per claim when within tolerance; ambiguous if multiple matches.
   8. Per-claim verification loop:
      - Create `VerificationResult` for each claim (types in `verifier/types.py`).
      - `verify_lookup(vr, grounding_match, tolerance)` in `verifier/engines/lookup.py` marks lookup_supported if grounding match within tolerance.
      - `verify_constraints(claim, grounding_match, normalized_claims, evidence_items, question, pnl_periods)` in `verifier/engines/constraints.py` adds violations for scale/period mismatch and missing periods.
   9. P&L checks: `run_pnl_checks(question, pnl_table, tolerance, margin_asked_or_claimed=False)` in `verifier/engines/pnl_execution.py` performs identity checks (Gross Profit = Revenue - COGS, Operating Income = GrossProfit - Opex, Net Income vs Operating Income - Taxes - Interest), margin heuristics, and YoY baseline detection.
   10. Compute signals: `compute_signals(normalized_claims, verification_results, tolerance, pnl_check_result, domain_table_type="pnl", pnl_period_strict_mismatch_count=...)` in `verifier/signals.py` — aggregates coverage, relative errors, scale/period mismatch counts, ambiguity counts, and PnL-specific counters.
   11. Decision: `decide(signals, verification_results)` in `ml/decision_model.py` — either rule-based `make_decision(...)` (in `verifier/decision_rules.py`) or ML model (if `USE_ML_DECIDER=true` and artifacts present), with hard safety gates.
   12. Reporting & logging: `generate_report(...)` in `verifier/report.py` builds `AuditReport`. If `log_run` true, `eval/logging.py` writes runs and `signals_v2.csv`.
   13. Return: A JSON structure assembled in `route_and_verify` with `decision`, `signals.to_dict()`, `claims`, `grounding`, `verification`, `report.to_dict()`, and domain/metadata.

Data transformations: text candidate answer → `NumericClaim` objects; table content → `PnLTable` and `EvidenceItem` list; claims + evidence → `GroundingMatch` + `VerificationResult`; verification results → aggregated `VerifierSignals`; signals + verification → `Decision` + `AuditReport`.

---

## 3. MODULE-BY-MODULE BREAKDOWN

Below are modules found in the codebase and the most important symbols, purposes, inputs, outputs, logic and known weaknesses based on reading the implementation.

- `verifier/extract.py`
  - Function: `extract_numeric_claims(text: str) -> List[NumericClaim]`
  - Purpose: Identify numeric tokens in the candidate answer and produce `NumericClaim` objects including parsed_value, unit and scale_token.
  - Inputs: free text candidate answer.
  - Outputs: list of `NumericClaim` (see `verifier/types.py`).
  - Key logic: regex patterns for percentages, scale tokens (K/M/B and words), currency prefixes/suffixes, parentheses negatives, and plain numbers. Converts numbers to float and resolves scale multipliers using `SCALE_MULTIPLIERS` map.
  - Weaknesses: heavy reliance on regex ordering for overlaps (ad-hoc de-duplication). No explicit handling for ambiguous textual expressions like "5 to 6 million" or spelled-out numbers. Limited context-aware mapping of units beyond immediate tokens.

- `verifier/normalize.py`
  - Function: `normalize_claims(claims)`
  - Purpose: canonicalization of extracted claims.
  - Inputs: `NumericClaim` list.
  - Outputs: normalized `NumericClaim` list (currently mostly passthrough).
  - Weaknesses: minimal normalization; scale/period canonicalization mostly left to extract and other modules.

- `verifier/pnl_parser.py`
  - Key types: `PnLTable` dataclass; functions `_parse_layout_a`, `_parse_layout_b`, `parse_pnl_table`.
  - Purpose: Detect table layout A (line item + periods) or layout B (Period, Line Item, Value) and map row labels to canonical keys.
  - Inputs: `content` dict with `columns` and `rows`.
  - Outputs: `PnLTable` with `periods`, `items` (dict canonical_key -> period->value), `row_label_by_key`.
  - Key logic: label normalization `_normalize_label`, synonyms mapping `_SYNONYMS` to canonical keys (revenue, cogs, gross_profit, operating_expenses, operating_income, taxes, net_income, interest), numeric parsing of string cells.
  - Weaknesses: synonym matching is substring-based and may incorrectly map ambiguous labels; no fuzzy matching or configurable synonyms; missing unit handling (currency/scale) and no provenance beyond simple row label save.

- `verifier/evidence.py`
  - Functions: `parse_table_evidence`, `parse_text_evidence`, `ingest_evidence`.
  - Purpose: Convert raw evidence into `EvidenceItem` objects (value, source, location, context).
  - Inputs: table content (columns/rows) or free text.
  - Outputs: list of `EvidenceItem`.
  - Weaknesses: context for table cells is simply `row[0]` (first column) which is fragile for Layout B; units mapping is a simple dict lookup of `units` by column name but not normalized; no explicit period-to-column mapping beyond index.

- `verifier/grounding.py`
  - Functions: `ground_claim`, `ground_claims`.
  - Purpose: Match numeric claims to evidence items by absolute distance and relative error within `tolerance`. Mark ambiguous matches when multiple candidates are close.
  - Inputs: `NumericClaim`, list of `EvidenceItem`, tolerance.
  - Outputs: `GroundingMatch` or list of matches.
  - Key logic: compute `distance = abs(claim - evidence.value)` and `relative_error`; accept matches where distance <= tolerance OR relative_error <= tolerance. If multiple matches, choose best and set `ambiguous=True`.
  - Weaknesses: `tolerance` is used both as absolute and relative threshold (same threshold for both), which is questionable (should use separate absolute/relative thresholds). Ambiguity resolution returns the best match but marks ambiguous — downstream consumers treat ambiguous simply as a counter; more nuanced scoring could help.

- `verifier/engines/lookup.py`
  - Function: `verify_lookup(verification_result, grounding_match, tolerance)`
  - Purpose: Mark `lookup_supported` if a grounded match exists within tolerance.
  - Weaknesses: Small; it does not handle plausible rounding/scale adjustments outside strict tolerance.

- `verifier/engines/constraints.py`
  - Function: `verify_constraints(...) -> VerificationResult`
  - Purpose: Heuristic checks for scale mismatches, period mismatches, and missing periods referenced in the question.
  - Inputs/Outputs: accepts `claim`, optional `grounding_match`, full `all_claims`, `evidence_items`, question string, `pnl_periods`; returns `VerificationResult` with `constraint_violations` appended.
  - Key logic: detects claim `scale_token` vs evidence magnitude to report `Scale mismatch`. Detects period mismatches by heuristics on text (time keywords list). Detects missing question-referenced periods in parsed `pnl_periods` and emits violations like `missing_period_in_evidence`, `pnl_period_strict_mismatch`.
  - Weaknesses: Period heuristics are simplistic (keyword containment), easily misses variations (e.g., "FY23" vs "2023"), and scale detection infers expected scale solely from magnitude thresholds which are brittle.

- `verifier/engines/pnl_execution.py`
  - Function: `run_pnl_checks(question, pnl_table, tolerance, margin_asked_or_claimed)` returns `PnLCheckResult`.
  - Purpose: Domain-level accounting identity checks (Gross Profit = Revenue - COGS; Operating Income = GrossProfit - Opex; Net Income = Operating Income - Taxes - Interest), margin sanity checks, and YoY baseline existence.
  - Inputs: parsed `PnLTable`, question string, tolerance.
  - Outputs: `PnLCheckResult` with identity_fail_count, margin_fail_count, missing_yoy_baseline flag and violations list.
  - Weaknesses: margin checks use hard thresholds (−1.01 to 1.01) which are coarse; YoY detection relies on explicit year tokens in question; no fuzzy matching for period labels.

- `verifier/signals.py`
  - Function: `compute_signals(claims, verification_results, tolerance, pnl_check_result, domain_table_type, pnl_period_strict_mismatch_count)` returns `VerifierSignals`.
  - Purpose: Aggregate per-claim verification into structured signals used by decision rules or ML: coverage_ratio, unsupported_claims_count, recomputation_fail_count, max/mean_relative_error, scale_mismatch_count, period_mismatch_count, ambiguity_count, plus P&L-specific counters.
  - Weaknesses: relies on results of previous heuristics; ambiguousness and period/scale counters are increments of simple string matching on violation messages (fragile and error-prone if messages change).

- `verifier/decision_rules.py`
  - Function(s): `make_decision(signals, verification_results)` — rule-based logic to map signals to decisions (ACCEPT/REPAIR/FLAG).
  - Purpose: deterministic fall-back decisioning when ML is disabled or model unavailable.
  - Weaknesses: rules are not documented inline with schema; unit tests / thresholds may be limited.

- `ml/decision_model.py`
  - Key functions: `decide(signals, verification_results)`, `load_model()`, `_hard_gate_flag(signals)`, `predict_decision(...)`.
  - Purpose: orchestrate ML vs rule-based decision path. When `USE_ML_DECIDER=true`, applies hard safety gates (pnl_missing_baseline_count, pnl_period_strict_mismatch_count, pnl_table_detected==0) to force FLAG; otherwise attempts to load artifacts from `runs/` and call model pipeline to predict decision label mapped by `label_mapping`.
  - Inputs: `VerifierSignals`, verification_results, optional model object.
  - Outputs: `Decision(decision, rationale)`.
  - Known weaknesses: model artifacts loading is brittle (requires joblib, feature_schema, label mapping in `runs/`); fallback logic is conservative but may mask model prediction errors. Hard gates use only a few signals, which is safe but reduces ML utility.

---

## 4. SIGNALS AND FEATURES USED BY ML

Signals produced (see `verifier/types.VerifierSignals` and `verifier/signals.py`):

- `unsupported_claims_count` — number of claims not grounded and not recomputed.
- `coverage_ratio` — fraction of supported numeric claims (grounded or recomputable).
- `recomputation_fail_count` — number of claims where execution attempted but failed.
- `max_relative_error` — maximum relative error observed between claimed and evidence values (from grounding matches).
- `mean_relative_error` — mean relative error across grounded claims.
- `scale_mismatch_count` — aggregated count of scale mismatch violations detected by constraints engine.
- `period_mismatch_count` — aggregated count of non-strict period mismatches.
- `ambiguity_count` — number of claims that had ambiguous grounding (multiple candidate matches within tolerance).

P&L v2 specific fields:
- `schema_version` — integer (2).
- `pnl_table_detected` — 0/1 flag indicating parsed PnL detection.
- `pnl_identity_fail_count` — number of accounting identity violations from `run_pnl_checks`.
- `pnl_margin_fail_count` — number of margin violations (if margin checks enabled).
- `pnl_missing_baseline_count` — boolean-as-int (1/0) if YoY baseline missing.
- `pnl_period_strict_mismatch_count` — strict mismatch count raised when question periods are absent or misaligned in evidence.

How signals are computed
- Signals are aggregated by iterating `verification_results` and counting attributes (grounded, execution_result, execution_error, constraint_violations). Many counters are derived by string-matching violation messages (i.e., if "scale mismatch" in violation.lower()).

Feature vector to ML
- The model uses `feature_order` read from `runs/feature_schema_v2.json` and maps `signals.to_dict()` into that order. The code constructs a list of float values (one per feature) using `signals.to_dict()` keys.

Influence on decision
- The ML pipeline predicts labels (mapped via label_mapping) and the model result is used as final decision unless pre-empted by hard gates. When ML is unavailable the code falls back to `make_decision` rule-based logic.

---

## 5. DECISION LOGIC

- Rule-based path
  - `make_decision(signals, verification_results)` implements domain heuristics. Typical triggers:
    - Many unsupported claims or low coverage → FLAG.
    - Minor mismatches may result in REPAIR (repair suggestions not shown here) or FLAG depending on thresholds.
  - The rules are conservative and used when ML is disabled or model artifacts missing.

- ML decision path
  - Controlled by environment variable `USE_ML_DECIDER`.
  - Pre-check (hard safety gates in `ml/decision_model._hard_gate_flag`): if any of:
    - `pnl_missing_baseline_count > 0`
    - `pnl_period_strict_mismatch_count > 0`
    - `pnl_table_detected == 0`
    then immediately return `FLAG` and do NOT call ML.
  - If model artifacts exist in `runs/` (joblib pipeline + feature schema + label mapping), the model is loaded and `pipeline.predict(X)` is called on the feature vector; predicted label index is mapped via `index_to_label` to final decision.
  - On any model loading or inference error, system falls back to rule-based `make_decision`.

- Thresholds used
  - `tolerance` is a central numeric threshold (config: `settings.tolerance`) used both as an absolute and relative tolerance in grounding and identity checks; this conflation can change behavior depending on magnitude.
  - Margin checks in execution engine use fixed sanity ranges (e.g., gross margin outside [-0.01, 1.01] signals violation).

---

## 6. CURRENT LIMITATIONS (VERY IMPORTANT)

This section is an honest appraisal of weak points discovered in the code.

- Weak normalization areas
  - `normalize_claims` is effectively a pass-through. Extraction handles many conversions, but post-extraction normalization (unit harmonization, scale inference, period canonicalization, handling of spelled-out numbers) is limited.

- Missing or brittle scale handling
  - Scale detection is ad-hoc: `constraints.verify_constraints` infers expected scale solely by magnitude thresholds (>=1000 → thousand, >=1e6 → million), then compares to claim scale token. This will fail for small numbers that are expressed in millions in text (e.g., "0.5M") and for cases where units are ambiguous or documented elsewhere.

- Missing period validation and canonicalization
  - Period detection uses a fixed `_TIME_KEYWORDS` set and substring containment heuristics. It cannot match variants like `FY23`, `’23`, or `2023A` without explicit mapping. Evidence contexts are derived from `row[0]` which may not correspond to canonical period labels.

- Weak repair triggers
  - The system returns `REPAIR` in only narrow conditions (rules). There is little automated repair generation beyond flagging mismatches. The repair workflow (how to propose corrected numbers) is not implemented in engines — `REPAIR` is primarily rule-driven.

- Ambiguous grounding causes
  - Grounding marks ambiguous when multiple evidence items are within tolerance but then picks the nearest match and only sets `ambiguous=True`. There is no ranking explanation or multi-match propagation; ambiguous cases are surfaced in a single counter which loses per-claim nuance.

- Architectural fragility
  - Signal computation relies on textual violation messages to increment counters (`'scale mismatch' in v.lower()`), coupling semantics to string literals — fragile for refactors.
  - The ML artifact loading path assumes specific filenames in `runs/` and requires `joblib` and a matching feature schema; if any artifact is missing, system silently falls back to rules. This is safe but can hide model regression issues.
  - The `evidence.parse_table_evidence` function treats every cell uniformly and sets `context` to `row[0]` — this mixes line-item labels and period labels depending on the table layout.

---

## 7. IMPROVEMENT CHECKLIST (ACTIONABLE)

Below table maps areas, current state, risk, improvement, and priority. Priorities: High / Medium / Low.

| Area | Current State | Risk | Improvement Required | Priority |
|---|---|---|---|---|
| Claim normalization | Minimal; extraction does most work | Medium — ambiguous units or spelled numbers may be mis-parsed | Implement a normalization pipeline: unit canonicalization, spelled-number parsing, scale disambiguation, and explicit period tokenization | High |
| Scale handling | Heuristic magnitude thresholds + scale token matching | High — false positives for scale mismatches | Add explicit unit detection in table (units column), use separate absolute/relative scale thresholds, add consistency checks for scaled claims (e.g., 5M vs 5,000,000) | High |
| Period detection | Keyword-based heuristic on raw text/context | High — many period mismatch false positives/negatives | Normalize period tokens (FY, '23, Q1-4), canonical period parsing, map table headers to canonical period ids | High |
| Evidence ingestion | Table cells parsed uniformly; context=row[0] | Medium — incorrect context for Layout B | Ingest with column-aware context; annotate cells with column header and row label separately | Medium |
| Grounding ambiguity | Single best match with ambiguous flag | Medium — lack of multi-match analysis | Return ranked matches with scores; expose top-N candidates and distances in report | Medium |
| Signal computation | Counters derived from string-matching violations | Medium — brittle on refactor | Replace string-matching with typed violation enums, update `VerificationResult` to contain structured violation codes | High |
| ML artifact handling | Model loaded from `runs/` if present; otherwise rules | Low — safe fallback but fragile CI | Add unit tests to verify model->feature schema consistency; surface detailed load errors in logs and CI gating | Medium |
| Repair generation | Minimal/absent | Medium — user workflow incomplete | Implement a repair suggestion module that proposes corrected values and rationale (e.g., recompute net income) | Medium |

---

## 8. ALIGNMENT WITH RESEARCH CONTRIBUTION

- What the system supports
  - Modular verification: The pipeline is cleanly modularized (extract → normalize → ground → lookup/constraints/execution → signals → decision) which supports incremental improvements and ablation studies.
  - Post-generation validation: The `verify` endpoint accepts LLM-generated answers and runs the same verification, enabling evaluation of model outputs; the `log_run` and `signals_v2.csv` logging supports offline analysis.
  - Hybrid deterministic + ML design: The system implements safety-first hard gates, a rule-based fallback, and an optional ML decider that consumes structured signals. This is a pragmatic hybrid architecture consistent with research on combining deterministic constraints with ML.

- Where contribution claims are weak
  - Feature engineering & interpretability: Features are simple aggregated signals; there is no interpretability layer that maps model decisions back to human-friendly rules beyond the `rationale` string. Research claims about fine-grained explainability would need more instrumentation (e.g., SHAP, feature importances, per-feature audits).
  - Robustness to varied table layouts and units: The current parser handles two layouts but depends on clean columns/rows; scaling, currency units, and period normalization are fragile. For a research-grade verification benchmark, more robust table understanding is required.
  - Grounding ambiguity handling: The system signals ambiguity but doesn't provide granular uncertainty estimates or a probabilistic grounding model; research claims about calibrated uncertainty would need enhancements.

---

## Appendix — Key code locations

- Entry points
  - API: `backend/app/api/verify.py`
  - Router: `backend/app/verifier/router.py`

- Parsing / extraction / normalization
  - `backend/app/verifier/extract.py`
  - `backend/app/verifier/normalize.py`
  - `backend/app/verifier/pnl_parser.py`
  - `backend/app/verifier/evidence.py`

- Grounding and verification
  - `backend/app/verifier/grounding.py`
  - `backend/app/verifier/engines/lookup.py`
  - `backend/app/verifier/engines/constraints.py`
  - `backend/app/verifier/engines/pnl_execution.py`

- Signals and decision
  - `backend/app/verifier/signals.py`
  - `backend/app/verifier/decision_rules.py`
  - `backend/app/ml/decision_model.py`

- Types and reporting
  - `backend/app/verifier/types.py`
  - `backend/app/verifier/report.py`

---

If you want, I can:
- produce a prioritized implementation plan (detailed tasks with estimated effort),
- add unit tests that cover the corner cases listed (scale, period formats, ambiguous grounding), or
- implement one high-impact fix now (structured violation enum and robust signal computation).

End of audit.
