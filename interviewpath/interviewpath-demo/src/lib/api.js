import i18n from '../i18n/index.js';

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8001').replace(/\/$/, '');
const TOKEN_KEY = 'portal_token';

export class ApiError extends Error {
  constructor(status, message, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (token) => sessionStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);

export async function api(path, { method = 'GET', body, formData, skipAuthRedirect = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });

  if (response.status === 401 && !skipAuthRedirect) {
    clearToken();
    if (window.location.pathname !== '/login') window.location.assign('/login');
    throw new ApiError(401, 'Session expired');
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    // The company has used up its daily AI allowance: say so in the user's language, wherever the error is shown.
    if (detail.code === 'ai_budget_exceeded') throw new ApiError(response.status, i18n.t('common.aiBudgetExceeded'), detail.code);
    // A detail is text, or an object whose `message` says what happened (a draft blocked by lint, for one).
    const text = typeof detail.detail === 'string' ? detail.detail : detail.detail?.message;
    throw new ApiError(response.status, typeof text === 'string' && text ? text : `Request failed (${response.status})`, detail.detail?.code);
  }
  return response.status === 204 ? null : response.json();
}
