"""Run 20 real-world Apple FY2023 questions through LLM -> NumericVerifier.

Usage:
  DEBUG=false python3 -m evaluation.run_apple_llm_eval_20
  DEBUG=false python3 -m evaluation.run_apple_llm_eval_20 --output evaluation/apple_llm_eval_20_results.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.ingestion.csv_pnl_parser import parse_csv_pnl
from backend.app.llm.provider import generate_llm_answer, get_openai_api_key
from backend.app.verifier.router import route_and_verify


@dataclass
class Case:
    id: str
    question: str
    expected: float
    expected_unit: str


class EvidenceLike:
    def __init__(self, data: dict[str, Any]):
        self.type = data.get("type", "table")
        self.content = data.get("content", {})


def build_cases() -> list[Case]:
    return [
        Case("Q1", "What was Apple's total net sales in FY2023 (in millions of dollars)?", 383285.0, "amount"),
        Case("Q2", "What was Apple's total cost of sales in FY2023 (in millions of dollars)?", 214137.0, "amount"),
        Case("Q3", "What was Apple's gross margin in FY2023 (in millions of dollars)?", 169148.0, "amount"),
        Case("Q4", "What were Apple's total operating expenses in FY2023 (in millions of dollars)?", 54847.0, "amount"),
        Case("Q5", "What was Apple's operating income in FY2023 (in millions of dollars)?", 114301.0, "amount"),
        Case("Q6", "What was Apple's provision for income taxes in FY2023 (in millions of dollars)?", 16741.0, "amount"),
        Case("Q7", "What was Apple's net income in FY2023 (in millions of dollars)?", 96995.0, "amount"),
        Case("Q8", "What were Apple's net sales from services in FY2023 (in millions of dollars)?", 85200.0, "amount"),
        Case("Q9", "What were Apple's net sales from products in FY2023 (in millions of dollars)?", 298085.0, "amount"),
        Case("Q10", "What was Apple's gross margin percentage in FY2023?", 44.1309, "percent"),
        Case("Q11", "What was Apple's operating income margin in FY2023 as a percentage of total net sales?", 29.8198, "percent"),
        Case("Q12", "What was Apple's cost of sales as a percentage of total net sales in FY2023?", 55.8691, "percent"),
        Case("Q13", "What was Apple's operating expenses ratio in FY2023 as a percentage of total net sales?", 14.3096, "percent"),
        Case("Q14", "What was the year-over-year percentage change in Apple's total net sales from FY2022 to FY2023?", -2.8006, "percent"),
        Case("Q15", "What was the year-over-year percentage change in Apple's operating income from FY2022 to FY2023?", -4.2992, "percent"),
        Case("Q16", "What was the year-over-year percentage change in Apple's net income from FY2022 to FY2023?", -2.8134, "percent"),
        Case("Q17", "By how much did Apple's gross margin change from FY2022 to FY2023 (in millions of dollars)?", -1634.0, "amount"),
        Case("Q18", "By how much did Apple's total operating expenses change from FY2022 to FY2023 (in millions of dollars)?", 3502.0, "amount"),
        Case("Q19", "What was Apple's income before provision for income taxes in FY2023 (in millions of dollars)?", 113736.0, "amount"),
        Case("Q20", "What was Apple's other income expense net in FY2023 (in millions of dollars)?", -565.0, "amount"),
    ]


def parse_numbers(text: str) -> list[float]:
    if not text:
        return []
    matches = re.findall(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", text)
    nums: list[float] = []
    for m in matches:
        try:
            nums.append(float(m.replace(",", "")))
        except ValueError:
            continue
    return nums


def relative_error(pred: float, truth: float) -> float:
    if truth == 0:
        return abs(pred - truth)
    return abs(pred - truth) / abs(truth)


def pick_best_value(answer: str, expected: float) -> tuple[float | None, float | None]:
    nums = parse_numbers(answer)
    if not nums:
        return None, None
    best = min(nums, key=lambda n: relative_error(n, expected))
    return best, relative_error(best, expected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Apple FY2023 20-case LLM evaluation")
    parser.add_argument("--output", default="evaluation/apple_llm_eval_20_results.json")
    parser.add_argument("--decision_mode", default="rules", choices=["rules", "ml"])
    parser.add_argument("--tolerance", type=float, default=0.01)
    args = parser.parse_args()

    if not get_openai_api_key():
        raise RuntimeError("OPENAI_API_KEY not found. Set backend/.env or environment before running.")

    csv_path = ROOT / "data" / "tatqa" / "real_pnl" / "apple_2023_income_statement.csv"
    table = parse_csv_pnl(csv_path)
    evidence_obj = EvidenceLike({"type": "table", "content": table})

    cases = build_cases()
    per_case: list[dict[str, Any]] = []

    for case in cases:
        t0 = time.time()
        answer, llm_used, llm_fallback = generate_llm_answer(case.question, table)
        llm_latency_ms = (time.time() - t0) * 1000

        t1 = time.time()
        result = route_and_verify(
            question=case.question,
            evidence=evidence_obj,
            candidate_answer=answer,
            options={
                "tolerance": args.tolerance,
                "log_run": False,
                "enable_repair": True,
                "decision_mode": args.decision_mode,
            },
            llm_used=llm_used,
            llm_fallback_reason=llm_fallback,
            generated_answer=answer,
        )
        verify_latency_ms = (time.time() - t1) * 1000

        extracted, err = pick_best_value(answer, case.expected)
        llm_correct = (err is not None) and (err <= args.tolerance)

        per_case.append(
            {
                "id": case.id,
                "question": case.question,
                "expected_value": case.expected,
                "expected_unit": case.expected_unit,
                "llm_answer": answer,
                "llm_used": llm_used,
                "llm_fallback_reason": llm_fallback,
                "llm_extracted_value_best": extracted,
                "llm_relative_error": err,
                "llm_correct_within_tolerance": llm_correct,
                "verifier_decision": result.get("decision"),
                "verifier_rationale": result.get("rationale"),
                "signals": result.get("signals", {}),
                "latency_llm_ms": round(llm_latency_ms, 2),
                "latency_verify_ms": round(verify_latency_ms, 2),
            }
        )

    total = len(per_case)
    llm_correct_count = sum(1 for r in per_case if r["llm_correct_within_tolerance"])
    accept_count = sum(1 for r in per_case if r["verifier_decision"] == "ACCEPT")
    flag_count = sum(1 for r in per_case if r["verifier_decision"] == "FLAG")
    repair_count = sum(1 for r in per_case if r["verifier_decision"] == "REPAIR")

    verifier_correct = 0
    for row in per_case:
        if row["llm_correct_within_tolerance"] and row["verifier_decision"] == "ACCEPT":
            verifier_correct += 1
        if (not row["llm_correct_within_tolerance"]) and row["verifier_decision"] in {"FLAG", "REPAIR"}:
            verifier_correct += 1

    out = {
        "dataset": "Apple FY2023 Consolidated Statements of Operations",
        "source_csv": str(csv_path),
        "total_cases": total,
        "tolerance": args.tolerance,
        "decision_mode": args.decision_mode,
        "summary": {
            "llm_correct": llm_correct_count,
            "llm_accuracy": round(llm_correct_count / total, 4),
            "verifier_accept": accept_count,
            "verifier_flag": flag_count,
            "verifier_repair": repair_count,
            "verifier_behavior_correct": verifier_correct,
            "verifier_behavior_accuracy": round(verifier_correct / total, 4),
            "avg_llm_latency_ms": round(statistics.mean(r["latency_llm_ms"] for r in per_case), 2),
            "avg_verify_latency_ms": round(statistics.mean(r["latency_verify_ms"] for r in per_case), 2),
        },
        "results": per_case,
    }

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote {out_path}")
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
