# Final Summary: NumericVerifier P&L Upgrade

## Key Metrics

| Metric | Baseline (Phase 0) | After P&L Pipeline |
|--------|--------------------|--------------------|
| Synthetic accuracy | 84.52% | (see ablation_pnl_results.csv) |
| False ACCEPT rate | 19.44% | (see ablation) |
| Gold ACCEPT rate (TAT-QA) | — | (see tatqa_pnl_gold_*_metrics.json) |
| FLAG recall | 0.64 | (see ablation) |

## Output Locations

| Output | Path |
|--------|------|
| TAT-QA P&L cases | evaluation/base_cases_tatqa_pnl_{train,dev,test}.json |
| Gold eval results | evaluation/tatqa_pnl_gold_{split}_results.jsonl |
| Gold eval signals | evaluation/tatqa_pnl_gold_{split}_signals.csv |
| Gold eval metrics | evaluation/tatqa_pnl_gold_{split}_metrics.json |
| LLM eval (optional) | evaluation/tatqa_pnl_llm_results.jsonl |
| Signals dataset | evaluation/signals_pnl_{train,dev,test}.csv |
| v3 model | runs/decision_model_v3.joblib |
| v3 schema | runs/feature_schema_v3.json |
| Ablation results | evaluation/ablation_pnl_results.csv |
| Ablation report | evaluation/ablation_pnl_report.md |
| Figures | evaluation/figures/*.png |

## Reproducibility

See [reproducibility.md](reproducibility.md) for exact commands and dataset hashes.

## Run Full Pipeline

```bash
python -m evaluation.run_all_pnl
```

With LLM eval (requires OPENAI_API_KEY):

```bash
python -m evaluation.run_all_pnl --include_llm
```
