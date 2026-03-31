import { API_BASE_URL } from './constants';
import { JsonValue, VerifyRequestBody, VerifyResponse } from '../types/api';

export async function verifyAnswer(payload: VerifyRequestBody): Promise<VerifyResponse> {
  // Use /verify-only when candidate_answer is provided; /verify when not (LLM generates answer)
  const isManualMode = !!(payload.candidate_answer && payload.candidate_answer.trim());
  const endpoint = isManualMode
    ? `${API_BASE_URL}/verify-only`
    : `${API_BASE_URL}/verify`;

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    if (!response.ok) {
      throw new Error(`Verification failed with status ${response.status}.`);
    }
    throw new Error('Backend returned a non-JSON response.');
  }

  if (!response.ok) {
    const message =
      typeof parsed === 'object' &&
      parsed !== null &&
      'detail' in parsed &&
      typeof (parsed as { detail?: unknown }).detail === 'string'
        ? (parsed as { detail: string }).detail
        : `Verification failed with status ${response.status}.`;
    throw new Error(message);
  }

  const result = parsed as VerifyResponse;
  // Tag the mode so the UI can display it
  result._mode = isManualMode ? 'manual' : 'llm-verified';
  return result;
}

export async function uploadTable(file: File): Promise<JsonValue> {
  const formData = new FormData();
  formData.append('file', file);

  // Do NOT set Content-Type — browser sets it (with boundary) for FormData
  const response = await fetch(`${API_BASE_URL}/upload-table`, {
    method: 'POST',
    body: formData,
  });

  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    if (!response.ok) {
      throw new Error(`Upload failed with status ${response.status}.`);
    }
    throw new Error('Backend returned a non-JSON response.');
  }

  if (!response.ok) {
    const message =
      typeof parsed === 'object' &&
      parsed !== null &&
      'detail' in parsed &&
      typeof (parsed as { detail?: unknown }).detail === 'string'
        ? (parsed as { detail: string }).detail
        : `Upload failed with status ${response.status}.`;
    throw new Error(message);
  }

  // Backend returns {"type": "table", "content": {...}}
  // Return the full object so caller can decide what to put in evidence
  return parsed as JsonValue;
}
