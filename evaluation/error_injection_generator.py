"""Generate error-injected candidate answers from TAT-QA P&L test cases.

For each gold case, produces up to 5 incorrect variants:
  - arithmetic_error:  gold * random factor (15-30% off)
  - percentage_error:  shift by +2 to +5 absolute points
  - scale_error:       gold * 1000 or gold / 1000
  - period_error:      use value from a different period column
  - near_miss_error:   gold * small factor (2-5% off, outside 1% tolerance)

Output: evaluation/error_injected_cases.json
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.verifier.normalize import normalize_cell_text

_SEED = 42


def _parse_gold(gold_str: str) -> Optional[float]:
    """Parse a gold answer string to float using the verifier's own normalizer."""
    result = normalize_cell_text(gold_str)
    if result["value"] is not None:
        val = result["value"] * result["scale_factor"]
        return val
    cleaned = re.sub(r"[,$%€£¥₹]", "", gold_str).strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _format_value(val: float) -> str:
    """Format a numeric value for injection into a candidate answer."""
    if val == int(val) and abs(val) < 1e12:
        return str(int(val))
    if abs(val) < 0.01:
        return f"{val:.4f}"
    if abs(val) < 100:
        return f"{val:.2f}"
    return f"{val:.2f}"


def _find_period_columns(content: dict) -> list:
    """Return column indices that look like year/period columns."""
    columns = content.get("columns", [])
    period_indices = []
    for i, col in enumerate(columns):
        col_str = str(col).strip()
        if re.search(r"20\d{2}", col_str) or re.search(r"FY\s*\d{2}", col_str, re.IGNORECASE):
            period_indices.append(i)
    return period_indices


def _find_gold_in_table(content: dict, gold_value: float, tolerance: float = 0.02) -> list:
    """Find cells in the table that match the gold value. Returns list of (row_idx, col_idx)."""
    rows = content.get("rows", [])
    matches = []
    for r_idx, row in enumerate(rows):
        for c_idx, cell in enumerate(row):
            parsed = normalize_cell_text(str(cell))
            if parsed["value"] is not None:
                cell_val = parsed["value"] * parsed["scale_factor"]
                if gold_value != 0 and abs((cell_val - gold_value) / gold_value) <= tolerance:
                    matches.append((r_idx, c_idx))
                elif gold_value == 0 and abs(cell_val) <= tolerance:
                    matches.append((r_idx, c_idx))
    return matches


def generate_errors(cases: list, rng: random.Random) -> list:
    """Generate error-injected cases from gold cases."""
    injected = []

    for case in cases:
        cid = case["id"]
        gold_str = case.get("gold_answer", "")
        gold_val = _parse_gold(gold_str)
        if gold_val is None:
            continue

        content = case.get("evidence", {}).get("content", {})
        base = {
            "original_id": cid,
            "question": case["question"],
            "evidence": case["evidence"],
            "gold_answer": gold_str,
        }

        # --- arithmetic_error ---
        factor = rng.choice([0.7, 0.85, 1.15, 1.3])
        wrong = gold_val * factor
        injected.append({
            **base,
            "id": f"{cid}_arithmetic_error",
            "candidate_answer": f"The answer is {_format_value(wrong)}.",
            "error_type": "arithmetic_error",
            "injected_value": _format_value(wrong),
            "expected_decision": "FLAG",
        })

        # --- percentage_error ---
        shift = rng.uniform(2.0, 5.0) * rng.choice([-1, 1])
        wrong_pct = gold_val + shift
        injected.append({
            **base,
            "id": f"{cid}_percentage_error",
            "candidate_answer": f"The answer is {_format_value(wrong_pct)}.",
            "error_type": "percentage_error",
            "injected_value": _format_value(wrong_pct),
            "expected_decision": "FLAG",
        })

        # --- scale_error ---
        scale_dir = rng.choice(["up", "down"])
        wrong_scale = gold_val * 1000 if scale_dir == "up" else gold_val / 1000
        injected.append({
            **base,
            "id": f"{cid}_scale_error",
            "candidate_answer": f"The answer is {_format_value(wrong_scale)}.",
            "error_type": "scale_error",
            "injected_value": _format_value(wrong_scale),
            "expected_decision": "FLAG",
        })

        # --- period_error ---
        period_cols = _find_period_columns(content)
        gold_cells = _find_gold_in_table(content, gold_val)
        period_injected = False
        if len(period_cols) >= 2 and gold_cells:
            for r_idx, c_idx in gold_cells:
                if c_idx in period_cols:
                    other_cols = [p for p in period_cols if p != c_idx]
                    if other_cols:
                        alt_col = rng.choice(other_cols)
                        row = content["rows"][r_idx]
                        if alt_col < len(row):
                            alt_parsed = normalize_cell_text(str(row[alt_col]))
                            if alt_parsed["value"] is not None:
                                alt_val = alt_parsed["value"] * alt_parsed["scale_factor"]
                                if gold_val == 0 or abs((alt_val - gold_val) / max(abs(gold_val), 1e-9)) > 0.01:
                                    injected.append({
                                        **base,
                                        "id": f"{cid}_period_error",
                                        "candidate_answer": f"The answer is {_format_value(alt_val)}.",
                                        "error_type": "period_error",
                                        "injected_value": _format_value(alt_val),
                                        "expected_decision": "FLAG",
                                    })
                                    period_injected = True
                    break
        if not period_injected:
            wrong_period = gold_val * rng.choice([0.9, 1.1])
            injected.append({
                **base,
                "id": f"{cid}_period_error",
                "candidate_answer": f"The answer is {_format_value(wrong_period)}.",
                "error_type": "period_error",
                "injected_value": _format_value(wrong_period),
                "expected_decision": "FLAG",
            })

        # --- near_miss_error ---
        near_factor = rng.uniform(1.02, 1.05) * rng.choice([-1, 1])
        if near_factor < 0:
            near_factor = 1.0 + (near_factor + 1.0)
        wrong_near = gold_val * near_factor
        if gold_val != 0 and abs((wrong_near - gold_val) / gold_val) < 0.015:
            wrong_near = gold_val * (1.0 + rng.choice([0.03, -0.03]))
        injected.append({
            **base,
            "id": f"{cid}_near_miss_error",
            "candidate_answer": f"The answer is {_format_value(wrong_near)}.",
            "error_type": "near_miss_error",
            "injected_value": _format_value(wrong_near),
            "expected_decision": "FLAG",
        })

    return injected


def main():
    base_dir = Path(__file__).resolve().parent
    cases_path = base_dir / "base_cases_tatqa_pnl_test.json"
    if not cases_path.exists():
        print(f"ERROR: {cases_path} not found")
        sys.exit(1)

    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    rng = random.Random(_SEED)
    injected = generate_errors(cases, rng)

    output_path = base_dir / "error_injected_cases.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(injected, f, indent=2, default=str)

    from collections import Counter
    type_counts = Counter(c["error_type"] for c in injected)
    print(f"Generated {len(injected)} error-injected cases from {len(cases)} gold cases")
    for etype, count in sorted(type_counts.items()):
        print(f"  {etype}: {count}")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
