import { useRef, useState } from 'react';
import { uploadTable } from '../lib/api';

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploadedRowCount, setUploadedRowCount] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadStatus('loading');
    setUploadError(null);
    setUploadedFileName(null);
    setUploadedRowCount(null);

    try {
      const result = await uploadTable(file);
      // Populate evidence textarea with the full JSON
      onEvidenceChange(JSON.stringify(result, null, 2));

      // Extract row count from the response content
      let rowCount: number | null = null;
      if (
        result !== null &&
        typeof result === 'object' &&
        !Array.isArray(result) &&
        'content' in result
      ) {
        const content = (result as Record<string, unknown>).content;
        if (
          content !== null &&
          typeof content === 'object' &&
          !Array.isArray(content) &&
          'rows' in content &&
          Array.isArray((content as Record<string, unknown>).rows)
        ) {
          rowCount = ((content as Record<string, unknown>).rows as unknown[]).length;
        }
      }

      setUploadedFileName(file.name);
      setUploadedRowCount(rowCount);
      setUploadStatus('done');
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'File upload failed.');
      setUploadStatus('error');
    }

    // Reset input so the same file can be re-uploaded if needed
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClearUpload = () => {
    setUploadStatus('idle');
    setUploadedFileName(null);
    setUploadedRowCount(null);
    setUploadError(null);
  };

  return (
    <section className="panel panel-input">
      <h2>Input</h2>

      <label className="field">
        <span>Financial question</span>
        <textarea
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="e.g. What was gross profit in FY2023?"
          rows={3}
        />
      </label>

      <label className="field">
        <span>Income statement</span>
        {uploadStatus === 'done' && uploadedFileName ? (
          <div className="file-badge-evidence">
            <span className="upload-filename">{uploadedFileName}</span>
            {uploadedRowCount !== null && (
              <span className="upload-rows">{uploadedRowCount} rows loaded</span>
            )}
            <button
              type="button"
              className="button-ghost upload-clear"
              onClick={() => { handleClearUpload(); onEvidenceChange(''); fileInputRef.current?.click(); }}
              style={{ color: 'var(--primary)', fontSize: '0.82rem', fontWeight: 500 }}
            >
              Replace
            </button>
          </div>
        ) : (
          <textarea
            value={evidence}
            onChange={(event) => onEvidenceChange(event.target.value)}
            placeholder="Paste your income statement as CSV — or use the upload button above"
            rows={10}
          />
        )}
      </label>

      {/* File upload row */}
      <div className="upload-row">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          style={{ display: 'none' }}
          onChange={handleFileUpload}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || uploadStatus === 'loading'}
          className="button-upload"
        >
          {uploadStatus === 'loading' ? 'Parsing table...' : 'Upload CSV / Excel'}
        </button>

        {uploadStatus === 'done' && uploadedFileName && (
          <div className="upload-indicator">
            <span className="upload-filename">{uploadedFileName}</span>
            {uploadedRowCount !== null && (
              <span className="upload-rows">{uploadedRowCount} row{uploadedRowCount !== 1 ? 's' : ''}</span>
            )}
            <button
              type="button"
              className="button-ghost upload-clear"
              onClick={handleClearUpload}
              title="Clear upload status"
            >
              ×
            </button>
          </div>
        )}
      </div>

      {uploadError && <p className="status status-error">{uploadError}</p>}

      <label className="field">
        <span>Your answer (optional)</span>
        <textarea
          value={candidateAnswer}
          onChange={(event) => onCandidateAnswerChange(event.target.value)}
          placeholder="Leave blank — AI will generate and verify an answer automatically"
          rows={4}
        />
      </label>

      {parseError && <p className="status status-error">{parseError}</p>}
      {parseInfo && <p className="status status-info">{parseInfo}</p>}

      <div className="button-row">
        <button type="button" onClick={onParseTable}>
          Parse
        </button>
        <button type="button" onClick={onLoadAppleExample}>
          Load Apple Example
        </button>
        <button type="button" className="button-primary" onClick={onVerify} disabled={isLoading}>
          {isLoading ? 'Analyzing...' : candidateAnswer.trim() ? 'Verify my answer' : 'Analyze'}
        </button>
        <button type="button" className="button-ghost" onClick={onClear} disabled={isLoading}>
          Clear
        </button>
      </div>
    </section>
  );
}
