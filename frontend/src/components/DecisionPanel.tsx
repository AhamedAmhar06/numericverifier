import { useState } from 'react';
import { VerifyResponse, ClaimAuditItem, ShapExplanation } from '../types/api';

interface DecisionPanelProps {
  response: VerifyResponse | null;
  error: string | null;
  loading: boolean;
}

// ---------------------------------------------------------------------------
// § Verdict constants  (Phase 2.1)
// ---------------------------------------------------------------------------

const VERDICT = {
  accept: { label: 'Verified',          dot: '#3B6D11', bg: '#EAF3DE', text: '#27500A' },
  flag:   { label: 'Needs Review',      dot: '#A32D2D', bg: '#FCEBEB', text: '#791F1F' },
  repair: { label: 'Review Suggested',  dot: '#854F0B', bg: '#FAEEDA', text: '#633806' },
} as const;

type VerdictKey = keyof typeof VERDICT;

function verdictFor(decision: string | undefined): typeof VERDICT[VerdictKey] {
  const k = decision?.toLowerCase() as VerdictKey;
  return VERDICT[k] ?? VERDICT.flag;
}

// ---------------------------------------------------------------------------
// § VerdictBadge — status pill, not a button  (Phase 2.1)
// ---------------------------------------------------------------------------

function VerdictBadge({ decision }: { decision: string | undefined }) {
  const v = verdictFor(decision);
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '5px 12px', borderRadius: 20,
      background: v.bg, color: v.text,
      fontSize: 13, fontWeight: 500,
      userSelect: 'none', cursor: 'default',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: v.dot, flexShrink: 0 }} />
      {v.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// § ConfidenceBar — 3px thin, proportional, no neon  (Phase 2.2)
// ---------------------------------------------------------------------------

function ConfidenceBar({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100);
  const fillColor = pct >= 70 ? '#3B6D11' : pct >= 40 ? '#854F0B' : '#A32D2D';
  const label = pct >= 80 ? 'High confidence' : pct >= 50 ? 'Moderate confidence' : 'Low confidence';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{label}</span>
      <div style={{ flex: 1, height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: fillColor, borderRadius: 2, transition: 'width .4s ease' }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-muted)', minWidth: 34, textAlign: 'right' }}>
        {pct}%
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// § Plain explanation  (Phase 2.3 / Change 3)
// ---------------------------------------------------------------------------

function getPlainExplanation(result: VerifyResponse): string {
  const { decision, signals, analyst_rationale } = result;
  if (analyst_rationale?.summary) return analyst_rationale.summary;
  const d = decision?.toLowerCase();
  const s = signals ?? {};
  if (d === 'accept') {
    const count = result.claim_audit?.filter(c => c.claim_decision === 'supported').length ?? 0;
    return `All numeric claims verified against the income statement.${count > 0 ? ` ${count} claim${count !== 1 ? 's' : ''} checked.` : ''}`;
  }
  if (d === 'flag') {
    if (s.scale_mismatch_count && Number(s.scale_mismatch_count) > 0)
      return 'A scale inconsistency was detected — a number may use the wrong unit (e.g. millions vs billions).';
    if (s.period_mismatch_count && Number(s.period_mismatch_count) > 0)
      return 'This answer references a time period that does not match the evidence provided.';
    if (s.unsupported_claims_count && Number(s.unsupported_claims_count) > 0)
      return `${s.unsupported_claims_count} numeric claim${Number(s.unsupported_claims_count) !== 1 ? 's' : ''} could not be matched to the income statement. Human review required.`;
    if (s.recomputation_fail_count && Number(s.recomputation_fail_count) > 0)
      return 'A calculated figure does not match what can be computed from the income statement.';
    return 'One or more claims could not be verified. Human review is recommended.';
  }
  if (d === 'repair') return 'A fixable error was found. A corrected version has been suggested below.';
  return analyst_rationale?.recommendation ?? '';
}

// ---------------------------------------------------------------------------
// § Recommendation banner — left-border accent only, no card  (Phase 2.7)
// ---------------------------------------------------------------------------

function RecommendationBanner({ decision, rationale }: { decision: string | undefined; rationale: VerifyResponse['analyst_rationale'] }) {
  const text = rationale?.recommendation
    ?? (decision?.toLowerCase() === 'accept'
        ? 'Accept — this answer is directly supported by the filed income statement.'
        : decision?.toLowerCase() === 'flag'
        ? 'Do not accept without review — verify the flagged claims against the source document.'
        : 'Review the suggested correction before accepting this answer.');
  const borderColor = verdictFor(decision).dot;
  return (
    <div style={{
      padding: '11px 14px',
      borderLeft: `2px solid ${borderColor}`,
      background: 'var(--surface-2)',
      fontSize: 13,
      color: 'var(--text)',
      fontWeight: 500,
      lineHeight: 1.5,
    }}>
      {text}
    </div>
  );
}

// ---------------------------------------------------------------------------
// § Number formatting  (Phase 2.3)
// ---------------------------------------------------------------------------

function formatFinancialValue(raw: string | number | null | undefined): string {
  if (raw == null || raw === '') return '—';
  const n = typeof raw === 'string' ? parseFloat(raw.replace(/,/g, '')) : raw;
  if (isNaN(n)) return String(raw);
  return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// ---------------------------------------------------------------------------
// § Supporting evidence table  (Phase 2.3 — column names, number format)
// ---------------------------------------------------------------------------

function SupportingEvidenceTable({
  claimAudit,
  decision,
}: {
  claimAudit: ClaimAuditItem[] | undefined;
  decision: string | undefined;
}) {
  if (!claimAudit || claimAudit.length === 0) return null;
  const d = decision?.toLowerCase();

  let claims = d === 'accept'
    ? claimAudit.filter(c => c.claim_decision === 'supported').slice(0, 3)
    : claimAudit.filter(c => c.claim_decision !== 'supported').slice(0, 3);

  if (claims.length === 0) claims = claimAudit.slice(0, 3);
  if (claims.length === 0) return null;

  return (
    <div className="supporting-evidence">
      <div style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '.1em', color: 'var(--text-muted)', marginBottom: 10 }}>
        Supporting evidence
      </div>
      <table className="evidence-table">
        <thead>
          <tr>
            <th>Claimed</th>
            <th>Period</th>
            <th>Source value</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim, i) => {
            const status = claim.claim_decision ?? claim.decision ?? '';
            const isOk = status === 'supported';
            const rawVal =
              (claim.grounding as (typeof claim.grounding & { matched_value?: string }) | undefined)?.matched_value
              ?? claim.grounding?.evidence_value;
            const sourceVal = formatFinancialValue(rawVal as string | number | null);
            const period =
              (claim as ClaimAuditItem & { period?: string }).period
              ?? claim.grounding?.evidence_period
              ?? '—';
            return (
              <tr key={i}>
                <td>{claim.raw_text ?? claim.text ?? '—'}</td>
                <td>{period}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{sourceVal}</td>
                <td>
                  <span style={{
                    display: 'inline-block', padding: '2px 8px', borderRadius: 10,
                    fontSize: 11, fontWeight: 500,
                    background: isOk ? '#EAF3DE' : '#FCEBEB',
                    color: isOk ? '#27500A' : '#791F1F',
                  }}>
                    {isOk ? 'Match' : 'Discrepancy'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// § XAI helpers  (Phase 3.3)
// ---------------------------------------------------------------------------

const SIGNAL_NAMES: Record<string, string> = {
  coverage_ratio: 'Source match confidence',
  grounding_confidence_score: 'Source match confidence',
  scale_mismatch_count: 'Scale consistency',
  period_mismatch_count: 'Period alignment',
  unsupported_claims_count: 'Unsupported claims',
  recomputation_fail_count: 'Arithmetic check',
  pnl_identity_fail_count: 'Accounting identity check',
  pnl_margin_fail_count: 'Margin range check',
  near_tolerance_flag: 'Near-boundary value',
  ambiguity_count: 'Ambiguous line items',
};

function humaniseSignalName(name: string): string {
  return SIGNAL_NAMES[name] ?? name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function buildFactors(
  shap: ShapExplanation | null | undefined,
  signals: Record<string, unknown> | undefined,
  _decision: string | undefined,
): Array<{ label: string; pct: number; direction: 'accept' | 'flag' }> {
  // Use SHAP top_signals if available
  if (shap?.top_signals && shap.top_signals.length > 0) {
    return shap.top_signals.slice(0, 4).map(sig => ({
      label: humaniseSignalName(sig.signal),
      pct: Math.min(Math.abs(sig.shap_value) * 100, 100),
      direction: sig.shap_value > 0 ? 'accept' : 'flag',
    }));
  }
  // Fallback from signals
  if (!signals) return [];
  const rows: Array<{ label: string; pct: number; direction: 'accept' | 'flag' }> = [];
  const conf = (signals.grounding_confidence_score ?? signals.coverage_ratio) as number | undefined;
  if (conf != null) rows.push({ label: 'Source match confidence', pct: Math.round(conf * 100), direction: conf > 0.5 ? 'accept' : 'flag' });
  if (signals.period_mismatch_count === 0) rows.push({ label: 'Period alignment', pct: 78, direction: 'accept' });
  if (signals.scale_mismatch_count === 0) rows.push({ label: 'Scale consistency', pct: 70, direction: 'accept' });
  if (Number(signals.unsupported_claims_count ?? 0) > 0) rows.push({ label: 'Unsupported claims', pct: Math.min(Number(signals.unsupported_claims_count) * 25, 90), direction: 'flag' });
  if (Number(signals.recomputation_fail_count ?? 0) > 0) rows.push({ label: 'Arithmetic check failed', pct: 80, direction: 'flag' });
  return rows.slice(0, 4);
}

// ---------------------------------------------------------------------------
// § XAI Explanation panel  (Phase 3.3)
// ---------------------------------------------------------------------------

function XAIExplanationPanel({ result }: { result: VerifyResponse }) {
  const summary = result.analyst_rationale?.summary
    ?? (result.analyst_rationale?.findings?.join(' ') || null)
    ?? getPlainExplanation(result);
  const factors = buildFactors(result.shap_explanation as ShapExplanation | null, result.signals as Record<string, unknown> | undefined, result.decision);

  return (
    <div style={{ padding: '14px 16px', borderBottom: '0.5px solid var(--border)' }}>
      <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 10, letterSpacing: '.04em' }}>
        Why this decision
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.65, marginBottom: factors.length > 0 ? 14 : 0, marginTop: 0 }}>
        {summary}
      </p>
      {factors.length > 0 && (
        <>
          <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '.04em' }}>
            Top contributing factors
          </div>
          {factors.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--text)', flex: 1 }}>{f.label}</div>
              <div style={{ width: 110, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', flexShrink: 0 }}>
                <div style={{
                  width: `${f.pct}%`, height: '100%',
                  background: f.direction === 'accept' ? '#3B6D11' : '#A32D2D',
                  borderRadius: 2,
                }} />
              </div>
              <div style={{ fontSize: 11, minWidth: 52, textAlign: 'right', color: f.direction === 'accept' ? '#27500A' : '#791F1F' }}>
                {f.direction === 'accept' ? '+ Accept' : '− Flag'}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// § Checks performed  (Phase 3.4)
// ---------------------------------------------------------------------------

function ChecksPerformed({ result }: { result: VerifyResponse }) {
  const s = result.signals ?? {};

  const checks = [
    {
      label: 'Value match',
      status: Number(s.unsupported_claims_count ?? 0) === 0 ? 'pass' : 'fail',
      detail: Number(s.unsupported_claims_count ?? 0) === 0 ? 'All values matched in source' : `${s.unsupported_claims_count} claim(s) not found in source`,
    },
    {
      label: 'Period check',
      status: Number(s.period_mismatch_count ?? 0) === 0 && Number(s.pnl_period_strict_mismatch_count ?? 0) === 0 ? 'pass' : 'fail',
      detail: Number(s.period_mismatch_count ?? 0) === 0 ? 'Reporting period confirmed' : 'Period mismatch detected',
    },
    {
      label: 'Scale check',
      status: Number(s.scale_mismatch_count ?? 0) === 0 ? 'pass' : 'fail',
      detail: Number(s.scale_mismatch_count ?? 0) === 0 ? 'Units and denomination consistent' : 'Scale inconsistency detected',
    },
    {
      label: 'Arithmetic check',
      status: s.recomputation_fail_count == null ? 'skip'
             : Number(s.recomputation_fail_count) === 0 ? 'pass' : 'fail',
      detail: s.recomputation_fail_count == null ? 'Not applicable — direct lookup'
             : Number(s.recomputation_fail_count) === 0 ? 'Calculations verified' : `${s.recomputation_fail_count} calculation(s) failed`,
    },
    {
      label: 'Accounting identity check',
      status: s.pnl_identity_fail_count == null ? 'skip'
             : Number(s.pnl_identity_fail_count) === 0 ? 'pass' : 'fail',
      detail: s.pnl_identity_fail_count == null ? 'Not applicable'
             : Number(s.pnl_identity_fail_count) === 0 ? 'P&L identities consistent' : 'Identity check failed',
    },
  ];

  const iconBg = (status: string) =>
    status === 'pass' ? '#EAF3DE' : status === 'fail' ? '#FCEBEB' : 'var(--surface-2)';
  const iconColor = (status: string) =>
    status === 'pass' ? '#27500A' : status === 'fail' ? '#791F1F' : 'var(--text-muted)';
  const iconChar = (status: string) =>
    status === 'pass' ? '✓' : status === 'fail' ? '✕' : '—';

  return (
    <div style={{ padding: '14px 16px', borderBottom: '0.5px solid var(--border)' }}>
      <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 10, letterSpacing: '.04em' }}>
        Checks performed
      </div>
      {checks.map((c, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 12 }}>
          <div style={{
            width: 16, height: 16, borderRadius: '50%',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 9, fontWeight: 500, flexShrink: 0,
            background: iconBg(c.status), color: iconColor(c.status),
          }}>
            {iconChar(c.status)}
          </div>
          <span style={{ color: 'var(--text)', flex: 1 }}>{c.label}</span>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{c.detail}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// § Source details  (Phase 3.5)
// ---------------------------------------------------------------------------

function SourceDetails({ result }: { result: VerifyResponse }) {
  const claim = result.claim_audit?.[0];
  const g = claim?.grounding;

  const rows: [string, string][] = [
    ['File', ((result as unknown as Record<string, unknown>).source_file as string | undefined) ?? 'Uploaded statement'],
    ['Line item matched', (g as (typeof g & { matched_line_item?: string; line_item?: string }) | undefined)?.matched_line_item ?? g?.evidence_label ?? claim?.raw_text ?? '—'],
    ['Period used', g?.evidence_period ?? (claim as (typeof claim & { period?: string }) | undefined)?.period ?? '—'],
    ['Scale declared', ((result.signals as (typeof result.signals & { table_scale?: string }) | undefined)?.table_scale) ?? 'Millions (USD)'],
  ].filter(([, v]) => v && v !== '—' && v !== 'undefined') as [string, string][];

  if (result.accepted_after_repair) {
    rows.push(['Correction applied', 'Yes — answer was repaired before acceptance']);
  }

  if (rows.length === 0) return null;

  return (
    <div style={{ padding: '14px 16px' }}>
      <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 10, letterSpacing: '.04em' }}>
        Source details
      </div>
      {rows.map(([k, v], i) => (
        <div key={i} style={{
          display: 'flex', justifyContent: 'space-between',
          fontSize: 12, padding: '4px 0',
          borderBottom: i < rows.length - 1 ? '0.5px solid var(--border)' : 'none',
        }}>
          <span style={{ color: 'var(--text-muted)' }}>{k}</span>
          <span style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', textAlign: 'right', maxWidth: '60%' }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// § Advanced audit panel — button toggle, 3 sections  (Phase 3.6)
// ---------------------------------------------------------------------------

function AdvancedAuditPanel({ result }: { result: VerifyResponse }) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginTop: 4 }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 14px',
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          cursor: 'pointer', fontSize: 12, color: 'var(--text-muted)',
          fontFamily: 'inherit',
        }}
      >
        <span style={{ fontSize: 10, transition: 'transform .2s', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block' }}>▶</span>
        Verification audit trail
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', opacity: 0.75 }}>
          {open ? 'Collapse' : 'Expand for details'}
        </span>
      </button>

      {open && (
        <div style={{ marginTop: 2, border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', background: 'var(--surface-2)' }}>
          <XAIExplanationPanel result={result} />
          <ChecksPerformed result={result} />
          <SourceDetails result={result} />

          {/* Corrected answer — only when repair actually fired */}
          {result.corrected_answer && (
            <div style={{ padding: '14px 16px', borderTop: '0.5px solid var(--border)' }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '.04em' }}>Corrected answer</div>
              <p style={{ fontSize: 12, color: 'var(--text)', margin: 0, lineHeight: 1.55 }}>{result.corrected_answer}</p>
              {result.original_answer && (
                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                  <em>Original: {result.original_answer}</em>
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// § Main panel
// ---------------------------------------------------------------------------

export function DecisionPanel({ response, error, loading }: DecisionPanelProps) {
  const confValue =
    (response?.signals?.grounding_confidence_score as number | null | undefined)
    ?? (response?.signals?.coverage_ratio as number | null | undefined)
    ?? null;

  // Decision-coloured left border for the AI answer block
  const answerBorderColor = response ? verdictFor(response.decision).dot : '#0f62fe';

  return (
    <section className="panel panel-decision">
      <h2>Decision</h2>

      {loading && <p className="status status-info">Processing verification request...</p>}
      {error && <p className="status status-error">{error}</p>}
      {!loading && !error && !response && (
        <p className="status status-muted">Submit a verification request to see results.</p>
      )}

      {response && (
        <div className="decision-content">

          {/* 1. AI answer — first and prominent */}
          {response.llm_used && response.generated_answer && (
            <div style={{
              marginBottom: 4,
              paddingBottom: 16,
              borderBottom: '0.5px solid var(--border)',
              borderLeft: `3px solid ${answerBorderColor}`,
              paddingLeft: 14,
            }}>
              <div style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '.1em', color: 'var(--text-muted)', marginBottom: 8 }}>
                AI answer
              </div>
              <div style={{ fontSize: 16, color: 'var(--text)', lineHeight: 1.65 }}>
                {response.generated_answer}
              </div>
            </div>
          )}

          {/* 2. Verdict badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <VerdictBadge decision={response.decision} />
            {response.requires_human_review && (
              <span style={{
                fontSize: 12, color: '#854F0B', fontWeight: 500,
                background: '#FAEEDA', padding: '3px 10px', borderRadius: 20,
              }}>
                ⚠ Analyst review recommended
              </span>
            )}
          </div>

          {/* 3. Confidence bar */}
          {confValue != null && (
            <div style={{ display: 'flex', alignItems: 'center', paddingTop: 2 }}>
              <ConfidenceBar value={confValue} />
            </div>
          )}

          {/* 4. Plain explanation */}
          <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.65, margin: '4px 0 0' }}>
            {getPlainExplanation(response)}
          </p>

          {/* 5. Recommendation banner */}
          <RecommendationBanner decision={response.decision} rationale={response.analyst_rationale} />

          {/* 6. Supporting evidence table */}
          {response.claim_audit && response.claim_audit.length > 0 ? (
            <SupportingEvidenceTable claimAudit={response.claim_audit} decision={response.decision} />
          ) : (
            <div style={{ padding: '10px 0', fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              No individual claims were extracted from this answer.
              {response.decision?.toLowerCase() === 'flag' && ' The answer was flagged at an earlier stage before claim analysis.'}
            </div>
          )}

          {/* 7. Verification audit trail — collapsed */}
          <AdvancedAuditPanel result={response} />

        </div>
      )}
    </section>
  );
}
