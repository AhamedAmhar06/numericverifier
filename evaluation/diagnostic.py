"""
Comprehensive evaluation diagnostic for NumericVerifier.

Step 1 — 84-case synthetic evaluation in rules_full mode.
Step 2 — Apple FY2023 real-world test cases via route_and_verify.
Step 3 — Failure summary table.
Step 4 — Save Apple results to evaluation/apple_real_world_test.json.
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.verifier.router import route_and_verify

SIGNAL_KEYS = [
    "unsupported_claims_count",
    "coverage_ratio",
    "recomputation_fail_count",
    "max_relative_error",
    "mean_relative_error",
    "scale_mismatch_count",
    "period_mismatch_count",
    "ambiguity_count",
    "pnl_table_detected",
    "pnl_identity_fail_count",
    "pnl_margin_fail_count",
    "pnl_missing_baseline_count",
    "pnl_period_strict_mismatch_count",
]

COVERAGE_THRESHOLD = 0.7   # from default settings
OPTIONS = {"tolerance": 0.01, "log_run": False, "decision_mode": "rules"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _EvidenceLike:
    def __init__(self, d):
        self.type = d.get("type", "table")
        self.content = d.get("content", {})


def run_case(case: dict) -> dict:
    t0 = time.time()
    try:
        result = route_and_verify(
            question=case["question"],
            evidence=_EvidenceLike(case["evidence"]),
            candidate_answer=case["candidate_answer"],
            options=dict(OPTIONS),
        )
        return {
            "id": case.get("id", "?"),
            "expected": case["expected_decision"],
            "actual": result.get("decision", "ERROR"),
            "candidate_answer": case["candidate_answer"],
            "signals": result.get("signals", {}),
            "rationale": result.get("rationale", ""),
            "correct": result.get("decision") == case["expected_decision"],
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "error": None,
        }
    except Exception as exc:
        return {
            "id": case.get("id", "?"),
            "expected": case["expected_decision"],
            "actual": "ERROR",
            "candidate_answer": case.get("candidate_answer", ""),
            "signals": {},
            "rationale": "",
            "correct": False,
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "error": str(exc),
        }


def fmt_signals(sig: dict) -> str:
    lines = []
    for k in SIGNAL_KEYS:
        v = sig.get(k, "N/A")
        if isinstance(v, float):
            v = f"{v:.4f}"
        lines.append(f"    {k:<38} {v}")
    return "\n".join(lines)


def classify_failure(r: dict) -> tuple[str, str]:
    """Return (failure_type_code, sub_type_detail)."""
    exp, act = r["expected"], r["actual"]
    sig = r["signals"]
    cov = sig.get("coverage_ratio", 0.0)
    scale_mm = sig.get("scale_mismatch_count", 0)
    period_mm = sig.get("period_mismatch_count", 0)
    violations = (sig.get("pnl_identity_fail_count", 0)
                  + sig.get("pnl_margin_fail_count", 0)
                  + sig.get("pnl_period_strict_mismatch_count", 0))
    unsupported = sig.get("unsupported_claims_count", 0)

    # A: False ACCEPT — accepted something bad
    if act == "ACCEPT" and exp in ("FLAG", "REPAIR"):
        if cov >= COVERAGE_THRESHOLD:
            sub = "A1-coverage-ok-despite-errors"
        elif violations == 0 and scale_mm == 0 and period_mm == 0:
            sub = "A2-constraint-violations-missed"
        else:
            sub = "A3-other"
        return "A-FALSE_ACCEPT", sub

    # B: False FLAG — flagged something correct
    if act == "FLAG" and exp == "ACCEPT":
        if cov < COVERAGE_THRESHOLD:
            sub = "B1-low-coverage-grounding-failure"
        elif violations > 0 or scale_mm > 0 or period_mm > 0:
            sub = "B2-spurious-constraint-violation"
        else:
            sub = "B3-other"
        return "B-FALSE_FLAG", sub

    # C: Wrong REPAIR
    if act == "REPAIR":
        if exp == "FLAG":
            sub = "C1-repaired-should-have-flagged"
        elif exp == "ACCEPT":
            sub = "C2-repaired-should-have-accepted"
        else:
            sub = "C3-other"
        return "C-WRONG_REPAIR", sub

    if exp == "REPAIR":
        if act == "FLAG":
            sub = "C4-flagged-should-have-repaired"
        elif act == "ACCEPT":
            sub = "C5-accepted-should-have-repaired"
        else:
            sub = "C3-other"
        return "C-WRONG_REPAIR", sub

    return "UNKNOWN", "unknown"


# ---------------------------------------------------------------------------
# Step 1: 84-case synthetic evaluation
# ---------------------------------------------------------------------------
def step1_synthetic(cases_path: Path) -> list:
    with open(cases_path) as f:
        cases = json.load(f)

    print("=" * 72)
    print(f"STEP 1 — 84-CASE SYNTHETIC EVALUATION  (rules_full mode)")
    print(f"  Dataset: {cases_path}")
    print(f"  Cases  : {len(cases)}")
    print("=" * 72)

    results = []
    mismatches = []
    for i, case in enumerate(cases):
        r = run_case(case)
        results.append(r)
        status = "OK " if r["correct"] else "ERR"
        print(f"  [{i+1:02d}/{len(cases)}] {r['id']:12s}  {status}  "
              f"exp={r['expected']:<6} act={r['actual']:<6}  ({r['latency_ms']:.0f}ms)")
        if not r["correct"]:
            mismatches.append(r)

    correct = sum(1 for r in results if r["correct"])
    print(f"\n  Accuracy: {correct}/{len(cases)} = {correct/len(cases):.1%}")
    print(f"  Mismatches: {len(mismatches)}")

    # Detailed mismatch report
    if mismatches:
        print()
        print("─" * 72)
        print("MISMATCH DETAILS")
        print("─" * 72)
        for r in mismatches:
            ftype, fsub = classify_failure(r)
            ans_trunc = r["candidate_answer"][:80].replace("\n", " ")
            if len(r["candidate_answer"]) > 80:
                ans_trunc += "…"

            print(f"\n  case_id          : {r['id']}")
            print(f"  expected_decision: {r['expected']}")
            print(f"  actual_decision  : {r['actual']}")
            print(f"  candidate_answer : {ans_trunc}")
            print(f"  failure_type     : {ftype}")
            print(f"  failure_sub_type : {fsub}")
            print(f"  rationale        : {r['rationale']}")
            print("  signals:")
            print(fmt_signals(r["signals"]))
            if r["error"]:
                print(f"  ERROR: {r['error']}")

    return results, mismatches


# ---------------------------------------------------------------------------
# Step 2: Apple FY2023 real-world test cases
# ---------------------------------------------------------------------------

# Table values provided by user (in millions, used as raw integers here so
# that "$169,148 million" → 169,148,000,000 matches the scaled evidence).
# We store actual dollar amounts to make the parser match correctly.
APPLE_EVIDENCE = {
    "type": "table",
    "content": {
        "caption": "Apple Inc. Consolidated Statements of Operations (in millions)",
        "columns": ["Line Item", "FY2023", "FY2022"],
        "rows": [
            ["Total net sales",               "383285000000", "394328000000"],
            ["Cost of sales",                 "214137000000", "223546000000"],
            ["Gross margin",                  "169148000000", "170782000000"],
            ["Operating expenses",            "54847000000",  "51345000000"],
            ["Operating income",              "114301000000", "119437000000"],
            ["Provision for income taxes",    "29749000000",  "19300000000"],
            ["Net income",                    "96995000000",  "99803000000"],
        ],
        "units": {},
    },
}

APPLE_CASES = [
    {
        "id": "apple_tc1",
        "description": "Correct value, correct period — should ACCEPT",
        "expected_decision": "ACCEPT",
        "question": "What was Apple's gross margin in FY2023?",
        "candidate_answer": "Apple's gross margin in FY2023 was $169,148 million.",
    },
    {
        "id": "apple_tc2",
        "description": "Wrong value ($112B instead of $97B) — should FLAG",
        "expected_decision": "FLAG",
        "question": "What was Apple's net income in FY2023?",
        "candidate_answer": "Apple's net income in FY2023 was $112,000 million.",
    },
    {
        "id": "apple_tc3",
        "description": "Scale mismatch ($383B ≈ $383.285B but different magnitude) — should FLAG",
        "expected_decision": "FLAG",
        "question": "What was Apple's revenue in FY2023?",
        "candidate_answer": "Apple's total net sales were $383 billion in FY2023.",
    },
    {
        "id": "apple_tc4",
        "description": "Wrong period (FY2023 value stated for FY2022 question) — should FLAG",
        "expected_decision": "FLAG",
        "question": "What was Apple's operating income in FY2022?",
        "candidate_answer": "Apple's operating income was $114,301 million.",
    },
]


def step2_apple() -> list:
    print()
    print("=" * 72)
    print("STEP 2 — APPLE FY2023 REAL-WORLD TEST CASES")
    print("=" * 72)

    apple_results = []
    for tc in APPLE_CASES:
        case = {
            "id": tc["id"],
            "question": tc["question"],
            "evidence": APPLE_EVIDENCE,
            "candidate_answer": tc["candidate_answer"],
            "expected_decision": tc["expected_decision"],
        }
        r = run_case(case)
        r["description"] = tc["description"]
        apple_results.append(r)

        match_str = "✓ MATCH" if r["correct"] else "✗ MISMATCH"
        print(f"\n  {tc['id']}  [{match_str}]")
        print(f"  Description : {tc['description']}")
        print(f"  Question    : {tc['question']}")
        print(f"  Answer      : {tc['candidate_answer']}")
        print(f"  Expected    : {tc['expected_decision']}")
        print(f"  Received    : {r['actual']}")
        print(f"  Rationale   : {r['rationale']}")
        print("  Signals:")
        print(fmt_signals(r["signals"]))

    return apple_results


# ---------------------------------------------------------------------------
# Step 3: Failure summary table
# ---------------------------------------------------------------------------
def step3_summary(results: list, mismatches: list):
    print()
    print("=" * 72)
    print("STEP 3 — FAILURE SUMMARY TABLE")
    print("=" * 72)

    # Overall accuracy
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    print(f"\n  Overall accuracy : {correct}/{total} = {correct/total:.1%}")
    print(f"  Total errors     : {len(mismatches)}")

    if not mismatches:
        print("  No failures — system is perfect on this dataset.")
        return

    # Classify all mismatches
    type_counts = defaultdict(int)
    sub_counts = defaultdict(int)
    type_sigs = defaultdict(list)

    for r in mismatches:
        ftype, fsub = classify_failure(r)
        type_counts[ftype] += 1
        sub_counts[fsub] += 1
        sig = r["signals"]
        type_sigs[ftype].append(
            f"cov={sig.get('coverage_ratio', 0):.2f} "
            f"unsup={sig.get('unsupported_claims_count', 0)} "
            f"scale={sig.get('scale_mismatch_count', 0)} "
            f"period={sig.get('period_mismatch_count', 0)} "
            f"pnl_id={sig.get('pnl_identity_fail_count', 0)} "
            f"pnl_strict={sig.get('pnl_period_strict_mismatch_count', 0)}"
        )

    n_err = len(mismatches)
    print()
    print(f"  {'Failure type':<25} {'Count':>5}  {'% of errors':>11}  Main signal pattern")
    print(f"  {'-'*25} {'-'*5}  {'-'*11}  {'-'*35}")
    for ftype in sorted(type_counts.keys()):
        cnt = type_counts[ftype]
        pct = cnt / n_err * 100
        # modal signal pattern
        sig_patterns = type_sigs[ftype]
        print(f"  {ftype:<25} {cnt:>5}  {pct:>10.1f}%  {sig_patterns[0] if sig_patterns else 'N/A'}")

    print()
    print("  Sub-type breakdown:")
    for sub in sorted(sub_counts.keys()):
        cnt = sub_counts[sub]
        pct = cnt / n_err * 100
        print(f"    {sub:<45} {cnt:>3}  ({pct:.1f}%)")

    # Confusion matrix
    labels = ["ACCEPT", "REPAIR", "FLAG"]
    matrix = defaultdict(lambda: defaultdict(int))
    for r in results:
        matrix[r["expected"]][r["actual"]] += 1

    print()
    print("  Confusion matrix (expected \\ actual):")
    header = f"  {'':12}" + "".join(f"  {a:<8}" for a in labels)
    print(header)
    for exp in labels:
        row_str = f"  {exp:<12}"
        for act in labels:
            v = matrix[exp][act]
            marker = " *" if exp != act and v > 0 else "  "
            row_str += f"  {v:<6}{marker}"
        print(row_str)


# ---------------------------------------------------------------------------
# Step 4: Save Apple results
# ---------------------------------------------------------------------------
def step4_save(apple_results: list, out_path: Path):
    print()
    print("=" * 72)
    print("STEP 4 — SAVING APPLE TEST CASES")
    print("=" * 72)

    # Serialize signals as plain dicts (already dicts from route_and_verify)
    output = {
        "dataset": "apple_fy2023_real_world",
        "description": (
            "Real-world Apple Inc. FY2023 income-statement test cases. "
            "Values sourced from Apple 10-K (FY2023). "
            "Used to validate the NumericVerifier P&L pipeline."
        ),
        "evidence": {
            "source": "Apple Inc. Consolidated Statements of Operations (10-K FY2023)",
            "columns": ["Line Item", "FY2023 (USD)", "FY2022 (USD)"],
            "values_unit": "dollars (absolute)",
            "original_unit": "millions",
            "line_items": {
                "total_net_sales":           {"FY2023": 383285000000, "FY2022": 394328000000},
                "cost_of_sales":             {"FY2023": 214137000000, "FY2022": 223546000000},
                "gross_margin":              {"FY2023": 169148000000, "FY2022": 170782000000},
                "operating_expenses":        {"FY2023":  54847000000, "FY2022":  51345000000},
                "operating_income":          {"FY2023": 114301000000, "FY2022": 119437000000},
                "provision_for_income_taxes":{"FY2023":  29749000000, "FY2022":  19300000000},
                "net_income":                {"FY2023":  96995000000, "FY2022":  99803000000},
            },
        },
        "test_cases": [],
    }

    for r in apple_results:
        tc_data = {
            "id": r["id"],
            "description": r.get("description", ""),
            "question": next(
                (tc["question"] for tc in APPLE_CASES if tc["id"] == r["id"]), ""
            ),
            "candidate_answer": r["candidate_answer"],
            "expected_decision": r["expected"],
            "actual_decision": r["actual"],
            "correct": r["correct"],
            "rationale": r["rationale"],
            "latency_ms": r["latency_ms"],
            "signals": r["signals"],
        }
        output["test_cases"].append(tc_data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Saved to: {out_path}")
    print(f"  Cases   : {len(output['test_cases'])}")
    tc_match = sum(1 for tc in output["test_cases"] if tc["correct"])
    print(f"  Match   : {tc_match}/{len(output['test_cases'])} expected decisions")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cases_path = ROOT / "evaluation" / "cases_v2.json"
    out_path   = ROOT / "evaluation" / "apple_real_world_test.json"

    # Step 1
    results, mismatches = step1_synthetic(cases_path)

    # Step 2
    apple_results = step2_apple()

    # Step 3
    all_results = results + apple_results
    all_mismatches = [r for r in all_results if not r["correct"]]
    # Print summary for synthetic only (cleaner for dissertation)
    step3_summary(results, mismatches)

    # Step 4
    step4_save(apple_results, out_path)

    print()
    print("=" * 72)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 72)
