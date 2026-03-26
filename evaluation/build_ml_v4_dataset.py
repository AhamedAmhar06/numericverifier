#!/usr/bin/env python3
"""
Build ML v4 training dataset using TAT-QA P&L cases + perturbation strategy.

Steps:
  2 — ACCEPT dataset from TAT-QA gold (re-run for fresh signals)
  3 — FLAG dataset via perturbation (value_error / period_error / scale_error)
  4 — Ambiguous/unlabeled dataset (REPAIR + low coverage)
  5 — Signal statistics (class separability)
  6 — Save CSV files

Run from repo root:
  python3 evaluation/build_ml_v4_dataset.py
"""
import sys, json, re, random, csv
from pathlib import Path
from collections import defaultdict

random.seed(42)

# ── paths ──────────────────────────────────────────────────────────────────
REPO_ROOT  = Path(__file__).parent.parent
EVAL_DIR   = Path(__file__).parent
BACKEND    = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.verifier.router import route_and_verify  # noqa: E402

# ── 13 signal keys (schema_version excluded — constant) ────────────────────
SIGNAL_KEYS = [
    "unsupported_claims_count", "coverage_ratio", "recomputation_fail_count",
    "max_relative_error", "mean_relative_error", "scale_mismatch_count",
    "period_mismatch_count", "ambiguity_count", "pnl_table_detected",
    "pnl_identity_fail_count", "pnl_margin_fail_count",
    "pnl_missing_baseline_count", "pnl_period_strict_mismatch_count",
]

ACCEPT_TARGET   = 100
FLAG_TARGET     = 100   # ~33 per perturbation type
AMBIGUOUS_TARGET = 50

# ── helpers ────────────────────────────────────────────────────────────────

def run_case(question, evidence, answer):
    """Run one case through the verifier with rules mode; return full result."""
    return route_and_verify(
        question, evidence, answer,
        options={"log_run": False, "decision_mode": "rules"},
    )


def signals_row(result, label, source, case_id, **extra):
    row = {"case_id": case_id, "label": label, "source": source}
    row.update(extra)
    sigs = result["signals"]
    for k in SIGNAL_KEYS:
        row[k] = sigs.get(k, 0)
    return row


def load_base_cases(split):
    path = EVAL_DIR / f"base_cases_tatqa_pnl_{split}.json"
    with open(path) as f:
        return {c["id"]: c for c in json.load(f)}


def load_results(split):
    path = EVAL_DIR / f"tatqa_pnl_gold_{split}_results.jsonl"
    results = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            results[r["id"]] = r
    return results


# ── perturbation helpers ────────────────────────────────────────────────────

_NUM_RE = re.compile(r'[\$\(]?([\d,]+\.?\d*)[\)]?')   # first numeric value


def _parse_first_number(text):
    """Return (match_obj, float_value) for first numeric token, or (None, None)."""
    m = _NUM_RE.search(text)
    if not m:
        return None, None
    raw = m.group(1).replace(",", "")
    try:
        return m, float(raw)
    except ValueError:
        return None, None


def perturb_value_error(answer, factor):
    """
    Replace first numeric value with val * factor.
    factor should give 12-25% error (e.g. 1.15, 0.80, 1.25, 0.75).
    """
    m, val = _parse_first_number(answer)
    if m is None:
        return None
    new_val = val * factor
    if abs(new_val - round(new_val)) < 1e-9:
        new_str = str(int(round(new_val)))
    else:
        new_str = f"{new_val:.2f}"
    # Rebuild answer preserving everything outside the numeric digits
    start, end = m.span(1)   # span of the digit group (group 1)
    return answer[:start] + new_str + answer[end:]


def perturb_period_error(answer, question, evidence_content):
    """
    Replace year in answer with another year found in table columns / question.
    Returns None if answer contains no year or no alternative year available.
    """
    years_in_ans = re.findall(r'\b(20\d{2}|19\d{2})\b', answer)
    if not years_in_ans:
        return None
    target = years_in_ans[0]

    # Gather all years from columns and question
    col_text = " ".join(str(c) for c in evidence_content.get("columns", []))
    pool = set(re.findall(r'\b(20\d{2}|19\d{2})\b', col_text + " " + question))
    alts = sorted(pool - {target})
    if not alts:
        return None
    new_year = alts[0]
    return re.sub(r'\b' + re.escape(target) + r'\b', new_year, answer, count=1)


def perturb_scale_error(answer):
    """
    Shift scale by 3 orders of magnitude.
    million → billion, billion → trillion.
    If no scale word: multiply value by 1 000 and append ' thousand'.
    """
    if re.search(r'\bmillion\b', answer, re.I):
        return re.sub(r'\bmillion\b', 'billion', answer, flags=re.I)
    if re.search(r'\bbillion\b', answer, re.I):
        return re.sub(r'\bbillion\b', 'trillion', answer, flags=re.I)
    # no scale word — multiply by 1 000 and label as thousand
    m, val = _parse_first_number(answer)
    if m is None:
        return None
    new_val = val * 1000
    if abs(new_val - round(new_val)) < 1e-9:
        new_str = str(int(round(new_val)))
    else:
        new_str = f"{new_val:.2f}"
    start, end = m.span(1)
    return answer[:start] + new_str + " thousand" + answer[end:]


def try_perturb_until_flag(perturb_fn, question, evidence, gold_answer, max_attempts=4):
    """
    Apply perturb_fn with increasing magnitude until the pipeline returns FLAG.
    perturb_fn signature: (answer) -> perturbed_answer | None
    Returns (perturbed_answer, result) or (None, None) if all attempts fail.
    """
    for attempt in range(max_attempts):
        perturbed = perturb_fn(gold_answer, attempt)
        if perturbed is None or perturbed == gold_answer:
            continue
        result = run_case(question, evidence, perturbed)
        if result["decision"] == "FLAG":
            return perturbed, result
    return None, None


def value_error_fn(gold_answer, attempt):
    factors = [1.15, 0.80, 1.30, 0.65]   # escalating magnitude
    return perturb_value_error(gold_answer, factors[attempt])


def period_error_fn(case, attempt=0):
    """period_error doesn't need escalation — it's binary (right year / wrong year)."""
    return perturb_period_error(
        case["gold_answer"], case["question"],
        case["evidence"]["content"],
    )


def scale_error_fn(gold_answer, attempt=0):
    return perturb_scale_error(gold_answer)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — ACCEPT dataset
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 70)
print("STEP 2 — Building ACCEPT dataset from TAT-QA gold")
print("=" * 70)

accept_rows  = []
accept_cases = []   # keep for perturbation in step 3

for split in ("train", "dev", "test"):
    if len(accept_rows) >= ACCEPT_TARGET:
        break
    base   = load_base_cases(split)
    old_results = load_results(split)
    gold_accept_ids = [cid for cid, r in old_results.items() if r["decision"] == "ACCEPT"]
    print(f"  {split}: {len(gold_accept_ids)} old-ACCEPT cases available")

    for cid in gold_accept_ids:
        if len(accept_rows) >= ACCEPT_TARGET:
            break
        case = base.get(cid)
        if case is None:
            continue
        result = run_case(case["question"], case["evidence"], case["gold_answer"])
        if result["decision"] == "ACCEPT":
            accept_rows.append(signals_row(
                result, "ACCEPT", f"tatqa_gold_{split}", cid,
            ))
            accept_cases.append(case)
        # if pipeline now returns FLAG for this gold case, skip it

print(f"\n  → ACCEPT rows collected: {len(accept_rows)}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — FLAG dataset via perturbation
# ══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 70)
print("STEP 3 — Building FLAG dataset via perturbation")
print("=" * 70)

flag_rows   = []
type_counts = defaultdict(int)
skipped     = defaultdict(int)

PER_TYPE_TARGET = FLAG_TARGET // 3   # 33 each

def collect_flag(case, perturbed_answer, result, error_type):
    flag_rows.append(signals_row(
        result, "FLAG", "tatqa_perturbed", case["id"],
        error_type=error_type,
        original_answer=case["gold_answer"],
        perturbed_answer=perturbed_answer,
    ))
    type_counts[error_type] += 1


for case in accept_cases:
    q   = case["question"]
    ev  = case["evidence"]
    ga  = case["gold_answer"]

    # ── TYPE 1: value_error ───────────────────────────────────────────────
    if type_counts["value_error"] < PER_TYPE_TARGET + 5:
        pa, res = try_perturb_until_flag(
            lambda ans, attempt: value_error_fn(ans, attempt),
            q, ev, ga,
        )
        if res is not None:
            collect_flag(case, pa, res, "value_error")
        else:
            skipped["value_error"] += 1

    # ── TYPE 2: period_error ──────────────────────────────────────────────
    if type_counts["period_error"] < PER_TYPE_TARGET + 5:
        pa = period_error_fn(case)
        if pa and pa != ga:
            res = run_case(q, ev, pa)
            if res["decision"] == "FLAG":
                collect_flag(case, pa, res, "period_error")
            else:
                skipped["period_error"] += 1
        else:
            skipped["period_error"] += 1

    # ── TYPE 3: scale_error ───────────────────────────────────────────────
    if type_counts["scale_error"] < PER_TYPE_TARGET + 5:
        pa = scale_error_fn(ga)
        if pa and pa != ga:
            res = run_case(q, ev, pa)
            if res["decision"] == "FLAG":
                collect_flag(case, pa, res, "scale_error")
            else:
                skipped["scale_error"] += 1
        else:
            skipped["scale_error"] += 1

print(f"\n  FLAG rows by type:")
for et, cnt in sorted(type_counts.items()):
    print(f"    {et}: {cnt}  (skipped/ACCEPT: {skipped[et]})")
print(f"  → FLAG rows total: {len(flag_rows)}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Ambiguous / unlabeled dataset
# ══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 70)
print("STEP 4 — Building AMBIGUOUS (unlabeled) dataset")
print("=" * 70)

ambig_rows = []

for split in ("train", "dev", "test"):
    if len(ambig_rows) >= AMBIGUOUS_TARGET:
        break
    base = load_base_cases(split)
    old_results = load_results(split)

    for cid, old_r in old_results.items():
        if len(ambig_rows) >= AMBIGUOUS_TARGET:
            break
        # Criteria: old REPAIR or coverage between 0.4 and 0.8
        old_sigs = old_r.get("signals", {})
        cov = old_sigs.get("coverage_ratio", 0.0)
        is_repair = old_r["decision"] == "REPAIR"
        is_mid_coverage = 0.4 <= cov <= 0.8

        if not (is_repair or is_mid_coverage):
            continue

        case = base.get(cid)
        if case is None:
            continue

        result = run_case(case["question"], case["evidence"], case["gold_answer"])
        row = {
            "case_id": cid,
            "coverage": result["signals"].get("coverage_ratio", 0.0),
            "rel_error": result["signals"].get("max_relative_error", 0.0),
            "scale_mismatch": result["signals"].get("scale_mismatch_count", 0),
            "period_mismatch": result["signals"].get("period_mismatch_count", 0),
            "identity_fail": result["signals"].get("pnl_identity_fail_count", 0),
            "rule_decision": result["decision"],
            "gold_answer": case["gold_answer"],
        }
        ambig_rows.append(row)

print(f"  → Ambiguous rows collected: {len(ambig_rows)}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Signal statistics
# ══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 70)
print("STEP 5 — Signal statistics (ACCEPT vs FLAG separability)")
print("=" * 70)

def mean(vals):
    return sum(vals) / len(vals) if vals else 0.0

accept_signals = {k: [r[k] for r in accept_rows] for k in SIGNAL_KEYS}
flag_signals   = {k: [r[k] for r in flag_rows]   for k in SIGNAL_KEYS}

print(f"\n{'Signal':<38} {'ACCEPT mean':>12} {'FLAG mean':>12}  Separable?")
print("-" * 70)
for k in SIGNAL_KEYS:
    a_mean = mean(accept_signals[k])
    f_mean = mean(flag_signals[k])
    # Separable if FLAG mean > ACCEPT mean by >= 0.05 (or ACCEPT > FLAG for coverage_ratio)
    if k == "coverage_ratio":
        sep = "YES" if (a_mean - f_mean) >= 0.05 else "no"
    else:
        sep = "YES" if (f_mean - a_mean) >= 0.05 else "no"
    print(f"  {k:<36} {a_mean:>12.4f} {f_mean:>12.4f}  {sep}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Save datasets
# ══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 70)
print("STEP 6 — Saving datasets")
print("=" * 70)

def write_csv(path, rows, fieldnames=None):
    if not rows:
        print(f"  WARNING: 0 rows — skipping {path.name}")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved {len(rows)} rows → {path.name}")


ACCEPT_FIELDS = ["case_id", "label", "source"] + SIGNAL_KEYS
FLAG_FIELDS   = ["case_id", "label", "source", "error_type",
                  "original_answer", "perturbed_answer"] + SIGNAL_KEYS
AMBIG_FIELDS  = ["case_id", "coverage", "rel_error", "scale_mismatch",
                  "period_mismatch", "identity_fail", "rule_decision", "gold_answer"]

accept_path = EVAL_DIR / "signals_v4_accept.csv"
flag_path   = EVAL_DIR / "signals_v4_flag.csv"
ambig_path  = EVAL_DIR / "tier3_tatqa_ambiguous_UNLABELED.csv"

write_csv(accept_path, accept_rows, ACCEPT_FIELDS)
write_csv(flag_path,   flag_rows,   FLAG_FIELDS)
write_csv(ambig_path,  ambig_rows,  AMBIG_FIELDS)

# ── final counts ────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  signals_v4_accept.csv       : {len(accept_rows):>4} rows")
print(f"  signals_v4_flag.csv         : {len(flag_rows):>4} rows")
print(f"  tier3_tatqa_ambiguous_UNLABELED.csv : {len(ambig_rows):>4} rows")

print()
print("First 3 rows — ACCEPT:")
for r in accept_rows[:3]:
    print(f"  {r['case_id']:20s}  cov={r['coverage_ratio']:.2f}  "
          f"unsup={r['unsupported_claims_count']}  label={r['label']}")

print()
print("First 3 rows — FLAG:")
for r in flag_rows[:3]:
    print(f"  {r['case_id']:20s}  type={r.get('error_type','?'):15s}  "
          f"perturbed={r.get('perturbed_answer','?')[:30]}  label={r['label']}")

print()
print("First 20 rows — AMBIGUOUS:")
print(f"  {'case_id':<22} {'coverage':>8} {'rel_err':>8} "
      f"{'scale_mm':>9} {'per_mm':>7} {'id_fail':>8} "
      f"{'rule_dec':>8}  gold_answer")
print("  " + "-" * 90)
for r in ambig_rows[:20]:
    print(f"  {r['case_id']:<22} {r['coverage']:>8.3f} {r['rel_error']:>8.4f} "
          f"{r['scale_mismatch']:>9} {r['period_mismatch']:>7} {r['identity_fail']:>8} "
          f"{r['rule_decision']:>8}  {str(r['gold_answer'])[:30]}")
