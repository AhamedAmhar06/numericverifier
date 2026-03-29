interface InputPanelProps {
  question: string;
  evidence: string;
  candidateAnswer: string;
  parseError: string | null;
  parseInfo: string | null;
  isLoading: boolean;
  onQuestionChange: (value: string) => void;
  onEvidenceChange: (value: string) => void;
  onCandidateAnswerChange: (value: string) => void;
  onParseTable: () => void;
  onLoadAppleExample: () => void;
  onVerify: () => void;
  onClear: () => void;
}

export function InputPanel({
  question,
  evidence,
  candidateAnswer,
  parseError,
  parseInfo,
  isLoading,
  onQuestionChange,
  onEvidenceChange,
  onCandidateAnswerChange,
  onParseTable,
  onLoadAppleExample,
  onVerify,
  onClear,
}: InputPanelProps) {
  return (
    <section className="panel panel-input">
      <h2>Input</h2>

      <label className="field">
        <span>Financial Question</span>
        <textarea
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="What was Apple's gross margin in FY2023?"
          rows={3}
        />
      </label>

      <label className="field">
        <span>Evidence (CSV or JSON)</span>
        <textarea
          value={evidence}
          onChange={(event) => onEvidenceChange(event.target.value)}
          placeholder="Paste structured evidence here."
          rows={10}
        />
      </label>

      <label className="field">
        <span>Candidate Answer (Optional)</span>
        <textarea
          value={candidateAnswer}
          onChange={(event) => onCandidateAnswerChange(event.target.value)}
          placeholder="Optional answer to be verified/repaired."
          rows={4}
        />
      </label>

      {parseError && <p className="status status-error">{parseError}</p>}
      {parseInfo && <p className="status status-info">{parseInfo}</p>}

      <div className="button-row">
        <button type="button" onClick={onParseTable}>
          Parse Table
        </button>
        <button type="button" onClick={onLoadAppleExample}>
          Load Apple Example
        </button>
        <button type="button" className="button-primary" onClick={onVerify} disabled={isLoading}>
          {isLoading ? 'Verifying...' : 'Verify'}
        </button>
        <button type="button" className="button-ghost" onClick={onClear} disabled={isLoading}>
          Clear
        </button>
      </div>
    </section>
  );
}
