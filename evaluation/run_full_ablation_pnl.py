"""Full ablation on P&L-only: synthetic + TAT-QA gold test.

Runs on:
  - evaluation/cases_v2.json (synthetic)
  - evaluation/base_cases_tatqa_pnl_test.json (TAT-QA gold; candidate_answer = "The answer is {gold_answer}.")

Configs: full_rules, no_constraints, no_execution, no_lookup, no_repair, ml_full (v3)

Outputs:
  evaluation/ablation_pnl_results.csv
  evaluation/ablation_pnl_report.md
"""
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.run_eval import run_single, compute_metrics

CONFIGS = [
    {"name": "full_rules", "mode": "rules", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": False, "enable_repair": True},
    {"name": "no_constraints", "mode": "rules", "disable_lookup": False,
     "disable_constraints": True, "disable_execution": False, "enable_repair": True},
    {"name": "no_execution", "mode": "rules", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": True, "enable_repair": True},
    {"name": "no_lookup", "mode": "rules", "disable_lookup": True,
     "disable_constraints": False, "disable_execution": False, "enable_repair": True},
    {"name": "no_repair", "mode": "rules", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": False, "enable_repair": False},
    {"name": "ml_full", "mode": "ml", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": False, "enable_repair": True},
]


def _make_case_for_eval(case):
    """Convert TAT-QA case to run_eval format (candidate_answer, expected_decision)."""
    if "candidate_answer" in case:
        return case
    gold = case.get("gold_answer", "")
    return {
        **case,
        "candidate_answer": f"The answer is {gold}.",
        "expected_decision": "ACCEPT",
        "category": "gold",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tatqa_only", action="store_true",
                        help="Run ablation on TAT-QA P&L test cases only (no synthetic)")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    output_dir = base

    syn_cases = []
    if not args.tatqa_only:
        syn_path = base / "cases_v2.json"
        if syn_path.exists():
            with open(syn_path) as f:
                syn_cases = json.load(f)

    tatqa_path = base / "base_cases_tatqa_pnl_test.json"
    tatqa_cases = []
    if tatqa_path.exists():
        with open(tatqa_path) as f:
            tatqa_cases = [_make_case_for_eval(c) for c in json.load(f)]

    all_cases = syn_cases + tatqa_cases
    print(f"Loaded {len(syn_cases)} synthetic + {len(tatqa_cases)} TAT-QA test = {len(all_cases)} cases")

    # For ml_full, use v3 model
    orig_ml_ver = os.environ.get("ML_MODEL_VERSION")
    if orig_ml_ver is None:
        os.environ["ML_MODEL_VERSION"] = "v3"

    all_metrics = []
    for cfg in CONFIGS:
        print(f"\nRunning config: {cfg['name']}")
        options = {
            "tolerance": 0.01,
            "log_run": False,
            "disable_lookup": cfg.get("disable_lookup", False),
            "disable_constraints": cfg.get("disable_constraints", False),
            "disable_execution": cfg.get("disable_execution", False),
            "enable_repair": cfg.get("enable_repair", False),
        }
        if cfg.get("mode"):
            options["decision_mode"] = cfg["mode"]

        results = []
        for case in all_cases:
            r = run_single(case, options)
            results.append(r)

        metrics = compute_metrics(results)
        metrics["config"] = cfg["name"]
        all_metrics.append(metrics)
        print(f"  Accuracy: {metrics['accuracy']:.2%}  False ACCEPT: {metrics['false_accept_rate']:.2%}  "
              f"FLAG recall: {metrics['per_class'].get('FLAG', {}).get('recall', 0):.2%}")

    if orig_ml_ver is not None:
        os.environ["ML_MODEL_VERSION"] = orig_ml_ver
    elif "ML_MODEL_VERSION" in os.environ:
        del os.environ["ML_MODEL_VERSION"]

    # Write ablation_pnl_results.csv
    csv_path = output_dir / "ablation_pnl_results.csv"
    fieldnames = ["config", "accuracy", "false_accept_rate", "repair_success_rate",
                  "avg_latency_ms", "ACCEPT_f1", "REPAIR_f1", "FLAG_f1", "FLAG_recall"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in all_metrics:
            writer.writerow({
                "config": m["config"],
                "accuracy": m["accuracy"],
                "false_accept_rate": m["false_accept_rate"],
                "repair_success_rate": m["repair_success_rate"],
                "avg_latency_ms": m.get("avg_latency_ms", m.get("avg_latency", 0)),
                "ACCEPT_f1": m["per_class"].get("ACCEPT", {}).get("f1", 0),
                "REPAIR_f1": m["per_class"].get("REPAIR", {}).get("f1", 0),
                "FLAG_f1": m["per_class"].get("FLAG", {}).get("f1", 0),
                "FLAG_recall": m["per_class"].get("FLAG", {}).get("recall", 0),
            })

    # Write ablation_pnl_report.md
    baseline = all_metrics[0]
    md = ["# Ablation Report (P&L-only)", "",
          f"Baseline: **{baseline['config']}** (accuracy={baseline['accuracy']:.2%}, "
          f"false_accept={baseline['false_accept_rate']:.2%})", "",
          "| Config | Accuracy | False Accept | FLAG Recall | Acc Delta | FA Delta |",
          "|--------|----------|--------------|-------------|-----------|----------|"]
    for m in all_metrics:
        acc_delta = m["accuracy"] - baseline["accuracy"]
        fa_delta = m["false_accept_rate"] - baseline["false_accept_rate"]
        flag_recall = m["per_class"].get("FLAG", {}).get("recall", 0)
        md.append(f"| {m['config']} | {m['accuracy']:.2%} | {m['false_accept_rate']:.2%} | "
                  f"{flag_recall:.2%} | {acc_delta:+.2%} | {fa_delta:+.2%} |")
    md.extend(["", "## Deltas", "",
               "- false ACCEPT: increase = worse", "- gold ACCEPT: decrease = worse",
               "- FLAG recall: decrease = worse", "- latency: reported in ms", ""])
    with open(output_dir / "ablation_pnl_report.md", "w") as f:
        f.write("\n".join(md) + "\n")

    print(f"\nAblation results: {csv_path}")
    print(f"Ablation report: {output_dir / 'ablation_pnl_report.md'}")


if __name__ == "__main__":
    main()
