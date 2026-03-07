"""Run ablation study: evaluate under multiple engine configurations.

Configurations:
1. rules_full (all engines on, rules mode)
2. rules_no_execution
3. rules_no_constraints
4. rules_no_lookup
5. rules_no_repair
6. ml_full (all engines on, ML mode)

Outputs:
  evaluation/ablation_results.csv
  evaluation/ablation_report.md
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.run_eval import run_single, compute_metrics, write_outputs


CONFIGS = [
    {"name": "rules_full", "mode": "rules", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": False, "enable_repair": True},
    {"name": "rules_no_execution", "mode": "rules", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": True, "enable_repair": True},
    {"name": "rules_no_constraints", "mode": "rules", "disable_lookup": False,
     "disable_constraints": True, "disable_execution": False, "enable_repair": True},
    {"name": "rules_no_lookup", "mode": "rules", "disable_lookup": True,
     "disable_constraints": False, "disable_execution": False, "enable_repair": True},
    {"name": "rules_no_repair", "mode": "rules", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": False, "enable_repair": False},
    {"name": "ml_full", "mode": "ml", "disable_lookup": False,
     "disable_constraints": False, "disable_execution": False, "enable_repair": True},
]


def main():
    cases_path = Path(__file__).parent / "cases_v2.json"
    if not cases_path.exists():
        print("cases_v2.json not found. Run generate_pnl_cases.py first.")
        sys.exit(1)

    with open(cases_path) as f:
        cases_data = json.load(f)
    print(f"Loaded {len(cases_data)} cases")

    output_dir = Path(__file__).parent
    all_metrics = []

    for cfg in CONFIGS:
        print(f"\n{'='*60}")
        print(f"Running config: {cfg['name']}")
        print(f"{'='*60}")

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
        for i, case in enumerate(cases_data):
            r = run_single(case, options)
            results.append(r)

        metrics = compute_metrics(results)
        metrics["config"] = cfg["name"]
        all_metrics.append(metrics)
        write_outputs(results, metrics, [], output_dir, config_name=cfg["name"])
        print(f"  Accuracy: {metrics['accuracy']:.2%}  False ACCEPT: {metrics['false_accept_rate']:.2%}  Repair: {metrics['repair_success_rate']:.2%}")

    # Write ablation_results.csv
    csv_path = output_dir / "ablation_results.csv"
    fieldnames = ["config", "accuracy", "false_accept_rate", "repair_success_rate",
                  "avg_latency_ms", "ACCEPT_f1", "REPAIR_f1", "FLAG_f1"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in all_metrics:
            writer.writerow({
                "config": m["config"],
                "accuracy": m["accuracy"],
                "false_accept_rate": m["false_accept_rate"],
                "repair_success_rate": m["repair_success_rate"],
                "avg_latency_ms": m["avg_latency_ms"],
                "ACCEPT_f1": m["per_class"].get("ACCEPT", {}).get("f1", 0),
                "REPAIR_f1": m["per_class"].get("REPAIR", {}).get("f1", 0),
                "FLAG_f1": m["per_class"].get("FLAG", {}).get("f1", 0),
            })

    # Write ablation_report.md
    baseline = all_metrics[0]  # rules_full
    md = ["# Ablation Study Report", "",
          f"Baseline: **{baseline['config']}** (accuracy={baseline['accuracy']:.2%}, "
          f"false_accept={baseline['false_accept_rate']:.2%})", ""]
    md.append("| Config | Accuracy | False Accept | Repair Success | Acc Delta | FA Delta |")
    md.append("|--------|----------|--------------|----------------|-----------|----------|")
    for m in all_metrics:
        acc_delta = m["accuracy"] - baseline["accuracy"]
        fa_delta = m["false_accept_rate"] - baseline["false_accept_rate"]
        md.append(f"| {m['config']} | {m['accuracy']:.2%} | {m['false_accept_rate']:.2%} | "
                  f"{m['repair_success_rate']:.2%} | {acc_delta:+.2%} | {fa_delta:+.2%} |")

    md.extend(["", "## Observations", "",
               "- Disabling lookup reduces grounding coverage and accuracy.",
               "- Disabling constraints removes period/scale checks, potentially increasing false accepts.",
               "- Disabling execution removes P&L identity and formula checks.",
               "- Disabling repair prevents automatic correction of recoverable errors.",
               "- ML mode uses the trained classifier after hard safety gates.",
               ])

    with open(output_dir / "ablation_report.md", "w") as f:
        f.write("\n".join(md) + "\n")

    print(f"\nAblation results: {csv_path}")
    print(f"Ablation report: {output_dir / 'ablation_report.md'}")


if __name__ == "__main__":
    main()
