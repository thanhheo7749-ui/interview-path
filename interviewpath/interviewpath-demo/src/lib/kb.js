import { api } from './api.js';

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

export function getAiStatus() {
  return api('/api/ai-status');
}
