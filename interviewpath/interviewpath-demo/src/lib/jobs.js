import { api } from './api.js';

const jobsPath = (companyId) => `/api/companies/${companyId}/jobs`;

// Address of the candidate-facing site, where channel links point.
export const SPEAKCV_URL = (import.meta.env.VITE_SPEAKCV_URL || 'http://localhost:3000').replace(/\/$/, '');

export const INTERVIEW_LANGUAGES = ['vi', 'en', 'ko'];
export const REQUIREMENT_VISIBILITIES = ['public', 'internal', 'confidential'];
// Channels created when a job is published. HR can add more by name.
export const DEFAULT_CHANNELS = ['company_site', 'linkedin', 'referral'];
export const CHANNEL_PATTERN = /^[a-z0-9_]{1,50}$/;

export const channelUrl = (slug, token) => `${SPEAKCV_URL}/jobs/${slug}?src=${encodeURIComponent(token)}`;

export const listJobs = (companyId) => api(jobsPath(companyId));
export const getJob = (companyId, jobId) => api(`${jobsPath(companyId)}/${jobId}`);
export const listRoleOptions = (companyId) => api(`${jobsPath(companyId)}/role-options`);
export const getPrefill = (companyId, roleNodeId) => api(`${jobsPath(companyId)}/prefill?role_node_id=${roleNodeId}`);
export const createJob = (companyId, body) => api(jobsPath(companyId), { method: 'POST', body });
export const patchJob = (companyId, jobId, body) => api(`${jobsPath(companyId)}/${jobId}`, { method: 'PATCH', body });
export const publishJob = (companyId, jobId) => api(`${jobsPath(companyId)}/${jobId}/publish`, { method: 'POST' });
export const closeJob = (companyId, jobId) => api(`${jobsPath(companyId)}/${jobId}/close`, { method: 'POST' });
export const addChannels = (companyId, jobId, channels) =>
  api(`${jobsPath(companyId)}/${jobId}/channels`, { method: 'POST', body: { channels } });
