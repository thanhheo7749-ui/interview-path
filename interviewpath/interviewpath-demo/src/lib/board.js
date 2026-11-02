import { API_URL, ApiError, api, getToken } from './api.js';

const base = (companyId) => `/api/companies/${companyId}`;
const post = (path, body) => api(path, { method: 'POST', body });

// The four cells in reading order: rows are the CV, columns are the amount of interview evidence.
export const CELLS = ['priority', 'strong_cv_unclear', 'hidden_gem', 'not_enough_evidence'];
export const LANES = ['analyzing', 'analysis_failed', 'transcription_failed', 'cv_failed', 'not_interviewed', 'refused_recording', 'withdrawn'];

export const getBoard = (companyId, jobId) => api(`${base(companyId)}/jobs/${jobId}/board`);
export const getApplication = (companyId, appId) => api(`${base(companyId)}/applications/${appId}`);
export const decide = (companyId, appId, decision, reason) =>
  post(`${base(companyId)}/applications/${appId}/decision`, { decision, reason: reason || null });
export const correctCvStatus = (companyId, appId, cvStatus, reason) =>
  post(`${base(companyId)}/applications/${appId}/cv-status`, { cv_status: cvStatus, reason });
export const revealIdentity = (companyId, appId) => post(`${base(companyId)}/applications/${appId}/reveal`);
export const grantRestart = (companyId, appId) => post(`${base(companyId)}/applications/${appId}/restart`);
export const fastTrack = (companyId, appId) => post(`${base(companyId)}/applications/${appId}/fast-track`);
export const retryAnalysis = (companyId, appId) => post(`${base(companyId)}/applications/${appId}/analysis/retry`);
export const retryTranscription = (companyId, appId) => post(`${base(companyId)}/applications/${appId}/transcription/retry`);
export const inviteAnyway = (companyId, appId) => post(`${base(companyId)}/applications/${appId}/invite-anyway`);
export const bulkReject = (companyId, jobId, applicationIds) =>
  post(`${base(companyId)}/jobs/${jobId}/decisions/bulk`, { application_ids: applicationIds });

// Audio needs the sign-in token, so it is fetched on demand and played from a local object URL.
export async function fetchTurnAudio(companyId, appId, position) {
  const response = await fetch(`${API_URL}${base(companyId)}/applications/${appId}/turns/${position}/audio`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) throw new ApiError(response.status, `Request failed (${response.status})`);
  return URL.createObjectURL(await response.blob());
}

export const isUndecided = (card) => card.hr_decision === 'pending';
