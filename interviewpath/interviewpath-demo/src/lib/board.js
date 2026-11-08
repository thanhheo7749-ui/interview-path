import { API_URL, ApiError, api, getToken } from './api.js';

const base = (companyId) => `/api/companies/${companyId}`;
const post = (path, body) => api(path, { method: 'POST', body });

// The four cells in reading order: rows are the CV, columns are the amount of interview evidence.
export const CELLS = ['priority', 'strong_cv_unclear', 'hidden_gem', 'not_enough_evidence'];
export const LANES = ['cv_hold', 'missing_contact', 'analyzing', 'analysis_failed', 'transcription_failed', 'cv_failed', 'not_interviewed', 'refused_recording', 'withdrawn'];

export const CANDIDATE_PORTAL_URL = import.meta.env.VITE_CANDIDATE_URL || 'http://localhost:3001';

export const getBoard = (companyId, jobId) => api(`${base(companyId)}/jobs/${jobId}/board`);
export const getApplication = (companyId, appId) => api(`${base(companyId)}/applications/${appId}`);
export const getCandidateAccounts = (companyId, jobId = null) =>
  api(`${base(companyId)}/candidate-accounts${jobId ? `?job_id=${jobId}` : ''}`);
export const resetCandidateCredentials = (companyId, appId, payload = {}) =>
  post(`${base(companyId)}/candidate-accounts/${appId}/reset-credentials`, payload);
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
export const inviteFromHold = (companyId, appId) => post(`${base(companyId)}/applications/${appId}/invite-from-hold`);
export const updateContact = (companyId, appId, payload) =>
  post(`${base(companyId)}/applications/${appId}/contact`, payload);
export const bulkReject = (companyId, jobId, applicationIds) =>
  post(`${base(companyId)}/jobs/${jobId}/decisions/bulk`, { application_ids: applicationIds });

export async function importCvs(companyId, jobId, sourceChannel, fileList) {
  const form = new FormData();
  form.append('source_channel', sourceChannel);
  for (const file of fileList) {
    form.append('files', file);
  }
  const response = await fetch(`${API_URL}${base(companyId)}/jobs/${jobId}/import-cvs`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` },
    body: form,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

// Audio needs the sign-in token, so it is fetched on demand and played from a local object URL.
export async function fetchTurnAudio(companyId, appId, position) {
  const response = await fetch(`${API_URL}${base(companyId)}/applications/${appId}/turns/${position}/audio`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) throw new ApiError(response.status, `Request failed (${response.status})`);
  return URL.createObjectURL(await response.blob());
}

export async function downloadCvFile(companyId, appId, fallbackName = 'CV') {
  const response = await fetch(`${API_URL}${base(companyId)}/applications/${appId}/cv-file`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) throw new ApiError(response.status, `Request failed (${response.status})`);
  const blob = await response.blob();
  const cd = response.headers.get('Content-Disposition') || '';
  const match = cd.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `${fallbackName}.docx`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

const AVATAR_PALETTES = [
  ['#2563eb', '#dbeafe'],
  ['#059669', '#d1fae5'],
  ['#7c3aed', '#ede9fe'],
  ['#d97706', '#fef3c7'],
  ['#db2777', '#fce7f3'],
  ['#0891b2', '#cffafe'],
];

export function getCandidateInitials(name, alias) {
  const clean = (name || '').trim();
  if (!clean) return (alias || 'CV').replace('#', '').slice(0, 2).toUpperCase();
  const parts = clean.split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function getCandidateAvatarUrl(name, alias, id = 1) {
  const seed = encodeURIComponent((name || alias || `user-${id}`).trim());
  return `https://api.dicebear.com/9.x/notionists/svg?seed=${seed}&backgroundColor=dbeafe,d1fae5,ede9fe,fef3c7,fce7f3`;
}

export function getCandidatePalette(id = 1) {
  return AVATAR_PALETTES[Math.abs(Number(id) || 1) % AVATAR_PALETTES.length];
}

export const isUndecided = (card) => card.hr_decision === 'pending';
export const CONSENT_WITHDRAWN = 'consent_withdrawn';
// A candidate who withdrew consent to recording is never rejected along with others: HR decides on them alone.
export const isBulkSelectable = (card) => isUndecided(card) && card.analysis_status !== CONSENT_WITHDRAWN;
