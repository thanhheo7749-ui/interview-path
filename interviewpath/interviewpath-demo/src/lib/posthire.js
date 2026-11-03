import { api } from './api.js';
import { getGraph } from './kb.js';

const base = (companyId) => `/api/companies/${companyId}`;

// Feedback. HR approves every message before it reaches the candidate.
export const listFeedback = (companyId, jobId, status) =>
  api(`${base(companyId)}/jobs/${jobId}/feedback${status ? `?status=${status}` : ''}`);
export const getFeedback = (companyId, appId) => api(`${base(companyId)}/applications/${appId}/feedback`);
export const draftFeedback = (companyId, appId) => api(`${base(companyId)}/applications/${appId}/feedback/draft`, { method: 'POST' });
export const saveFeedback = (companyId, appId, draft) =>
  api(`${base(companyId)}/applications/${appId}/feedback`, { method: 'PATCH', body: { draft } });
export const approveFeedback = (companyId, applicationIds) =>
  api(`${base(companyId)}/feedback/approve`, { method: 'POST', body: { application_ids: applicationIds } });

// The learning catalogue: the only source of links in feedback.
export const listResources = (companyId) => api(`${base(companyId)}/learning-resources`);
export const addResource = (companyId, resource) =>
  api(`${base(companyId)}/learning-resources`, { method: 'POST', body: resource });
export const deleteResource = (companyId, id) => api(`${base(companyId)}/learning-resources/${id}`, { method: 'DELETE' });
export const listSkills = async (companyId) => (await getGraph(companyId)).nodes.filter((node) => node.type === 'skill');

// Talent pool. Matching calls the AI, so it runs only when HR asks.
export const getTalentMatches = (companyId, jobId) => api(`${base(companyId)}/jobs/${jobId}/talent-matches`);
export const inviteFromPool = (companyId, entryId, jobId) =>
  api(`${base(companyId)}/talent-pool/${entryId}/invite`, { method: 'POST', body: { job_id: jobId } });
