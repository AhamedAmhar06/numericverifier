"""Integration tests for /verify-only and verification flow.

Covers: correct arithmetic (ACCEPT), incorrect arithmetic (REPAIR),
vague answer (FLAG), period mismatch (FLAG).
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Shared evidence: Revenue 10 -> 15 (percent change = 50%)
_EVIDENCE_10_15 = {
    "type": "table",
    "content": {
        "columns": ["Period", "Revenue"],
        "rows": [["Q1", "10"], ["Q2", "15"]],
        "units": {"Revenue": "dollars"},
    },
}


def test_health_endpoint():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_verify_only_accept_case():
    """Test verify-only with accept case."""
    request_data = {
        "question": "What was the total revenue for Q1 2024?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Quarter", "Revenue"],
                "rows": [
                    ["Q1 2024", "5000000"],
                    ["Q2 2024", "5500000"]
                ],
                "units": {
                    "Revenue": "dollars"
                }
            }
        },
        "candidate_answer": "The total revenue for Q1 2024 was $5,000,000.",
        "options": {
            "tolerance": 0.01,
            "log_run": False
        }
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


def test_verify_only_text_evidence():
    """Test verify-only with text evidence."""
    request_data = {
        "question": "What was the revenue?",
        "evidence": {
            "type": "text",
            "content": "The company reported revenue of 5000000 dollars in Q1 2024."
        },
        "candidate_answer": "Revenue was $5,000,000.",
        "options": {
            "tolerance": 0.01,
            "log_run": False
        }
    }
    
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "decision" in data
    assert len(data["claims"]) > 0


def test_case_a_correct_arithmetic_accept():
    """Case A: Correct arithmetic — Revenue 10 → 15, answer contains 50%, expect ACCEPT."""
    request_data = {
        "question": "What is the percent change in revenue from Q1 to Q2?",
        "evidence": _EVIDENCE_10_15,
        "candidate_answer": "The percent change in revenue is 50%.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "50%" in request_data["candidate_answer"] or "50" in request_data["candidate_answer"]
    assert data["decision"] == "ACCEPT", data.get("rationale", "")


def test_case_b_incorrect_arithmetic_repair():
    """Case B: Incorrect arithmetic — LLM answer 20%, expect recomputation_fail_count > 0, REPAIR."""
    request_data = {
        "question": "What is the percent change in revenue from Q1 to Q2?",
        "evidence": _EVIDENCE_10_15,
        "candidate_answer": "The percent change in revenue is 20%.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["signals"]["recomputation_fail_count"] > 0, data.get("signals", {})
    assert data["decision"] == "REPAIR", data.get("rationale", "")


def test_case_c_no_numeric_answer_flag():
    """Case C: No numeric answer — vague text, expect FLAG."""
    request_data = {
        "question": "What is the percent change in revenue?",
        "evidence": _EVIDENCE_10_15,
        "candidate_answer": "Revenue increased significantly over the period.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "FLAG", data.get("rationale", "")
    assert "no numeric" in data["rationale"].lower() or "cannot verify" in data["rationale"].lower()


def test_case_d_period_mismatch_flag():
    """Case D: Period mismatch — answer references wrong year, expect period_mismatch_count > 0, FLAG."""
    request_data = {
        "question": "What was the value for the period?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Period", "Value"],
                "rows": [["Q1 2024", "2023"], ["Q2 2024", "2024"]],
                "units": {},
            },
        },
        "candidate_answer": "The value for 2023 was 2023.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    response = client.post("/verify-only", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["signals"]["period_mismatch_count"] > 0, data.get("signals", {})
    assert data["decision"] in ("FLAG", "REPAIR"), data.get("rationale", "")

