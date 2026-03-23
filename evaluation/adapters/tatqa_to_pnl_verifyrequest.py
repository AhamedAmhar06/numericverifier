"""TAT-QA to NumericVerifier P&L case adapter.

Loads TAT-QA dataset (train + dev), filters for P&L-like tables using heuristics
(does NOT call verifier.classify_table_type), converts to NumericVerifier format,
and outputs train/dev/test splits (70/15/15, seed=42).

Dataset location: Set TATQA_DATASET_DIR to directory containing:
  - tatqa_dataset_train.json
  - tatqa_dataset_dev.json

Or pass --tatqa_dir PATH.

Usage:
  python -m evaluation.adapters.tatqa_to_pnl_verifyrequest [--tatqa_dir PATH] [--output_dir PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# P&L row-label keywords (regex patterns, case-insensitive)
_PNL_KEYWORDS = [
    r"revenue", r"sales",
    r"cogs|cost\s+of\s+goods",
    r"gross\s+profit",
    r"operating\s+income",
    r"operating\s+expense|opex",
    r"net\s+income|profit",
    r"tax", r"interest",
]
_PNL_PATTERNS = [re.compile(p, re.I) for p in _PNL_KEYWORDS]

# Period column patterns
_PERIOD_PATTERNS = [
    re.compile(r"20\d\d"),           # 2020, 2021, etc.
    re.compile(r"FY\d\d"),           # FY20, FY21
    re.compile(r"Q[1-4]"),           # Q1, Q2, Q3, Q4
    re.compile(r"^\d{4}$"),          # 4-digit year
]

SPLIT_SEED = 42
TRAIN_RATIO = 0.70
DEV_RATIO = 0.15
TEST_RATIO = 0.15


def _parse_numeric(s: str) -> float | None:
    """Parse string to float; return None if not numeric."""
    if not isinstance(s, str):
        return None
    s = s.strip().replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None


def _tatqa_table_to_content(table_2d: list) -> dict | None:
    """Convert TAT-QA 2D table to NumericVerifier content dict."""
    if not table_2d or not isinstance(table_2d, list):
        return None
    rows = []
    for r in table_2d:
        if isinstance(r, (list, tuple)):
            rows.append([str(c) if c is not None else "" for c in r])
        else:
            return None
    if not rows:
        return None
    # First row = headers
    columns = rows[0]
    data_rows = rows[1:]
    return {
        "columns": columns,
        "rows": data_rows,
        "units": {},
    }


def _count_period_columns(columns: list) -> int:
    """Count headers matching year/quarter patterns."""
    count = 0
    for col in columns:
        if not isinstance(col, str):
            continue
        for pat in _PERIOD_PATTERNS:
            if pat.search(col):
                count += 1
                break
    return count


def _count_pnl_keywords_in_first_col(rows: list) -> int:
    """Count distinct P&L keywords found in first column values."""
    found = set()
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 1:
            continue
        cell = str(row[0]).lower() if row[0] is not None else ""
        for pat in _PNL_PATTERNS:
            if pat.search(cell):
                found.add(pat.pattern)
                break
    return len(found)


def _numeric_density(columns: list, rows: list) -> float:
    """Fraction of cells in period columns that parse as numbers."""
    period_indices = []
    for i, col in enumerate(columns):
        if not isinstance(col, str):
            continue
        for pat in _PERIOD_PATTERNS:
            if pat.search(col):
                period_indices.append(i)
                break
    if not period_indices:
        return 0.0
    total = 0
    numeric = 0
    for row in rows:
        for i in period_indices:
            if i < len(row):
                total += 1
                if _parse_numeric(str(row[i])) is not None:
                    numeric += 1
    return numeric / total if total else 0.0


def _passes_pnl_heuristic(content: dict) -> bool:
    """Strict P&L heuristic filter. Does NOT call verifier."""
    columns = content.get("columns", [])
    rows = content.get("rows", [])
    if not columns or not rows:
        return False
    # 1. Period columns: >= 2
    if _count_period_columns(columns) < 2:
        return False
    # 2. Row labels: >= 2 distinct P&L keywords
    if _count_pnl_keywords_in_first_col(rows) < 2:
        return False
    # 3. Numeric density: >= 45%
    if _numeric_density(columns, rows) < 0.45:
        return False
    return True


def _load_tatqa_records(path: Path) -> list:
    """Load TAT-QA JSON; return list of records (table + questions)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # TAT-QA format: list of {table: {uid, table}, paragraphs: [...], questions: [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return []


def _extract_cases(records: list, source_tag: str, start_id: int = 0) -> tuple[list, dict, int]:
    """Extract cases from TAT-QA records. Returns (cases, stats, next_id)."""
    cases = []
    stats = {"total_questions": 0, "answer_from_ok": 0, "answer_type_ok": 0, "numeric_ok": 0,
             "pnl_heuristic_ok": 0, "kept": 0, "dropped": 0}
    case_id = start_id

    for rec in records:
        table_obj = rec.get("table") or rec.get("table_obj")
        if not table_obj:
            continue
        raw_table = table_obj.get("table") if isinstance(table_obj, dict) else None
        if not raw_table or not isinstance(raw_table, list):
            continue

        content = _tatqa_table_to_content(raw_table)
        if not content:
            continue

        rows = content.get("rows", [])
        if len(rows) < 2:
            continue

        if not _passes_pnl_heuristic(content):
            continue

        questions = rec.get("questions", [])
        if not questions:
            continue

        for q in questions:
            stats["total_questions"] += 1
            answer_from = (q.get("answer_from") or "").lower()
            if answer_from not in ("table", "table-text"):
                continue
            stats["answer_from_ok"] += 1

            answer_type = (q.get("answer_type") or "").lower()
            if answer_type not in ("span", "arithmetic"):
                continue
            stats["answer_type_ok"] += 1

            gold = q.get("answer")
            if gold is None:
                continue
            # TAT-QA span answers are lists (e.g. ['2.9']); arithmetic are scalars
            if isinstance(gold, (list, tuple)):
                if len(gold) != 1:
                    continue  # multi-value span; skip
                gold = gold[0]
            gold_str = str(gold).strip()
            if _parse_numeric(gold_str) is None:
                continue
            stats["numeric_ok"] += 1
            stats["pnl_heuristic_ok"] += 1

            case_id += 1
            case = {
                "id": f"tatqa_pnl_{case_id:05d}",
                "question": q.get("question", ""),
                "evidence": {"type": "table", "content": content},
                "gold_answer": gold_str,
                "answer_type": answer_type,
                "answer_from": answer_from,
            }
            if q.get("derivation"):
                case["derivation"] = q["derivation"]
            cases.append(case)

    stats["kept"] = len(cases)
    stats["dropped"] = stats["total_questions"] - stats["kept"]
    return cases, stats, case_id


def _split_cases(cases: list) -> tuple[list, list, list]:
    """Deterministic 70/15/15 split."""
    import random
    rng = random.Random(SPLIT_SEED)
    shuffled = list(cases)
    rng.shuffle(shuffled)
    n = len(shuffled)
    t1 = int(n * TRAIN_RATIO)
    t2 = int(n * (TRAIN_RATIO + DEV_RATIO))
    return shuffled[:t1], shuffled[t1:t2], shuffled[t2:]


def main():
    parser = argparse.ArgumentParser(description="TAT-QA to P&L NumericVerifier cases")
    parser.add_argument("--tatqa_dir", default=os.environ.get("TATQA_DATASET_DIR", ""),
                        help="Directory with tatqa_dataset_train.json, tatqa_dataset_dev.json")
    parser.add_argument("--output_dir", default=None,
                        help="Output directory (default: evaluation/)")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent.parent
    tatqa_dir = Path(args.tatqa_dir) if args.tatqa_dir else base / "data" / "tatqa"
    output_dir = Path(args.output_dir) if args.output_dir else base / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = tatqa_dir / "tatqa_dataset_train.json"
    dev_path = tatqa_dir / "tatqa_dataset_dev.json"

    if not train_path.exists():
        print(f"TAT-QA train not found: {train_path}", file=sys.stderr)
        print("Set TATQA_DATASET_DIR or use --tatqa_dir to point to dataset.", file=sys.stderr)
        sys.exit(1)

    all_cases = []
    all_stats = {"train": {}, "dev": {}}
    next_id = 0

    for name, path in [("train", train_path), ("dev", dev_path)]:
        if not path.exists():
            continue
        records = _load_tatqa_records(path)
        cases, stats, next_id = _extract_cases(records, name, start_id=next_id)
        all_cases.extend(cases)
        all_stats[name] = stats
        print(f"{name}: {len(cases)} cases kept, stats={stats}")

    if not all_cases:
        print("No P&L cases extracted. Check filter rules and dataset.", file=sys.stderr)
        sys.exit(1)

    train_cases, dev_cases, test_cases = _split_cases(all_cases)
    print(f"Split (seed={SPLIT_SEED}): train={len(train_cases)}, dev={len(dev_cases)}, test={len(test_cases)}")

    for split_name, split_cases in [("train", train_cases), ("dev", dev_cases), ("test", test_cases)]:
        out_path = output_dir / f"base_cases_tatqa_pnl_{split_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(split_cases, f, indent=2)
        print(f"Wrote {out_path} ({len(split_cases)} cases)")

    # Write filter doc stats
    doc_path = base / "docs" / "tatqa_pnl_filter.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("# TAT-QA P&L Filter\n\n")
        f.write("## Filter Rules\n\n")
        f.write("- answer_from in {table, table-text}\n")
        f.write("- answer_type in {span, arithmetic}\n")
        f.write("- gold answer parseable as numeric\n")
        f.write("- Period columns: >= 2 headers match 20XX, FYXX, Q1-Q4\n")
        f.write("- Row labels: >= 3 distinct P&L keywords (revenue, cogs, gross profit, etc.)\n")
        f.write("- Numeric density: >= 60% of period-column cells parse as numbers\n\n")
        f.write("## Counts\n\n")
        total_q = sum(s.get("total_questions", 0) for s in all_stats.values())
        f.write(f"- Total questions processed: {total_q}\n")
        f.write(f"- Kept (P&L): {len(all_cases)}\n")
        f.write(f"- Dropped: {total_q - len(all_cases)}\n\n")
        f.write(f"- Train: {len(train_cases)}, Dev: {len(dev_cases)}, Test: {len(test_cases)}\n")
    print(f"Wrote {doc_path}")


if __name__ == "__main__":
    main()
