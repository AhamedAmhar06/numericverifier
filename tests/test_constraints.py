"""Regression tests for verify_constraints — especially V_SCALE_LABEL_MISMATCH."""
from decimal import Decimal
import pytest
from backend.app.verifier.engines.constraints import verify_constraints
from backend.app.verifier.types import (
    NumericClaim, EvidenceItem, GroundingMatch,
    V_SCALE_LABEL_MISMATCH,
)


def _claim(raw: str, value: float, scale_token: str = None, value_decimal=None) -> NumericClaim:
    c = NumericClaim(raw_text=raw, parsed_value=value, char_span=(0, len(raw)),
                     scale_token=scale_token)
    if value_decimal is not None:
        c.value_decimal = value_decimal
    return c


def _evidence(value: float) -> EvidenceItem:
    return EvidenceItem(value=value, source="table")


def _grounding(claim: NumericClaim, ev: EvidenceItem) -> GroundingMatch:
    return GroundingMatch(
        claim=claim, evidence=ev,
        distance=abs(claim.parsed_value - ev.value),
        relative_error=abs(claim.parsed_value - ev.value) / max(abs(ev.value), 1),
    )


# ---------------------------------------------------------------------------
# PRE-FIX REGRESSION — was firing V_SCALE_LABEL_MISMATCH on correct
# denomination conversions.  After the fix this must NOT fire.
# ---------------------------------------------------------------------------

class TestScaleLabelMismatch_ValidDenominationConversion:
    """383.285 billion == 383,285 million — numerically consistent → NO violation."""

    def test_billion_answer_vs_million_table_accept(self):
        """Correct answer in billions where table is in millions → ACCEPT (no violation)."""
        # "383.285 billion" → parsed_value = 383_285_000_000 (absolute)
        claim = _claim(
            raw="383.285 billion",
            value=383_285_000_000.0,
            scale_token="billion",
            value_decimal=Decimal("383285000000"),
        )
        ev_million = _evidence(383285.0)   # raw table value stored in millions
        gm = _grounding(claim, ev_million)

        result = verify_constraints(
            claim=claim,
            grounding_match=gm,
            all_claims=[claim],
            evidence_items=[ev_million],
            table_scale="million",
        )

        scale_violations = [v for v in result.constraint_violations if v.code == V_SCALE_LABEL_MISMATCH]
        assert scale_violations == [], (
            f"False positive: correct denomination conversion should NOT fire "
            f"V_SCALE_LABEL_MISMATCH, but got: {scale_violations}"
        )

    def test_net_income_billion_vs_million_table_accept(self):
        """96,995 million == 96.995 billion — numerically consistent → no violation."""
        claim = _claim(
            raw="96.995 billion",
            value=96_995_000_000.0,
            scale_token="billion",
            value_decimal=Decimal("96995000000"),
        )
        ev = _evidence(96995.0)  # stored in millions
        gm = _grounding(claim, ev)

        result = verify_constraints(
            claim=claim,
            grounding_match=gm,
            all_claims=[claim],
            evidence_items=[ev],
            table_scale="million",
        )

        scale_violations = [v for v in result.constraint_violations if v.code == V_SCALE_LABEL_MISMATCH]
        assert scale_violations == [], (
            "96.995 billion == 96,995 million — should not be flagged"
        )


# ---------------------------------------------------------------------------
# MUST-STILL-FAIL — a genuinely wrong scale must still produce a violation.
# ---------------------------------------------------------------------------

class TestScaleLabelMismatch_TrueWrongScale:
    """96,995 billion is NOT equal to 96,995 million → MUST fire violation."""

    def test_true_wrong_scale_still_flagged(self):
        """Claim says '$96,995 billion' but table has 96,995 (millions) — not consistent."""
        # claim.value = 96_995_000_000_000 (96,995 * 1e9)
        # expected_raw = 96_995_000_000_000 / 1000 = 96_995_000_000 ≠ 96_995 → mismatch
        claim = _claim(
            raw="96995 billion",
            value=96_995_000_000_000.0,
            scale_token="billion",
            value_decimal=Decimal("96995000000000"),
        )
        ev = _evidence(96995.0)  # stored in millions
        gm = _grounding(claim, ev)

        result = verify_constraints(
            claim=claim,
            grounding_match=gm,
            all_claims=[claim],
            evidence_items=[ev],
            table_scale="million",
        )

        scale_violations = [v for v in result.constraint_violations if v.code == V_SCALE_LABEL_MISMATCH]
        assert len(scale_violations) == 1, (
            f"True wrong scale ($96,995 billion vs 96,995 million) MUST fire "
            f"V_SCALE_LABEL_MISMATCH, but got: {scale_violations}"
        )

    def test_fabricated_billion_still_flagged(self):
        """Claim says '$383 billion' but evidence is 383 (millions) — not consistent."""
        # expected_raw = 383_000_000_000 / 1000 = 383_000_000 ≠ 383
        claim = _claim(
            raw="383 billion",
            value=383_000_000_000.0,
            scale_token="billion",
            value_decimal=Decimal("383000000000"),
        )
        ev = _evidence(383.0)  # a small-company entry in millions
        gm = _grounding(claim, ev)

        result = verify_constraints(
            claim=claim,
            grounding_match=gm,
            all_claims=[claim],
            evidence_items=[ev],
            table_scale="million",
        )

        scale_violations = [v for v in result.constraint_violations if v.code == V_SCALE_LABEL_MISMATCH]
        assert len(scale_violations) == 1, (
            "Fabricated scale mismatch must still fire V_SCALE_LABEL_MISMATCH"
        )


# ---------------------------------------------------------------------------
# UNCHANGED BEHAVIOUR — same-family scale should never fire.
# ---------------------------------------------------------------------------

class TestScaleLabelMismatch_SameFamily:
    """Same scale family: answer in millions, table in millions → no violation."""

    def test_same_scale_no_violation(self):
        claim = _claim("383285 million", 383_285_000_000.0, scale_token="million",
                       value_decimal=Decimal("383285000000"))
        ev = _evidence(383285.0)
        gm = _grounding(claim, ev)

        result = verify_constraints(
            claim=claim,
            grounding_match=gm,
            all_claims=[claim],
            evidence_items=[ev],
            table_scale="million",
        )

        scale_violations = [v for v in result.constraint_violations if v.code == V_SCALE_LABEL_MISMATCH]
        assert scale_violations == [], "Same scale family must never fire V_SCALE_LABEL_MISMATCH"
