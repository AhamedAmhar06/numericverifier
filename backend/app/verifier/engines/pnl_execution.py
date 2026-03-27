"""P&L execution engine: identity checks, margin checks, YoY baseline, and claim-level execution."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re

from .finance_formulas import (
    yoy_growth, margin, gross_profit_check,
    operating_income_check, net_income_check,
)


# ---------------------------------------------------------------------------
# Standard P&L ratio library (Layer 2)
# ---------------------------------------------------------------------------

# Single-period ratios: (numerator_key, denominator_key, ratio_name)
STANDARD_PNL_RATIOS = [
    ("gross_profit",        "revenue",          "gross_margin_pct"),
    ("operating_income",    "revenue",          "operating_margin_pct"),
    ("net_income",          "revenue",          "net_margin_pct"),
    ("tax_expense",         "operating_income", "effective_tax_rate_pct"),
    ("cogs",                "revenue",          "cogs_ratio_pct"),
    ("operating_expenses",  "revenue",          "opex_ratio_pct"),
    ("operating_expenses",  "gross_profit",     "opex_to_gp_pct"),
    ("r_and_d",             "revenue",          "rd_ratio_pct"),
    ("sga",                 "revenue",          "sga_ratio_pct"),
    ("net_income",          "operating_income", "ni_to_op_pct"),
]

# YoY change ratios: (line_item_key, ratio_name)
STANDARD_YOY_RATIOS = [
    ("revenue",             "revenue_yoy_pct"),
    ("gross_profit",        "gross_profit_yoy_pct"),
    ("operating_income",    "operating_income_yoy_pct"),
    ("net_income",          "net_income_yoy_pct"),
    ("operating_expenses",  "opex_yoy_pct"),
    ("cogs",                "cogs_yoy_pct"),
    ("tax_expense",         "tax_yoy_pct"),
]

# Maps ratio-library key names → pnl_parser canonical item keys (where they differ)
_RATIO_KEY_MAP: Dict[str, str] = {
    "tax_expense": "taxes",
    "r_and_d":     "research_and_development",
    "sga":         "selling_general_administrative",
}


@dataclass
class PnLCheckResult:
    """Result of P&L domain checks."""
    identity_fail_count: int = 0
    margin_fail_count: int = 0
    missing_yoy_baseline: bool = False
    violations: List[str] = field(default_factory=list)


def _get(items: Dict[str, Dict[str, float]], key: str, period: str) -> Optional[float]:
    if key not in items or period not in items[key]:
        return None
    return items[key][period]


def _check_identity_for_period(
    items: Dict[str, Dict[str, float]],
    period: str,
    tolerance: float,
) -> List[str]:
    violations = []
    rev = _get(items, "revenue", period)
    cogs = _get(items, "cogs", period)
    gp = _get(items, "gross_profit", period)
    opex = _get(items, "operating_expenses", period)
    op_inc = _get(items, "operating_income", period)
    taxes = _get(items, "taxes", period)
    interest = _get(items, "interest", period)
    net = _get(items, "net_income", period)

    if rev is not None and cogs is not None and gp is not None:
        expected_gp = gross_profit_check(rev, cogs)
        if abs(expected_gp - gp) > tolerance * max(abs(gp), 1e-9):
            violations.append("pnl_identity_mismatch: Gross Profit != Revenue - COGS")
    if gp is not None and opex is not None and op_inc is not None:
        expected_op = operating_income_check(gp, opex)
        if abs(expected_op - op_inc) > tolerance * max(abs(op_inc), 1e-9):
            violations.append("pnl_identity_mismatch: Operating Income != Gross Profit - Operating Expenses")
    if op_inc is not None and net is not None and taxes is not None and interest is not None:
        expected_net = net_income_check(op_inc, taxes, interest)
        if abs(expected_net - net) > tolerance * max(abs(net), 1e-9):
            violations.append("pnl_identity_mismatch: Net Income != Operating Income - Taxes - Interest")
    return violations


def _check_margins_for_period(
    items: Dict[str, Dict[str, float]],
    period: str,
    tolerance: float,
) -> List[str]:
    violations = []
    rev = _get(items, "revenue", period)
    gp = _get(items, "gross_profit", period)
    op_inc = _get(items, "operating_income", period)
    if rev is not None and rev != 0 and gp is not None:
        gm = margin(gp, rev)
        if gm is not None and (gm < -0.01 or gm > 1.01):
            violations.append("pnl_margin_mismatch: Gross margin out of range")
    if rev is not None and rev != 0 and op_inc is not None:
        om = margin(op_inc, rev)
        if om is not None and (om < -1.01 or om > 1.01):
            violations.append("pnl_margin_mismatch: Operating margin out of range")
    return violations


def _yoy_periods_from_question(question: str) -> Optional[List[str]]:
    q = question.lower()
    if "yoy" not in q and "year over year" not in q and "year-over-year" not in q:
        return None
    years = re.findall(r"\b(20\d{2})\b", question)
    if len(years) >= 2:
        return list(dict.fromkeys(years))[:2]
    if len(years) == 1:
        return years
    return None


def run_pnl_checks(
    question: str,
    pnl_table: Any,
    tolerance: float = 0.01,
    margin_asked_or_claimed: bool = False,
) -> PnLCheckResult:
    """Run P&L domain checks: identities, margins, YoY baseline."""
    result = PnLCheckResult()
    if pnl_table is None:
        return result
    items = getattr(pnl_table, "items", {}) or {}
    periods = getattr(pnl_table, "periods", []) or []
    if not periods:
        return result

    for period in periods:
        id_v = _check_identity_for_period(items, period, tolerance)
        result.violations.extend(id_v)
        result.identity_fail_count += len(id_v)
        if margin_asked_or_claimed:
            m_v = _check_margins_for_period(items, period, tolerance)
            result.violations.extend(m_v)
            result.margin_fail_count += len(m_v)

    yoy = _yoy_periods_from_question(question)
    if yoy is not None and len(yoy) >= 1:
        for p in yoy:
            if p not in periods:
                result.missing_yoy_baseline = True
                result.violations.append("missing_yoy_baseline")
                break
    return result


# ---------------------------------------------------------------------------
# Claim-level semantic execution (Phase 5)
# ---------------------------------------------------------------------------

def execute_claim_against_table(
    claim_value: float,
    claim_unit_type: str,
    question: str,
    pnl_table: Any,
    tolerance: float = 0.01,
    scale_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Attempt to verify a claim value by recomputing from the P&L table.

    Returns dict with keys: supported (bool), computed_value (float|None),
    confidence (high|medium|low), formula (str), error (str|None).
    """
    if pnl_table is None:
        return {"supported": False, "computed_value": None, "confidence": None,
                "formula": None, "error": "no_pnl_table"}

    items = getattr(pnl_table, "items", {}) or {}
    periods = getattr(pnl_table, "periods", []) or []
    q_lower = question.lower()

    # pnl_parser multiplies all item values by the table's scale_multiplier
    # (e.g. caption "In millions" → scale_multiplier=1_000_000).  Extracted
    # claim values without a scale suffix are raw (e.g. "72,361"), so we must
    # scale them up to match items.  But when the claim already carries a scale
    # suffix ("211,915 million"), the extractor has already applied the multiplier,
    # so skip normalization to avoid double-scaling.
    scale_multiplier = getattr(getattr(pnl_table, "metadata", None), "scale_multiplier", 1) or 1
    was_normalized = scale_multiplier != 1 and claim_unit_type != "percent" and scale_token is None
    if was_normalized:
        claim_value = claim_value * scale_multiplier

    # Determine target period from question (prefer the most recent year).
    # pnl_parser._normalize_period() may produce FY-prefixed labels ("FY2023"),
    # so bare year tokens from the question ("2023") must be resolved via
    # substring matching before the period lookup.
    #
    # The \b anchor misses years embedded in FY-prefixed tokens ("FY2022")
    # because "FY" and digits are both word chars — no word boundary exists
    # before "2022" in "FY2022".  Add a second pass for FY notation.
    year_matches = re.findall(r"\b(20\d{2})\b", question)
    fy_raw = re.findall(r"\bFY\s*(20\d{2}|\d{2})\b", question, re.IGNORECASE)
    for fy in fy_raw:
        normalized = f"20{fy}" if len(fy) == 2 else fy
        if normalized not in year_matches:
            year_matches.append(normalized)
    if year_matches:
        def _resolve(y):
            """Map bare year 'YYYY' → actual period label, e.g. 'FY2023'."""
            if y in periods:          # exact match (bare-year tables)
                return y
            for p in periods:
                if y in p:            # substring match (FY-prefixed tables)
                    return p
            return None
        resolved = [_resolve(y) for y in year_matches]
        valid_years = [r for r in resolved if r is not None]
        target_period = max(valid_years) if valid_years else max(year_matches)
    else:
        target_period = periods[0] if periods else None
    if not target_period or target_period not in periods:
        return {"supported": False, "computed_value": None, "confidence": None,
                "formula": None, "error": "period_not_found"}

    # Margin claims (check before growth since both may have percent unit_type)
    if "margin" in q_lower:
        margin_result = _try_margin_execution(claim_value, items, target_period, q_lower, tolerance)
        if margin_result["supported"]:
            return margin_result

    # Growth / comparison claims: require two periods for same line item
    if (claim_unit_type == "percent"
            or "growth" in q_lower or "yoy" in q_lower or "change" in q_lower
            or "difference" in q_lower or "differ" in q_lower):
        growth_result = _try_growth_execution(claim_value, items, periods, target_period, q_lower, tolerance)
        if growth_result["supported"]:
            return growth_result

    # Standard P&L ratio library (Layer 2): single-period and YoY ratio formulas.
    # Runs for all percent-unit claims not already handled by margin or growth above.
    # Catches derived metrics like effective_tax_rate, cogs_ratio, opex_to_gp, etc.
    if claim_unit_type == "percent":
        ratio_result = _try_ratio_execution(claim_value, items, target_period, periods, q_lower, tolerance)
        if ratio_result["supported"]:
            return ratio_result
        # Propagate unverifiable flag for downstream signal counting
        if ratio_result.get("unverifiable_claim"):
            return {**ratio_result, "formula": None, "error": "unverifiable_pct_claim"}

    # When normalization was applied (or claim has explicit scale suffix), tighten
    # tolerance across all remaining checks to avoid wrong-period values matching
    # via coincidental proximity (e.g. FY2022 $170,782M within 1% of FY2023 $169,148M).
    effective_tolerance = tolerance / 10 if (scale_token is not None or was_normalized) else tolerance

    # Identity checks: try to match claim against computed identity
    identity_result = _try_identity_execution(claim_value, items, target_period, effective_tolerance)
    if identity_result["supported"]:
        return identity_result

    # Direct lookup (already handled by grounding; low-confidence fallback here).
    direct_tolerance = effective_tolerance
    for key, period_values in items.items():
        if target_period in period_values:
            ev_val = period_values[target_period]
            if ev_val != 0 and abs((claim_value - ev_val) / ev_val) <= direct_tolerance:
                return {"supported": True, "computed_value": ev_val, "confidence": "medium",
                        "formula": f"direct_lookup:{key}:{target_period}", "error": None}

    # Generic derived-value fallback: check V ≈ A - B (or A + B for totals)
    # for every ordered pair of evidence values in the table.  Only fires
    # when the question contains a comparison keyword, so random coincidences
    # in unrelated questions do not produce false positives.
    derived_result = _try_derived_value_check(claim_value, items, q_lower, tolerance)
    if derived_result["supported"]:
        return derived_result

    return {"supported": False, "computed_value": None, "confidence": None,
            "formula": None, "error": "no_matching_formula"}


def _resolve_ratio_key(ratio_key: str, items: dict) -> Optional[str]:
    """Map a ratio-library key to the actual key present in the pnl_table items dict."""
    candidates = [ratio_key, _RATIO_KEY_MAP.get(ratio_key, ratio_key)]
    for k in candidates:
        if k in items:
            return k
    return None


def _try_ratio_execution(
    claim_value: float,
    items: Dict[str, Dict[str, float]],
    target_period: str,
    periods: List[str],
    q_lower: str,
    tolerance: float,
) -> Dict[str, Any]:
    """Verify a percentage claim against the standard P&L ratio library.

    Tries single-period ratios first (e.g. effective_tax_rate = tax/op_income),
    then YoY change ratios when two periods are detectable in the question.

    For each formula both the decimal form (0.2603) and the percent form (26.03)
    of the computed ratio are tested, matching however the claim extractor stored
    the value.

    Returns a result dict with an extra ``unverifiable_claim`` key set to True
    when no formula in the library can be applied (both numerator and denominator
    exist in the table but no formula matched), signalling graceful scope-limit
    rather than a hard unsupported error.
    """
    _not_found = {"supported": False, "computed_value": None, "confidence": None,
                  "formula": None, "error": "ratio_not_matched",
                  "unverifiable_claim": False}

    # ── Single-period ratios ──────────────────────────────────────────────────
    for (num_key, den_key, ratio_name) in STANDARD_PNL_RATIOS:
        actual_num = _resolve_ratio_key(num_key, items)
        actual_den = _resolve_ratio_key(den_key, items)
        if actual_num is None or actual_den is None:
            continue
        num_val = _get_val(items, actual_num, target_period)
        den_val = _get_val(items, actual_den, target_period)
        if num_val is None or den_val is None or den_val == 0:
            continue
        ratio_dec = num_val / den_val          # e.g. 0.2603
        ratio_pct = ratio_dec * 100.0          # e.g. 26.03
        for cv in (ratio_dec, ratio_pct):
            rel_err = abs(claim_value - cv) / abs(cv) if cv != 0 else abs(claim_value)
            if rel_err <= tolerance:
                return {
                    "supported": True, "computed_value": cv, "confidence": "high",
                    "formula": f"ratio:{ratio_name}:{target_period}",
                    "derived_from": [actual_num, actual_den],
                    "error": None, "unverifiable_claim": False,
                }

    # ── YoY change ratios ─────────────────────────────────────────────────────
    # Determine the two periods from the question or fall back to consecutive years.
    year_tokens = re.findall(r"\b(20\d{2})\b", q_lower)
    fy_raw = re.findall(r"\bfy\s*(20\d{2}|\d{2})\b", q_lower)
    for fy in fy_raw:
        n = f"20{fy}" if len(fy) == 2 else fy
        if n not in year_tokens:
            year_tokens.append(n)

    def _res(y: str) -> Optional[str]:
        if y in periods:
            return y
        for p in periods:
            if y in p:
                return p
        return None

    resolved = sorted(set(r for r in (_res(y) for y in year_tokens) if r is not None))
    if len(resolved) >= 2:
        period_t, period_t1 = resolved[-1], resolved[-2]
    else:
        tp_num = re.search(r"(20\d{2})", target_period)
        if tp_num:
            prev = str(int(tp_num.group(1)) - 1)
            period_t  = target_period
            period_t1 = next((p for p in periods if prev in p), None)
        else:
            period_t1 = None

    if period_t1 is not None and period_t1 in periods:
        for (item_key, ratio_name) in STANDARD_YOY_RATIOS:
            actual_key = _resolve_ratio_key(item_key, items)
            if actual_key is None:
                continue
            val_t  = _get_val(items, actual_key, period_t)
            val_t1 = _get_val(items, actual_key, period_t1)
            if val_t is None or val_t1 is None or val_t1 == 0:
                continue
            yoy_dec = (val_t - val_t1) / abs(val_t1)   # e.g. -0.043
            yoy_pct = yoy_dec * 100.0                   # e.g. -4.30
            for cv in (yoy_dec, yoy_pct):
                rel_err = abs(claim_value - cv) / abs(cv) if cv != 0 else abs(claim_value)
                if rel_err <= tolerance:
                    return {
                        "supported": True, "computed_value": cv, "confidence": "high",
                        "formula": f"yoy_ratio:{ratio_name}:{period_t1}->{period_t}",
                        "derived_from": [actual_key],
                        "error": None, "unverifiable_claim": False,
                    }

    # No formula matched — mark as unverifiable (honest scope limit)
    _not_found["unverifiable_claim"] = True
    return _not_found


_DERIVED_COMPARISON_KEYWORDS = frozenset([
    "change", "changed", "difference", "differ", "increase", "decrease",
    "compared", "by how much", "how much did", "grew", "fell", "dropped",
    "rose", "year over year", "yoy",
])


def _try_derived_value_check(
    claim_value: float,
    items: Dict[str, Dict[str, float]],
    q_lower: str,
    tolerance: float,
) -> Dict[str, Any]:
    """Check whether claim_value equals A - B (or A + B) for any ordered pair
    of evidence values from the P&L table.

    - Only fires when the question contains a comparison keyword.
    - Addition is only checked for totals keywords to limit false positives.
    - Uses relative tolerance: abs(V - computed) / max(abs(computed), 1) < tolerance.
    """
    if not any(kw in q_lower for kw in _DERIVED_COMPARISON_KEYWORDS):
        return {"supported": False, "computed_value": None, "confidence": None,
                "formula": None, "error": "no_derived_keywords"}

    check_addition = any(kw in q_lower for kw in ("total", "sum", "combined", "together"))

    # Flatten items into (label, value) pairs
    all_vals = []
    for key, period_vals in items.items():
        for period, val in period_vals.items():
            if val is not None:
                all_vals.append((f"{key}:{period}", float(val)))

    for i, (label_a, val_a) in enumerate(all_vals):
        for j, (label_b, val_b) in enumerate(all_vals):
            if i == j:
                continue
            # Subtraction: V ≈ A - B  (also catches V ≈ abs(A-B) via reverse pair)
            diff = val_a - val_b
            denom = max(abs(diff), 1.0)
            if abs(claim_value - diff) / denom < tolerance:
                return {
                    "supported": True,
                    "computed_value": diff,
                    "confidence": "medium",
                    "formula": f"derived:{label_a} - {label_b}",
                    "error": None,
                }
            # Addition: V ≈ A + B (only for total-type questions)
            if check_addition:
                total = val_a + val_b
                denom_sum = max(abs(total), 1.0)
                if abs(claim_value - total) / denom_sum < tolerance:
                    return {
                        "supported": True,
                        "computed_value": total,
                        "confidence": "medium",
                        "formula": f"derived:{label_a} + {label_b}",
                        "error": None,
                    }

    return {"supported": False, "computed_value": None, "confidence": None,
            "formula": None, "error": "derived_check_not_matched"}


_ITEM_SYNONYMS = {
    "revenue": ["revenue", "revenues", "sales", "turnover", "total revenue"],
    "cogs": ["cogs", "cost of sales", "cost of revenue", "cost of goods sold"],
    "gross_profit": ["gross profit", "gross income"],
    "operating_expenses": ["operating expenses", "opex", "sg&a"],
    "operating_income": ["operating income", "operating profit", "ebit", "ebitda"],
    "net_income": ["net income", "net profit", "profit", "profits", "profit for the year",
                    "profit after tax", "earnings"],
    "taxes": ["tax", "taxes", "income tax"],
    "interest": ["interest", "interest expense"],
}


def _match_item_key(q_lower: str, items: dict) -> list:
    """Match question text to table item keys using synonyms."""
    matched = []
    for key in items:
        if key in q_lower or key.replace("_", " ") in q_lower:
            matched.append(key)
            continue
        for syn in _ITEM_SYNONYMS.get(key, []):
            if syn in q_lower:
                matched.append(key)
                break
    return matched


def _try_growth_execution(claim_value, items, periods, target_period, q_lower, tolerance):
    # Find baseline period (the earlier of the two years mentioned in the question).
    # Also handle FY-prefixed tokens (fy2022 after lower()) that \b misses.
    year_matches = re.findall(r"\b(20\d{2})\b", q_lower)
    fy_raw = re.findall(r"\bfy\s*(20\d{2}|\d{2})\b", q_lower)
    for fy in fy_raw:
        normalized = f"20{fy}" if len(fy) == 2 else fy
        if normalized not in year_matches:
            year_matches.append(normalized)
    baseline = None
    if len(year_matches) >= 2:
        # Resolve raw year strings to actual period labels via substring match.
        def _res_baseline(y):
            if y in periods: return y
            for p in periods:
                if y in p: return p
            return None
        resolved_bl = sorted(set(r for r in (_res_baseline(y) for y in year_matches) if r is not None))
        if len(resolved_bl) >= 2:
            baseline = resolved_bl[0] if target_period == resolved_bl[-1] else min(r for r in resolved_bl if r != target_period)
    if baseline is None:
        # Fall back: derive previous year from target_period's numeric part.
        # Using regex avoids ValueError when target_period is "FY2023" not "2023".
        tp_num = re.search(r"(20\d{2})", target_period)
        if tp_num:
            prev_year = str(int(tp_num.group(1)) - 1)
            baseline = next((p for p in periods if prev_year in p), prev_year)
        else:
            return {"supported": False, "computed_value": None, "confidence": None,
                    "formula": None, "error": "cannot_determine_baseline"}

    if baseline not in periods:
        return {"supported": False, "computed_value": None, "confidence": None,
                "formula": None, "error": "baseline_period_missing"}

    matched_keys = _match_item_key(q_lower, items)
    for key in matched_keys:
        curr = _get_val(items, key, target_period)
        prev = _get_val(items, key, baseline)
        if curr is not None and prev is not None:
            growth_decimal = yoy_growth(curr, prev)
            if growth_decimal is None:
                continue
            growth_pct = growth_decimal * 100.0
            diff = curr - prev
            # Try matching: claim as decimal (0.41), claim as percentage (41.09),
            # and absolute difference
            for computed, label in [
                (growth_decimal, "yoy_growth_decimal"),
                (growth_pct, "yoy_growth_pct"),
                (diff, "yoy_diff"),
            ]:
                # growth_decimal values are tiny (e.g. -0.0096); use a tight minimum
                # so a claim like "48%" (0.48) does not accidentally match within the
                # broad 0.5 floor that makes sense for percentage-point and dollar diffs.
                min_tol = 0.001 if label == "yoy_growth_decimal" else 0.5
                if abs(claim_value - computed) <= max(tolerance * abs(computed), min_tol):
                    return {"supported": True, "computed_value": computed, "confidence": "high",
                            "formula": f"{label}:{key}:{baseline}->{target_period}", "error": None}

    # Also try absolute difference for non-matched items (broader search).
    # Also check abs(diff): LLM may express a negative change as a positive
    # magnitude ("decreased by 11,043") so the extracted claim is positive
    # even though diff = curr - prev is negative.
    if "change" in q_lower or "difference" in q_lower or "differ" in q_lower or "increase" in q_lower or "decrease" in q_lower:
        for key in items:
            curr = _get_val(items, key, target_period)
            prev = _get_val(items, key, baseline)
            if curr is not None and prev is not None:
                diff = curr - prev
                tol_diff = max(tolerance * abs(diff) if diff != 0 else tolerance, 0.5)
                if abs(claim_value - diff) <= tol_diff:
                    return {"supported": True, "computed_value": diff, "confidence": "medium",
                            "formula": f"yoy_diff:{key}:{baseline}->{target_period}", "error": None}
                # magnitude match: "decreased by X" → claim positive, diff negative
                if abs(claim_value - abs(diff)) <= tol_diff:
                    return {"supported": True, "computed_value": abs(diff), "confidence": "medium",
                            "formula": f"yoy_diff_abs:{key}:{baseline}->{target_period}", "error": None}
                growth_decimal = yoy_growth(curr, prev)
                if growth_decimal is not None:
                    growth_pct = growth_decimal * 100.0
                    if abs(claim_value - growth_pct) <= max(tolerance * abs(growth_pct) if growth_pct != 0 else tolerance, 0.5):
                        return {"supported": True, "computed_value": growth_pct, "confidence": "medium",
                                "formula": f"yoy_growth_pct:{key}:{baseline}->{target_period}", "error": None}

    return {"supported": False, "computed_value": None, "confidence": None,
            "formula": None, "error": "growth_formula_not_matched"}


def _try_margin_execution(claim_value, items, target_period, q_lower, tolerance):
    rev = _get_val(items, "revenue", target_period)
    if rev is None or rev == 0:
        return {"supported": False, "computed_value": None, "confidence": None,
                "formula": None, "error": "revenue_missing_for_margin"}

    candidates = [
        ("gross_profit", "gross_margin"),
        ("operating_income", "operating_margin"),
        ("net_income", "net_margin"),
    ]
    for num_key, margin_name in candidates:
        num_val = _get_val(items, num_key, target_period)
        if num_val is not None:
            computed = margin(num_val, rev)
            if computed is not None:
                # Try both decimal (0.37) and percentage (37.0) forms
                for cv in [computed, computed * 100.0]:
                    if abs(claim_value - cv) <= max(tolerance * abs(cv) if cv != 0 else tolerance, 0.005):
                        return {"supported": True, "computed_value": cv, "confidence": "high",
                                "formula": f"margin:{num_key}/revenue:{target_period}", "error": None}

    return {"supported": False, "computed_value": None, "confidence": None,
            "formula": None, "error": "margin_formula_not_matched"}


def _try_identity_execution(claim_value, items, target_period, tolerance):
    identities = [
        (["revenue", "cogs"], gross_profit_check, "gross_profit = revenue - cogs"),
        (["gross_profit", "operating_expenses"], operating_income_check, "op_income = gp - opex"),
    ]
    for operand_keys, func, formula_name in identities:
        vals = [_get_val(items, k, target_period) for k in operand_keys]
        if all(v is not None for v in vals):
            computed = func(*vals)
            if abs(claim_value - computed) <= tolerance * max(abs(computed), 1e-9):
                return {"supported": True, "computed_value": computed, "confidence": "high",
                        "formula": f"identity:{formula_name}:{target_period}", "error": None}

    # Net income with optional taxes/interest
    op_inc = _get_val(items, "operating_income", target_period)
    if op_inc is not None:
        taxes = _get_val(items, "taxes", target_period) or 0.0
        interest = _get_val(items, "interest", target_period) or 0.0
        computed = net_income_check(op_inc, taxes, interest)
        if abs(claim_value - computed) <= tolerance * max(abs(computed), 1e-9):
            return {"supported": True, "computed_value": computed, "confidence": "high",
                    "formula": f"identity:net_income:{target_period}", "error": None}

    return {"supported": False, "computed_value": None, "confidence": None,
            "formula": None, "error": None}


def _get_val(items, key, period):
    return items.get(key, {}).get(period)
