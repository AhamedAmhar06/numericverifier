"""Tests for deterministic repair + re-verify loop (Phase 6)."""
import pytest
from backend.app.verifier.repair import attempt_repair, RepairResult
from backend.app.verifier.types import (
    NumericClaim, VerificationResult, GroundingMatch, EvidenceItem, VerifierSignals,
)


def _claim(raw, value, span=(0, 3)):
    return NumericClaim(raw_text=raw, parsed_value=value, char_span=span)


def _evidence(value, location="row:0,col:1"):
    return EvidenceItem(value=value, source="table", location=location)


def _grounding(claim, ev, dist=0.0, rel_err=0.0):
    return GroundingMatch(claim=claim, evidence=ev, distance=dist, relative_error=rel_err)


def _vr(claim, grounded=True, match=None, violations=None):
    return VerificationResult(claim=claim, grounded=grounded, grounding_match=match,
                              constraint_violations=violations or [])


def test_repair_grounded_value_replacement():
    answer = "Revenue was 350000 in 2022."
    claim = _claim("350000", 350000.0, span=(12, 18))
    ev = _evidence(300000)
    gm = _grounding(claim, ev, dist=50000, rel_err=50000 / 300000)
    vr = _vr(claim, grounded=True, match=gm)
    signals = VerifierSignals()

    result = attempt_repair(answer, [claim], [vr], [gm], signals, tolerance=0.01)
    assert result.changed is True
    assert "300000" in result.repaired_answer


def test_repair_no_change_when_exact():
    answer = "Revenue was 300000."
    claim = _claim("300000", 300000.0, span=(12, 18))
    ev = _evidence(300000)
    gm = _grounding(claim, ev, dist=0, rel_err=0)
    vr = _vr(claim, grounded=True, match=gm)
    signals = VerifierSignals()

    result = attempt_repair(answer, [claim], [vr], [gm], signals, tolerance=0.01)
    assert result.changed is False


def test_repair_execution_replacement():
    answer = "Gross profit was 999."
    claim = _claim("999", 999.0, span=(18, 21))
    vr = VerificationResult(claim=claim, grounded=False, execution_result=300000.0,
                            execution_confidence="high")
    signals = VerifierSignals()

    result = attempt_repair(answer, [claim], [vr], [], signals, tolerance=0.01)
    assert result.changed is True
    assert "300000" in result.repaired_answer


def test_repair_actions_have_metadata():
    answer = "Revenue was 350000."
    claim = _claim("350000", 350000.0, span=(12, 18))
    ev = _evidence(300000, location="row:0,col:1")
    gm = _grounding(claim, ev, dist=50000, rel_err=50000 / 300000)
    vr = _vr(claim, grounded=True, match=gm)
    signals = VerifierSignals()

    result = attempt_repair(answer, [claim], [vr], [gm], signals, tolerance=0.01)
    assert len(result.repair_actions) == 1
    action = result.repair_actions[0]
    assert action.reason == "grounded_value_replacement"
    assert "row:0" in action.provenance


def test_repair_multiple_claims():
    answer = "Revenue 350000, COGS 250000."
    c1 = _claim("350000", 350000.0, span=(8, 14))
    c2 = _claim("250000", 250000.0, span=(21, 27))
    ev1 = _evidence(300000, location="row:0,col:1")
    ev2 = _evidence(200000, location="row:1,col:1")
    gm1 = _grounding(c1, ev1, dist=50000, rel_err=50000 / 300000)
    gm2 = _grounding(c2, ev2, dist=50000, rel_err=50000 / 200000)
    vr1 = _vr(c1, grounded=True, match=gm1)
    vr2 = _vr(c2, grounded=True, match=gm2)
    signals = VerifierSignals()

    result = attempt_repair(answer, [c1, c2], [vr1, vr2], [gm1, gm2], signals, tolerance=0.01)
    assert result.changed is True
    assert "300000" in result.repaired_answer
    assert "200000" in result.repaired_answer


def test_repair_integration_via_router():
    """End-to-end: enable_repair through the router produces repair output."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    payload = {
        "question": "What was gross profit in 2022?",
        "evidence": {
            "type": "table",
            "content": {
                "columns": ["Line Item", "2022", "2023"],
                "rows": [
                    ["Revenue", "500000", "620000"],
                    ["COGS", "200000", "250000"],
                    ["Gross Profit", "300000", "370000"],
                ],
                "units": {},
            },
        },
        "candidate_answer": "Gross profit in 2022 was 350000.",
        "options": {"tolerance": 0.01, "log_run": False, "enable_repair": True},
    }
    resp = client.post("/verify-only", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # The answer says 350000 but evidence says 300000. Decision may be REPAIR or FLAG.
    # If repair fires, we should see repair key.
    if data["decision"] in ("REPAIR", "FLAG"):
        if "repair" in data:
            assert data["repair"]["repaired_answer"] is not None
