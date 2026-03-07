"""Deterministic finance formula library for P&L verification.

Each function uses Decimal internally and returns float at boundary.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def yoy_growth(current: float, previous: float) -> Optional[float]:
    """Year-over-year growth rate: (current - previous) / previous."""
    prev = _dec(previous)
    if prev == 0:
        return None
    result = (_dec(current) - prev) / prev
    return float(result)


def margin(numerator: float, denominator: float) -> Optional[float]:
    """Margin ratio: numerator / denominator (e.g., gross_profit / revenue)."""
    denom = _dec(denominator)
    if denom == 0:
        return None
    return float(_dec(numerator) / denom)


def gross_profit_check(revenue: float, cogs: float) -> float:
    """Expected gross profit = revenue - cogs."""
    return float(_dec(revenue) - _dec(cogs))


def operating_income_check(gross_profit: float, operating_expenses: float) -> float:
    """Expected operating income = gross_profit - operating_expenses."""
    return float(_dec(gross_profit) - _dec(operating_expenses))


def net_income_check(
    operating_income: float,
    taxes: float = 0.0,
    interest: float = 0.0,
) -> float:
    """Expected net income = operating_income - taxes - interest."""
    return float(_dec(operating_income) - _dec(taxes) - _dec(interest))
