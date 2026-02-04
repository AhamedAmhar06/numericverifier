"""Integration tests for P&L-only verification flow."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# P&L Layout A: first column = line items, rest = periods
_PNL_TABLE_ACCEPT = {
    "type": "table",
    "content": {
        "columns": ["Line Item", "2022", "2023"],
        "rows": [
            ["Revenue", "100", "120"],
            ["COGS", "40", "50"],
            ["Gross Profit", "60", "70"],
        ],
        "units": {"Revenue": "dollars"},
    },
}


def test_health_endpoint():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_verify_only_accept_case():
    """Test verify-only with P&L table: correct lookup -> ACCEPT or FLAG (coverage)."""
    request_data = {
        "question": "What was revenue in 2022?",
        "evidence": _PNL_TABLE_ACCEPT,
        "candidate_answer": "Revenue was 100.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "decision" in data
    assert "rationale" in data
    assert "signals" in data
    assert "claims" in data
    assert "grounding" in data
    assert "verification" in data
    assert "report" in data
    assert data["decision"] in ["ACCEPT", "REPAIR", "FLAG"]
    assert data.get("engine_used") == "pnl"
    assert data.get("domain", {}).get("table_type") == "pnl"


def test_verify_only_text_evidence():
    """P&L verifier requires table evidence -> FLAG."""
    request_data = {
        "question": "What was the revenue?",
        "evidence": {
            "type": "text",
            "content": "The company reported revenue of 5000000 dollars in Q1 2024.",
        },
        "candidate_answer": "Revenue was $5,000,000.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "FLAG"
    assert "table evidence" in data["rationale"].lower() or "pnl" in data["rationale"].lower()


def test_pnl_identity_accept():
    """P&L identity correct (Gross Profit = Revenue - COGS) -> ACCEPT."""
    request_data = {
        "question": "What was gross profit in 2022?",
        "evidence": _PNL_TABLE_ACCEPT,
        "candidate_answer": "Gross profit was 60.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["engine_used"] == "pnl"
    assert data["signals"].get("pnl_identity_fail_count", 0) == 0
    assert data["decision"] in ["ACCEPT", "FLAG"]


def test_pnl_accept_with_temporal_in_answer():
    """CASE 1: Answer contains year (2022); temporal must not reduce coverage -> ACCEPT."""
    request_data = {
        "question": "What was the gross profit in 2022?",
        "evidence": _PNL_TABLE_ACCEPT,
        "candidate_answer": "The gross profit in 2022 was 60.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["engine_used"] == "pnl"
    assert data["signals"].get("coverage_ratio") == 1.0
    assert data["signals"].get("unsupported_claims_count", 0) == 0
    assert data["decision"] == "ACCEPT"


def test_pnl_identity_repair():
    """P&L table with wrong identity (Gross Profit row != Revenue - COGS) -> pnl_identity_fail_count > 0, REPAIR."""
    table_wrong_identity = {
        "type": "table",
        "content": {
            "columns": ["Line Item", "2022"],
            "rows": [
                ["Revenue", "100"],
                ["COGS", "40"],
                ["Gross Profit", "50"],
            ],
            "units": {},
        },
    }
    request_data = {
        "question": "What was gross profit in 2022?",
        "evidence": table_wrong_identity,
        "candidate_answer": "Gross profit was 50.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["engine_used"] == "pnl"
    assert data["signals"].get("pnl_identity_fail_count", 0) > 0
    assert data["decision"] in ["REPAIR", "FLAG"]


def test_pnl_vague_answer_flag():
    """No numeric answer with P&L table -> FLAG."""
    request_data = {
        "question": "What was revenue in 2022?",
        "evidence": _PNL_TABLE_ACCEPT,
        "candidate_answer": "Revenue increased significantly.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "FLAG"
    assert "no numeric" in data["rationale"].lower() or "cannot verify" in data["rationale"].lower()


def test_pnl_yoy_missing_baseline_flag():
    """YoY question but baseline period missing in table -> FLAG, pnl_missing_baseline_count > 0."""
    request_data = {
        "question": "What was the YoY growth from 2021 to 2022?",
        "evidence": _PNL_TABLE_ACCEPT,
        "candidate_answer": "YoY growth was 20%.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "FLAG"
    assert data["signals"].get("pnl_missing_baseline_count", 0) > 0 or "baseline" in data["rationale"].lower() or "yoy" in data["rationale"].lower()


def test_non_pnl_table_flag():
    """Non-P&L table (random columns) -> FLAG."""
    request_data = {
        "question": "What is the value?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Category", "Count"],
                "rows": [["A", "10"], ["B", "20"]],
                "units": {},
            },
        },
        "candidate_answer": "The value is 10.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "FLAG"
    assert "not a P&L" in data["rationale"] or "Income Statement" in data["rationale"]


def test_pnl_margin_accept():
    """P&L margin check correct (Gross Margin = Gross Profit / Revenue) -> ACCEPT."""
    table_with_margin = {
        "type": "table",
        "content": {
            "columns": ["Line Item", "2022"],
            "rows": [
                ["Revenue", "100"],
                ["COGS", "40"],
                ["Gross Profit", "60"],
            ],
            "units": {},
        },
    }
    request_data = {
        "question": "What was gross margin in 2022?",
        "evidence": table_with_margin,
        "candidate_answer": "Gross margin was 60%.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["engine_used"] == "pnl"
    assert data["signals"].get("pnl_margin_fail_count", 0) == 0
    assert data["decision"] in ["ACCEPT", "FLAG"]


def test_pnl_synonym_accept():
    """Synonym-heavy table (Sales, Cost of revenue, SG&A) -> correct lookup ACCEPT."""
    synonym_table = {
        "type": "table",
        "content": {
            "columns": ["Line Item", "2022", "2023"],
            "rows": [
                ["Sales", "100", "120"],
                ["Cost of revenue", "40", "50"],
                ["Gross Profit", "60", "70"],
                ["SG&A", "15", "18"],
                ["Operating Income", "45", "52"],
            ],
            "units": {},
        },
    }
    request_data = {
        "question": "What was sales in 2022?",
        "evidence": synonym_table,
        "candidate_answer": "Sales was 100.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["engine_used"] == "pnl"
    assert data["domain"].get("table_type") == "pnl"
    assert data["decision"] in ["ACCEPT", "FLAG"]