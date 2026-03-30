# NumericVerifier

A post-generation numeric verification system for finance-style LLM answers.

## Overview

NumericVerifier is a baseline system that:
- Extracts numeric claims from candidate answers
- Verifies them against financial evidence
- Produces verification signals and decisions (ACCEPT/REPAIR/FLAG)
- Generates full audit-style reports

This baseline works **without ML and without OpenAI**. ML and OpenAI integration are designed to be pluggable later.

## Architecture

The system follows a strict pipeline:

1. **Numeric Claim Detection** - Extracts numbers from text
2. **Normalization Layer** - Normalizes numeric formats
3. **Evidence Grounding** - Matches claims to evidence
4. **Verification Engines**:
   - Lookup-based check
   - Execution-based check (recomputation)
   - Constraint-based check (scale/period mismatches)
5. **Verifier Signals** - Computes risk features
6. **Rule-based Decision** - Makes deterministic decision
7. **Audit Report** - Generates full report

## Installation

### Prerequisites

- Python 3.10+
- macOS (tested on macOS)

### Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

Start the FastAPI server:

```bash
python3 -m uvicorn app.main:app --reload --port 8877
```

The API will be available at `http://localhost:8877`.

API documentation is available at:
- Swagger UI: `http://localhost:8877/docs`
- ReDoc: `http://localhost:8877/redoc`

## API Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

### POST /verify-only

Runs the full verification pipeline on a provided candidate answer.

**Request:**
```json
{
  "question": "What was the total revenue for Q1 2024?",
  "evidence": {
    "type": "text",
    "content": "The company reported revenue of 5000000 dollars."
  },
  "candidate_answer": "The total revenue for Q1 2024 was $5,000,000.",
  "options": {
    "tolerance": 0.01,
    "log_run": true
  }
}
```

**Response:**
```json
{
  "decision": "ACCEPT",
  "rationale": "All claims are grounded and verified...",
  "signals": { ... },
  "claims": [ ... ],
  "grounding": [ ... ],
  "verification": [ ... ],
  "report": { ... }
}
```

## Examples

Example JSON files are provided in the `examples/` directory:

- `accept_case.json` - Example that should result in ACCEPT
- `repair_case.json` - Example that should result in REPAIR
- `flag_case.json` - Example that should result in FLAG

To test an example:

```bash
curl -X POST "http://localhost:8877/verify-only" \
  -H "Content-Type: application/json" \
  -d @../examples/accept_case.json
```

## Running Tests

Run all tests:

```bash
pytest app/tests/
```

Run specific test file:

```bash
pytest app/tests/test_extract.py
```

Run with verbose output:

```bash
pytest app/tests/ -v
```

## Evaluation Logging

When `log_run=true` in the request options, the system logs:

- **runs/logs.jsonl** - Full audit reports (one JSON object per line)
- **runs/signals.csv** - Signals and decisions for ML training

These files are created in the `runs/` directory at the project root.

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── api/                 # API endpoints
│   │   ├── health.py
│   │   └── verify.py
│   ├── core/                # Core configuration
│   │   ├── config.py
│   │   └── logging.py
│   ├── verifier/            # Verification pipeline
│   │   ├── types.py
│   │   ├── extract.py
│   │   ├── normalize.py
│   │   ├── evidence.py
│   │   ├── grounding.py
│   │   ├── engines/
│   │   │   ├── lookup.py
│   │   │   ├── execution.py
│   │   │   └── constraints.py
│   │   ├── signals.py
│   │   ├── decision_rules.py
│   │   └── report.py
│   ├── eval/                # Evaluation logging
│   │   └── logging.py
│   ├── ml/                  # ML stubs (not implemented)
│   ├── llm/                 # LLM stubs (not implemented)
│   └── tests/               # Tests
├── requirements.txt
└── README.md
```

## Decision Logic

The baseline uses deterministic rules:

- **ACCEPT**: No unsupported claims, no scale/period mismatches, all recomputations successful, coverage >= threshold
- **REPAIR**: Good coverage, but arithmetic or scale issues exist (appear correctable)
- **FLAG**: Low coverage, high ambiguity, or many unsupported claims

## Limitations

- No ML-based decision making (uses rule-based only)
- No OpenAI integration (stubs only)
- Execution engine uses heuristics (may not catch all computations)
- Period mismatch detection is basic (keyword-based)

## Future Enhancements

- ML-based decision model (plug-in ready)
- OpenAI integration for answer generation and repair
- Improved execution engine with better computation detection
- Enhanced period/scale mismatch detection

## License

This is a baseline implementation for research/development purposes.
