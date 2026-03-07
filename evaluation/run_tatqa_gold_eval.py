"""TAT-QA P&L gold evaluation (no LLM).

For each split file, sets candidate_answer = "The answer is {gold_answer}."
and runs route_and_verify with enable_repair=false, log_run=false.

Outputs:
  - evaluation/tatqa_pnl_gold_{split}_results.jsonl
  - evaluation/tatqa_pnl_gold_{split}_signals.csv
  - evaluation/tatqa_pnl_gold_{split}_metrics.json

Usage:
  python -m evaluation.run_tatqa_gold_eval [--splits train,dev,test] [--output_dir PATH]
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.verifier.router import route_and_verify

SIGNAL_COLS = [
    "unsupported_claims_count", "coverage_ratio", "recomputation_fail_count",
    "max_relative_error", "mean_relative_error", "scale_mismatch_count",
    "period_mismatch_count", "ambiguity_count",
    "pnl_table_detected", "pnl_identity_fail_count", "pnl_margin_fail_count",
    "pnl_missing_baseline_count", "pnl_period_strict_mismatch_count",
]


def _make_evidence_obj(ev_dict):
    class EvidenceLike:
        def __init__(self, d):
            self.type = d.get("type", "table")
            self.content = d.get("content", {})

    return EvidenceLike(ev_dict)


def run_single(case: dict) -> dict:
    candidate_answer = f"The answer is {case['gold_answer']}."
    t0 = time.time()
    try:
        result = route_and_verify(
            question=case["question"],
            evidence=_make_evidence_obj(case["evidence"]),
            candidate_answer=candidate_answer,
            options={"enable_repair": False, "log_run": False},
        )
        latency_ms = (time.time() - t0) * 1000
        signals = result.get("signals", {})
        return {
            "id": case["id"],
            "question": case["question"],
            "gold_answer": case["gold_answer"],
            "decision": result.get("decision", "ERROR"),
            "rationale": result.get("rationale", ""),
            "signals": signals,
            "grounding": result.get("grounding", []),
            "violations": (result.get("report") or {}).get("constraint_violations", []),
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        latency_ms = (time.time() - t0) * 1000
        return {
            "id": case["id"],
            "question": case["question"],
            "gold_answer": case["gold_answer"],
            "decision": "ERROR",
            "rationale": str(e),
            "signals": {},
            "grounding": [],
            "violations": [],
            "latency_ms": round(latency_ms, 2),
        }


def compute_metrics(results: list) -> dict:
    total = len(results)
    accept_count = sum(1 for r in results if r["decision"] == "ACCEPT")
    flag_count = sum(1 for r in results if r["decision"] == "FLAG")
    repair_count = sum(1 for r in results if r["decision"] == "REPAIR")
    error_count = sum(1 for r in results if r["decision"] == "ERROR")

    gold_accept_rate = accept_count / total if total else 0
    false_flag_rate = flag_count / total if total else 0
    repair_rate = repair_count / total if total else 0

    grounded = sum(1 for r in results if (r.get("signals") or {}).get("coverage_ratio", 0) > 0)
    grounding_rate = grounded / total if total else 0

    scale_mismatch = sum(1 for r in results if (r.get("signals") or {}).get("scale_mismatch_count", 0) > 0)
    period_mismatch = sum(1 for r in results if (r.get("signals") or {}).get("period_mismatch_count", 0) > 0)
    scale_mismatch_rate = scale_mismatch / total if total else 0
    period_mismatch_rate = period_mismatch / total if total else 0

    avg_latency = sum(r["latency_ms"] for r in results) / total if total else 0

    return {
        "total": total,
        "gold_accept_count": accept_count,
        "gold_accept_rate": round(gold_accept_rate, 4),
        "false_flag_count": flag_count,
        "false_flag_rate": round(false_flag_rate, 4),
        "repair_count": repair_count,
        "repair_rate": round(repair_rate, 4),
        "error_count": error_count,
        "grounding_rate": round(grounding_rate, 4),
        "scale_mismatch_count": scale_mismatch,
        "scale_mismatch_rate": round(scale_mismatch_rate, 4),
        "period_mismatch_count": period_mismatch,
        "period_mismatch_rate": round(period_mismatch_rate, 4),
        "avg_latency_ms": round(avg_latency, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="TAT-QA P&L gold evaluation")
    parser.add_argument("--splits", default="train,dev,test",
                        help="Comma-separated splits to run")
    parser.add_argument("--output_dir", default=None)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir) if args.output_dir else base
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]

    for split in splits:
        cases_path = output_dir / f"base_cases_tatqa_pnl_{split}.json"
        if not cases_path.exists():
            print(f"Skipping {split}: {cases_path} not found")
            continue

        with open(cases_path, encoding="utf-8") as f:
            cases = json.load(f)

        print(f"\n--- {split} ({len(cases)} cases) ---")
        results = []
        for i, case in enumerate(cases):
            r = run_single(case)
            results.append(r)
            status = "OK" if r["decision"] == "ACCEPT" else r["decision"]
            print(f"  [{i + 1}/{len(cases)}] {case['id']}: {r['decision']} ({r['latency_ms']:.0f}ms)")

        metrics = compute_metrics(results)

        results_path = output_dir / f"tatqa_pnl_gold_{split}_results.jsonl"
        with open(results_path, "w", encoding="utf-8") as f:
            for r in results:
                out = {k: v for k, v in r.items() if k != "signals"}
                out["signals"] = r.get("signals", {})
                f.write(json.dumps(out, default=str) + "\n")
        print(f"Wrote {results_path}")

        signals_path = output_dir / f"tatqa_pnl_gold_{split}_signals.csv"
        with open(signals_path, "w", newline="", encoding="utf-8") as f:
            cols = ["case_id", "decision"] + [c for c in SIGNAL_COLS if c != "schema_version"]
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                row = {"case_id": r["id"], "decision": r["decision"]}
                sig = r.get("signals", {})
                for c in cols:
                    if c not in row and c in sig:
                        row[c] = sig[c]
                writer.writerow(row)
        print(f"Wrote {signals_path}")

        metrics_path = output_dir / f"tatqa_pnl_gold_{split}_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"Wrote {metrics_path}")
        print(f"  Gold ACCEPT: {metrics['gold_accept_rate']:.2%}, False FLAG: {metrics['false_flag_rate']:.2%}")
        print(f"  Grounding: {metrics['grounding_rate']:.2%}, Scale mismatch: {metrics['scale_mismatch_rate']:.2%}")


if __name__ == "__main__":
    main()
