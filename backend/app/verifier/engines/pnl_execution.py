"""P&L execution engine: identity checks, margin checks, YoY baseline, and claim-level execution."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re

from .finance_formulas import (
    yoy_growth, margin, gross_profit_check,
    operating_income_check, net_income_check,
)


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

    # Determine target period from question (prefer the most recent year)
    year_matches = re.findall(r"\b(20\d{2})\b", question)
    if year_matches:
        valid_years = [y for y in year_matches if y in periods]
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

    # Growth claims: require two periods for same line item
    if claim_unit_type == "percent" or "growth" in q_lower or "yoy" in q_lower or "change" in q_lower:
        growth_result = _try_growth_execution(claim_value, items, periods, target_period, q_lower, tolerance)
        if growth_result["supported"]:
            return growth_result

    # Identity checks: try to match claim against computed identity
    identity_result = _try_identity_execution(claim_value, items, target_period, tolerance)
    if identity_result["supported"]:
        return identity_result

    # Direct lookup (already handled by grounding; low-confidence fallback here)
    for key, period_values in items.items():
        if target_period in period_values:
            ev_val = period_values[target_period]
            if ev_val != 0 and abs((claim_value - ev_val) / ev_val) <= tolerance:
                return {"supported": True, "computed_value": ev_val, "confidence": "medium",
                        "formula": f"direct_lookup:{key}:{target_period}", "error": None}

    return {"supported": False, "computed_value": None, "confidence": None,
            "formula": None, "error": "no_matching_formula"}


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
    # Find baseline period (the earlier of the two years mentioned in the question)
    year_matches = re.findall(r"\b(20\d{2})\b", q_lower)
    baseline = None
    if len(year_matches) >= 2:
        valid = sorted(set(y for y in year_matches if y in periods))
        if len(valid) >= 2:
            baseline = valid[0] if target_period == valid[-1] else min(y for y in valid if y != target_period)
    if baseline is None:
        try:
            baseline = str(int(target_period) - 1)
        except ValueError:
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
                if abs(claim_value - computed) <= max(tolerance * abs(computed), 0.5):
                    return {"supported": True, "computed_value": computed, "confidence": "high",
                            "formula": f"{label}:{key}:{baseline}->{target_period}", "error": None}

    # Also try absolute difference for non-matched items (broader search)
    if "change" in q_lower or "difference" in q_lower or "increase" in q_lower or "decrease" in q_lower:
        for key in items:
            curr = _get_val(items, key, target_period)
            prev = _get_val(items, key, baseline)
            if curr is not None and prev is not None:
                diff = curr - prev
                if abs(claim_value - diff) <= max(tolerance * abs(diff) if diff != 0 else tolerance, 0.5):
                    return {"supported": True, "computed_value": diff, "confidence": "medium",
                            "formula": f"yoy_diff:{key}:{baseline}->{target_period}", "error": None}
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
