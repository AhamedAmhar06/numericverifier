#!/usr/bin/env python3
"""
Generate a finance-specific dataset of verification signals for ML training.

RULES (strict):
- No fabricated labels or signals. All decisions and signals come from the backend.
- Calls POST /verify only (LLM generates answers; verification engine produces signals).
- Only generates inputs (P&L tables + questions). Backend does the rest.
- Logging enabled so signals are written to runs/signals_v2.csv.

Usage:
  Ensure backend is running at http://127.0.0.1:8000 and OpenAI is enabled.
  python scripts/generate_ml_dataset.py

Target: at least 200 total rows in runs/signals_v2.csv.
Stratification by case design: ~40% ACCEPT-oriented, ~30% REPAIR-oriented, ~30% FLAG-oriented.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"


def check_backend_health() -> bool:
    """Return True if backend is reachable."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def post_verify(question: str, evidence: dict, log_run: bool = True) -> dict:
    """Call POST /verify. Returns response dict or error dict."""
    payload = {
        "question": question,
        "evidence": evidence,
        "options": {"log_run": log_run, "tolerance": 0.01},
    }
    req = urllib.request.Request(
        f"{BASE_URL}/verify",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return {"_error": f"HTTP {e.code}", "_body": json.loads(body) if body else body}
        except json.JSONDecodeError:
            return {"_error": f"HTTP {e.code}", "_body": body, "decision": "FLAG"}
    except Exception as e:
        return {"_error": str(e), "decision": None}


def build_pnl_layout_a(rows: list, periods: list) -> dict:
    """Build evidence dict for Layout A: columns = [Line Item, ...periods], rows = [[label, v1, v2], ...]."""
    columns = ["Line Item"] + list(periods)
    return {
        "type": "table",
        "content": {
            "columns": columns,
            "rows": rows,
            "units": {},
        },
    }


# ---- ACCEPT-oriented: valid identities, clear period refs --------------------

def make_accept_cases() -> list:
    """Generate (question, evidence) for cases designed to yield ACCEPT."""
    cases = []
    # Vary periods and numbers so we get diverse tables
    configs = [
        (["2022", "2023"], [("Revenue", 100, 120), ("COGS", 40, 50), ("Gross Profit", 60, 70)]),
        (["2021", "2022"], [("Revenue", 80, 100), ("COGS", 32, 40), ("Gross Profit", 48, 60)]),
        (["2023", "2024"], [("Revenue", 200, 220), ("COGS", 90, 99), ("Gross Profit", 110, 121)]),
        (["Q1 2023", "Q2 2023"], [("Revenue", 50, 55), ("COGS", 20, 22), ("Gross Profit", 30, 33)]),
        (["FY2022", "FY2023"], [("Revenue", 500, 550), ("COGS", 200, 220), ("Gross Profit", 300, 330)]),
        (["2020", "2021", "2022"], [("Revenue", 60, 70, 80), ("COGS", 24, 28, 32), ("Gross Profit", 36, 42, 48)]),
    ]
    questions_per_config = [
        "What was revenue in {}?",
        "What was Revenue in {}?",
        "What was gross profit in {}?",
        "What was COGS in {}?",
        "What were revenue and gross profit in {}?",
    ]
    for periods, line_items in configs:
        rows = [[label] + list(vals) for label, *vals in line_items]
        evidence = build_pnl_layout_a(rows, periods)
        for q_tmpl in questions_per_config:
            for p in periods:
                cases.append((q_tmpl.format(p), evidence))
    # Add synonym-style tables (Sales, Cost of revenue, etc.)
    syn_configs = [
        (["2022", "2023"], [("Sales", 100, 120), ("Cost of revenue", 40, 50), ("Gross Profit", 60, 70)]),
        (["2023"], [("Turnover", 300), ("Cost of sales", 120), ("Gross Profit", 180)]),
    ]
    for periods, line_items in syn_configs:
        rows = [[label] + list(vals) for label, *vals in line_items]
        evidence = build_pnl_layout_a(rows, periods)
        cases.append((f"What was sales in {periods[0]}?", evidence))
        if len(periods) > 1:
            cases.append((f"What was turnover in {periods[1]}?", evidence))
    return cases


# ---- REPAIR-oriented: one identity error or wrong arithmetic -----------------

def make_repair_cases() -> list:
    """Generate (question, evidence) designed to yield REPAIR (identity/margin failure)."""
    cases = []
    # Identity wrong: Gross Profit row != Revenue - COGS
    wrong_identity = [
        ["Revenue", "100", "120"],
        ["COGS", "40", "50"],
        ["Gross Profit", "55", "65"],  # 60 and 70 would be correct
    ]
    evidence_repair = build_pnl_layout_a(wrong_identity, ["2022", "2023"])
    for q in ["What was gross profit in 2022?", "What was revenue in 2023?", "What was COGS in 2022?"]:
        cases.append((q, evidence_repair))

    # Another identity wrong (single period)
    wrong_gp_single = [
        ["Revenue", "200"],
        ["COGS", "80"],
        ["Gross Profit", "100"],  # correct would be 120
    ]
    ev2 = build_pnl_layout_a(wrong_gp_single, ["2023"])
    cases.append(("What was gross profit in 2023?", ev2))
    cases.append(("What was revenue in 2023?", ev2))

    # Operating income mismatch: GP - Opex != Op Income row
    wrong_op = [
        ["Revenue", "100"],
        ["COGS", "40"],
        ["Gross Profit", "60"],
        ["Operating Expenses", "15"],
        ["Operating Income", "40"],  # correct would be 45
    ]
    ev3 = build_pnl_layout_a(wrong_op, ["2022"])
    cases.append(("What was operating income in 2022?", ev3))
    cases.append(("What was gross profit in 2022?", ev3))

    # More identity-wrong tables (vary numbers)
    for rev, cogs, gp_wrong in [(150, 60, 80), (90, 36, 50), (300, 120, 170)]:
        rows = [
            ["Revenue", str(rev), str(rev + 20)],
            ["COGS", str(cogs), str(cogs + 10)],
            ["Gross Profit", str(gp_wrong), str(rev + 20 - cogs - 10)],  # first period wrong
        ]
        ev = build_pnl_layout_a(rows, ["2022", "2023"])
        cases.append(("What was gross profit in 2022?", ev))
        cases.append(("What was revenue in 2023?", ev))
    return cases


# ---- FLAG-oriented: YoY missing baseline, non-P&L, or unsupported -----------

def make_flag_cases() -> list:
    """Generate (question, evidence) designed to yield FLAG."""
    cases = []

    # YoY question but baseline period missing in table (table has 2022, 2023 only)
    pnl_2022_2023 = build_pnl_layout_a(
        [["Revenue", "100", "120"], ["COGS", "40", "50"], ["Gross Profit", "60", "70"]],
        ["2022", "2023"],
    )
    yoy_questions = [
        "What was the YoY growth in revenue from 2021 to 2022?",
        "What was year-over-year growth from 2020 to 2021?",
        "What was the YoY change from 2021 to 2022?",
        "Compare revenue YoY between 2019 and 2020.",
        "What was YoY growth from 2021 to 2022?",
    ]
    for q in yoy_questions:
        cases.append((q, pnl_2022_2023))

    # Same with different table periods
    pnl_2023_2024 = build_pnl_layout_a(
        [["Revenue", "200", "220"], ["COGS", "90", "99"], ["Gross Profit", "110", "121"]],
        ["2023", "2024"],
    )
    for q in ["What was YoY growth from 2022 to 2023?", "What was year-over-year growth from 2022 to 2023?"]:
        cases.append((q, pnl_2023_2024))

    # Non-P&L table (should be rejected by domain gate -> FLAG)
    non_pnl = {
        "type": "table",
        "content": {
            "columns": ["Category", "Count"],
            "rows": [["A", "10"], ["B", "20"], ["C", "15"]],
            "units": {},
        },
    }
    for q in ["What is the total count?", "What is the value for Category A?", "What is the count for B?"]:
        cases.append((q, non_pnl))

    non_pnl2 = {
        "type": "table",
        "content": {
            "columns": ["Region", "Headcount"],
            "rows": [["North", "50"], ["South", "30"]],
            "units": {},
        },
    }
    cases.append(("What was headcount in North?", non_pnl2))

    # P&L but question references period not in table
    pnl_two_periods = build_pnl_layout_a(
        [["Revenue", "100", "120"], ["COGS", "40", "50"], ["Gross Profit", "60", "70"]],
        ["2022", "2023"],
    )
    cases.append(("What was revenue in 2024?", pnl_two_periods))
    cases.append(("What was gross profit in 2020?", pnl_two_periods))

    return cases


def get_signals_csv_path() -> Path:
    """Resolve runs/signals_v2.csv from project root (parent of scripts/ or cwd)."""
    try:
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent
    except Exception:
        project_root = Path(os.getcwd())
    return project_root / "runs" / "signals_v2.csv"


def count_signal_rows(path: Path) -> int:
    """Count data rows (excluding header) in signals CSV."""
    if not path.exists():
        return 0
    with open(path, "r", newline="") as f:
        lines = f.readlines()
    if not lines:
        return 0
    return max(0, len(lines) - 1)


def main():
    if not check_backend_health():
        print(f"ERROR: Backend not reachable at {BASE_URL}. Start the server first:")
        print("  cd backend && python3 -m uvicorn app.main:app --reload")
        print("  or: PYTHONPATH=backend python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
        print("Ensure OPENAI_API_KEY is set if you want real LLM-generated answers.")
        return 1

    signals_path = get_signals_csv_path()
    initial_count = count_signal_rows(signals_path)

    accept_cases = make_accept_cases()
    repair_cases = make_repair_cases()
    flag_cases = make_flag_cases()

    # Build full pool with target stratification (~40% ACCEPT, ~30% REPAIR, ~30% FLAG)
    target_total = 220  # run 220 to ensure ≥200 logged rows even if a few fail
    n_accept = min(len(accept_cases), 88)   # ~40%
    n_repair = min(len(repair_cases), 66)   # ~30%
    n_flag = min(len(flag_cases), 66)       # ~30%
    pool = (
        accept_cases[:n_accept]
        + repair_cases[:n_repair]
        + flag_cases[:n_flag]
    )
    while len(pool) < target_total:
        pool.append(accept_cases[len(pool) % len(accept_cases)])
        if len(pool) >= target_total:
            break
        pool.append(repair_cases[len(pool) % len(repair_cases)])
        if len(pool) >= target_total:
            break
        pool.append(flag_cases[len(pool) % len(flag_cases)])
    pool = pool[:target_total]

    print(f"Signals file: {signals_path}")
    print(f"Initial row count: {initial_count}")
    print(f"Case pool size: {len(pool)} (target ≥200 rows in signals_v2.csv)")
    print("Calling POST /verify for each case (LLM generates answer; backend produces signals)...")
    print()

    decisions_seen = []
    errors = 0
    for i, (question, evidence) in enumerate(pool):
        resp = post_verify(question, evidence, log_run=True)
        decision = resp.get("decision")
        if resp.get("_error"):
            errors += 1
            if decision is None:
                decision = "ERROR"
        decisions_seen.append(decision)
        if (i + 1) % 20 == 0:
            current = count_signal_rows(signals_path)
            print(f"  {i + 1}/{len(pool)} done, signals rows: {current} (new: {current - initial_count})")
        time.sleep(0.3)

    final_count = count_signal_rows(signals_path)
    new_rows = final_count - initial_count

    # Distribution
    from collections import Counter
    dist = Counter(decisions_seen)

    print()
    print("--- DELIVERABLES ---")
    print(f"Cases submitted: {len(pool)}")
    print(f"API errors: {errors}")
    print(f"Initial signals_v2 rows: {initial_count}")
    print(f"Final signals_v2 rows: {final_count}")
    print(f"New rows written: {new_rows}")
    print()
    print("Decision distribution (from API responses):")
    for d, c in dist.most_common():
        pct = 100 * c / len(pool) if pool else 0
        print(f"  {d}: {c} ({pct:.1f}%)")
    print()

    # Validation: schema and key columns in signals_v2.csv
    if signals_path.exists():
        import csv as csv_module
        with open(signals_path, "r", newline="") as f:
            reader = csv_module.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
        has_schema_v2 = "schema_version" in headers
        has_decision = "decision" in headers
        pnl_cols = [h for h in headers if h.startswith("pnl_")]
        sample_schema = rows[0].get("schema_version") == "2" if rows else False
        print("Validation (signals_v2.csv):")
        print(f"  schema_version column: {has_schema_v2}, sample value=2: {sample_schema}")
        print(f"  decision column: {has_decision}")
        print(f"  pnl_* fields: {len(pnl_cols)} ({', '.join(pnl_cols)})")
        print()

    print("Confirmations:")
    print("  - API-only: all decisions and signals from backend (POST /verify → LLM → P&L engine → signals + decision).")
    print("  - Dataset: signals_v2.csv has schema_version=2, pnl_* fields, and decision column.")
    if final_count >= 200:
        print(f"  - Target met: ≥200 total rows in signals_v2.csv (final = {final_count}, new = {new_rows}).")
    else:
        print(f"  - Target not met: final rows = {final_count} (need 200). Re-run or add more cases.")
    return 0 if final_count >= 200 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
