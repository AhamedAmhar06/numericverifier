"""Run full P&L pipeline: adapter -> gold eval -> build signals -> train v3 -> ablation.

LLM eval excluded unless --include_llm is passed.

Usage:
  python -m evaluation.run_all_pnl [--include_llm]
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None):
    print(f"\n>>> {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd)
    if r.returncode != 0:
        print(f"FAILED: {cmd}", file=sys.stderr)
        sys.exit(r.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include_llm", action="store_true", help="Run LLM eval (requires OPENAI_API_KEY)")
    parser.add_argument("--skip_adapter", action="store_true", help="Skip TAT-QA adapter (use existing base_cases)")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent

    if not args.skip_adapter:
        run("python -m evaluation.adapters.tatqa_to_pnl_verifyrequest", cwd=base)

    run("python -m evaluation.run_tatqa_gold_eval", cwd=base)

    if args.include_llm:
        run("python -m evaluation.run_tatqa_llm_eval --cache evaluation/tatqa_llm_cache.jsonl", cwd=base)

    run("python -m evaluation.build_signals_full_pnl" + (" --include_llm" if args.include_llm else ""), cwd=base)

    run("python scripts/train_ml_decision_v3.py", cwd=base)

    run("python -m evaluation.run_full_ablation_pnl", cwd=base)

    print("\n--- Pipeline complete ---")
    print("Outputs: evaluation/base_cases_tatqa_pnl_*.json, signals_pnl_*.csv,")
    print("        runs/decision_model_v3.joblib, evaluation/ablation_pnl_*.csv")


if __name__ == "__main__":
    main()
