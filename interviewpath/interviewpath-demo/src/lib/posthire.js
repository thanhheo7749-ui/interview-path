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
// `items` are { application_id, version }: the version names the text HR read, and a changed text is refused.
export const approveFeedback = (companyId, items) =>
  api(`${base(companyId)}/feedback/approve`, { method: 'POST', body: { items } });

// The guard sends codes, such as "comparison: other candidates". A list, or a map of lists by application.
export const reasonList = (problems) => {
  const flat = Array.isArray(problems) ? problems : Object.values(problems ?? {}).flat();
  return flat.map((problem) => {
    const [code, ...rest] = String(problem).split(': ');
    return { code, detail: rest.join(': ') };
  });
};

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

// Onboarding 30-60-90. Creating a plan calls the AI; HR and the department's manager edit and approve it.
export const createOnboarding = (companyId, appId) =>
  api(`${base(companyId)}/applications/${appId}/onboarding`, { method: 'POST' });
export const getOnboarding = (companyId, planId) => api(`${base(companyId)}/onboarding/${planId}`);
export const editOnboarding = (companyId, planId, items) =>
  api(`${base(companyId)}/onboarding/${planId}`, { method: 'PATCH', body: { items } });
export const approveOnboarding = (companyId, planId) =>
  api(`${base(companyId)}/onboarding/${planId}/approve`, { method: 'POST' });
export const recordProbation = (companyId, appId, result) =>
  api(`${base(companyId)}/applications/${appId}/probation`, { method: 'POST', body: { result } });
// The hire's own checklist. The only progress kept is the time an item was ticked.
export const getMyOnboarding = (companyId) => api(`${base(companyId)}/my-onboarding`);
export const tickOnboardingItem = (companyId, itemId) =>
  api(`${base(companyId)}/onboarding/items/${itemId}/done`, { method: 'POST' });
