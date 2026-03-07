# Reproducibility

## Filter Rules + Seed

- **P&L filter:** See [tatqa_pnl_filter.md](tatqa_pnl_filter.md)
- **Split seed:** 42
- **Split ratios:** train 70%, dev 15%, test 15%

## Counts Per Split

After running the TAT-QA adapter:

```
python -m evaluation.adapters.tatqa_to_pnl_verifyrequest
```

Counts are written to `docs/tatqa_pnl_filter.md`. Example:

- Train: N, Dev: N, Test: N

## Dataset Hashes

To compute SHA256 hashes for JSON files:

```bash
shasum -a 256 evaluation/base_cases_tatqa_pnl_train.json
shasum -a 256 evaluation/base_cases_tatqa_pnl_dev.json
shasum -a 256 evaluation/base_cases_tatqa_pnl_test.json
```

## Exact Commands to Reproduce

### Phase 0 — Baseline

```bash
pytest
python -m evaluation.run_eval --enable_repair
python -m evaluation.run_ablation
```

### Phase 1 — TAT-QA Adapter

```bash
# Place TAT-QA in data/tatqa/ or set TATQA_DATASET_DIR
python -m evaluation.adapters.tatqa_to_pnl_verifyrequest
```

### Phase 2 — Gold Eval

```bash
python -m evaluation.run_tatqa_gold_eval
```

### Phase 3 — LLM Eval (optional)

```bash
# Requires OPENAI_API_KEY
python -m evaluation.run_tatqa_llm_eval --limit 100 --cache evaluation/tatqa_llm_cache.jsonl
```

### Phase 4 — Build Signals

```bash
python -m evaluation.build_signals_full_pnl [--include_llm]
```

### Phase 5 — Train v3

```bash
python scripts/train_ml_decision_v3.py
```

### Phase 6 — Ablation

```bash
python -m evaluation.run_full_ablation_pnl
```

### Phase 7 — Figures

```bash
python -m evaluation.generate_figures_pnl
```

### Full Pipeline (no LLM)

```bash
python -m evaluation.run_all_pnl
```
