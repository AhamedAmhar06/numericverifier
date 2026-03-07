"""Build P&L-only ML signal datasets for train/dev/test.

Input sources:
  - Synthetic signals (evaluation results_raw.jsonl from cases_v2.json)
  - TAT-QA P&L train + dev gold signals (NOT test for train/dev)
  - Optionally TAT-QA LLM signals (train+dev only)

Output:
  - evaluation/signals_pnl_train.csv
  - evaluation/signals_pnl_dev.csv
  - evaluation/signals_pnl_test.csv (TAT-QA gold test only; held out for reporting)

Removes schema_version from features. Adds: source, split, case_id.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

SPLIT_SEED = 42
TRAIN_RATIO = 0.70
DEV_RATIO = 0.15

FEATURE_COLS = [
    "unsupported_claims_count", "coverage_ratio", "recomputation_fail_count",
    "max_relative_error", "mean_relative_error", "scale_mismatch_count",
    "period_mismatch_count", "ambiguity_count",
    "pnl_table_detected", "pnl_identity_fail_count", "pnl_margin_fail_count",
    "pnl_missing_baseline_count", "pnl_period_strict_mismatch_count",
]


def _load_synthetic(base):
    """Load synthetic signals from results_raw.jsonl."""
    path = base / "evaluation" / "results_raw.jsonl"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            sig = r.get("signals", {})
            decision = r.get("actual", r.get("decision", ""))
            if decision not in ("ACCEPT", "REPAIR", "FLAG"):
                continue
            row = {"case_id": r["id"], "decision": decision, "source": "synthetic"}
            for c in FEATURE_COLS:
                if c in sig:
                    row[c] = sig[c]
            rows.append(row)
    return rows


def _load_tatqa_gold(base: Path, split: str) -> list:
    """Load TAT-QA gold signals for a split."""
    path = base / "evaluation" / f"tatqa_pnl_gold_{split}_signals.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            decision = r.get("decision", "")
            if decision not in ("ACCEPT", "REPAIR", "FLAG"):
                continue
            row = {"case_id": r.get("case_id", ""), "decision": decision, "source": "tatqa_gold", "split": split}
            for c in FEATURE_COLS:
                if c in r:
                    row[c] = r[c]
            rows.append(row)
    return rows


def _load_tatqa_llm(base: Path, train_ids: set, dev_ids: set) -> list:
    """Load TAT-QA LLM signals; assign split from case_id."""
    path = base / "evaluation" / "tatqa_pnl_llm_signals.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cid = r.get("case_id", "")
            decision = r.get("decision_after", r.get("decision", ""))
            if decision not in ("ACCEPT", "REPAIR", "FLAG"):
                continue
            split = "train" if cid in train_ids else "dev" if cid in dev_ids else None
            if split is None:
                continue
            row = {"case_id": cid, "decision": decision, "source": "tatqa_llm", "split": split}
            for c in FEATURE_COLS:
                if c in r:
                    row[c] = r[c]
            rows.append(row)
    return rows


def _split_synthetic(rows):
    """Deterministic 70/15 split (15% test held out from train/dev)."""
    rng = random.Random(SPLIT_SEED)
    indices = list(range(len(rows)))
    rng.shuffle(indices)
    n = len(indices)
    t1 = int(n * TRAIN_RATIO)
    t2 = int(n * (TRAIN_RATIO + DEV_RATIO))
    train_rows = [rows[i] for i in indices[:t1]]
    dev_rows = [rows[i] for i in indices[t1:t2]]
    return train_rows, dev_rows


def main():
    parser = argparse.ArgumentParser(description="Build P&L signals dataset")
    parser.add_argument("--include_llm", action="store_true", help="Include TAT-QA LLM signals")
    parser.add_argument("--output_dir", default=None)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output_dir) if args.output_dir else base / "evaluation"

    train_ids = set()
    dev_ids = set()
    for split in ["train", "dev"]:
        p = base / "evaluation" / f"base_cases_tatqa_pnl_{split}.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                cases = json.load(f)
            ids = {c["id"] for c in cases}
            if split == "train":
                train_ids = ids
            else:
                dev_ids = ids

    # Synthetic
    synthetic = _load_synthetic(base)
    syn_train, syn_dev = _split_synthetic(synthetic)
    for r in syn_train:
        r["split"] = "train"
    for r in syn_dev:
        r["split"] = "dev"

    # TAT-QA gold
    tatqa_train = _load_tatqa_gold(base, "train")
    tatqa_dev = _load_tatqa_gold(base, "dev")
    tatqa_test = _load_tatqa_gold(base, "test")

    # TAT-QA LLM (optional)
    llm_rows = []
    if args.include_llm:
        llm_rows = _load_tatqa_llm(base, train_ids, dev_ids)

    # Combine
    train_rows = syn_train + tatqa_train + [r for r in llm_rows if r.get("split") == "train"]
    dev_rows = syn_dev + tatqa_dev + [r for r in llm_rows if r.get("split") == "dev"]
    test_rows = tatqa_test

    def to_csv_rows(rows):
        if not rows:
            return [], []
        all_cols = ["case_id", "source", "split", "decision"] + FEATURE_COLS
        cols = [c for c in all_cols if any(c in r for r in rows)]
        return cols, rows

    for name, rows in [("train", train_rows), ("dev", dev_rows), ("test", test_rows)]:
        cols, data = to_csv_rows(rows)
        out_path = output_dir / f"signals_pnl_{name}.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            for r in data:
                writer.writerow({c: r.get(c, "") for c in cols})
        print(f"Wrote {out_path} ({len(rows)} rows)")

    print(f"Train: {len(train_rows)}, Dev: {len(dev_rows)}, Test: {len(test_rows)}")


if __name__ == "__main__":
    main()
