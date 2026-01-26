"""Core data types for the verifier system."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class NumericClaim:
    """Represents a numeric claim extracted from text."""
    raw_text: str
    parsed_value: float
    char_span: tuple[int, int]  # (start, end)
    unit: Optional[str] = None  # e.g., "percent", "dollar", "K", "M", "B"
    scale_token: Optional[str] = None  # e.g., "thousand", "million", "billion"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "raw_text": self.raw_text,
            "parsed_value": self.parsed_value,
            "char_span": list(self.char_span),
            "unit": self.unit,
            "scale_token": self.scale_token
        }


@dataclass
class EvidenceItem:
    """Represents a piece of evidence."""
    value: float
    source: str  # "text" or "table"
    location: Optional[str] = None  # For tables: "row:col" or cell identifier
    context: Optional[str] = None  # Surrounding text for text evidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "value": self.value,
            "source": self.source,
            "location": self.location,
            "context": self.context
        }


@dataclass
class GroundingMatch:
    """Represents a match between a claim and evidence."""
    claim: NumericClaim
    evidence: EvidenceItem
    distance: float  # Absolute difference
    relative_error: float  # Relative error
    ambiguous: bool = False  # True if multiple matches found
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "claim": self.claim.to_dict(),
            "evidence": self.evidence.to_dict(),
            "distance": self.distance,
            "relative_error": self.relative_error,
            "ambiguous": self.ambiguous
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
    constraint_violations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "claim": self.claim.to_dict(),
            "grounded": self.grounded,
            "grounding_match": self.grounding_match.to_dict() if self.grounding_match else None,
            "lookup_supported": self.lookup_supported,
            "execution_supported": self.execution_supported,
            "execution_result": self.execution_result,
            "execution_error": self.execution_error,
            "constraint_violations": self.constraint_violations
        }


@dataclass
class VerifierSignals:
    """Risk signals computed from verification results."""
    unsupported_claims_count: int = 0
    coverage_ratio: float = 0.0
    recomputation_fail_count: int = 0
    max_relative_error: float = 0.0
    mean_relative_error: float = 0.0
    scale_mismatch_count: int = 0
    period_mismatch_count: int = 0
    ambiguity_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "unsupported_claims_count": self.unsupported_claims_count,
            "coverage_ratio": self.coverage_ratio,
            "recomputation_fail_count": self.recomputation_fail_count,
            "max_relative_error": self.max_relative_error,
            "mean_relative_error": self.mean_relative_error,
            "scale_mismatch_count": self.scale_mismatch_count,
            "period_mismatch_count": self.period_mismatch_count,
            "ambiguity_count": self.ambiguity_count
        }


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

