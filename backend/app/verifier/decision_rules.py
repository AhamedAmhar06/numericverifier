"""Rule-based decision logic. P&L mode: stricter FLAG rules."""
from typing import List
from .types import Decision, VerifierSignals, VerificationResult
from ..core.config import settings


def make_decision(
    signals: VerifierSignals,
    verification_results: List[VerificationResult],
    coverage_threshold: float = None,
) -> Decision:
    """
    Make decision based on signals. P&L mode (when pnl_table_detected=1) enforces:
    - pnl_missing_baseline_count > 0 -> FLAG
    - pnl_period_strict_mismatch_count > 0 -> FLAG
    - coverage good and (pnl_identity_fail_count or pnl_margin_fail_count) -> REPAIR
    """
    if coverage_threshold is None:
        coverage_threshold = settings.coverage_threshold

    # P&L mode: strict FLAG conditions (finance safety first)
    if getattr(signals, "pnl_table_detected", 0) == 1:
        if getattr(signals, "pnl_missing_baseline_count", 0) > 0:
            return Decision(
                decision="FLAG",
                rationale="YoY or baseline period requested but missing in evidence. Requires review.",
            )
        if getattr(signals, "pnl_period_strict_mismatch_count", 0) > 0:
            return Decision(
                decision="FLAG",
                rationale="Period strict mismatch between question and evidence. Requires review.",
            )
        if getattr(signals, "scale_mismatch_count", 0) > 0:
            return Decision(
                decision="FLAG",
                rationale=(
                    "P&L scale integrity violation — the answer uses a "
                    "different unit or scale than the evidence table. "
                    "This is a data integrity issue, not a correctable mismatch."
                ),
            )
        if (
            signals.coverage_ratio >= 0.6
            and (getattr(signals, "pnl_identity_fail_count", 0) > 0 or getattr(signals, "pnl_margin_fail_count", 0) > 0)
            and signals.unsupported_claims_count <= max(len(verification_results) * 0.3, 1)
        ):
            issues = []
            if getattr(signals, "pnl_identity_fail_count", 0) > 0:
                issues.append("P&L identity failures")
            if getattr(signals, "pnl_margin_fail_count", 0) > 0:
                issues.append("P&L margin failures")
            return Decision(
                decision="REPAIR",
                rationale=f"Good evidence coverage ({signals.coverage_ratio:.1%}), but P&L issues: {', '.join(issues)}. Errors appear correctable.",
            )

    # Non-P&L or pnl_table_detected=0: FLAG (do not accept non-P&L)
    if getattr(signals, "pnl_table_detected", 0) == 0:
        return Decision(
            decision="FLAG",
            rationale="Evidence is not a P&L / Income Statement table. Requires review.",
        )

    # Check for ACCEPT conditions (P&L, no strict violations)
    if (
        signals.unsupported_claims_count == 0
        and signals.scale_mismatch_count == 0
        and signals.period_mismatch_count == 0
        and signals.recomputation_fail_count == 0
        and getattr(signals, "pnl_identity_fail_count", 0) == 0
        and getattr(signals, "pnl_margin_fail_count", 0) == 0
        and getattr(signals, "pnl_missing_baseline_count", 0) == 0
        and getattr(signals, "pnl_period_strict_mismatch_count", 0) == 0
        and signals.coverage_ratio >= coverage_threshold
    ):
        return Decision(
            decision="ACCEPT",
            rationale="All claims are grounded and verified. No scale or period mismatches. All recomputations and P&L checks successful. Coverage meets threshold.",
        )

    # REPAIR conditions (generic)
    if (
        signals.coverage_ratio >= 0.6
        and (
            signals.scale_mismatch_count > 0
            or signals.period_mismatch_count > 0
            or signals.recomputation_fail_count > 0
        )
        and signals.unsupported_claims_count <= max(len(verification_results) * 0.3, 1)
    ):
        issues = []
        if signals.scale_mismatch_count > 0:
            issues.append("scale mismatches")
        if signals.period_mismatch_count > 0:
            issues.append("period mismatches")
        if signals.recomputation_fail_count > 0:
            issues.append("recomputation failures")
        return Decision(
            decision="REPAIR",
            rationale=f"Good evidence coverage ({signals.coverage_ratio:.1%}), but issues detected: {', '.join(issues)}. Errors appear correctable.",
        )

    # UNVERIFIABLE distinguishes "I cannot check this" from
    # "I checked and this is wrong" (FLAG).
    # Unverifiable answers contain no detected violations but
    # cannot be confirmed against the evidence table.
    if (
        signals.coverage_ratio < coverage_threshold
        and signals.unsupported_claims_count > 0
        and signals.scale_mismatch_count == 0
        and signals.period_mismatch_count == 0
        and getattr(signals, "pnl_identity_fail_count", 0) == 0
        and getattr(signals, "pnl_margin_fail_count", 0) == 0
        and getattr(signals, "pnl_missing_baseline_count", 0) == 0
        and signals.recomputation_fail_count == 0
    ):
        return Decision(
            decision="UNVERIFIABLE",
            rationale=(
                "Claims could not be grounded against evidence. No specific "
                "constraint violations detected. "
                "Escalate for human review."
            ),
        )

    # Default to FLAG
    issues = []
    if signals.coverage_ratio < coverage_threshold:
        issues.append(f"low coverage ({signals.coverage_ratio:.1%})")
    if signals.ambiguity_count > 0:
        issues.append(f"high ambiguity ({signals.ambiguity_count} ambiguous matches)")
    if verification_results and signals.unsupported_claims_count > len(verification_results) * 0.3:
        issues.append(f"many unsupported claims ({signals.unsupported_claims_count})")
    return Decision(
        decision="FLAG",
        rationale=f"Issues detected: {', '.join(issues)}. Requires review."
    )

