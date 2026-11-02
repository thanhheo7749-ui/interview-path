import { API_URL, api, getToken } from './api.js';

const company = (companyId) => `/api/companies/${companyId}`;

// Hiring requests and Manager Intake. Tasks 8 and 9 add the JD draft, brief and scorecard calls here.
export const listHiringRequests = (companyId) => api(`${company(companyId)}/hiring-requests`);
export const getHiringRequest = (companyId, requestId) => api(`${company(companyId)}/hiring-requests/${requestId}`);
export const createHiringRequest = (companyId, body) =>
  api(`${company(companyId)}/hiring-requests`, { method: 'POST', body });
export const startIntake = (companyId, requestId, language) =>
  api(`${company(companyId)}/hiring-requests/${requestId}/intake/start`, { method: 'POST', body: { language } });
export const listMembers = (companyId) => api(`${company(companyId)}/members`);
export const listDepartments = (companyId) => api(`${company(companyId)}/departments`);

// The generic voice routes: any purpose, for the session's owner.
export const getVoiceState = (sessionId) => api(`/api/voice/${sessionId}/state`);

export function submitVoiceAnswer(sessionId, position, blob) {
  const form = new FormData();
  const extension = blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'webm';
  form.append('file', blob, `answer.${extension}`);
  return api(`/api/voice/${sessionId}/turns/${position}/answer`, { method: 'POST', formData: form });
}

// Spoken question. Null when the server has no voice for it (204) or the call fails: the text is always shown.
export async function fetchQuestionAudio(sessionId, position) {
  try {
    const response = await fetch(`${API_URL}/api/voice/${sessionId}/turns/${position}/question-audio`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!response.ok || response.status === 204) return null;
    return await response.blob();
  } catch {
    return null;
  }
}
