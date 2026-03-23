"""TAT-QA P&L optional LLM evaluation.

Runs only if OPENAI_API_KEY exists. Uses --limit N and --cache to JSONL.
For each case: generate LLM answer, verify without repair, verify with repair.
Computes: false ACCEPT rate, repair success rate, latency delta.

Usage:
  python -m evaluation.run_tatqa_llm_eval [--limit N] [--cache PATH] [--splits train,dev]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.llm.provider import generate_llm_answer, get_openai_api_key
from backend.app.verifier.router import route_and_verify

SIGNAL_COLS = [
    "unsupported_claims_count", "coverage_ratio", "recomputation_fail_count",
    "max_relative_error", "mean_relative_error", "scale_mismatch_count",
    "period_mismatch_count", "ambiguity_count",
    "pnl_table_detected", "pnl_identity_fail_count", "pnl_margin_fail_count",
    "pnl_missing_baseline_count", "pnl_period_strict_mismatch_count",
]

TOLERANCE = 0.01


def _make_evidence_obj(ev_dict):
    class EvidenceLike:
        def __init__(self, d):
            self.type = d.get("type", "table")
            self.content = d.get("content", {})

    return EvidenceLike(ev_dict)


def _parse_numeric_from_text(text: str):
    """Extract first numeric value from text."""
    if not text:
        return None
    # Match numbers with optional commas, decimals, %
    m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    if m:
        try:
            return float(m.group(0).replace(",", ""))
        except ValueError:
            pass
    return None


def _numeric_close(a, b, rel_tol=TOLERANCE):
    """Check if two numbers are close within relative tolerance."""
    if a is None or b is None:
        return False
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return abs(a - b) < 1e-9
    return abs(a - b) / max(abs(a), abs(b)) <= rel_tol


def run_single(case, use_cache, cache):
    """Run LLM + verify (no repair) + verify (with repair)."""
    cid = case["id"]
    gold_num = _parse_numeric_from_text(case.get("gold_answer", ""))

    if use_cache and cid in cache:
        return cache[cid]

    content = case.get("evidence", {}).get("content", {})
    evidence = _make_evidence_obj(case["evidence"])

    # 1. Generate LLM answer
    t0 = time.time()
    llm_answer, llm_used, llm_fallback = generate_llm_answer(case["question"], content)
    llm_latency = (time.time() - t0) * 1000

    # 2. Verify without repair
    t0 = time.time()
    result_no_repair = route_and_verify(
        question=case["question"],
        evidence=evidence,
        candidate_answer=llm_answer,
        options={"enable_repair": False, "log_run": False},
    )
    latency_no_repair = (time.time() - t0) * 1000

    # 3. Verify with repair
    t0 = time.time()
    result_repair = route_and_verify(
        question=case["question"],
        evidence=evidence,
        candidate_answer=llm_answer,
        options={"enable_repair": True, "log_run": False},
    )
    latency_repair = (time.time() - t0) * 1000

    decision_no = result_no_repair.get("decision", "ERROR")
    decision_repair = result_repair.get("decision", "ERROR")
    repair_info = result_repair.get("repair")
    repaired_answer = repair_info.get("repaired_answer", "") if repair_info else ""
    repaired_num = _parse_numeric_from_text(repaired_answer)

    repair_success = (
        decision_repair == "ACCEPT"
        and repaired_num is not None
        and gold_num is not None
        and _numeric_close(repaired_num, gold_num)
    )

    out = {
        "id": cid,
        "question": case["question"],
        "gold_answer": case.get("gold_answer", ""),
        "llm_answer": llm_answer,
        "llm_used": llm_used,
        "llm_fallback": llm_fallback,
        "decision_before": decision_no,
        "decision_after": decision_repair,
        "repair_success": repair_success,
        "repaired_answer": repaired_answer,
        "latency_llm_ms": round(llm_latency, 2),
        "latency_no_repair_ms": round(latency_no_repair, 2),
        "latency_repair_ms": round(latency_repair, 2),
        "signals": result_repair.get("signals", {}),
    }
    return out


def compute_metrics(results: list) -> dict:
    total = len(results)
    llm_used_count = sum(1 for r in results if r.get("llm_used"))
    false_accept_before = sum(1 for r in results if r["decision_before"] == "ACCEPT" and r.get("gold_answer"))
    false_accept_after = sum(1 for r in results if r["decision_after"] == "ACCEPT" and r.get("gold_answer"))
    repair_success_count = sum(1 for r in results if r.get("repair_success"))
    repair_attempted = sum(1 for r in results if r.get("repaired_answer"))

    avg_latency_before = sum(r["latency_no_repair_ms"] for r in results) / total if total else 0
    avg_latency_after = sum(r["latency_repair_ms"] for r in results) / total if total else 0
    latency_delta = avg_latency_after - avg_latency_before

    return {
        "total": total,
        "llm_used_count": llm_used_count,
        "false_accept_before": false_accept_before,
        "false_accept_after": false_accept_after,
        "repair_success_count": repair_success_count,
        "repair_attempted": repair_attempted,
        "repair_success_rate": round(repair_success_count / repair_attempted, 4) if repair_attempted else 0,
        "avg_latency_before_ms": round(avg_latency_before, 2),
        "avg_latency_after_ms": round(avg_latency_after, 2),
        "latency_delta_ms": round(latency_delta, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="TAT-QA P&L LLM evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Max cases per split")
    parser.add_argument("--cache", default=None, help="JSONL cache path; skip generation if cached")
    parser.add_argument("--splits", default="train,dev", help="Splits to run (no test by default)")
    parser.add_argument("--output_dir", default=None)
    args = parser.parse_args()

    if not get_openai_api_key():
        print("OPENAI_API_KEY not set. Skipping LLM eval.", file=sys.stderr)
        sys.exit(0)

    base = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir) if args.output_dir else base
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]

    cache = {}
    if args.cache:
        cache_path = Path(args.cache)
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        cache[r["id"]] = r
            print(f"Loaded {len(cache)} cached results from {cache_path}")

    all_results = []
    for split in splits:
        cases_path = output_dir / f"base_cases_tatqa_pnl_{split}.json"
        if not cases_path.exists():
            print(f"Skipping {split}: {cases_path} not found")
            continue

        with open(cases_path, encoding="utf-8") as f:
            cases = json.load(f)

        if args.limit:
            cases = cases[: args.limit]

        print(f"\n--- {split} ({len(cases)} cases) ---")
        for i, case in enumerate(cases):
            r = run_single(case, use_cache=bool(args.cache), cache=cache)
            all_results.append(r)
            if args.cache and r["id"] not in cache:
                cache[r["id"]] = r
            status = "repair_ok" if r.get("repair_success") else r["decision_after"]
            print(f"  [{i + 1}/{len(cases)}] {case['id']}: {r['decision_before']} -> {status}")

    if not all_results:
        print("No results.")
        return

    metrics = compute_metrics(all_results)

    results_path = output_dir / "tatqa_pnl_llm_results.jsonl"
    with open(results_path, "w", encoding="utf-8") as f:
        for r in all_results:
            out = {k: v for k, v in r.items() if k != "signals"}
            out["signals"] = r.get("signals", {})
            f.write(json.dumps(out, default=str) + "\n")
    print(f"\nWrote {results_path}")

    if args.cache:
        with open(args.cache, "w", encoding="utf-8") as f:
            for r in all_results:
                out = {k: v for k, v in r.items() if k != "signals"}
                out["signals"] = r.get("signals", {})
                f.write(json.dumps(out, default=str) + "\n")
        print(f"Updated cache {args.cache}")

    signals_path = output_dir / "tatqa_pnl_llm_signals.csv"
    with open(signals_path, "w", newline="", encoding="utf-8") as f:
        cols = ["case_id", "decision_before", "decision_after", "repair_success"] + [
            c for c in SIGNAL_COLS if c != "schema_version"
        ]
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for r in all_results:
            row = {
                "case_id": r["id"],
                "decision_before": r["decision_before"],
                "decision_after": r["decision_after"],
                "repair_success": r.get("repair_success", False),
            }
            for c in cols:
                if c not in row and c in (r.get("signals") or {}):
                    row[c] = r["signals"][c]
            writer.writerow(row)
    print(f"Wrote {signals_path}")

    metrics_path = output_dir / "tatqa_pnl_llm_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Wrote {metrics_path}")
    print(f"  Repair success rate: {metrics['repair_success_rate']:.2%}")
    print(f"  Latency delta: {metrics['latency_delta_ms']:.1f} ms")


if __name__ == "__main__":
    main()
