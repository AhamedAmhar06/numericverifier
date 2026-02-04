"""P&L execution engine: identity checks, margin checks, YoY baseline existence."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re


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
    """Check accounting identities for one period. Return list of violation messages."""
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
        expected_gp = rev - cogs
        if abs(expected_gp - gp) > tolerance * max(abs(gp), 1e-9):
            violations.append("pnl_identity_mismatch: Gross Profit != Revenue - COGS")
    if gp is not None and opex is not None and op_inc is not None:
        expected_op = gp - opex
        if abs(expected_op - op_inc) > tolerance * max(abs(op_inc), 1e-9):
            violations.append("pnl_identity_mismatch: Operating Income != Gross Profit - Operating Expenses")
    if op_inc is not None and net is not None:
        subtract = 0.0
        if taxes is not None:
            subtract += taxes
        if interest is not None:
            subtract += interest
        expected_net = op_inc - subtract
        if abs(expected_net - net) > tolerance * max(abs(net), 1e-9):
            violations.append("pnl_identity_mismatch: Net Income != Operating Income - Taxes - Interest")
    return violations


def _check_margins_for_period(
    items: Dict[str, Dict[str, float]],
    period: str,
    tolerance: float,
) -> List[str]:
    """Check that gross/operating margin formulas hold if table had margin rows. Currently no separate margin row; used when claim comparison runs."""
    violations = []
    rev = _get(items, "revenue", period)
    gp = _get(items, "gross_profit", period)
    op_inc = _get(items, "operating_income", period)
    if rev is not None and rev != 0 and gp is not None:
        expected_gm = gp / rev
        if expected_gm < -0.01 or expected_gm > 1.01:
            violations.append("pnl_margin_mismatch: Gross margin out of range")
    if rev is not None and rev != 0 and op_inc is not None:
        expected_om = op_inc / rev
        if expected_om < -1.01 or expected_om > 1.01:
            violations.append("pnl_margin_mismatch: Operating margin out of range")
    return violations


def _yoy_periods_from_question(question: str) -> Optional[List[str]]:
    """If question asks YoY, try to extract two period references (e.g. 2021, 2022). Return [baseline, current] or None."""
    q = question.lower()
    if "yoy" not in q and "year over year" not in q and "year-over-year" not in q:
        return None
    # Extract years (4 digits)
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
    """
    Run P&L domain checks: identities, margins (if asked/claimed), YoY baseline.
    pnl_table: PnLTable from pnl_parser.parse_pnl_table.
    """
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
