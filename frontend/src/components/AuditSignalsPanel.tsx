import { useMemo, useState } from 'react';
import { ClaimAuditItem, VerifyResponse } from '../types/api';

interface AuditSignalsPanelProps {
  response: VerifyResponse | null;
}

// ---------------------------------------------------------------------------
// Translation helpers (mirrors backend analyst_rationale.py)
// ---------------------------------------------------------------------------

const CLAIM_DECISION_LABELS: Record<string, string> = {
  supported:        'Verified against source data ✓',
  value_error:      'Value differs from source data ✗',
  ungrounded:       'Could not find matching value in table ✗',
  scale_violation:  'Unit scale mismatch detected ✗',
  period_violation: 'Wrong fiscal period ✗',
  repaired:         'Automatically corrected to match source data ↻',
  unverifiable:     'Could not be independently computed ?',
};

const RISK_LEVEL_LABELS: Record<string, string> = {
  low:      'Low risk — verified',
  medium:   'Medium risk — review recommended',
  high:     'High risk — manual verification required',
  critical: 'Critical — do not use without verification',
};

function translateClaimDecision(code: string | undefined): string {
  if (!code) return '—';
  return CLAIM_DECISION_LABELS[code.toLowerCase()] ?? code;
}

function translateRiskLevel(level: string | undefined): string {
  if (!level) return 'Unknown';
  return RISK_LEVEL_LABELS[level.toLowerCase()] ?? level;
}

function formatEvidenceMatch(label?: string, period?: string): string {
  if (!label && !period) return '—';
  if (label && period) return `Matched to: ${label} (${period})`;
  return `Matched to: ${label || period}`;
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function toReadable(value: unknown): string {
  if (value === undefined || value === null) return '-';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function claimRiskClass(level?: string): string {
  const normalized = level?.toLowerCase();
  if (!normalized) return 'risk-neutral';
  if (normalized.includes('critical')) return 'risk-high';
  if (normalized.includes('high')) return 'risk-high';
  if (normalized.includes('medium')) return 'risk-medium';
  if (normalized.includes('low')) return 'risk-low';
  return 'risk-neutral';
}

function isSignalWarning(key: string, value: unknown): boolean {
  const keyRisk = /(warn|error|risk|violation|mismatch|failure)/i.test(key);
  if (typeof value === 'number') return value !== 0 && keyRisk;
  if (typeof value === 'boolean') return value && keyRisk;
  if (typeof value === 'string') return value !== '0' && value.toLowerCase() !== 'none' && keyRisk;
  return false;
}

function computeCoverageRatio(response: VerifyResponse | null): number | null {
  if (!response) return null;

  const audit = response.audit_summary;
  if (audit) {
    const candidateKeys = ['coverage_ratio', 'claim_coverage_ratio', 'grounding_coverage', 'coverage'];
    for (const key of candidateKeys) {
      const value = audit[key];
      if (typeof value === 'number') {
        return value > 1 ? Math.min(value / 100, 1) : Math.max(value, 0);
      }
    }
  }

  const claims = response.claim_audit;
  if (claims && claims.length > 0) {
    const matched = claims.filter((item) => item.grounding?.matched === true).length;
    return matched / claims.length;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Claim item renderer — analyst-friendly
// ---------------------------------------------------------------------------

function renderClaimItem(item: ClaimAuditItem, idx: number) {
  const id = item.claim_id ?? item.id ?? idx + 1;
  const claimDecisionRaw = item.claim_decision ?? item.decision ?? '';
  const riskRaw = item.risk_level ?? item.risk ?? 'unknown';

  const claimDecisionLabel = translateClaimDecision(claimDecisionRaw);
  const riskLabel = translateRiskLevel(String(riskRaw));

  const evidenceLabel = item.grounding?.evidence_label;
  const evidencePeriod = item.grounding?.evidence_period;
  const evidenceMatch = formatEvidenceMatch(evidenceLabel, evidencePeriod);

  return (
    <li key={String(id)} className="claim-item">
      <div className="claim-head">
        <strong>Claim {id}</strong>
        <span className={`risk-badge ${claimRiskClass(String(riskRaw))}`}>{riskLabel}</span>
      </div>

      <p>
        <span className="kv-label">Value:</span> {item.raw_text ?? item.text ?? '—'}
      </p>
      <p>
        <span className="kv-label">Parsed:</span> {toReadable(item.parsed_value)}
      </p>
      <p>
        <span className="kv-label">Status:</span> {claimDecisionLabel}
      </p>

      {item.grounding && (
        <div className="sub-card">
          <h4>Evidence</h4>
          {item.grounding.matched ? (
            <>
              <p>{evidenceMatch}</p>
              {item.grounding.evidence_value !== undefined && (
                <p>
                  <span className="kv-label">Source value:</span>{' '}
                  {toReadable(item.grounding.evidence_value)}
                </p>
              )}
              {item.grounding.relative_error !== undefined && (
                <p>
                  <span className="kv-label">Relative error:</span>{' '}
                  {(Number(item.grounding.relative_error) * 100).toFixed(2)}%
                </p>
              )}
            </>
          ) : (
            <p className="status status-muted">No matching row found in the evidence table.</p>
          )}
        </div>
      )}

      {item.verification && (
        <div className="sub-card">
          <h4>Checks</h4>
          <p>
            <span className="kv-label">Lookup:</span>{' '}
            {item.verification.lookup_supported ? 'Supported ✓' : 'Not supported'}
          </p>
          {item.verification.execution_result && (
            <p>
              <span className="kv-label">Formula check:</span>{' '}
              {item.verification.execution_result}
            </p>
          )}
          {item.verification.constraint_violations &&
            (item.verification.constraint_violations as string[]).length > 0 && (
              <p>
                <span className="kv-label">Violations:</span>{' '}
                {(item.verification.constraint_violations as string[]).join(', ')}
              </p>
            )}
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Panel component
// ---------------------------------------------------------------------------

export function AuditSignalsPanel({ response }: AuditSignalsPanelProps) {
  // Signals start collapsed — analysts see plain-language view by default
  const [signalsOpen, setSignalsOpen] = useState(false);

  const coverageRatio = useMemo(() => computeCoverageRatio(response), [response]);
  const coveragePercent = coverageRatio === null ? 0 : Math.round(coverageRatio * 100);

  const auditEntries = response?.audit_summary ? Object.entries(response.audit_summary) : [];
  const claims = response?.claim_audit ?? [];
  const signals = response?.signals ? Object.entries(response.signals) : [];

  return (
    <section className="panel panel-audit">
      <h2>Audit + Signals</h2>

      {!response && <p className="status status-muted">Audit information appears after verify.</p>}

      {response && (
        <>
          <div className="card">
            <h3>Coverage Ratio</h3>
            {coverageRatio === null ? (
              <p>No coverage ratio provided.</p>
            ) : (
              <>
                <div className="progress-track" aria-label="Coverage ratio progress">
                  <div className="progress-fill" style={{ width: `${coveragePercent}%` }} />
                </div>
                <p>{coveragePercent}%</p>
              </>
            )}
          </div>

          <div className="card">
            <h3>Audit Summary</h3>
            {auditEntries.length === 0 && <p>No audit summary provided.</p>}
            {auditEntries.length > 0 && (
              <ul className="kv-list">
                {auditEntries.map(([key, value]) => (
                  <li key={key}>
                    <span className="kv-label">{key}</span>
                    <span>{toReadable(value)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h3>Claim Audit</h3>
            {claims.length === 0 && <p>No claim audit list returned.</p>}
            {claims.length > 0 && (
              <ul className="claim-list">{claims.map(renderClaimItem)}</ul>
            )}
          </div>

          {/* Technical signals — collapsed by default, labelled for developers */}
          <div className="card">
            <div className="signals-header">
              <h3>Technical Details <span className="meta-label">(for developers)</span></h3>
              <button
                type="button"
                className="button-ghost"
                onClick={() => setSignalsOpen((v) => !v)}
              >
                {signalsOpen ? 'Collapse' : 'Expand'}
              </button>
            </div>
            {signalsOpen && (
              <>
                {signals.length === 0 && <p>No signals provided.</p>}
                {signals.length > 0 && (
                  <div className="signal-grid">
                    {signals.map(([key, value]) => (
                      <div
                        key={key}
                        className={`signal-chip ${isSignalWarning(key, value) ? 'signal-warning' : ''}`}
                      >
                        <span>{key}</span>
                        <strong>{toReadable(value)}</strong>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}
