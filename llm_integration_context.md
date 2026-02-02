# LLM Input Integration – NumericVerifier

## Purpose
Integrate an LLM as an **answer generator** for the NumericVerifier system.

The LLM will:
- generate an answer from a question and tabular evidence
- pass that answer into the existing numeric verification engine

The verifier remains the authority.

---

## IMPORTANT: EXISTING SYSTEM (DO NOT MODIFY)

The following already exists and MUST remain unchanged:

- Numeric extraction
- Normalization
- Grounding
- Verification engines
- Signal generation
- Rule-based decision logic
- /verify-only endpoint behaviour
- Logging to runs/signals.csv and runs/logs.jsonl

This integration must be additive only.

---

## Scope of This Task

DO:
- Add LLM-based answer generation
- Add a thin orchestration layer that feeds LLM output into the verifier

DO NOT:
- Add repair logic
- Modify verification logic
- Modify decision thresholds
- Retrain or modify ML models
- Add frontend code

---

## New Input Contract

The system must accept the following JSON input:

{
  "question": string,
  "evidence": {
    "type": "table",
    "content": {
      "columns": string[],
      "rows": string[][],
      "units": { string: string }
    }
  },
  "options": {
    "tolerance": number
  }
}

Notes:
- The user does NOT provide an answer
- The LLM always generates the answer
- Evidence is mandatory

---

## New Orchestration Flow

1. Receive question + tabular evidence
2. Call LLM to generate an answer
3. Treat the LLM output as untrusted text
4. Pass the generated answer into the existing verifier pipeline
5. Produce signals and decision exactly as before
6. Return the full verifier output

---

## LLM Usage Rules (STRICT)

- LLM is used ONLY for answer generation
- One LLM call per request
- No repair logic at this stage
- No conversation memory
- Deterministic output

If OPENAI_API_KEY is NOT set:
- Use a deterministic stubbed answer
- Do NOT fail the request

---

## LLM Prompt – Answer Generation

System prompt:
"You are a financial assistant.
Answer the question using ONLY the provided table.
Do not introduce numbers that are not present in the table.
If the answer cannot be derived, say so explicitly."

User prompt template:
Question:
{question}

Table:
{formatted_table}

---

## OpenAI API Integration

- Read API key from environment variable:
  OPENAI_API_KEY

- Do NOT hardcode keys
- Do NOT log the key
- If key is missing, use stub mode

Recommended parameters:
- model: gpt-4o-mini
- temperature: 0.0
- max_tokens: 100

---

## Backend Integration Requirements

- Implement a function:
  generate_llm_answer(question, table_evidence) -> string

- Add a new endpoint OR wrapper that:
  - calls generate_llm_answer
  - forwards the result into the existing verification pipeline
  - preserves existing logging and output format

---

## Constraints

- No verifier logic changes
- No repair logic
- No ML changes
- No frontend
- Keep changes minimal and isolated
