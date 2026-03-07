"""API-level tests for POST /verify-only ensuring valid requests return 200."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

_PNL_TABLE = {
    "columns": ["Line Item", "2022", "2023"],
    "rows": [
        ["Revenue", "500000", "620000"],
        ["COGS", "200000", "250000"],
        ["Gross Profit", "300000", "370000"],
        ["Operating Expenses", "100000", "120000"],
        ["Operating Income", "200000", "250000"],
        ["Net Income", "150000", "190000"],
    ],
    "units": {},
}


def _post(payload: dict) -> dict:
    resp = client.post("/verify-only", json=payload)
    return resp


def test_valid_accept_case_returns_200():
    payload = {
        "question": "What was revenue in 2023?",
        "evidence": {"type": "table", "content": _PNL_TABLE},
        "candidate_answer": "Revenue in 2023 was 620000.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    resp = _post(payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] in ("ACCEPT", "REPAIR", "FLAG")
    assert "signals" in data


def test_valid_flag_case_returns_200():
    payload = {
        "question": "What was net income in 2021?",
        "evidence": {"type": "table", "content": _PNL_TABLE},
        "candidate_answer": "Net income in 2021 was 130000.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    resp = _post(payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "FLAG"


def test_valid_repair_candidate_returns_200():
    payload = {
        "question": "What was gross profit in 2022?",
        "evidence": {"type": "table", "content": _PNL_TABLE},
        "candidate_answer": "Gross profit in 2022 was 350000.",
        "options": {"tolerance": 0.01, "log_run": False},
    }
    resp = _post(payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] in ("ACCEPT", "REPAIR", "FLAG")


def test_text_evidence_returns_200_flag():
    payload = {
        "question": "What was revenue?",
        "evidence": {"type": "text", "content": "Revenue was 500000."},
        "candidate_answer": "Revenue was 500000.",
        "options": {"log_run": False},
    }
    resp = _post(payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "FLAG"


def test_missing_candidate_answer_returns_422():
    payload = {
        "question": "What was revenue?",
        "evidence": {"type": "table", "content": _PNL_TABLE},
    }
    resp = _post(payload)
    assert resp.status_code == 422


def test_response_contains_expected_keys():
    payload = {
        "question": "What was revenue in 2023?",
        "evidence": {"type": "table", "content": _PNL_TABLE},
        "candidate_answer": "Revenue in 2023 was 620000.",
        "options": {"log_run": False},
    }
    resp = _post(payload)
    assert resp.status_code == 200
    data = resp.json()
    for key in ("decision", "rationale", "signals", "claims", "grounding", "verification", "domain"):
        assert key in data, f"Missing key: {key}"
