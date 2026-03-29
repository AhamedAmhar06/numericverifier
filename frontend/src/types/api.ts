export type Primitive = string | number | boolean | null;

export type JsonValue = Primitive | JsonValue[] | { [key: string]: JsonValue };

export interface VerifyRequestBody {
  question: string;
  evidence: JsonValue;
  candidate_answer?: string;
}

export interface GroundingInfo {
  matched?: boolean;
  unmatched?: boolean;
  evidence_label?: string;
  evidence_period?: string;
  evidence_value?: Primitive;
  relative_error?: number;
  confidence?: number;
  [key: string]: Primitive | undefined;
}

export interface VerificationInfo {
  lookup_supported?: boolean;
  execution_result?: string;
  constraint_violations?: string[];
  [key: string]: Primitive | string[] | undefined;
}

export interface ClaimAuditItem {
  claim_id?: string | number;
  id?: string | number;
  raw_text?: string;
  text?: string;
  parsed_value?: Primitive;
  claim_decision?: string;
  decision?: string;
  risk_level?: string;
  risk?: string;
  grounding?: GroundingInfo;
  verification?: VerificationInfo;
}

export interface AuditSummary {
  [key: string]: Primitive | undefined;
}

export interface IngestionResult {
  mode?: string;
  coverage?: number;
  matched_rows?: string[];
  unmapped_rows?: string[];
  llm_suggestions?: Record<string, string>;
  confidence?: number;
  [key: string]: Primitive | string[] | Record<string, string> | undefined;
}

export interface VerifyResponse {
  decision?: string;
  rationale?: string;
  signals?: Record<string, Primitive>;
  claims?: JsonValue;
  grounding?: JsonValue;
  verification?: JsonValue;
  report?: JsonValue;
  claim_audit?: ClaimAuditItem[];
  audit_summary?: AuditSummary;
  original_answer?: string;
  corrected_answer?: string;
  repair_iterations?: number;
  accepted_after_repair?: boolean;
  ingestion?: IngestionResult;
  generated_answer?: string;
  llm_used?: boolean;
  llm_fallback_reason?: string;
}
