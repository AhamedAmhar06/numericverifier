# AI Reference Cleanup Report

**Date:** 2026-03-29
**Branch:** claude/peaceful-goldberg (≡ main ≡ final-integrated-2026-03-29)

---

## Summary

A full sweep of all project files was performed for references to Claude, Codex, AI-generated wording, co-authored-by-AI footers, or similar attribution that would be inappropriate in academic project-facing artifacts.

**Search coverage:**
- All `*.md` files
- All `*.py`, `*.ts`, `*.tsx`, `*.js`, `*.html` source files
- All `*.json` data and evaluation files
- All `*.ipynb` notebook files

---

## Findings

### FIXED — Project-facing artifact (blocking)

| File | Line | Issue | Fix Applied |
|------|------|-------|-------------|
| `evaluation/llm_evaluation_apple_20cases.json` | 6 | `"model": "claude-sonnet (via /verify endpoint with LLM fallback enabled)"` — **factually incorrect**: actual LLM used is `gpt-4o-mini` via OpenAI (per `backend/app/llm/provider.py`) | Changed to `"model": "gpt-4o-mini (via OpenAI, /verify endpoint)"` |

**Why this was a problem:** This file is listed as "Show in Report? Yes" in FINAL_ACTIVE_PROJECT_MAP.md. The model field contained a wrong model name (claude-sonnet) when the actual implementation uses OpenAI `gpt-4o-mini`. This was both an AI reference issue and a factual inaccuracy.

---

### NOTED — Non-project-facing artifacts (non-blocking)

| File | Line | Content | Status |
|------|------|---------|--------|
| `evaluation/ml_v5_findings.json` | 94 | `"real_llm_errors": "Collect actual GPT-4/Claude P&L answers for authentic error distribution in training data"` | Not in FINAL_ACTIVE_PROJECT_MAP.md active file list. Future work note only. No action required. |
| `evaluation/ml_v4_findings.json` | 45 | `"real_llm_errors": "Collect actual LLM-generated wrong answers from GPT-4/Claude on real P&L questions"` | Not in FINAL_ACTIVE_PROJECT_MAP.md active file list. Future work note only. No action required. |

These files are internal experiment tracking artifacts from earlier ML iterations (V4, V5). They are not listed in the active project map and are not shown in the dissertation report.

---

## Clean Files Confirmed

- All `*.md` project documentation files: **clean**
- All backend Python source files (`backend/app/**/*.py`): **clean**
- All frontend TypeScript/TSX source files (`frontend/src/**`): **clean**
- `README.md`: **clean**
- `notebooks/FINAL_V6_1_Demo.ipynb`: **clean**
- All `runs/*.json` model artifacts: **clean**

---

## Git Author History

Not modified. No git author history contains inappropriate references — only commit messages contain standard co-authorship footers from the version control workflow. No `--amend` or history rewrite has been performed.

If git history rewrite is needed for submission, consult the repository owner before running `git filter-branch` or `git rebase -i`.
