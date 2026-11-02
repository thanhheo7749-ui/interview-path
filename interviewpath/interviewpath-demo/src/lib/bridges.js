import { API_URL, api, getToken } from './api.js';

const company = (companyId) => `/api/companies/${companyId}`;

// Hiring requests, Manager Intake, JD Studio, the brief and the scorecard.
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
// Every manager's submitted scorecard, newest first; an empty list when none. 404 (anonymized) reads as none.
export const getScorecards = async (companyId, appId) =>
  (await orNull(api(`${application(companyId, appId)}/scorecard`)))?.scorecards ?? [];
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

// JD Studio. A draft is made from a hiring request, edited by hand or with the assistant, approved by the manager and
// published by HR. Nothing here posts to a job board: channel content is text for HR to copy.
const drafts = (companyId) => `${company(companyId)}/job-drafts`;
export const generateDraft = (companyId, requestId, roleNodeId) =>
  api(`${company(companyId)}/hiring-requests/${requestId}/drafts`, {
    method: 'POST',
    body: roleNodeId == null ? {} : { role_node_id: roleNodeId },
  });
export const getDraft = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}`);
export const patchDraftLines = (companyId, draftId, lines) =>
  api(`${drafts(companyId)}/${draftId}`, { method: 'PATCH', body: { lines } });
export const askAssistant = (companyId, draftId, message) =>
  api(`${drafts(companyId)}/${draftId}/assistant`, { method: 'POST', body: { message } });
export const confirmDraftLine = (companyId, draftId, lineId) =>
  api(`${drafts(companyId)}/${draftId}/lines/${encodeURIComponent(lineId)}/confirm`, { method: 'POST' });
export const dismissProposal = (companyId, draftId, proposalId) =>
  api(`${drafts(companyId)}/${draftId}/proposals/${encodeURIComponent(proposalId)}/dismiss`, { method: 'POST' });
export const rerunLint = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/lint`, { method: 'POST' });
export const acknowledgeUnchecked = (companyId, draftId, lineId) =>
  api(`${drafts(companyId)}/${draftId}/lint/acknowledge`, { method: 'POST', body: lineId ? { line_id: lineId } : {} });
export const submitDraft = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/submit`, { method: 'POST' });
export const approveDraft = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/approve`, { method: 'POST' });
export const publishDraft = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/publish`, { method: 'POST' });
export const getChannelContent = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/channels`);
export const generateChannelContent = (companyId, draftId) =>
  api(`${drafts(companyId)}/${draftId}/channels/generate`, { method: 'POST' });
