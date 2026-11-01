import { api } from './api.js';

const trust = (companyId) => `/api/companies/${companyId}/trust`;

export const listConsents = (companyId, page = 1) => api(`${trust(companyId)}/consents?page=${page}`);

export const listAudit = (companyId, { action = '', page = 1 } = {}) => {
  const params = new URLSearchParams({ page: String(page) });
  if (action) params.set('action', action);
  return api(`${trust(companyId)}/audit?${params}`);
};

export const getRetention = (companyId) => api(`${trust(companyId)}/retention`);

export const runFairnessCheck = (companyId, applicationId) =>
  api(`${trust(companyId)}/fairness-check`, { method: 'POST', body: { application_id: applicationId } });

// The API has no application list, so the picker is built from each job's board: id and alias only.
export async function listApplicationChoices(companyId) {
  const jobs = await api(`/api/companies/${companyId}/jobs`);
  const boards = await Promise.all(
    jobs.map((job) => api(`/api/companies/${companyId}/jobs/${job.id}/board`).then((board) => ({ job, board }))),
  );
  return boards
    .flatMap(({ job, board }) =>
      [...Object.values(board.cells), ...Object.values(board.lanes)]
        .flat()
        .map((card) => ({ id: card.id, alias: card.alias, jobTitle: job.title })),
    )
    .sort((a, b) => a.id - b.id);
}

// Actions the audit log records. The API accepts any text, so this only offers the known ones.
export const AUDIT_ACTIONS = [
  'cv_assessed',
  'voice_session_started',
  'voice_session_completed',
  'voice_session_expired',
  'recording_declined',
  'fast_tracked',
  'hr_decision',
  'cv_status_corrected',
  'identity_revealed',
  'audio_played',
  'restart_granted',
  'analysis_retried',
  'fairness_check',
  'consent_withdrawn',
  'application_withdrawn',
  'application_anonymized',
  'reminder_queued',
];
