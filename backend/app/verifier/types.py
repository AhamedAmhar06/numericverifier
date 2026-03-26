"""Core data types for the verifier system."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from datetime import datetime


# ---------------------------------------------------------------------------
# Violation codes (typed, for signals counting)
# ---------------------------------------------------------------------------
V_SCALE_MISMATCH = "SCALE_MISMATCH"
V_SCALE_LABEL_MISMATCH = "SCALE_LABEL_MISMATCH"
V_PERIOD_MISMATCH = "PERIOD_MISMATCH"
V_PNL_PERIOD_STRICT = "PNL_PERIOD_STRICT"
V_MISSING_PERIOD_IN_EVIDENCE = "MISSING_PERIOD_IN_EVIDENCE"
V_PNL_IDENTITY_MISMATCH = "PNL_IDENTITY_MISMATCH"
V_PNL_MARGIN_MISMATCH = "PNL_MARGIN_MISMATCH"
V_MISSING_YOY_BASELINE = "MISSING_YOY_BASELINE"


@dataclass
class Violation:
    """Structured constraint violation with typed code."""
    code: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "metadata": self.metadata}


@dataclass
class NumericClaim:
    """Represents a numeric claim extracted from text."""
    raw_text: str
    parsed_value: float
    char_span: tuple[int, int]  # (start, end)
    unit: Optional[str] = None  # e.g., "percent", "dollar", "K", "M", "B"
    scale_token: Optional[str] = None  # e.g., "thousand", "million", "billion"
    # Extended normalization fields (populated by normalize_claims)
    unit_type: Optional[str] = None  # amount | percent | ratio | bps | count
    scale_label: Optional[str] = None  # raw | K | M | B
    currency: Optional[str] = None
    period: Optional[str] = None
    tolerance_abs: float = 0.0
    tolerance_rel: float = 0.01
    approximate: bool = False
    value_decimal: Optional[Decimal] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "raw_text": self.raw_text,
            "parsed_value": self.parsed_value,
            "char_span": list(self.char_span),
            "unit": self.unit,
            "scale_token": self.scale_token,
        }
        if self.unit_type is not None:
            d["unit_type"] = self.unit_type
        if self.scale_label is not None:
            d["scale_label"] = self.scale_label
        if self.currency is not None:
            d["currency"] = self.currency
        if self.period is not None:
            d["period"] = self.period
        if self.approximate:
            d["approximate"] = True
        return d


@dataclass
class EvidenceItem:
    """Represents a piece of evidence."""
    value: float
    source: str  # "text" or "table"
    location: Optional[str] = None  # For tables: "row:col" or cell identifier
    context: Optional[str] = None  # Surrounding text for text evidence
    # Extended fields (populated by enriched evidence ingestion)
    row_label: Optional[str] = None
    col_label: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    period: Optional[str] = None
    canonical_line_item: Optional[str] = None
    currency: Optional[str] = None
    scale_label: Optional[str] = None
    is_percent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "value": self.value,
            "source": self.source,
            "location": self.location,
            "context": self.context,
        }
        if self.row_label is not None:
            d["row_label"] = self.row_label
        if self.col_label is not None:
            d["col_label"] = self.col_label
        if self.period is not None:
            d["period"] = self.period
        if self.canonical_line_item is not None:
            d["canonical_line_item"] = self.canonical_line_item
        if self.is_percent:
            d["is_percent"] = True
        return d


@dataclass
class GroundingMatch:
    """Represents a match between a claim and evidence."""
    claim: NumericClaim
    evidence: EvidenceItem
    distance: float  # Absolute difference
    relative_error: float  # Relative error
    ambiguous: bool = False  # True if multiple matches found
    confidence: float = 0.0
    confidence_margin: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "claim": self.claim.to_dict(),
            "evidence": self.evidence.to_dict(),
            "distance": self.distance,
            "relative_error": self.relative_error,
            "ambiguous": self.ambiguous,
            "confidence": round(self.confidence, 4),
            "confidence_margin": round(self.confidence_margin, 4),
        }


@dataclass
class VerificationResult:
    """Result of verifying a claim."""
    claim: NumericClaim
    grounded: bool
    grounding_match: Optional[GroundingMatch] = None
    lookup_supported: bool = False
    execution_supported: bool = False
    execution_result: Optional[float] = None
    execution_error: Optional[str] = None
    execution_confidence: Optional[str] = None  # high | medium | low
    constraint_violations: List[Union[str, Violation]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        violations_out = []
        for v in self.constraint_violations:
            if isinstance(v, Violation):
                violations_out.append(v.to_dict())
            else:
                violations_out.append(v)
        return {
            "claim": self.claim.to_dict(),
            "grounded": self.grounded,
            "grounding_match": self.grounding_match.to_dict() if self.grounding_match else None,
            "lookup_supported": self.lookup_supported,
            "execution_supported": self.execution_supported,
            "execution_result": self.execution_result,
            "execution_error": self.execution_error,
            "execution_confidence": self.execution_confidence,
            "constraint_violations": violations_out,
        }


@dataclass
class VerifierSignals:
    """Risk signals computed from verification results. Schema v2 adds P&L fields."""
    unsupported_claims_count: int = 0
    coverage_ratio: float = 0.0
    recomputation_fail_count: int = 0
    max_relative_error: float = 0.0
    mean_relative_error: float = 0.0
    scale_mismatch_count: int = 0
    period_mismatch_count: int = 0
    ambiguity_count: int = 0
    # Schema v2 (P&L-only refactor)
    schema_version: int = 2
    pnl_table_detected: int = 0  # 0 or 1
    pnl_identity_fail_count: int = 0
    pnl_margin_fail_count: int = 0
    pnl_missing_baseline_count: int = 0
    pnl_period_strict_mismatch_count: int = 0
    # Schema v3 (near-tolerance, grounding quality, claim count)
    near_tolerance_flag: int = 0        # 1 if any grounded claim has tolerance < rel_err < 0.10
    grounding_confidence_score: float = 0.0  # avg composite grounding confidence (0.0–1.0)
    claim_count: int = 0                # total numeric claims extracted from answer

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/CSV. Includes v2 and v3 fields."""
        d = {
            "unsupported_claims_count": self.unsupported_claims_count,
            "coverage_ratio": self.coverage_ratio,
            "recomputation_fail_count": self.recomputation_fail_count,
            "max_relative_error": self.max_relative_error,
            "mean_relative_error": self.mean_relative_error,
            "scale_mismatch_count": self.scale_mismatch_count,
            "period_mismatch_count": self.period_mismatch_count,
            "ambiguity_count": self.ambiguity_count,
        }
        d["schema_version"] = self.schema_version
        d["pnl_table_detected"] = self.pnl_table_detected
        d["pnl_identity_fail_count"] = self.pnl_identity_fail_count
        d["pnl_margin_fail_count"] = self.pnl_margin_fail_count
        d["pnl_missing_baseline_count"] = self.pnl_missing_baseline_count
        d["pnl_period_strict_mismatch_count"] = self.pnl_period_strict_mismatch_count
        d["near_tolerance_flag"] = self.near_tolerance_flag
        d["grounding_confidence_score"] = self.grounding_confidence_score
        d["claim_count"] = self.claim_count
        return d


@dataclass
class Decision:
    """Final decision output."""
    decision: str  # "ACCEPT", "REPAIR", or "FLAG"
    rationale: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "decision": self.decision,
            "rationale": self.rationale
        }


@dataclass
class AuditReport:
    """Full audit report."""
    timestamp: str
    question: str
    candidate_answer: str
    evidence_type: str
    tolerance: float
    claims: List[NumericClaim]
    grounding: List[GroundingMatch]
    verification: List[VerificationResult]
    signals: VerifierSignals
    decision: Decision
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "question": self.question,
            "candidate_answer": self.candidate_answer,
            "evidence_type": self.evidence_type,
            "tolerance": self.tolerance,
            "claims": [c.to_dict() for c in self.claims],
            "grounding": [g.to_dict() for g in self.grounding],
            "verification": [v.to_dict() for v in self.verification],
            "signals": self.signals.to_dict(),
            "decision": self.decision.to_dict()
        }

