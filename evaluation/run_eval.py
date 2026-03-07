"""Evaluation runner for NumericVerifier.

Calls route_and_verify() directly (no server needed).
Writes: results_raw.jsonl, results_summary.json, confusion_matrix.csv, metrics.md

Usage:
  python -m evaluation.run_eval [--mode rules|ml]
    [--disable_lookup] [--disable_constraints] [--disable_execution] [--disable_repair]
    [--enable_repair] [--cases PATH] [--output_dir PATH]
"""
import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.verifier.router import route_and_verify


def _make_evidence_obj(ev_dict):
    """Convert evidence dict to object-like for route_and_verify."""
    class EvidenceLike:
        def __init__(self, d):
            self.type = d.get("type", "table")
            self.content = d.get("content", {})
    return EvidenceLike(ev_dict)


def run_single(case: dict, options: dict) -> dict:
    t0 = time.time()
    try:
        result = route_and_verify(
            question=case["question"],
            evidence=_make_evidence_obj(case["evidence"]),
            candidate_answer=case["candidate_answer"],
            options=dict(options),
        )
        latency_ms = (time.time() - t0) * 1000
        return {
            "id": case["id"],
            "expected": case["expected_decision"],
            "actual": result.get("decision", "ERROR"),
            "category": case.get("category", ""),
            "correct": result.get("decision") == case["expected_decision"],
            "latency_ms": round(latency_ms, 2),
            "signals": result.get("signals", {}),
            "rationale": result.get("rationale", ""),
            "repair": result.get("repair"),
        }
    except Exception as e:
        latency_ms = (time.time() - t0) * 1000
        return {
            "id": case["id"],
            "expected": case["expected_decision"],
            "actual": "ERROR",
            "category": case.get("category", ""),
            "correct": False,
            "latency_ms": round(latency_ms, 2),
            "error": str(e),
        }


def compute_metrics(results: list) -> dict:
    labels = ["ACCEPT", "REPAIR", "FLAG"]
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total if total else 0

    # Per-class
    per_class = {}
    for label in labels:
        tp = sum(1 for r in results if r["expected"] == label and r["actual"] == label)
        fp = sum(1 for r in results if r["expected"] != label and r["actual"] == label)
        fn = sum(1 for r in results if r["expected"] == label and r["actual"] != label)
        precision = tp / (tp + fp) if (tp + fp) else 0
        recall = tp / (tp + fn) if (tp + fn) else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
        per_class[label] = {"precision": round(precision, 4), "recall": round(recall, 4),
                            "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}

    # False accept rate: cases that should be FLAG or REPAIR but were ACCEPT
    false_accepts = sum(1 for r in results if r["actual"] == "ACCEPT" and r["expected"] != "ACCEPT")
    should_not_accept = sum(1 for r in results if r["expected"] != "ACCEPT")
    false_accept_rate = false_accepts / should_not_accept if should_not_accept else 0

    # Repair success rate
    repair_attempted = [r for r in results if r.get("repair") and r["repair"].get("repaired_decision")]
    repair_success = sum(1 for r in repair_attempted
                         if r["repair"]["repaired_decision"] == "ACCEPT" and r["expected"] == "ACCEPT")
    repair_success_rate = repair_success / len(repair_attempted) if repair_attempted else 0

    avg_latency = sum(r["latency_ms"] for r in results) / total if total else 0

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "false_accept_count": false_accepts,
        "false_accept_rate": round(false_accept_rate, 4),
        "repair_attempted": len(repair_attempted),
        "repair_success": repair_success,
        "repair_success_rate": round(repair_success_rate, 4),
        "avg_latency_ms": round(avg_latency, 2),
    }


def confusion_matrix(results: list) -> list:
    labels = ["ACCEPT", "REPAIR", "FLAG"]
    matrix = defaultdict(lambda: defaultdict(int))
    for r in results:
        matrix[r["expected"]][r["actual"]] += 1
    rows = [["expected\\actual"] + labels]
    for exp in labels:
        rows.append([exp] + [matrix[exp][act] for act in labels])
    return rows


def write_outputs(results: list, metrics: dict, cm: list, output_dir: Path, config_name: str = ""):
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{config_name}" if config_name else ""

    with open(output_dir / f"results_raw{suffix}.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r, default=str) + "\n")

    with open(output_dir / f"results_summary{suffix}.json", "w") as f:
        json.dump(metrics, f, indent=2)

    with open(output_dir / f"confusion_matrix{suffix}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(cm)

    md_lines = [
        f"# Evaluation Metrics{' (' + config_name + ')' if config_name else ''}",
        "",
        f"- **Total cases:** {metrics['total']}",
        f"- **Accuracy:** {metrics['accuracy']:.2%}",
        f"- **False ACCEPT rate:** {metrics['false_accept_rate']:.2%} ({metrics['false_accept_count']} false accepts)",
        f"- **Repair success rate:** {metrics['repair_success_rate']:.2%} ({metrics['repair_success']}/{metrics['repair_attempted']})",
        f"- **Avg latency:** {metrics['avg_latency_ms']:.1f} ms",
        "",
        "## Per-Class Metrics",
        "",
        "| Class | Precision | Recall | F1 |",
        "|-------|-----------|--------|----|",
    ]
    for label in ["ACCEPT", "REPAIR", "FLAG"]:
        pc = metrics["per_class"].get(label, {})
        md_lines.append(f"| {label} | {pc.get('precision', 0):.4f} | {pc.get('recall', 0):.4f} | {pc.get('f1', 0):.4f} |")

    with open(output_dir / f"metrics{suffix}.md", "w") as f:
        f.write("\n".join(md_lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="NumericVerifier Evaluation Runner")
    parser.add_argument("--cases", default=str(Path(__file__).parent / "cases_v2.json"))
    parser.add_argument("--output_dir", default=str(Path(__file__).parent))
    parser.add_argument("--mode", choices=["rules", "ml"], default=None)
    parser.add_argument("--disable_lookup", action="store_true")
    parser.add_argument("--disable_constraints", action="store_true")
    parser.add_argument("--disable_execution", action="store_true")
    parser.add_argument("--disable_repair", action="store_true")
    parser.add_argument("--enable_repair", action="store_true")
    parser.add_argument("--config_name", default="")
    args = parser.parse_args()

    with open(args.cases) as f:
        cases_data = json.load(f)
    print(f"Loaded {len(cases_data)} cases from {args.cases}")

    options = {
        "tolerance": 0.01,
        "log_run": False,
        "disable_lookup": args.disable_lookup,
        "disable_constraints": args.disable_constraints,
        "disable_execution": args.disable_execution,
        "enable_repair": args.enable_repair and not args.disable_repair,
    }
    if args.mode:
        options["decision_mode"] = args.mode

    results = []
    for i, case in enumerate(cases_data):
        r = run_single(case, options)
        results.append(r)
        status = "OK" if r["correct"] else "MISMATCH"
        print(f"  [{i+1}/{len(cases_data)}] {case['id']}: expected={r['expected']} actual={r['actual']} {status} ({r['latency_ms']:.0f}ms)")

    metrics = compute_metrics(results)
    cm = confusion_matrix(results)
    output_dir = Path(args.output_dir)
    write_outputs(results, metrics, cm, output_dir, config_name=args.config_name)

    print(f"\nResults written to {output_dir}")
    print(f"Accuracy: {metrics['accuracy']:.2%}")
    print(f"False ACCEPT rate: {metrics['false_accept_rate']:.2%}")
    print(f"Repair success rate: {metrics['repair_success_rate']:.2%}")
    print(f"Avg latency: {metrics['avg_latency_ms']:.1f} ms")

    return metrics


if __name__ == "__main__":
    main()
