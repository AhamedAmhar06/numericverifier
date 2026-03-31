import { useState } from 'react';
import { DecisionPanel } from './components/DecisionPanel';
import { InputPanel } from './components/InputPanel';
import { verifyAnswer } from './lib/api';
import { APPLE_EXAMPLE_EVIDENCE, APPLE_EXAMPLE_QUESTION } from './lib/constants';
import { parseEvidenceInput, stringifyEvidence } from './lib/parser';
import { VerifyResponse } from './types/api';

export default function App() {
  const [question, setQuestion] = useState('');
  const [evidence, setEvidence] = useState('');
  const [candidateAnswer, setCandidateAnswer] = useState('');
  const [response, setResponse] = useState<VerifyResponse | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parseInfo, setParseInfo] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const clearTransientMessages = () => {
    setParseError(null);
    setParseInfo(null);
    setVerifyError(null);
  };

  const onParseTable = () => {
    setVerifyError(null);
    try {
      const parsed = parseEvidenceInput(evidence);
      setEvidence(stringifyEvidence(parsed));
      setParseError(null);
      setParseInfo('Evidence parsed successfully and normalized to JSON.');
    } catch (error) {
      setParseInfo(null);
      setParseError(error instanceof Error ? error.message : 'Failed to parse evidence.');
    }
  };

  const onLoadAppleExample = () => {
    clearTransientMessages();
    setResponse(null);
    setQuestion(APPLE_EXAMPLE_QUESTION);
    setEvidence(stringifyEvidence(APPLE_EXAMPLE_EVIDENCE));
    setCandidateAnswer('');
    setParseInfo('Apple FY2023 example loaded.');
  };

  const onClear = () => {
    setQuestion('');
    setEvidence('');
    setCandidateAnswer('');
    setResponse(null);
    clearTransientMessages();
  };

  const onVerify = async () => {
    clearTransientMessages();
    setResponse(null);

    if (!question.trim()) {
      setVerifyError('Question is required.');
      return;
    }

    let parsedEvidence;
    try {
      parsedEvidence = parseEvidenceInput(evidence);
    } catch (error) {
      setVerifyError(error instanceof Error ? error.message : 'Invalid evidence.');
      return;
    }

    const payload = {
      question: question.trim(),
      evidence: parsedEvidence,
      ...(candidateAnswer.trim() ? { candidate_answer: candidateAnswer.trim() } : {}),
    };

    setLoading(true);
    try {
      const result = await verifyAnswer(payload);
      setResponse(result);
    } catch (error) {
      setVerifyError(error instanceof Error ? error.message : 'Verification failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>NumericVerifier</h1>
        <p>P&amp;L numeric verification and decision workspace</p>
      </header>

      <div className="layout-grid">
        <InputPanel
          question={question}
          evidence={evidence}
          candidateAnswer={candidateAnswer}
          parseError={parseError}
          parseInfo={parseInfo}
          isLoading={loading}
          onQuestionChange={setQuestion}
          onEvidenceChange={setEvidence}
          onCandidateAnswerChange={setCandidateAnswer}
          onParseTable={onParseTable}
          onLoadAppleExample={onLoadAppleExample}
          onVerify={onVerify}
          onClear={onClear}
        />

        <DecisionPanel response={response} error={verifyError} loading={loading} />
      </div>
    </main>
  );
}
