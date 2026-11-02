import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect } from '@playwright/test';

export const API_URL = `http://localhost:${process.env.E2E_API_PORT || '8099'}`;
export const HR_EMAIL = 'hr@e2e.test';
export const NEW_PASSWORD = 'e2e-hr-own-password';
export const CORS = { 'access-control-allow-origin': '*' };

// Each spec file that changes knowledge or passwords uses its own company, so spec order does not matter.
export const LOGIN_USER = { email: HR_EMAIL, passwordFile: 'portal_e2e_password' };
export const BRAIN_USER = { email: 'brain-hr@e2e.test', passwordFile: 'portal_e2e_brain_password' };

export const INTAKE_USER = { email: 'intake-hr@e2e.test', passwordFile: 'portal_e2e_intake_password' };
export const BOARD_USER = { email: 'board-hr@e2e.test', passwordFile: 'portal_e2e_board_password' };
export const SWITCH_USER = { email: 'switch-hr@e2e.test', passwordFile: 'portal_e2e_switch_password' };

export const temporaryPassword = (user = LOGIN_USER) => readFileSync(join(process.env.E2E_TMP, user.passwordFile), 'utf8');

// The first login test changes the password in the browser. This keeps later tests independent of that one.
export async function ensurePasswordChanged(request, user = LOGIN_USER) {
  const login = (password) => request.post(`${API_URL}/api/login`, { data: { email: user.email, password } });
  if ((await login(NEW_PASSWORD)).ok()) return;
  const first = await login(temporaryPassword(user));
  // Another worker may have changed the password between the two logins.
  if (!first.ok()) {
    expect((await login(NEW_PASSWORD)).ok()).toBe(true);
    return;
  }
  const { access_token: token } = await first.json();
  const changed = await request.post(`${API_URL}/api/me/password`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { current_password: temporaryPassword(user), new_password: NEW_PASSWORD },
  });
  expect(changed.ok()).toBe(true);
}

export async function fillLogin(page, password, user = LOGIN_USER) {
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

export async function signIn(page, user = LOGIN_USER) {
  await ensurePasswordChanged(page.request, user);
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await fillLogin(page, NEW_PASSWORD, user);
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

const bearer = (token) => ({ Authorization: `Bearer ${token}` });

export async function apiLogin(request, email, password) {
  const response = await request.post(`${API_URL}/api/login`, { data: { email, password } });
  expect(response.ok()).toBe(true);
  return (await response.json()).access_token;
}

// HR's token and company for a user who can already sign in with this password.
export async function hrSession(request, email, password) {
  const token = await apiLogin(request, email, password);
  const me = await (await request.get(`${API_URL}/api/me`, { headers: bearer(token) })).json();
  return { token, headers: bearer(token), companyId: me.memberships.find((m) => m.role === 'hr').company_id };
}

// HR adds a manager through the API and the manager picks their own password, as the forced-change screen would.
export async function addManager(request, hr, { email, fullName, password, departmentId = null }) {
  const added = await request.post(`${API_URL}/api/companies/${hr.companyId}/members`, {
    headers: hr.headers,
    data: { email, full_name: fullName, role: 'manager', department_id: departmentId },
  });
  expect(added.ok()).toBe(true);
  const { user_id: userId, temporary_password: temporary } = await added.json();
  const token = await apiLogin(request, email, temporary);
  const changed = await request.post(`${API_URL}/api/me/password`, {
    headers: bearer(token),
    data: { current_password: temporary, new_password: password },
  });
  expect(changed.ok()).toBe(true);
  return userId;
}
