#!/usr/bin/env python3
"""
Execute evaluation test cases against NumericVerifier API.
Makes real HTTP requests; records actual decision, signals, rationale.
No fabricated outputs.

P&L-only refactor: runs P&L eval cases from examples/pnl_eval_cases.json by default.
Use --legacy to run legacy TEST_CASES instead; use --all to run both.
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8877"

# Path to P&L evaluation cases (authoritative for P&L-only refactor)
PNL_EVAL_PATH = os.path.join(os.path.dirname(__file__), "examples", "pnl_eval_cases.json")

def post(endpoint: str, data: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return {"_error": f"HTTP {e.code}", "_body": json.loads(body) if body else body}
        except json.JSONDecodeError:
            return {"_error": f"HTTP {e.code}", "_body": body}
    except Exception as e:
        return {"_error": str(e)}


# 15 test cases: question, evidence (table), endpoint, candidate_answer (if verify-only), expected_human_decision
TEST_CASES = [
    {
        "case_id": "E001",
        "scenario_type": "Correct numeric answer (lookup)",
        "question": "What was the revenue for Q1 2024?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1 2024", "5000000"], ["Q2 2024", "5500000"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "The revenue for Q1 2024 was $5,000,000.",
        "expected_human_decision": "ACCEPT",
    },
    {
        "case_id": "E002",
        "scenario_type": "Correct arithmetic (percent increase)",
        "question": "What is the percent change in revenue from Q1 to Q2?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Period", "Revenue"],
                "rows": [["Q1", "10"], ["Q2", "15"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "The percent change in revenue is 50%.",
        "expected_human_decision": "ACCEPT",
    },
    {
        "case_id": "E003",
        "scenario_type": "Correct total computation",
        "question": "What is the total revenue for Q1 and Q2?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1", "3"], ["Q2", "7"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Total revenue is 10.",
        "expected_human_decision": "ACCEPT",
    },
    {
        "case_id": "E004",
        "scenario_type": "Incorrect arithmetic (wrong percent)",
        "question": "What is the percent change in revenue from Q1 to Q2?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Period", "Revenue"],
                "rows": [["Q1", "10"], ["Q2", "15"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "The percent change in revenue is 20%.",
        "expected_human_decision": "REPAIR",
    },
    {
        "case_id": "E005",
        "scenario_type": "Incorrect total",
        "question": "What is the total revenue for Q1 and Q2?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1", "100"], ["Q2", "200"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Total revenue is 350.",
        "expected_human_decision": "REPAIR",
    },
    {
        "case_id": "E006",
        "scenario_type": "Fabricated number",
        "question": "What was the revenue for Q1 2024?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1 2024", "5000000"], ["Q2 2024", "5500000"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "The revenue for Q1 2024 was $7,000,000.",
        "expected_human_decision": "FLAG",
    },
    {
        "case_id": "E007",
        "scenario_type": "Period mismatch",
        "question": "What was the value for the period?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Period", "Value"],
                "rows": [["Q1 2024", "2023"], ["Q2 2024", "2024"]],
                "units": {},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "The value for 2023 was 2023.",
        "expected_human_decision": "FLAG",
    },
    {
        "case_id": "E008",
        "scenario_type": "Missing baseline data",
        "question": "What was the year-over-year growth?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1 2024", "100"], ["Q2 2024", "150"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Year-over-year growth was 50%.",
        "expected_human_decision": "REPAIR",
    },
    {
        "case_id": "E009",
        "scenario_type": "Vague / non-numeric answer",
        "question": "What is the percent change in revenue from Q1 to Q2?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Period", "Revenue"],
                "rows": [["Q1", "10"], ["Q2", "15"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Revenue increased significantly over the period.",
        "expected_human_decision": "FLAG",
    },
    {
        "case_id": "E010",
        "scenario_type": "Mixed correct and incorrect claims",
        "question": "What were Q1 and Q2 revenues and the growth rate?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1 2024", "10"], ["Q2 2024", "15"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Q1 revenue was 10, Q2 revenue was 15, and growth was 30%.",
        "expected_human_decision": "REPAIR",
    },
    {
        "case_id": "E011",
        "scenario_type": "Number not present in table",
        "question": "What was profit in Q2?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1 2024", "5000000"], ["Q2 2024", "5500000"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Profit in Q2 was 1,000,000.",
        "expected_human_decision": "FLAG",
    },
    {
        "case_id": "E012",
        "scenario_type": "Rounding / tolerance edge",
        "question": "What was the revenue for Q1?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1 2024", "5000000.00"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Revenue for Q1 was $5,000,000.",
        "expected_human_decision": "ACCEPT",
    },
    {
        "case_id": "E013",
        "scenario_type": "LLM-generated answer (verify endpoint)",
        "question": "What is the percent change in revenue from Q1 to Q2?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Period", "Revenue"],
                "rows": [["Q1", "10"], ["Q2", "15"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify",
        "candidate_answer": None,
        "expected_human_decision": "ACCEPT",
    },
    {
        "case_id": "E014",
        "scenario_type": "Hedged answer (approximately)",
        "question": "What was the total revenue for Q1?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [["Q1 2024", "5000000"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Approximately $5,000,000.",
        "expected_human_decision": "ACCEPT",
    },
    {
        "case_id": "E015",
        "scenario_type": "Question asks for percent but answer has no percent",
        "question": "What is the percentage increase in revenue?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Period", "Revenue"],
                "rows": [["Q1", "10"], ["Q2", "15"]],
                "units": {"Revenue": "dollars"},
            },
        },
        "endpoint": "/verify-only",
        "candidate_answer": "Revenue went from 10 to 15.",
        "expected_human_decision": "FLAG",
    },
]


def signals_summary(signals: dict) -> str:
    if not signals or not isinstance(signals, dict):
        return ""
    parts = []
    if signals.get("recomputation_fail_count", 0) > 0:
        parts.append("recomp_fail>0")
    if signals.get("period_mismatch_count", 0) > 0:
        parts.append("period_mismatch>0")
    if signals.get("unsupported_claims_count", 0) > 0:
        parts.append("unsupported>0")
    if signals.get("pnl_identity_fail_count", 0) > 0:
        parts.append("pnl_identity_fail>0")
    if signals.get("pnl_margin_fail_count", 0) > 0:
        parts.append("pnl_margin_fail>0")
    if signals.get("pnl_missing_baseline_count", 0) > 0:
        parts.append("pnl_missing_baseline>0")
    if signals.get("pnl_period_strict_mismatch_count", 0) > 0:
        parts.append("pnl_period_strict_mismatch>0")
    if signals.get("coverage_ratio") is not None:
        parts.append(f"coverage={signals['coverage_ratio']:.2f}")
    return "; ".join(parts) if parts else "none notable"


def load_pnl_eval_cases() -> list:
    """Load P&L evaluation cases from examples/pnl_eval_cases.json."""
    if not os.path.isfile(PNL_EVAL_PATH):
        return []
    with open(PNL_EVAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    run_legacy = "--legacy" in args
    run_all = "--all" in args

    if run_all:
        test_cases = load_pnl_eval_cases() + TEST_CASES
    elif run_legacy:
        test_cases = TEST_CASES
    else:
        pnl_cases = load_pnl_eval_cases()
        test_cases = pnl_cases if pnl_cases else TEST_CASES

    results = []
    for tc in test_cases:
        if tc["endpoint"] == "/verify-only":
            payload = {
                "question": tc["question"],
                "evidence": tc["evidence"],
                "candidate_answer": tc["candidate_answer"],
                "options": {"log_run": False},
            }
        else:
            payload = {
                "question": tc["question"],
                "evidence": tc["evidence"],
                "options": {"log_run": False},
            }
        resp = post(tc["endpoint"], payload)
        decision = resp.get("decision") or resp.get("_error", "ERROR")
        sig = resp.get("signals", {})
        rationale = resp.get("rationale", "")
        if resp.get("_error"):
            decision = resp.get("_error", "ERROR")
            sig = {}
            rationale = resp.get("_body", rationale)
        key_signals = signals_summary(sig)
        expected = tc["expected_human_decision"]
        if decision == expected:
            correctness = "Correct"
        elif decision in ("ACCEPT",) and expected in ("REPAIR", "FLAG"):
            correctness = "Over-permissive"
        elif decision in ("REPAIR", "FLAG") and expected == "ACCEPT":
            correctness = "Over-conservative"
        else:
            correctness = "Correct" if decision == expected else "Over-conservative" if decision in ("REPAIR", "FLAG") else "Over-permissive"
        results.append({
            "case_id": tc["case_id"],
            "scenario_type": tc["scenario_type"],
            "question": tc["question"],
            "evidence_table": json.dumps(tc["evidence"]["content"], separators=(',', ':')),
            "endpoint_used": tc["endpoint"],
            "expected_human_decision": expected,
            "actual_decision": decision,
            "key_actual_signals": key_signals,
            "correctness_label": correctness,
            "notes": rationale[:200] if rationale else "",
        })
    # Print CSV for Excel/Sheets
    cols = ["Case_ID", "Scenario_Type", "Question", "Evidence_Table", "Endpoint_Used", "Expected_Human_Decision", "Actual_System_Decision", "Key_Actual_Signals", "Correctness_Label", "Notes"]
    print("\t".join(cols))
    for r in results:
        row = [
            r["case_id"],
            r["scenario_type"].replace("\t", " ").replace("\n", " "),
            r["question"].replace("\t", " ").replace("\n", " "),
            r["evidence_table"].replace("\t", " "),
            r["endpoint_used"],
            r["expected_human_decision"],
            r["actual_decision"],
            r["key_actual_signals"].replace("\t", " "),
            r["correctness_label"],
            r["notes"].replace("\t", " ").replace("\n", " ")[:300],
        ]
        print("\t".join(row))
    # Summary
    n = len(results)
    correct = sum(1 for r in results if r["correctness_label"] == "Correct")
    over_perm = sum(1 for r in results if r["correctness_label"] == "Over-permissive")
    over_cons = sum(1 for r in results if r["correctness_label"] == "Over-conservative")
    print("\n--- SUMMARY STATISTICS ---")
    print(f"Total test cases: {n}")
    print(f"% Correct decisions: {100*correct/n:.1f}%" if n else "N/A")
    print(f"% Over-permissive: {100*over_perm/n:.1f}%" if n else "N/A")
    print(f"% Over-conservative: {100*over_cons/n:.1f}%" if n else "N/A")
    fail_signals = []
    for r in results:
        if r["key_actual_signals"]:
            fail_signals.append(r["key_actual_signals"])
    from collections import Counter
    c = Counter(fail_signals)
    if c:
        print(f"Most common failure signals: {c.most_common(3)}")


if __name__ == "__main__":
    main()
    # Usage: python run_evaluation_api.py          # P&L cases (from examples/pnl_eval_cases.json)
    #        python run_evaluation_api.py --legacy  # Legacy TEST_CASES
    #        python run_evaluation_api.py --all     # P&L + legacy
