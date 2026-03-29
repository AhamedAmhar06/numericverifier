# /verify Endpoint Status

## Status: WORKING

## How /verify works
1. Accepts: question, evidence (P&L table), optional tolerance, optional options
2. Calls generate_llm_answer() to produce candidate answer
   - If OPENAI_API_KEY set: uses OpenAI gpt-4o-mini (temperature=0.0, max_tokens=100)
   - If no key: returns stub answer with llm_used=false
3. Runs full verification pipeline on generated answer:
   - Domain classification (P&L detection)
   - Ingestion assessment (row label matching)
   - Claim extraction and normalization
   - Grounding against evidence
   - Lookup, constraint, and execution verification engines
   - Signal computation (14 signals)
   - ML decision (V6.1 XGBClassifier)
   - Repair loop (if REPAIR decision, attempt fix + re-verify)
4. Returns complete response with all verification metadata

## Response fields
- `decision` (ACCEPT/REPAIR/FLAG)
- `rationale` (human-readable explanation)
- `signals` (14 ML signals)
- `claims` (per-claim details with parsed values)
- `grounding` (per-claim evidence matching)
- `verification` (per-claim engine results)
- `ingestion` (row label mapping assessment)
- `llm_used` (bool -- was OpenAI used or stub?)
- `llm_fallback_reason` (why stub, if stub)
- `generated_answer` (the LLM-generated answer text)
- `candidate_answer` (alias for generated_answer, for frontend consistency)
- `report` (full audit trail)
- `claim_audit` (per-claim structured audit)
- `audit_summary` (aggregate audit metrics)
- `original_answer`, `corrected_answer`, `repair_iterations`, `accepted_after_repair`
- `domain`, `engine_used`

## Primary/Secondary distinction
- /verify = PRIMARY production/demo endpoint (LLM generates answer, pipeline verifies)
- /verify-only = SECONDARY manual/debug endpoint (user provides candidate answer)

## Frontend routing
- No candidate answer entered -> "Verify (LLM)" button -> calls /verify
- Candidate answer entered -> "Verify (Manual)" button -> calls /verify-only
- Mode indicator displayed: "LLM-Verified" or "Manual Verification"
- LLM status shown: "Yes (OpenAI)" or "No -- [reason]"

## Test Results
- Apple FY2023 /verify test: PASS (decision=FLAG, LLM generated "383,285" without units)
- Stub mode: PASS (returns llm_used=false, llm_fallback_reason="OPENAI_API_KEY not set")
- Wrong answer test via /verify-only ($200,000M vs actual $96,995M): PASS (decision=FLAG)
- Health check: PASS ({"status": "ok"})

## Limitations
- Stub mode produces non-verifiable answer (no numeric claims to check) -- always FLAG
- LLM path requires OPENAI_API_KEY in backend/.env
- LLM may omit units/scale context, causing scale mismatch with table evidence
- P&L-only: non-P&L tables are rejected with FLAG
- Maximum 2 pipeline passes (1 original + 1 repair attempt)
