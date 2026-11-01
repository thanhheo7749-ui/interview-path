import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

const API_URL = 'http://localhost:8099';
const HR_EMAIL = 'hr@e2e.test';
const NEW_PASSWORD = 'e2e-hr-own-password';
const CORS = { 'access-control-allow-origin': '*' };

const temporaryPassword = () => readFileSync(join(process.env.E2E_TMP, 'portal_e2e_password'), 'utf8');

// The first test changes the password in the browser. This keeps later tests independent of that one.
async function ensurePasswordChanged(request) {
  const login = (password) => request.post(`${API_URL}/api/login`, { data: { email: HR_EMAIL, password } });
  if ((await login(NEW_PASSWORD)).ok()) return;
  const { access_token: token } = await (await login(temporaryPassword())).json();
  const changed = await request.post(`${API_URL}/api/me/password`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { current_password: temporaryPassword(), new_password: NEW_PASSWORD },
  });
  expect(changed.ok()).toBe(true);
}

async function fillLogin(page, password) {
  await page.getByLabel('Email').fill(HR_EMAIL);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

async function signIn(page) {
  await ensurePasswordChanged(page.request);
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await fillLogin(page, NEW_PASSWORD);
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

test('first sign-in with a temporary password forces a change before anything else', async ({ page }) => {
  await page.goto('/login');
  await fillLogin(page, temporaryPassword());

  await expect(page.getByRole('heading', { name: 'Set a new password' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Company settings' })).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Set a new password' })).toBeVisible();

  await page.getByLabel('Current password').fill('not-the-current-password');
  await page.getByLabel('New password', { exact: true }).fill(NEW_PASSWORD);
  await page.getByLabel('Repeat new password').fill(NEW_PASSWORD);
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByRole('alert')).toContainText('Current password is incorrect');
  await expect(page.getByRole('heading', { name: 'Set a new password' })).toBeVisible();

  await page.getByLabel('Current password').fill(temporaryPassword());
  const changed = page.waitForResponse('**/api/me/password');
  await page.getByRole('button', { name: 'Change password' }).click();
  const { access_token: freshToken } = await (await changed).json();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
  await expect(page.getByText('Sample data')).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('portal_token'))).toBe(freshToken);

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
});

test('the temporary password stops working once it is changed', async ({ page }) => {
  await ensurePasswordChanged(page.request);
  await page.goto('/login');
  await fillLogin(page, temporaryPassword());
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test('the change password page is reachable from the sidebar and keeps the session on a wrong password', async ({ page }) => {
  await signIn(page);
  await page.getByRole('link', { name: 'Change password' }).click();
  await expect(page).toHaveURL(/\/account\/password$/);
  await expect(page.getByRole('heading', { name: 'Change password' })).toBeVisible();

  await page.getByLabel('Current password').fill('not-the-current-password');
  await page.getByLabel('New password', { exact: true }).fill('another-long-password');
  await page.getByLabel('Repeat new password').fill('a-different-long-password');
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByRole('alert')).toContainText('do not match');

  await page.getByLabel('Repeat new password').fill('another-long-password');
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByRole('alert')).toContainText('Current password is incorrect');
  await expect(page).toHaveURL(/\/account\/password$/);
});

test('a failing /api/me shows an error with Retry instead of loading forever', async ({ page }) => {
  await signIn(page);
  const fail = (route) => route.fulfill({ status: 500, headers: CORS, json: { detail: 'boom' } });
  await page.route('**/api/me', fail);
  await page.reload();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('status')).toHaveCount(0);

  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('alert')).toBeVisible();

  await page.unroute('**/api/me', fail);
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
});

test('a failing /api/me still lets the user sign out', async ({ page }) => {
  await signIn(page);
  await page.route('**/api/me', (route) => route.fulfill({ status: 500, headers: CORS, json: { detail: 'boom' } }));
  await page.reload();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
});

test('switching company clears the previous one at once and the banner follows the membership', async ({ page }) => {
  const membership = (id, name, isSample) => ({
    member_id: id, company_id: id, company_slug: name, company_name: name, is_sample: isSample, role: 'employee', department_id: null,
  });
  const company = (id, name, isSample) => ({
    id, slug: name, name, is_sample: isSample, default_locale: 'en', retention_days: 90, kb_version: 1,
  });
  let releaseSecond;
  const secondMayAnswer = new Promise((resolve) => {
    releaseSecond = resolve;
  });

  await page.addInitScript(() => {
    if (!sessionStorage.getItem('portal_token')) sessionStorage.setItem('portal_token', 'stubbed');
  });
  await page.route('**/api/me', (route) => route.fulfill({
    headers: CORS,
    json: {
      id: 1, email: HR_EMAIL, full_name: 'HR', role: 'user', must_change_password: false,
      memberships: [membership(1, 'Alpha', true), membership(2, 'Beta', false)],
    },
  }));
  await page.route('**/api/companies/1', (route) => route.fulfill({ headers: CORS, json: company(1, 'Alpha from server', true) }));
  await page.route('**/api/companies/2', async (route) => {
    await secondMayAnswer;
    await route.fulfill({ headers: CORS, json: company(2, 'Beta from server', false) });
  });
  await page.route('**/api/companies/*/departments', (route) => route.fulfill({ headers: CORS, json: [] }));

  await page.goto('/settings');
  await expect(page.getByText('Alpha from server')).toBeVisible();
  await expect(page.getByText('Sample data')).toBeVisible();

  await page.getByLabel('Company', { exact: true }).selectOption({ label: 'Beta' });
  await expect(page.getByText('Alpha from server')).toHaveCount(0);
  await expect(page.getByText('Sample data')).toHaveCount(0);

  releaseSecond();
  await expect(page.getByText('Beta from server')).toBeVisible();
});

test('wrong password shows an error and stays on login', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(HR_EMAIL);
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test('HR manages departments and members in the real database', async ({ page }) => {
  await signIn(page);
  await expect(page.getByText('Sample data')).toBeVisible();

  await page.getByLabel('New department name').fill('Engineering');
  await page.getByRole('button', { name: 'Add department' }).click();
  await expect(page.getByRole('treeitem', { name: /Engineering/ })).toBeVisible();

  await page.getByLabel('Member email').fill('new.employee@e2e.test');
  await page.getByLabel('Member role').selectOption('employee');
  await page.getByRole('button', { name: 'Add member' }).click();
  await expect(page.getByRole('cell', { name: 'new.employee@e2e.test' })).toBeVisible();
  await expect(page.getByText(/temporary password/i)).toBeVisible();

  await page.reload();
  await expect(page.getByRole('treeitem', { name: /Engineering/ })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'new.employee@e2e.test' })).toBeVisible();
});

test('language switches to Vietnamese', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: 'Tiếng Việt' }).click();
  await expect(page.getByRole('heading', { name: 'Cài đặt công ty' })).toBeVisible();
});

test('an expired token lands on the login page', async ({ page }) => {
  await signIn(page);
  await page.evaluate(() => sessionStorage.setItem('portal_token', 'not-a-valid-token'));
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
});

test('no page mentions the removed demo features', async ({ page }) => {
  await signIn(page);
  await expect(page.getByText(/n8n/i)).toHaveCount(0);
  await expect(page.getByRole('link', { name: /RAG Knowledge Graph|Workflow/ })).toHaveCount(0);
});
