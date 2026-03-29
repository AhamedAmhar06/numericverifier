import { API_BASE_URL } from './constants';
import { VerifyRequestBody, VerifyResponse } from '../types/api';

export async function verifyAnswer(payload: VerifyRequestBody): Promise<VerifyResponse> {
  // Use /verify-only when candidate_answer is provided; /verify when not (LLM generates answer)
  const endpoint =
    payload.candidate_answer && payload.candidate_answer.trim()
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

  return parsed as VerifyResponse;
}
