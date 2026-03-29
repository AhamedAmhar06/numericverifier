# Branch Decision

## Chosen Branch: final-integrated-2026-03-29

### Branch State
- Source: feat/react-frontend (most complete integrated state)
- Base commit: 2e4eb24 (add final evaluation artifacts and ignore local dev files)
- All commits from feat/react-frontend preserved

### Recent Commits (source branch)
- 2e4eb24 add final evaluation artifacts and ignore local dev files
- 930b84f eval: add ingestion layer test results
- 6d24177 feat(demo): add V6.1 final demo notebook for viva
- f1966a1 docs: fix stale numbers in existing FINAL_*.md files
- ef4ab91 docs: add dissertation safe/unsafe claims and report alignment
- 581fac8 docs: add final active project map, model trace, evidence pack
- 3ef74a5 fix: handle string units in evidence content
- 3f84f22 docs: add final codebase status and session 4 reports
- fa8d307 test(ingestion): add 7 unit tests for assess_ingestion() ingestion layer
- e9b6fb1 feat(ingestion): add LLM-assisted P&L row label ingestion layer
- 84f4ecc feat(frontend): import and align React frontend with backend contract
- 6d9effe feat(ml): V6.1 XGBoost — balanced training data
- 8a7f0e0 feat(ml): V6 XGBoost — regenerated signals
- 6fee0d6 eval: hard questions 10/10 after ratio library
- 4458c2f feat(execution): complete P&L ratio library

### What was excluded from local main
Local main was behind feat/react-frontend by 46 files / 6019 deletions. It was missing:
- Frontend (React SPA with InputPanel, DecisionPanel, AuditSignalsPanel)
- TypeScript config files (tsconfig.json, tsconfig.app.json, tsconfig.node.json)
- Vite config
- Demo notebook (FINAL_V6_1_Demo.ipynb)
- Ingestion layer tests (test_assess_ingestion.py)
- Runtime logs

### What this branch has
- Final backend pipeline (V6.1 XGBClassifier ML, ingestion layer, all verifiers)
- Final frontend (React, built, /verify as primary endpoint)
- Final demo notebook for viva
- Final documentation
- All 234 passing tests (4 skipped)
- /verify as PRIMARY endpoint (LLM-first flow)
- /verify-only as SECONDARY endpoint (manual verification)
