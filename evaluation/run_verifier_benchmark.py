"""Research-grade verification benchmark pipeline.

Track 1: Gold answer verification — measures verifier behavior on correct answers.
Track 2: Error-injected verification — measures detection of incorrect answers.

Usage:
  python -m evaluation.run_verifier_benchmark [--regenerate] [--skip-track1] [--skip-track2]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.verifier.router import route_and_verify
from backend.app.verifier.extract import extract_numeric_claims
from backend.app.verifier.normalize import normalize_cell_text

_EVAL_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _EvidenceLike:
    def __init__(self, d: dict):
        self.type = d.get("type", "table")
        self.content = d.get("content", {})


def _run_verifier(question: str, evidence: dict, candidate_answer: str,
                  enable_repair: bool = False) -> Dict[str, Any]:
    t0 = time.time()
    try:
        result = route_and_verify(
            question=question,
            evidence=_EvidenceLike(evidence),
            candidate_answer=candidate_answer,
            options={"enable_repair": enable_repair, "log_run": False},
        )
        latency_ms = (time.time() - t0) * 1000
        return {**result, "latency_ms": round(latency_ms, 2), "error": None}
    except Exception as e:
        latency_ms = (time.time() - t0) * 1000
        return {"decision": "ERROR", "latency_ms": round(latency_ms, 2), "error": str(e),
                "signals": {}, "grounding": [], "verification": [], "repair": None}


def _parse_gold_float(gold_str: str) -> Optional[float]:
    result = normalize_cell_text(gold_str)
    if result["value"] is not None:
        return result["value"] * result["scale_factor"]
    cleaned = re.sub(r"[,$%€£¥₹]", "", gold_str).strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _repair_matches_gold(repair_output: Optional[dict], gold_answer: str,
                         tolerance: float = 0.01) -> bool:
    """Check if the repaired answer contains a numeric value matching the gold answer."""
    if not repair_output:
        return False
    repaired_text = repair_output.get("repaired_answer", "")
    if not repaired_text:
        return False
    gold_val = _parse_gold_float(gold_answer)
    if gold_val is None:
        return False
    claims = extract_numeric_claims(repaired_text)
    for claim in claims:
        if gold_val == 0:
            if abs(claim.parsed_value) <= tolerance:
                return True
        elif abs((claim.parsed_value - gold_val) / gold_val) <= tolerance:
            return True
    return False


# ---------------------------------------------------------------------------
# Track 1: Gold Answer Verification
# ---------------------------------------------------------------------------

def run_track1(cases: List[dict]) -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("TRACK 1: Gold Answer Verification")
    print("=" * 60)

    results = []
    for i, case in enumerate(cases):
        candidate = f"The answer is {case['gold_answer']}."
        r = _run_verifier(case["question"], case["evidence"], candidate, enable_repair=False)

        has_grounding = len(r.get("grounding", [])) > 0
        has_execution = any(
            v.get("execution_supported", False) for v in r.get("verification", [])
        )

        record = {
            "id": case["id"],
            "question": case["question"],
            "gold_answer": case["gold_answer"],
            "decision": r.get("decision", "ERROR"),
            "rationale": r.get("rationale", ""),
            "latency_ms": r["latency_ms"],
            "has_grounding": has_grounding,
            "has_execution": has_execution,
            "signals": r.get("signals", {}),
        }
        results.append(record)
        print(f"  [{i+1}/{len(cases)}] {case['id']}: {record['decision']} ({record['latency_ms']:.1f}ms)")

    total = len(results)
    accept = sum(1 for r in results if r["decision"] == "ACCEPT")
    flag = sum(1 for r in results if r["decision"] == "FLAG")
    repair = sum(1 for r in results if r["decision"] == "REPAIR")
    grounded = sum(1 for r in results if r["has_grounding"])
    executed = sum(1 for r in results if r["has_execution"])
    avg_lat = sum(r["latency_ms"] for r in results) / total if total else 0

    metrics = {
        "total": total,
        "correct_accept_count": accept,
        "correct_accept_rate": round(accept / total, 4) if total else 0,
        "unsupported_but_correct_flag_count": flag,
        "unsupported_but_correct_flag_rate": round(flag / total, 4) if total else 0,
        "repair_count": repair,
        "repair_rate": round(repair / total, 4) if total else 0,
        "grounding_coverage_count": grounded,
        "grounding_coverage": round(grounded / total, 4) if total else 0,
        "execution_coverage_count": executed,
        "execution_coverage": round(executed / total, 4) if total else 0,
        "avg_latency_ms": round(avg_lat, 2),
    }

    print(f"\n  Correct Accept Rate:     {metrics['correct_accept_rate']:.2%}")
    print(f"  Unsupported-but-Correct: {metrics['unsupported_but_correct_flag_rate']:.2%}")
    print(f"  Grounding Coverage:      {metrics['grounding_coverage']:.2%}")
    print(f"  Execution Coverage:      {metrics['execution_coverage']:.2%}")
    print(f"  Avg Latency:             {metrics['avg_latency_ms']:.2f}ms")

    return {"metrics": metrics, "results": results}


# ---------------------------------------------------------------------------
# Track 2: Error-Injected Verification
# ---------------------------------------------------------------------------

def run_track2(injected_cases: List[dict]) -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("TRACK 2: Error-Injected Verification")
    print("=" * 60)

    results = []
    for i, case in enumerate(injected_cases):
        r = _run_verifier(case["question"], case["evidence"],
                          case["candidate_answer"], enable_repair=True)

        repair_output = r.get("repair")
        repair_success = _repair_matches_gold(repair_output, case["gold_answer"])

        record = {
            "id": case["id"],
            "original_id": case["original_id"],
            "error_type": case["error_type"],
            "gold_answer": case["gold_answer"],
            "injected_value": case["injected_value"],
            "decision": r.get("decision", "ERROR"),
            "latency_ms": r["latency_ms"],
            "repair_success": repair_success,
            "signals": r.get("signals", {}),
        }
        results.append(record)

        if (i + 1) % 25 == 0 or (i + 1) == len(injected_cases):
            print(f"  [{i+1}/{len(injected_cases)}] processed...")

    total = len(results)
    accept_all = sum(1 for r in results if r["decision"] == "ACCEPT")
    repair_all = sum(1 for r in results if r["decision"] == "REPAIR")
    flag_all = sum(1 for r in results if r["decision"] == "FLAG")
    detect_all = repair_all + flag_all
    repair_ok = sum(1 for r in results if r["decision"] == "REPAIR" and r["repair_success"])
    avg_lat = sum(r["latency_ms"] for r in results) / total if total else 0

    aggregate = {
        "total": total,
        "false_accept_count": accept_all,
        "false_accept_rate": round(accept_all / total, 4) if total else 0,
        "detection_count": detect_all,
        "detection_rate": round(detect_all / total, 4) if total else 0,
        "repair_count": repair_all,
        "repair_success_count": repair_ok,
        "repair_success_rate": round(repair_ok / repair_all, 4) if repair_all else 0,
        "avg_latency_ms": round(avg_lat, 2),
    }

    per_type: Dict[str, Dict[str, Any]] = {}
    by_type = defaultdict(list)
    for r in results:
        by_type[r["error_type"]].append(r)
    for etype, etype_results in sorted(by_type.items()):
        n = len(etype_results)
        a = sum(1 for r in etype_results if r["decision"] == "ACCEPT")
        rep = sum(1 for r in etype_results if r["decision"] == "REPAIR")
        fl = sum(1 for r in etype_results if r["decision"] == "FLAG")
        det = rep + fl
        rep_ok = sum(1 for r in etype_results if r["decision"] == "REPAIR" and r["repair_success"])
        lat = sum(r["latency_ms"] for r in etype_results) / n if n else 0
        per_type[etype] = {
            "total": n,
            "accept_count": a,
            "false_accept_rate": round(a / n, 4) if n else 0,
            "repair_count": rep,
            "flag_count": fl,
            "detection_count": det,
            "detection_rate": round(det / n, 4) if n else 0,
            "repair_success_count": rep_ok,
            "repair_success_rate": round(rep_ok / rep, 4) if rep else 0,
            "avg_latency_ms": round(lat, 2),
        }

    print(f"\n  {'Error Type':<22} {'Total':>5} {'ACCEPT':>7} {'REPAIR':>7} {'FLAG':>5} {'Detect%':>8} {'FA%':>6}")
    print(f"  {'-'*22} {'-'*5} {'-'*7} {'-'*7} {'-'*5} {'-'*8} {'-'*6}")
    for etype in sorted(per_type):
        m = per_type[etype]
        print(f"  {etype:<22} {m['total']:>5} {m['accept_count']:>7} {m['repair_count']:>7} "
              f"{m['flag_count']:>5} {m['detection_rate']:>7.1%} {m['false_accept_rate']:>5.1%}")
    print(f"  {'AGGREGATE':<22} {aggregate['total']:>5} {aggregate['false_accept_count']:>7} "
          f"{aggregate['repair_count']:>7} {flag_all:>5} {aggregate['detection_rate']:>7.1%} "
          f"{aggregate['false_accept_rate']:>5.1%}")

    return {"aggregate": aggregate, "per_type": per_type, "results": results}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _write_gold_report(t1: Dict[str, Any], path: Path):
    m = t1["metrics"]
    lines = [
        "# Track 1: Gold Answer Verification Report\n",
        "## Summary Metrics\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total cases | {m['total']} |",
        f"| Correct Accept Rate | {m['correct_accept_rate']:.2%} |",
        f"| Unsupported-but-Correct Flag Rate | {m['unsupported_but_correct_flag_rate']:.2%} |",
        f"| Repair Rate | {m['repair_rate']:.2%} |",
        f"| Grounding Coverage | {m['grounding_coverage']:.2%} |",
        f"| Execution Coverage | {m['execution_coverage']:.2%} |",
        f"| Avg Latency | {m['avg_latency_ms']:.2f}ms |",
        "",
        "## Per-Case Results\n",
        "| Case ID | Decision | Grounded | Executed | Latency (ms) |",
        "|---|---|---|---|---|",
    ]
    for r in t1["results"]:
        lines.append(f"| {r['id']} | {r['decision']} | {'Y' if r['has_grounding'] else 'N'} "
                      f"| {'Y' if r['has_execution'] else 'N'} | {r['latency_ms']:.1f} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_error_report(t2: Dict[str, Any], path: Path):
    agg = t2["aggregate"]
    pt = t2["per_type"]
    lines = [
        "# Track 2: Error-Injected Verification Report\n",
        "## Aggregate Metrics\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total injected cases | {agg['total']} |",
        f"| False Accept Rate | {agg['false_accept_rate']:.2%} |",
        f"| Detection Rate | {agg['detection_rate']:.2%} |",
        f"| Repair Success Rate | {agg['repair_success_rate']:.2%} |",
        f"| Avg Latency | {agg['avg_latency_ms']:.2f}ms |",
        "",
        "## Per-Error-Type Breakdown\n",
        "| Error Type | Total | ACCEPT | REPAIR | FLAG | Detection% | False Accept% | Repair Success% |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for etype in sorted(pt):
        m = pt[etype]
        lines.append(
            f"| {etype} | {m['total']} | {m['accept_count']} | {m['repair_count']} "
            f"| {m['flag_count']} | {m['detection_rate']:.1%} | {m['false_accept_rate']:.1%} "
            f"| {m['repair_success_rate']:.1%} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_final_summary(t1: Dict[str, Any], t2: Dict[str, Any], path: Path):
    m1 = t1["metrics"]
    agg2 = t2["aggregate"]
    pt2 = t2["per_type"]

    t1_accept = m1["correct_accept_count"]
    t1_repair = m1["repair_count"]
    t1_flag = m1["unsupported_but_correct_flag_count"]
    t1_total = m1["total"]

    lines = [
        "# NumericVerifier — Research-Grade Verification Benchmark\n",
        "## Combined Summary\n",
        "| Candidate Type | Total | ACCEPT | REPAIR | FLAG | Accept% | Detect% |",
        "|---|---|---|---|---|---|---|",
        f"| Correct (gold) | {t1_total} | {t1_accept} | {t1_repair} | {t1_flag} "
        f"| {m1['correct_accept_rate']:.1%} | -- |",
    ]
    for etype in ["arithmetic_error", "percentage_error", "scale_error", "period_error", "near_miss_error"]:
        if etype in pt2:
            m = pt2[etype]
            lines.append(
                f"| {etype} | {m['total']} | {m['accept_count']} | {m['repair_count']} "
                f"| {m['flag_count']} | {m['false_accept_rate']:.1%} | {m['detection_rate']:.1%} |"
            )
    lines.append(
        f"| **All errors** | {agg2['total']} | {agg2['false_accept_count']} | {agg2['repair_count']} "
        f"| {agg2['total'] - agg2['false_accept_count'] - agg2['repair_count']} "
        f"| {agg2['false_accept_rate']:.1%} | {agg2['detection_rate']:.1%} |"
    )

    lines.extend([
        "",
        "## Key Verification Quality Metrics\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Correct Accept Rate (gold) | {m1['correct_accept_rate']:.2%} |",
        f"| False Accept Rate (errors) | {agg2['false_accept_rate']:.2%} |",
        f"| Error Detection Rate | {agg2['detection_rate']:.2%} |",
        f"| Repair Success Rate | {agg2['repair_success_rate']:.2%} |",
        f"| Grounding Coverage (gold) | {m1['grounding_coverage']:.2%} |",
        f"| Execution Coverage (gold) | {m1['execution_coverage']:.2%} |",
        f"| Avg Latency (gold) | {m1['avg_latency_ms']:.2f}ms |",
        f"| Avg Latency (errors) | {agg2['avg_latency_ms']:.2f}ms |",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Research-grade verification benchmark")
    parser.add_argument("--regenerate", action="store_true",
                        help="Regenerate error-injected cases even if file exists")
    parser.add_argument("--skip-track1", action="store_true")
    parser.add_argument("--skip-track2", action="store_true")
    args = parser.parse_args()

    gold_path = _EVAL_DIR / "base_cases_tatqa_pnl_test.json"
    if not gold_path.exists():
        print(f"ERROR: {gold_path} not found")
        sys.exit(1)
    with open(gold_path, encoding="utf-8") as f:
        gold_cases = json.load(f)
    print(f"Loaded {len(gold_cases)} gold test cases")

    t1_out = None
    t2_out = None

    # --- Track 1 ---
    if not args.skip_track1:
        t1_out = run_track1(gold_cases)
        metrics_path = _EVAL_DIR / "gold_verification_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(t1_out["metrics"], f, indent=2)
        print(f"\n  Wrote {metrics_path}")

        report_path = _EVAL_DIR / "gold_verification_report.md"
        _write_gold_report(t1_out, report_path)
        print(f"  Wrote {report_path}")

    # --- Track 2 ---
    if not args.skip_track2:
        injected_path = _EVAL_DIR / "error_injected_cases.json"
        if args.regenerate or not injected_path.exists():
            print("\nGenerating error-injected cases...")
            import random
            from evaluation.error_injection_generator import generate_errors
            rng = random.Random(42)
            injected_cases = generate_errors(gold_cases, rng)
            with open(injected_path, "w", encoding="utf-8") as f:
                json.dump(injected_cases, f, indent=2, default=str)
            print(f"  Generated {len(injected_cases)} cases -> {injected_path}")
        else:
            with open(injected_path, encoding="utf-8") as f:
                injected_cases = json.load(f)
            print(f"\nLoaded {len(injected_cases)} error-injected cases from {injected_path}")

        t2_out = run_track2(injected_cases)
        metrics_path = _EVAL_DIR / "error_injection_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump({"aggregate": t2_out["aggregate"], "per_type": t2_out["per_type"]}, f, indent=2)
        print(f"\n  Wrote {metrics_path}")

        report_path = _EVAL_DIR / "error_injection_report.md"
        _write_error_report(t2_out, report_path)
        print(f"  Wrote {report_path}")

    # --- Final Summary ---
    if t1_out and t2_out:
        summary_path = _EVAL_DIR / "final_verification_summary.md"
        _write_final_summary(t1_out, t2_out, summary_path)
        print(f"\n  Wrote {summary_path}")

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
