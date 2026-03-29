# Final Repository State

## Tests: 234 passed, 4 skipped
## Frontend build: PASS -- dist/ exists (index.html + assets)
## Backend: running on port 8877 tested OK
## Model: V6.1 XGBClassifier loaded (frozen -- do NOT retrain)
## Endpoints:
- /verify -- PRIMARY (LLM-first flow: generates answer via OpenAI, then verifies)
- /verify-only -- SECONDARY (manual/debug: user provides candidate answer)
- /health -- OK (returns {"status": "ok"})
- / -- Root (returns {"message": "NumericVerifier API"})

## File counts:
- Backend Python files: 45
- Frontend components: 10 (3 TSX components + 7 TS modules)
- Test files: 18
- Evaluation files: 144

## Key model artifacts:
- runs/decision_model_v6_1.joblib
- runs/feature_schema_v6_1.json
- runs/ml_metrics_v6_1.json

## CORS:
- Configured for http://localhost:5173 and http://127.0.0.1:5173

## Frontend:
- React SPA with Vite
- Components: InputPanel, DecisionPanel, AuditSignalsPanel
- Default flow: /verify (LLM-first)
- Manual override: /verify-only (when candidate answer provided)
- Mode indicator shown in UI ("LLM-Verified" vs "Manual Verification")
- Button text dynamically shows "Verify (LLM)" or "Verify (Manual)"
