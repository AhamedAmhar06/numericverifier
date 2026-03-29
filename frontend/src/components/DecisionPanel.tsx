import { VerifyResponse } from '../types/api';

interface DecisionPanelProps {
  response: VerifyResponse | null;
  error: string | null;
  loading: boolean;
}

function getDecisionClass(decision: string | undefined): string {
  const normalized = decision?.toUpperCase();
  if (normalized === 'ACCEPT') {
    return 'decision-accept';
  }
  if (normalized === 'REPAIR') {
    return 'decision-repair';
  }
  if (normalized === 'FLAG') {
    return 'decision-flag';
  }
  return 'decision-unknown';
}

function stringifyUnknown(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (value === null || value === undefined) {
    return '';
  }
  return JSON.stringify(value, null, 2);
}

export function DecisionPanel({ response, error, loading }: DecisionPanelProps) {
  const decision = response?.decision?.toUpperCase() || 'PENDING';
  const rationale = response?.rationale ?? stringifyUnknown(response?.report) ?? '';
  const ingestionText = response?.ingestion
    ? JSON.stringify(response.ingestion, null, 2)
    : '';

  return (
    <section className="panel panel-decision">
      <h2>Decision</h2>

      <div className={`decision-badge ${getDecisionClass(response?.decision)}`}>{decision}</div>

      {loading && <p className="status status-info">Processing verification request...</p>}
      {error && <p className="status status-error">{error}</p>}
      {!loading && !error && !response && (
        <p className="status status-muted">Submit a verification request to see results.</p>
      )}

      {response && (
        <div className="decision-content">
          {rationale && (
            <div className="card">
              <h3>Rationale</h3>
              <p>{rationale}</p>
            </div>
          )}

          {response.original_answer && (
            <div className="card">
              <h3>Original Answer</h3>
              <p>{response.original_answer}</p>
            </div>
          )}

          {response.corrected_answer && (
            <div className="card">
              <h3>Corrected Answer</h3>
              <p>{response.corrected_answer}</p>
            </div>
          )}

          {ingestionText && (
            <div className="inline-meta">
              <span className="meta-label">Ingestion</span>
              <span className="meta-value">{ingestionText}</span>
            </div>
          )}

          {(response.repair_iterations !== undefined ||
            response.accepted_after_repair !== undefined) && (
            <div className="card">
              <h3>Repair Metadata</h3>
              {response.repair_iterations !== undefined && (
                <p>Repair Iterations: {response.repair_iterations}</p>
              )}
              {response.accepted_after_repair !== undefined && (
                <p>Accepted After Repair: {String(response.accepted_after_repair)}</p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
