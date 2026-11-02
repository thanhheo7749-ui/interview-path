import { API_URL, api, getToken } from './api.js';

const company = (companyId) => `/api/companies/${companyId}`;

// Hiring requests and Manager Intake. Task 8 adds the JD draft calls here.
export const listHiringRequests = (companyId) => api(`${company(companyId)}/hiring-requests`);
export const getHiringRequest = (companyId, requestId) => api(`${company(companyId)}/hiring-requests/${requestId}`);
export const createHiringRequest = (companyId, body) =>
  api(`${company(companyId)}/hiring-requests`, { method: 'POST', body });
export const startIntake = (companyId, requestId, language) =>
  api(`${company(companyId)}/hiring-requests/${requestId}/intake/start`, { method: 'POST', body: { language } });
export const listMembers = (companyId) => api(`${company(companyId)}/members`);
export const listDepartments = (companyId) => api(`${company(companyId)}/departments`);

// The brief, the manager's interviews, the scorecard and the hiring outcome.
const application = (companyId, appId) => `${company(companyId)}/applications/${appId}`;
export const generateBrief = (companyId, appId, language) =>
  api(`${application(companyId, appId)}/brief`, { method: 'POST', body: { language } });
// 404 means there is none yet (or the application was anonymized), which is a state, not an error.
async function orNull(request) {
  try {
    return await request;
  } catch (err) {
    if (err.status === 404) return null;
    throw err;
  }
}
export const getBrief = (companyId, appId) => orNull(api(`${application(companyId, appId)}/brief`));
export const getScorecard = (companyId, appId) => orNull(api(`${application(companyId, appId)}/scorecard`));
export const saveBrief = (companyId, appId, content) =>
  api(`${application(companyId, appId)}/brief`, {
    method: 'PATCH',
    body: {
      strengths: content.strengths.map((p) => ({ evidence_id: p.evidence_id, summary: p.summary })),
      to_clarify: content.to_clarify.map((p) => ({ evidence_id: p.evidence_id, summary: p.summary })),
      questions: content.questions.map((q) => ({ evidence_id: q.evidence_id, question: q.question })),
    },
  });
export const sendBrief = (companyId, appId) => api(`${application(companyId, appId)}/brief/send`, { method: 'POST' });
export const recordOutcome = (companyId, appId, outcome) =>
  api(`${application(companyId, appId)}/outcome`, { method: 'POST', body: { outcome } });
export const listMyInterviews = (companyId) => api(`${company(companyId)}/my-interviews`);
export const getMyInterview = (companyId, appId) => api(`${company(companyId)}/my-interviews/${appId}`);
export const submitScorecard = (companyId, appId, body) =>
  api(`${application(companyId, appId)}/scorecard`, { method: 'POST', body });

// 133 seconds is "02:13". Recording times come from the server as seconds.
export function formatRecordingTime(seconds) {
  const whole = Math.max(0, Math.floor(Number(seconds) || 0));
  const pad = (n) => String(n).padStart(2, '0');
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(whole % 60)}` : `${pad(minutes)}:${pad(whole % 60)}`;
}

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
