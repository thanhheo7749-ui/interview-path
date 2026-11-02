import { API_URL, api, getToken } from './api.js';

const company = (companyId) => `/api/companies/${companyId}`;

// Hiring requests, Manager Intake and JD Studio. Task 9 adds the brief and scorecard calls here.
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
export const rerunLint = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/lint`, { method: 'POST' });
export const acknowledgeUnchecked = (companyId, draftId, lineId) =>
  api(`${drafts(companyId)}/${draftId}/lint/acknowledge`, { method: 'POST', body: lineId ? { line_id: lineId } : {} });
export const submitDraft = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/submit`, { method: 'POST' });
export const approveDraft = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/approve`, { method: 'POST' });
export const publishDraft = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/publish`, { method: 'POST' });
export const getChannelContent = (companyId, draftId) => api(`${drafts(companyId)}/${draftId}/channels`);
export const generateChannelContent = (companyId, draftId) =>
  api(`${drafts(companyId)}/${draftId}/channels/generate`, { method: 'POST' });

// The API has no call that lists drafts and a hiring request does not carry its draft's id, so HR's browser remembers
// which draft it made for a request. A manager opens a draft from the address HR passes on.
const draftKey = (companyId, requestId) => `portal_draft_${companyId}_${requestId}`;
export const rememberDraft = (companyId, requestId, draftId) => localStorage.setItem(draftKey(companyId, requestId), String(draftId));
export const rememberedDraft = (companyId, requestId) => localStorage.getItem(draftKey(companyId, requestId));

// A conflict issue names the graph node in its message ("... (node 12) ..."); the issue has no field for it.
export const conflictNodeId = (issue) => {
  const match = /\(node (\d+)\)/.exec(issue?.message ?? '');
  return match ? Number(match[1]) : null;
};
