"""Generate structured P&L evaluation cases with controlled perturbations.

Produces cases_v2.json with 80+ cases across categories:
- correct (ACCEPT): exact match to evidence
- arithmetic_error (FLAG): value far off from evidence (>10%)
- scale_error (FLAG): claim uses wrong scale (e.g., millions when evidence is raw)
- period_error (FLAG): question asks for period not in table
- identity_error (FLAG): wrong value for identity-checkable items
- missing_evidence (FLAG): non-P&L table
- ambiguous_grounding (ACCEPT): same value in multiple cells but context resolves
- multi_claim (ACCEPT): multiple correct claims

Each case: {id, question, evidence, candidate_answer, expected_decision, notes, category}
"""
import json
import random
from pathlib import Path

random.seed(42)

_COMPANIES = [
    {"name": "AlphaCorp", "revenue": [500000, 620000], "cogs": [200000, 250000],
     "opex": [100000, 120000], "taxes": [30000, 38000], "interest": [20000, 22000]},
    {"name": "BetaInc", "revenue": [800000, 960000], "cogs": [350000, 420000],
     "opex": [150000, 180000], "taxes": [50000, 60000], "interest": [25000, 30000]},
    {"name": "GammaLtd", "revenue": [1200000, 1100000], "cogs": [600000, 550000],
     "opex": [200000, 190000], "taxes": [80000, 72000], "interest": [40000, 36000]},
    {"name": "DeltaGroup", "revenue": [300000, 345000], "cogs": [120000, 138000],
     "opex": [60000, 69000], "taxes": [18000, 20700], "interest": [12000, 13800]},
]

_PERIODS = ["2022", "2023"]


def _build_table(company):
    rev = company["revenue"]
    cogs = company["cogs"]
    gp = [rev[i] - cogs[i] for i in range(2)]
    opex = company["opex"]
    op_inc = [gp[i] - opex[i] for i in range(2)]
    taxes = company["taxes"]
    interest = company["interest"]
    net = [op_inc[i] - taxes[i] - interest[i] for i in range(2)]
    return {
        "columns": ["Line Item", "2022", "2023"],
        "rows": [
            ["Revenue", str(rev[0]), str(rev[1])],
            ["COGS", str(cogs[0]), str(cogs[1])],
            ["Gross Profit", str(gp[0]), str(gp[1])],
            ["Operating Expenses", str(opex[0]), str(opex[1])],
            ["Operating Income", str(op_inc[0]), str(op_inc[1])],
            ["Taxes", str(taxes[0]), str(taxes[1])],
            ["Interest", str(interest[0]), str(interest[1])],
            ["Net Income", str(net[0]), str(net[1])],
        ],
        "units": {},
    }


def _evidence(table):
    return {"type": "table", "content": table}


def _val(table, line_item, period_idx):
    for row in table["rows"]:
        if row[0].lower() == line_item.lower():
            return int(row[period_idx + 1])
    return None


cases = []
case_id = 0


def _add(question, evidence, answer, expected, category, notes=""):
    global case_id
    case_id += 1
    cases.append({
        "id": f"case_{case_id:03d}",
        "question": question,
        "evidence": evidence,
        "candidate_answer": answer,
        "expected_decision": expected,
        "category": category,
        "notes": notes,
    })


for co in _COMPANIES:
    table = _build_table(co)
    ev = _evidence(table)
    name = co["name"]

    for pi, period in enumerate(_PERIODS):
        # --- ACCEPT: correct direct lookup ---
        for line_item in ["Revenue", "COGS", "Gross Profit", "Operating Income", "Net Income"]:
            val = _val(table, line_item, pi)
            if val is not None:
                _add(f"What was {line_item} in {period} for {name}?", ev,
                     f"{line_item} in {period} was {val}.", "ACCEPT", "correct",
                     f"Direct lookup {line_item} {period}")

        # --- FLAG: arithmetic error (value >20% off, outside tolerance) ---
        rev = _val(table, "Revenue", pi)
        if rev:
            wrong = int(rev * random.choice([1.25, 0.70, 1.50, 0.50]))
            _add(f"What was revenue in {period}?", ev,
                 f"Revenue in {period} was {wrong}.", "FLAG", "arithmetic_error",
                 f"Off by {abs(wrong - rev)} ({abs(wrong - rev)/rev:.0%})")

        # --- FLAG: identity error (wrong gross profit, >20% off) ---
        gp = _val(table, "Gross Profit", pi)
        if gp:
            wrong_gp = int(gp * random.choice([1.30, 0.60]))
            _add(f"What was gross profit in {period}?", ev,
                 f"Gross profit in {period} was {wrong_gp}.", "FLAG", "identity_error",
                 f"Identity violated: GP value wrong by {abs(wrong_gp - gp)/gp:.0%}")

        # --- FLAG: period error (ask for period not in table) ---
        _add(f"What was revenue in 2021 for {name}?", ev,
             f"Revenue in 2021 was {rev}.", "FLAG", "period_error",
             "2021 not in evidence")

        # --- FLAG: scale error (claim in millions but evidence in raw) ---
        if rev:
            claim_val = rev / 1_000_000
            _add(f"What was revenue in {period}?", ev,
                 f"Revenue in {period} was {claim_val:.2f} million.", "FLAG", "scale_error",
                 "Claim uses 'million' scale but evidence is in raw units")

    # --- FLAG: missing evidence (non-P&L table) ---
    bad_table = {"columns": ["Product", "Sales"], "rows": [["Widget", "100"]], "units": {}}
    _add(f"What was revenue for {name}?", _evidence(bad_table),
         "Revenue was 100.", "FLAG", "missing_evidence",
         "Non-P&L table")

    # --- ACCEPT: multi-claim ---
    rev_22 = _val(table, "Revenue", 0)
    cogs_22 = _val(table, "COGS", 0)
    _add(f"What were revenue and COGS in 2022 for {name}?", ev,
         f"Revenue was {rev_22} and COGS was {cogs_22} in 2022.", "ACCEPT", "multi_claim",
         "Two claims both correct")

    # --- ACCEPT: ambiguous grounding resolved by context ---
    _add(f"What was revenue in 2022?",
         _evidence({"columns": ["Line Item", "2022", "2023"],
                     "rows": [["Revenue", "500", "500"], ["COGS", "200", "200"],
                              ["Gross Profit", "300", "300"]], "units": {}}),
         "Revenue in 2022 was 500.", "ACCEPT", "ambiguous_grounding",
         "Multiple cells have value 500; context-aware grounding resolves via line item + period")


assert len(cases) >= 80, f"Only {len(cases)} cases generated"

output_path = Path(__file__).resolve().parent.parent / "cases_v2.json"
with open(output_path, "w") as f:
    json.dump(cases, f, indent=2)
print(f"Generated {len(cases)} cases -> {output_path}")
