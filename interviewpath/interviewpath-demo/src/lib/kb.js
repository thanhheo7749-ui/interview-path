import { api } from './api.js';

const kb = (companyId) => `/api/companies/${companyId}/kb`;

// Pages call this after a change so the sidebar badges refresh.
export const KB_CHANGED_EVENT = 'kb-changed';
export const notifyKbChanged = () => window.dispatchEvent(new Event(KB_CHANGED_EVENT));

// A cosmetic notice must never sign the user out.
export const getAiStatus = () => api('/api/ai-status', { skipAuthRedirect: true });

export const listDocuments = (companyId) => api(`${kb(companyId)}/documents`);

// `form` is a FormData with file, title, visibility and optionally department_id and effective_date.
export const uploadDocument = (companyId, form) => api(`${kb(companyId)}/documents`, { method: 'POST', formData: form });

export const getJob = (companyId, jobId) => api(`${kb(companyId)}/jobs/${jobId}`);

export const retryJob = (companyId, jobId) => api(`${kb(companyId)}/jobs/${jobId}/retry`, { method: 'POST' });

export const getReviewQueue = (companyId) => api(`${kb(companyId)}/review`);

export const decideReview = (companyId, items) =>
  api(`${kb(companyId)}/review/decide`, { method: 'POST', body: { items } });

export const listConflicts = (companyId) => api(`${kb(companyId)}/conflicts`);

export const resolveConflict = (companyId, conflictId, action) =>
  api(`${kb(companyId)}/conflicts/${conflictId}/resolve`, { method: 'POST', body: { action } });

export const listGaps = (companyId) => api(`${kb(companyId)}/gaps`);

export const resolveGap = (companyId, groupId) => api(`${kb(companyId)}/gaps/${groupId}/resolve`, { method: 'POST' });

export function getGraph(companyId, { viewAs, departmentId } = {}) {
  const params = new URLSearchParams();
  if (viewAs) params.set('view_as', viewAs);
  if (departmentId != null) params.set('department_id', String(departmentId));
  const query = params.toString();
  return api(`/api/companies/${companyId}/kb/graph${query ? `?${query}` : ''}`);
}

export function askCopilot(companyId, question) {
  return api(`/api/companies/${companyId}/copilot/ask`, { method: 'POST', body: { question } });
}
