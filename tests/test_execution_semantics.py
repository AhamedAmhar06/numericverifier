"""Tests for semantic execution engine and finance formulas (Phase 5)."""
import pytest
from backend.app.verifier.engines.finance_formulas import (
    yoy_growth, margin, gross_profit_check,
    operating_income_check, net_income_check,
)
from backend.app.verifier.engines.pnl_execution import (
    execute_claim_against_table, run_pnl_checks,
)
from backend.app.verifier.pnl_parser import PnLTable


def _pnl_table():
    return PnLTable(
        periods=["2022", "2023"],
        items={
            "revenue": {"2022": 500000, "2023": 620000},
            "cogs": {"2022": 200000, "2023": 250000},
            "gross_profit": {"2022": 300000, "2023": 370000},
            "operating_expenses": {"2022": 100000, "2023": 120000},
            "operating_income": {"2022": 200000, "2023": 250000},
            "taxes": {"2022": 30000, "2023": 38000},
            "interest": {"2022": 20000, "2023": 22000},
            "net_income": {"2022": 150000, "2023": 190000},
        },
        row_label_by_key={},
    )


# --- Finance formulas ---
def test_yoy_growth():
    assert abs(yoy_growth(620000, 500000) - 0.24) < 1e-9

def test_yoy_growth_zero_baseline():
    assert yoy_growth(100, 0) is None

def test_margin_basic():
    assert abs(margin(300000, 500000) - 0.6) < 1e-9

def test_margin_zero_denom():
    assert margin(100, 0) is None

def test_gross_profit_check():
    assert abs(gross_profit_check(500000, 200000) - 300000) < 1e-9

def test_operating_income_check():
    assert abs(operating_income_check(300000, 100000) - 200000) < 1e-9

def test_net_income_check():
    assert abs(net_income_check(200000, 30000, 20000) - 150000) < 1e-9


# --- Claim-level execution ---
def test_identity_execution_gross_profit():
    pnl = _pnl_table()
    result = execute_claim_against_table(300000, "amount", "What was gross profit in 2022?", pnl, 0.01)
    assert result["supported"] is True
    assert result["confidence"] == "high"

def test_growth_execution():
    pnl = _pnl_table()
    growth = yoy_growth(620000, 500000)
    result = execute_claim_against_table(growth, "percent", "What was revenue YoY growth in 2023?", pnl, 0.01)
    assert result["supported"] is True

def test_margin_execution():
    pnl = _pnl_table()
    gm = margin(370000, 620000)
    result = execute_claim_against_table(gm, "percent", "What was gross profit margin in 2023?", pnl, 0.01)
    assert result["supported"] is True

def test_execution_missing_period():
    pnl = _pnl_table()
    result = execute_claim_against_table(100, "amount", "What was revenue in 2021?", pnl, 0.01)
    assert result["supported"] is False
    assert result["error"] == "period_not_found"


# --- run_pnl_checks ---
def test_pnl_checks_identity_pass():
    pnl = _pnl_table()
    result = run_pnl_checks("What was revenue?", pnl, tolerance=0.01)
    assert result.identity_fail_count == 0

def test_pnl_checks_yoy_missing():
    pnl = PnLTable(periods=["2023"], items={"revenue": {"2023": 100}}, row_label_by_key={})
    result = run_pnl_checks("What was YoY growth in 2022?", pnl, tolerance=0.01)
    assert result.missing_yoy_baseline is True
