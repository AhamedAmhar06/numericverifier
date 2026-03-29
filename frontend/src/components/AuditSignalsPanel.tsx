import { useMemo, useState } from 'react';
import { ClaimAuditItem, VerifyResponse } from '../types/api';

interface AuditSignalsPanelProps {
  response: VerifyResponse | null;
}

function toReadable(value: unknown): string {
  if (value === undefined || value === null) {
    return '-';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}

function claimRiskClass(level?: string): string {
  const normalized = level?.toLowerCase();
  if (!normalized) return 'risk-neutral';
  if (normalized.includes('high')) return 'risk-high';
  if (normalized.includes('medium')) return 'risk-medium';
  if (normalized.includes('low')) return 'risk-low';
  return 'risk-neutral';
}

function isSignalWarning(key: string, value: unknown): boolean {
  const keyRisk = /(warn|error|risk|violation|mismatch|failure)/i.test(key);
  if (typeof value === 'number') {
    return value !== 0 && keyRisk;
  }
  if (typeof value === 'boolean') {
    return value && keyRisk;
  }
  if (typeof value === 'string') {
    return value !== '0' && value.toLowerCase() !== 'none' && keyRisk;
  }
  return false;
}

function computeCoverageRatio(response: VerifyResponse | null): number | null {
  if (!response) return null;

  const audit = response.audit_summary;
  if (audit) {
    const candidateKeys = [
      'coverage_ratio',
      'claim_coverage_ratio',
      'grounding_coverage',
      'coverage',
    ];
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

function renderClaimItem(item: ClaimAuditItem, idx: number) {
  const id = item.claim_id ?? item.id ?? idx + 1;
  const claimDecision = item.claim_decision ?? item.decision ?? '-';
  const risk = item.risk_level ?? item.risk ?? 'unknown';

  return (
    <li key={String(id)} className="claim-item">
      <div className="claim-head">
        <strong>Claim {id}</strong>
        <span className={`risk-badge ${claimRiskClass(String(risk))}`}>{String(risk)}</span>
      </div>

      <p>
        <span className="kv-label">Raw:</span> {item.raw_text ?? item.text ?? '-'}
      </p>
      <p>
        <span className="kv-label">Parsed Value:</span> {toReadable(item.parsed_value)}
      </p>
      <p>
        <span className="kv-label">Decision:</span> {toReadable(claimDecision)}
      </p>

      {item.grounding && (
        <div className="sub-card">
          <h4>Grounding</h4>
          <p>
            <span className="kv-label">Matched:</span> {toReadable(item.grounding.matched)}
          </p>
          <p>
            <span className="kv-label">Unmatched:</span> {toReadable(item.grounding.unmatched)}
          </p>
          <p>
            <span className="kv-label">Evidence Label:</span>{' '}
            {toReadable(item.grounding.evidence_label)}
          </p>
          <p>
            <span className="kv-label">Evidence Period:</span>{' '}
            {toReadable(item.grounding.evidence_period)}
          </p>
          <p>
            <span className="kv-label">Evidence Value:</span>{' '}
            {toReadable(item.grounding.evidence_value)}
          </p>
          <p>
            <span className="kv-label">Relative Error:</span>{' '}
            {toReadable(item.grounding.relative_error)}
          </p>
          <p>
            <span className="kv-label">Confidence:</span> {toReadable(item.grounding.confidence)}
          </p>
        </div>
      )}

      {item.verification && (
        <div className="sub-card">
          <h4>Verification</h4>
          <p>
            <span className="kv-label">Lookup Supported:</span>{' '}
            {toReadable(item.verification.lookup_supported)}
          </p>
          <p>
            <span className="kv-label">Execution Result:</span>{' '}
            {toReadable(item.verification.execution_result)}
          </p>
          <p>
            <span className="kv-label">Constraint Violations:</span>{' '}
            {toReadable(item.verification.constraint_violations)}
          </p>
        </div>
      )}
    </li>
  );
}

export function AuditSignalsPanel({ response }: AuditSignalsPanelProps) {
  const [signalsOpen, setSignalsOpen] = useState(true);

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
            {claims.length > 0 && <ul className="claim-list">{claims.map(renderClaimItem)}</ul>}
          </div>

          <div className="card">
            <div className="signals-header">
              <h3>Signals</h3>
              <button type="button" className="button-ghost" onClick={() => setSignalsOpen((v) => !v)}>
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
