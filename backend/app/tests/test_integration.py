"""Integration tests for /verify-only endpoint."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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

