import { api } from './api.js';

const base = (companyId, jobId) => `/api/companies/${companyId}/jobs/${jobId}`;
const query = (data) => (data ? `?data=${data}` : '');

// The API speaks English and Vietnamese; Korean readers get English commentary.
export const apiLanguage = (language) => (language === 'vi' ? 'vi' : 'en');

export const getChannels = (companyId, jobId, data) => api(`${base(companyId, jobId)}/channels${query(data)}`);

export const getCommentary = (companyId, jobId, data, language) =>
  api(`${base(companyId, jobId)}/channels/commentary`, { method: 'POST', body: { data, language: apiLanguage(language) } });

export const saveCost = (companyId, jobId, item) =>
  api(`/api/companies/${companyId}/channel-costs`, { method: 'POST', body: { job_id: jobId, items: [item] } });

export const uploadCostsCsv = (companyId, jobId, file) => {
  const form = new FormData();
  form.append('job_id', String(jobId));
  form.append('file', file);
  return api(`/api/companies/${companyId}/channel-costs`, { method: 'POST', formData: form });
};

export const getRealityCheck = (companyId, jobId, data) => api(`${base(companyId, jobId)}/reality-check${query(data)}`);

export const saveThresholds = (companyId, thresholds) => api(`/api/companies/${companyId}`, { method: 'PATCH', body: thresholds });

// Rates arrive as fractions. They show as percent with one decimal, the form the commentary check uses.
export const percent = (rate) => (rate == null ? null : `${(Math.round(rate * 1000) / 10).toFixed(1)}%`);

export const vnd = (amount) => (amount == null ? null : new Intl.NumberFormat('en-US').format(amount));

// Nulls sort last in both directions.
export function sortRows(rows, key, direction) {
  const sign = direction === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = a[key];
    const y = b[key];
    if (x == null || y == null) return x == null && y == null ? 0 : x == null ? 1 : -1;
    return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sign;
  });
}

// A CSV with bad lines answers with a list of {line, message}; ApiError keeps it in `data`.
export const errorText = (error) =>
  Array.isArray(error?.data) ? error.data.map((e) => `${e.line}: ${e.message}`).join('; ') : error.message;
