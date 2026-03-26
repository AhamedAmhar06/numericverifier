#!/usr/bin/env python3
"""
ML v4 hybrid dataset builder — Option B + targeted ambiguous expansion.

Parts:
  A — 100 TAT-QA gold ACCEPTs  (already in signals_v4_accept.csv — read-only)
  B — 100 synthetic FLAG cases  (34 value_error + 33 period_error + 33 scale_error)
  C — 60 ambiguous unlabeled    (8 TAT-QA real + 52 synthetic)
  D — Signal diversity check

Run from repo root:
  python3 evaluation/build_ml_v4_hybrid.py
"""
import sys, json, csv, random
from pathlib import Path
from collections import defaultdict

random.seed(42)

REPO_ROOT = Path(__file__).parent.parent
EVAL_DIR  = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.verifier.router import route_and_verify   # noqa: E402

def mean(vals):
    return sum(vals)/len(vals) if vals else 0.0

SIGNAL_KEYS = [
    "unsupported_claims_count", "coverage_ratio", "recomputation_fail_count",
    "max_relative_error", "mean_relative_error", "scale_mismatch_count",
    "period_mismatch_count", "ambiguity_count", "pnl_table_detected",
    "pnl_identity_fail_count", "pnl_margin_fail_count",
    "pnl_missing_baseline_count", "pnl_period_strict_mismatch_count",
]   # 13 signals (schema_version excluded)

# ──────────────────────────────────────────────────────────────────────────────
# Table factories
# ──────────────────────────────────────────────────────────────────────────────

def _make_table(rev22, rev23, *, scale=1, identity_perturb=0.0):
    """
    Build a syntactically clean P&L table.

    scale: multiply all raw values by this (use 1e6 for billions-range scale_error cases)
    identity_perturb: fractional perturbation applied to Gross Profit to break identity
                      (e.g. 0.02 adds 2% to the computed GP so Rev - COGS != GP)
    """
    r22, r23 = int(rev22 * scale), int(rev23 * scale)
    cogs22, cogs23 = int(r22 * 0.40), int(r23 * 0.40)
    gp22_true = r22 - cogs22
    gp23_true = r23 - cogs23
    # optionally break identity for C2c cases
    gp22 = int(gp22_true * (1 + identity_perturb))
    gp23 = int(gp23_true * (1 + identity_perturb))
    opex22, opex23 = int(r22 * 0.20), int(r23 * 0.20)
    oi22, oi23     = gp22 - opex22, gp23 - opex23
    tax22, tax23   = int(oi22 * 0.25), int(oi23 * 0.25)
    int22, int23   = int(r22 * 0.02), int(r23 * 0.02)
    ni22, ni23     = oi22 - tax22 - int22, oi23 - tax23 - int23
    return {
        "columns": ["Line Item", "2022", "2023"],
        "rows": [
            ["Revenue",            str(r22),    str(r23)],
            ["Cost of Sales",      str(cogs22), str(cogs23)],
            ["Gross Profit",       str(gp22),   str(gp23)],
            ["Operating Expenses", str(opex22), str(opex23)],
            ["Operating Income",   str(oi22),   str(oi23)],
            ["Taxes",              str(tax22),  str(tax23)],
            ["Interest",           str(int22),  str(int23)],
            ["Net Income",         str(ni22),   str(ni23)],
        ],
        "units": {},
    }

def _evidence(content):
    return {"type": "table", "content": content}

# Row lookups for a table dict
def _row(table, label):
    for row in table["rows"]:
        if row[0].lower() == label.lower():
            return row
    return None

def _val(table, label, col_idx):
    row = _row(table, label)
    return int(row[col_idx]) if row else None

# ── revenue seeds for 100 varied tables ─────────────────────────────────────
# Generate 100 pairs (rev22, rev23) with ~5-30% YoY growth
rng = random.Random(42)
_SEEDS = [
    (rng.randint(200_000, 800_000), rng.randint(220_000, 900_000))
    for _ in range(100)
]

LINE_ITEMS = [
    ("Revenue",            1),   # col index for 2022
    ("Gross Profit",       1),
    ("Operating Income",   1),
    ("Net Income",         1),
]

# ──────────────────────────────────────────────────────────────────────────────
# Verifier call helpers
# ──────────────────────────────────────────────────────────────────────────────

def run_verify(question, evidence, answer, enable_repair=False):
    return route_and_verify(
        question, evidence, answer,
        options={"log_run": False, "decision_mode": "rules",
                 "enable_repair": enable_repair},
    )

def sig(result):
    return result["signals"]

def signals_row(result, label, source, case_id, **extra):
    row = {"case_id": case_id, "label": label, "source": source}
    row.update(extra)
    s = result["signals"]
    for k in SIGNAL_KEYS:
        row[k] = s.get(k, 0)
    return row

# ──────────────────────────────────────────────────────────────────────────────
# PART B — 100 synthetic FLAG cases
# ──────────────────────────────────────────────────────────────────────────────
print("=" * 70)
print("PART B — Generating 100 synthetic FLAG cases")
print("=" * 70)

flag_rows   = []
type_counts = defaultdict(int)
signal_check_fails = defaultdict(int)

ITEMS_2022 = [
    ("Revenue",            1, "revenue"),
    ("Gross Profit",       1, "gp"),
    ("Operating Income",   1, "oi"),
    ("Net Income",         1, "ni"),
]

# ── B1: 34 value_error ─────────────────────────────────────────────────────
# Value is 20-35% off (outside 5×tolerance grounding window) → coverage=0
# Signal: unsupported_claims_count=1, coverage_ratio=0.0
# Use up to 60 seeds to guarantee 34 passing (some perturbed values coincidentally
# match a different line item and return ACCEPT — those are skipped).
print("\n  [B1] value_error cases ...")
_ve_idx = 0
for i, (rev22, rev23) in enumerate(_SEEDS[:60]):
    if type_counts["value_error"] >= 34:
        break
    table   = _make_table(rev22, rev23)
    ev      = _evidence(table)
    label_idx  = i % len(ITEMS_2022)
    item_name, col_idx, short = ITEMS_2022[label_idx]
    correct_val = _val(table, item_name, col_idx)
    # Perturb 22-35% off (clear of 5×tolerance=5% grounding window AND of other rows)
    factor = 1.22 + (i % 10) * 0.013
    wrong_val = int(correct_val * factor)
    question = f"What was {item_name} in 2022?"
    answer   = f"{item_name} in 2022 was {wrong_val}."
    r = run_verify(question, ev, answer)
    s = sig(r)
    if r["decision"] != "FLAG":
        signal_check_fails["value_error_not_flag"] += 1
        continue
    if s["coverage_ratio"] != 0.0 or s["unsupported_claims_count"] < 1:
        signal_check_fails["value_error_bad_signal"] += 1
        continue
    flag_rows.append(signals_row(r, "FLAG", "synthetic_perturbed",
        f"syn_ve_{_ve_idx:03d}", error_type="value_error",
        correct_answer=str(correct_val), perturbed_answer=str(wrong_val),
        note="coverage=0; grounding fails when value >5*tolerance off"))
    type_counts["value_error"] += 1
    _ve_idx += 1

# ── B2: 33 period_error ────────────────────────────────────────────────────
# Question asks for year not in table (2024) → V_MISSING_PERIOD_IN_EVIDENCE
# Signal: pnl_period_strict_mismatch_count>0, coverage_ratio=1.0
print("  [B2] period_error cases ...")
for i, (rev22, rev23) in enumerate(_SEEDS[34:67]):
    table   = _make_table(rev22, rev23)
    ev      = _evidence(table)
    label_idx  = i % len(ITEMS_2022)
    item_name, col_idx, short = ITEMS_2022[label_idx]
    # Use 2023 value as the "answer" but question asks for 2024 (not in table)
    val_2023 = _val(table, item_name, 2)   # col 2 = 2023
    question = f"What was {item_name} in 2024?"
    answer   = f"{item_name} in 2024 was {val_2023}."
    r = run_verify(question, ev, answer)
    s = sig(r)
    if r["decision"] != "FLAG":
        signal_check_fails["period_error_not_flag"] += 1
        continue
    if s["pnl_period_strict_mismatch_count"] == 0:
        signal_check_fails["period_error_no_signal"] += 1
        continue   # strict exclude — signal not firing
    flag_rows.append(signals_row(r, "FLAG", "synthetic_perturbed",
        f"syn_pe_{i:03d}", error_type="period_error",
        question_year="2024", table_years="2022,2023",
        note="V_MISSING_PERIOD_IN_EVIDENCE: 2024 not in pnl_periods"))
    type_counts["period_error"] += 1

# ── B3: 33 scale_error ─────────────────────────────────────────────────────
# Billion-range table (×1,000,000). Answer says "X million" where X millions
# equals the absolute table value → grounding succeeds, then
# V_SCALE_MISMATCH fires (evidence>=1B, claim says "million").
# Signal: scale_mismatch_count=1, coverage_ratio=1.0
print("  [B3] scale_error cases ...")
for i, (rev22, rev23) in enumerate(_SEEDS[67:100]):
    # Scale raw values by 1,000,000 → billions range
    table   = _make_table(rev22, rev23, scale=1_000_000)
    ev      = _evidence(table)
    label_idx  = i % len(ITEMS_2022)
    item_name, col_idx, short = ITEMS_2022[label_idx]
    raw_val = _val(table, item_name, col_idx)   # e.g. 500_000_000_000
    # Express as "X million" where X = raw_val / 1e6 exactly (so parsed = raw_val)
    x_million = raw_val // 1_000_000   # integer millions
    question = f"What was {item_name} in 2022?"
    answer   = f"{item_name} in 2022 was {x_million:,} million."
    r = run_verify(question, ev, answer)
    s = sig(r)
    if r["decision"] != "FLAG":
        signal_check_fails["scale_error_not_flag"] += 1
        continue
    if s["scale_mismatch_count"] == 0:
        signal_check_fails["scale_error_no_signal"] += 1
        continue   # strict exclude — signal not firing
    flag_rows.append(signals_row(r, "FLAG", "synthetic_perturbed",
        f"syn_se_{i:03d}", error_type="scale_error",
        table_scale="raw_billions", answer_scale="million",
        note="V_SCALE_MISMATCH: evidence>=1B suggests billion, claim says million"))
    type_counts["scale_error"] += 1

print(f"\n  FLAG rows by type:")
for et in ("value_error", "period_error", "scale_error"):
    print(f"    {et:<18}: {type_counts[et]:>3}  (signal-check fails: {signal_check_fails.get(et+'_bad_signal',0) + signal_check_fails.get(et+'_no_signal',0)}, not-FLAG: {signal_check_fails.get(et+'_not_flag',0)})")
print(f"  Total FLAG rows: {len(flag_rows)}")

# ──────────────────────────────────────────────────────────────────────────────
# PART C — 60 ambiguous unlabeled cases
# ──────────────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("PART C — Building 60 ambiguous unlabeled cases")
print("=" * 70)

ambig_rows = []

# ── C0: 8 real TAT-QA cases (from previous run) ────────────────────────────
print("\n  [C0] Loading 8 real TAT-QA ambiguous cases ...")
_tatqa_ambig = [
    ("tatqa_pnl_00091", "tatqa_real", "coverage=1.0, identity_fail=2, gold=31.75"),
    ("tatqa_pnl_00092", "tatqa_real", "coverage=1.0, identity_fail=2, gold=25.7"),
    ("tatqa_pnl_00010", "tatqa_real", "coverage=1.0, identity_fail=2, gold=1171074.5"),
    ("tatqa_pnl_00008", "tatqa_real", "coverage=1.0, identity_fail=2, gold=3031930.5"),
    ("tatqa_pnl_00009", "tatqa_real", "coverage=1.0, identity_fail=2, gold=1860856"),
    ("tatqa_pnl_00083", "tatqa_real", "coverage=1.0, identity_fail=2, gold=10.8"),
    ("tatqa_pnl_00298", "tatqa_real", "coverage=1.0, identity_fail=3, gold=36%"),
    ("tatqa_pnl_00084", "tatqa_real", "coverage=1.0, identity_fail=2, gold=1.6"),
]
# Re-run through current pipeline for fresh signals
_base_all = {}
for split in ("train", "dev", "test"):
    path = EVAL_DIR / f"base_cases_tatqa_pnl_{split}.json"
    with open(path) as f:
        for c in json.load(f):
            _base_all[c["id"]] = c

for cid, ctype, desc in _tatqa_ambig:
    case = _base_all.get(cid)
    if not case:
        print(f"    WARNING: {cid} not found in base cases")
        continue
    r = run_verify(case["question"], case["evidence"], case["gold_answer"])
    row = {"case_id": cid, "case_type": ctype, "case_description": desc,
           "gold_answer": case["gold_answer"], "rule_decision": r["decision"]}
    for k in SIGNAL_KEYS:
        row[k] = r["signals"].get(k, 0)
    ambig_rows.append(row)
print(f"    Loaded: {len(ambig_rows)} TAT-QA real cases")

# ── C2a: 20 partial grounding (coverage ~0.5) ──────────────────────────────
# 2-claim answer: one claim is an exact table value, one is a derived % not in table
print("\n  [C2a] partial grounding (20 cases) ...")
_seeds_c2a = _SEEDS[:20]
for i, (rev22, rev23) in enumerate(_seeds_c2a):
    table  = _make_table(rev22, rev23)
    ev     = _evidence(table)
    rev    = _val(table, "Revenue", 1)
    gp     = _val(table, "Gross Profit", 1)
    true_gm_pct = round(gp / rev * 100, 1)
    # Use 2× actual margin so execution fails (computed=60% ≠ claimed=120%) and
    # the percent value also misses all evidence cells → claim is unsupported
    wrong_gm_pct = round(true_gm_pct * 2.0, 1)
    question = "What was Revenue and gross margin % in 2022?"
    answer   = f"Revenue was {rev} and gross margin was {wrong_gm_pct}%."
    r = run_verify(question, ev, answer)
    s = sig(r)
    row = {
        "case_id": f"c2a_{i:03d}",
        "case_type": "partial_grounding",
        "case_description": (f"2 claims: revenue={rev} grounds; "
                             f"gm%={wrong_gm_pct} wrong (actual={true_gm_pct})"),
        "gold_answer": f"Revenue={rev}, GM%={true_gm_pct}",
        "rule_decision": r["decision"],
    }
    for k in SIGNAL_KEYS:
        row[k] = s.get(k, 0)
    ambig_rows.append(row)

_sample_cov = mean([float(r["coverage_ratio"]) for r in ambig_rows if r["case_type"] == "partial_grounding"])
print(f"    Added {i+1} C2a cases. Mean coverage: {_sample_cov:.2f}")

# ── C2b: 16 small value error (2-4% off, grounded, rules may ACCEPT) ───────
print("\n  [C2b] small value error 2-4% off (16 cases) ...")
_small_errors = [0.021, 0.025, 0.030, 0.034, 0.022, 0.028, 0.032, 0.038,
                 0.023, 0.027, 0.031, 0.037, 0.024, 0.026, 0.033, 0.036]
for i, (err_frac, (rev22, rev23)) in enumerate(zip(_small_errors, _SEEDS[20:36])):
    table   = _make_table(rev22, rev23)
    ev      = _evidence(table)
    correct = _val(table, "Revenue", 1)
    wrong   = int(correct * (1 + err_frac))
    question = "What was Revenue in 2022?"
    answer   = f"Revenue in 2022 was {wrong}."
    r = run_verify(question, ev, answer)
    s = sig(r)
    row = {
        "case_id": f"c2b_{i:03d}",
        "case_type": "small_value_error",
        "case_description": f"Revenue {err_frac*100:.1f}% off: correct={correct}, given={wrong}",
        "gold_answer": str(correct),
        "rule_decision": r["decision"],
    }
    for k in SIGNAL_KEYS:
        row[k] = s.get(k, 0)
    ambig_rows.append(row)

# ── C2c: 16 identity near-miss (table identity broken, coverage=1.0) ───────
# Construct tables where Gross Profit is perturbed by 2-4% from Revenue-COGS
# → pnl_identity_fail_count > 0 (tolerance=1%, perturbation=2-4%)
print("\n  [C2c] identity near-miss (16 cases) ...")
_id_perturbs = [0.022, 0.025, 0.028, 0.031, 0.034, 0.037, 0.023, 0.026,
                0.029, 0.032, 0.035, 0.038, 0.024, 0.027, 0.030, 0.033]
for i, (perturb, (rev22, rev23)) in enumerate(zip(_id_perturbs, _SEEDS[36:52])):
    # identity_perturb > tolerance(0.01) so identity check fires
    table   = _make_table(rev22, rev23, identity_perturb=perturb)
    ev      = _evidence(table)
    gp      = _val(table, "Gross Profit", 1)   # already perturbed in table
    question = "What was Gross Profit in 2022?"
    answer   = f"Gross Profit in 2022 was {gp}."
    r = run_verify(question, ev, answer)
    s = sig(r)
    rev_val  = _val(table, "Revenue",       1)
    cogs_val = _val(table, "Cost of Sales", 1)
    expected_gp = rev_val - cogs_val
    row = {
        "case_id": f"c2c_{i:03d}",
        "case_type": "identity_near_miss",
        "case_description": (f"GP in table={gp} vs expected Rev-COGS={expected_gp} "
                             f"({perturb*100:.1f}% off identity)"),
        "gold_answer": str(gp),
        "rule_decision": r["decision"],
    }
    for k in SIGNAL_KEYS:
        row[k] = s.get(k, 0)
    ambig_rows.append(row)

print(f"\n  Total ambiguous rows: {len(ambig_rows)}")

# ──────────────────────────────────────────────────────────────────────────────
# PART D — Signal diversity check
# ──────────────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("PART D — Signal diversity check")
print("=" * 70)

# Load ACCEPT rows
accept_rows = []
with open(EVAL_DIR / "signals_v4_accept.csv") as f:
    for row in csv.DictReader(f):
        accept_rows.append({k: float(row[k]) if k in SIGNAL_KEYS else row[k]
                            for k in list(row.keys())})

# Split FLAG by error type for detailed check
flag_by_type = defaultdict(list)
for r in flag_rows:
    flag_by_type[r["error_type"]].append(r)

print(f"\n  Counts: ACCEPT={len(accept_rows)}  FLAG={len(flag_rows)}  AMBIG={len(ambig_rows)}")
print(f"  FLAG breakdown: "
      f"value_error={type_counts['value_error']}  "
      f"period_error={type_counts['period_error']}  "
      f"scale_error={type_counts['scale_error']}")

def _mean_sig(rows, key):
    return mean([float(r.get(key, 0)) for r in rows])

print()
print(f"{'Signal':<38} {'ACCEPT':>7} {'FLAG':>7} {'AMBIG':>7}  "
      f"{'FLAG_ve':>7} {'FLAG_pe':>7} {'FLAG_se':>7}  Sep?")
print("─" * 95)
for k in SIGNAL_KEYS:
    a = _mean_sig(accept_rows, k)
    f = _mean_sig(flag_rows,   k)
    m = _mean_sig(ambig_rows,  k)
    ve = _mean_sig(flag_by_type["value_error"],  k)
    pe = _mean_sig(flag_by_type["period_error"], k)
    se = _mean_sig(flag_by_type["scale_error"],  k)
    sep = "YES" if (abs(f - a) >= 0.05 or abs(ve - a) >= 0.05 or
                    abs(pe - a) >= 0.05 or abs(se - a) >= 0.05) else "no"
    print(f"  {k:<36} {a:>7.4f} {f:>7.4f} {m:>7.4f}  "
          f"{ve:>7.4f} {pe:>7.4f} {se:>7.4f}  {sep}")

# ── Specific signal checks ───────────────────────────────────────────────────
print()
print("  Required signal checks:")
ve_scale = mean([float(r["scale_mismatch_count"]) for r in flag_by_type["scale_error"]])
pe_strict = mean([float(r["pnl_period_strict_mismatch_count"]) for r in flag_by_type["period_error"]])
ve_cov = mean([float(r["coverage_ratio"]) for r in flag_by_type["value_error"]])
c2c_idfail = mean([float(r["pnl_identity_fail_count"])
                   for r in ambig_rows if r["case_type"] == "identity_near_miss"])

print(f"  scale_mismatch_count for scale_error FLAG:     {ve_scale:.3f}  "
      f"{'PASS ✓' if ve_scale > 0 else 'FAIL ✗'}")
print(f"  pnl_period_strict for period_error FLAG:       {pe_strict:.3f}  "
      f"{'PASS ✓' if pe_strict > 0 else 'FAIL ✗'}")
print(f"  coverage_ratio for value_error FLAG:           {ve_cov:.3f}  "
      f"{'PASS ✓' if ve_cov == 0.0 else 'NOTE: some grounded'}")
print(f"  pnl_identity_fail for C2c ambiguous:           {c2c_idfail:.3f}  "
      f"{'PASS ✓' if c2c_idfail > 0 else 'FAIL ✗'}")
print()
if ve_scale == 0 or pe_strict == 0 or c2c_idfail == 0:
    print("  !! DIVERSITY CHECK FAILED — stopping before save.")
    sys.exit(1)
print("  Diversity check PASSED.")

# ──────────────────────────────────────────────────────────────────────────────
# Save datasets
# ──────────────────────────────────────────────────────────────────────────────
def write_csv(path, rows, fieldnames):
    if not rows:
        print(f"  WARNING: 0 rows — skipping {path.name}")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved {len(rows):>3} rows → {path.name}")

FLAG_FIELDS = (["case_id", "label", "source", "error_type",
                "correct_answer", "perturbed_answer", "note",
                "question_year", "table_years", "table_scale", "answer_scale"]
               + SIGNAL_KEYS)
AMBIG_FIELDS = (["case_id", "case_type", "case_description", "gold_answer", "rule_decision"]
                + SIGNAL_KEYS)

print()
print("=" * 70)
print("Saving files")
print("=" * 70)
write_csv(EVAL_DIR / "signals_v4_flag.csv",             flag_rows,  FLAG_FIELDS)
write_csv(EVAL_DIR / "tier3_ambiguous_UNLABELED.csv",   ambig_rows, AMBIG_FIELDS)

# ──────────────────────────────────────────────────────────────────────────────
# Print all 60 ambiguous rows
# ──────────────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("All 60 ambiguous rows")
print("=" * 70)
print(f"  {'case_id':<18} {'type':<20} {'cov':>5} {'rel_err':>8} "
      f"{'scale_mm':>9} {'per_mm':>7} {'id_fail':>8} {'rule_dec':>9}  gold")
print("  " + "─" * 100)
for r in ambig_rows:
    print(f"  {r['case_id']:<18} {r['case_type']:<20} "
          f"{float(r['coverage_ratio']):>5.2f} "
          f"{float(r['max_relative_error']):>8.4f} "
          f"{int(float(r['scale_mismatch_count'])):>9} "
          f"{int(float(r['period_mismatch_count'])):>7} "
          f"{int(float(r['pnl_identity_fail_count'])):>8} "
          f"{r['rule_decision']:>9}  "
          f"{str(r['gold_answer'])[:25]}")

print()
print("=" * 70)
print("FINAL ROW COUNTS")
print("=" * 70)
print(f"  signals_v4_accept.csv              : {len(accept_rows):>4} rows  (TAT-QA gold, unchanged)")
print(f"  signals_v4_flag.csv                : {len(flag_rows):>4} rows  (synthetic)")
print(f"  tier3_ambiguous_UNLABELED.csv      : {len(ambig_rows):>4} rows  (awaiting manual labels)")

print()
print("NOTE on value_error FLAG cases:")
print("  max_relative_error = 0.0 for all value_error FLAG cases.")
print("  Root cause: grounding engine cutoff is 5×tolerance = 5%.")
print("  A 15-25% off value never grounds → relative_error not recorded.")
print("  The distinguishing signal for value_error is coverage_ratio=0.0 +")
print("  unsupported_claims_count=1 (distinct from scale/period FLAG = coverage=1.0).")
