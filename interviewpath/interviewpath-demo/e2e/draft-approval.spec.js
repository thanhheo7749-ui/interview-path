import { expect, test } from '@playwright/test';
import { API_URL, addManager, hrSession } from './helpers.js';

// What an approval covers and who gives it. The manager approves the version on their page, so a draft that moved answers
// 409 and the page shows what it says now. The manager can send a draft back with a comment, which HR reads in JD Studio,
// and HR can edit or cancel a request from the list.
const SAMPLE_PASSWORD = 'e2e-sample-password-123';
const HR = 'hr@daehan-precision.sample';
const WEB_URL = `http://localhost:${process.env.E2E_WEB_PORT || '5199'}`;
const RUN = Date.now().toString(36);
const MANAGER_EMAIL = `approve-mgr-${RUN}@e2e.test`;
const SECOND_EMAIL = `approve-second-${RUN}@e2e.test`;
const MANAGER_PASSWORD = 'approve-manager-pass-123';

async function setup(page) {
  const hr = await hrSession(page.request, HR, SAMPLE_PASSWORD);
  const url = (tail) => `${API_URL}/api/companies/${hr.companyId}${tail}`;
  const roles = await (await page.request.get(url('/jobs/role-options'), { headers: hr.headers })).json();
  const role = roles.find((r) => r.title === 'Backend Developer');
  return { hr, url, role };
}

async function draftInReview(page, { hr, url, role }, title, managerId) {
  const created = await page.request.post(url('/hiring-requests'), {
    headers: hr.headers, data: { title, manager_user_id: managerId, department_id: role.department_id },
  });
  expect(created.ok()).toBe(true);
  const generated = await page.request.post(url(`/hiring-requests/${(await created.json()).id}/drafts`), {
    headers: hr.headers, data: { role_node_id: role.id },
  });
  expect(generated.ok()).toBe(true);
  const draft = await generated.json();
  expect((await page.request.post(url(`/job-drafts/${draft.id}/submit`), { headers: hr.headers })).ok()).toBe(true);
  return draft;
}

async function signIn(page, email, password) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

test('an approval names the version on the page, and a draft that moved shows what it says now', async ({ page, browser }) => {
  const world = await setup(page);
  const managerId = await addManager(page.request, world.hr, {
    email: MANAGER_EMAIL, fullName: 'Approve Manager', password: MANAGER_PASSWORD, departmentId: world.role.department_id,
  });
  const secondId = await addManager(page.request, world.hr, {
    email: SECOND_EMAIL, fullName: 'Second Manager', password: MANAGER_PASSWORD, departmentId: world.role.department_id,
  });
  expect(secondId).not.toBe(managerId);
  const title = `Approve ${RUN}`;
  const draft = await draftInReview(page, world, title, managerId);
  const draftUrl = world.url(`/job-drafts/${draft.id}`);

  const context = await browser.newContext({ baseURL: WEB_URL });
  const manager = await context.newPage();
  await signIn(manager, MANAGER_EMAIL, MANAGER_PASSWORD);
  await expect(manager.getByRole('heading', { name: '회사 설정' })).toBeVisible();
  await manager.goto(`/jd-studio/${draft.id}`);
  await expect(manager.getByTestId('draft-status')).toContainText('매니저 검토 대기');
  const shown = Number(await manager.getByTestId('draft-version').getAttribute('data-version'));
  const lineId = (await (await page.request.get(draftUrl, { headers: world.hr.headers })).json()).lines[0].id;

  // HR changes the text and submits again while the manager's page still shows the old version.
  const changed = 'Changed while the manager was reading';
  const patched = await page.request.patch(draftUrl, {
    headers: world.hr.headers, data: { lines: [{ id: lineId, text: { ko: changed } }] },
  });
  expect(patched.ok()).toBe(true);
  expect((await page.request.post(`${draftUrl}/submit`, { headers: world.hr.headers })).ok()).toBe(true);

  const [refused] = await Promise.all([
    manager.waitForResponse((r) => r.url().endsWith(`/job-drafts/${draft.id}/approve`)),
    manager.getByRole('button', { name: '승인', exact: true }).click(),
  ]);
  expect(refused.status()).toBe(409);
  expect(refused.request().postDataJSON()).toEqual({ version: shown });
  await expect(manager.getByRole('alert')).toBeVisible();
  await expect(manager.getByTestId('jd-lines').getByRole('listitem').first().getByTestId('jd-line-text')).toHaveText(changed);
  await expect(manager.getByTestId('draft-status')).toContainText('매니저 검토 대기');

  // Now the page shows the new version, and approving it works.
  const [accepted] = await Promise.all([
    manager.waitForResponse((r) => r.url().endsWith(`/job-drafts/${draft.id}/approve`)),
    manager.getByRole('button', { name: '승인', exact: true }).click(),
  ]);
  expect(accepted.status()).toBe(200);
  await expect(manager.getByTestId('draft-status')).toContainText('승인됨');
  await context.close();

  // A second manager of the same department was not assigned: the draft does not exist for them.
  const token = (await (await page.request.post(`${API_URL}/api/login`, {
    data: { email: SECOND_EMAIL, password: MANAGER_PASSWORD },
  })).json()).access_token;
  const asSecond = await page.request.get(draftUrl, { headers: { Authorization: `Bearer ${token}` } });
  expect(asSecond.status()).toBe(404);
});

test('the manager sends a draft back with a comment, which HR reads in JD Studio', async ({ page, browser }) => {
  const world = await setup(page);
  const email = `feedback-mgr-${RUN}@e2e.test`;
  const managerId = await addManager(page.request, world.hr, {
    email, fullName: 'Feedback Manager', password: MANAGER_PASSWORD, departmentId: world.role.department_id,
  });
  const draft = await draftInReview(page, world, `Feedback ${RUN}`, managerId);

  const context = await browser.newContext({ baseURL: WEB_URL });
  const manager = await context.newPage();
  await signIn(manager, email, MANAGER_PASSWORD);
  await expect(manager.getByRole('heading', { name: '회사 설정' })).toBeVisible();
  await manager.goto(`/jd-studio/${draft.id}`);
  const comment = `첫 문장을 바꿔 주세요 ${RUN}`;
  await expect(manager.getByRole('button', { name: '수정 요청' })).toBeDisabled();
  await manager.getByLabel('무엇을 바꿔야 하나요?').fill(comment);
  await manager.getByRole('button', { name: '수정 요청' }).click();
  await expect(manager.getByTestId('draft-status')).toContainText('초안');
  await expect(manager.getByRole('button', { name: '승인', exact: true })).toHaveCount(0);
  await context.close();

  await signIn(page, HR, SAMPLE_PASSWORD);
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
  await page.goto(`/jd-studio/${draft.id}`);
  await expect(page.getByTestId('draft-status')).toContainText('Draft');
  await expect(page.getByTestId('manager-feedback')).toContainText(comment);
  await expect(page.getByRole('button', { name: 'Submit to manager' })).toBeEnabled();
});

test('HR edits a request and cancels it from the list', async ({ page }) => {
  const world = await setup(page);
  const email = `list-mgr-${RUN}@e2e.test`;
  const managerId = await addManager(page.request, world.hr, {
    email, fullName: 'List Manager', password: MANAGER_PASSWORD, departmentId: world.role.department_id,
  });
  const before = `Listed ${RUN}`;
  const after = `Renamed ${RUN}`;
  const created = await page.request.post(world.url('/hiring-requests'), {
    headers: world.hr.headers, data: { title: before, manager_user_id: managerId },
  });
  expect(created.ok()).toBe(true);

  await signIn(page, HR, SAMPLE_PASSWORD);
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
  await page.getByRole('link', { name: 'Hiring requests' }).click();
  const row = page.getByRole('listitem').filter({ hasText: before });
  await row.getByRole('button', { name: `Edit request: ${before}` }).click();
  const form = page.getByTestId('edit-request');
  await expect(form.getByLabel('Hiring manager').locator('option', { hasText: 'List Manager' })).toHaveCount(1);
  await form.getByLabel('Role to hire').fill(after);
  await form.getByRole('button', { name: 'Save' }).click();

  const renamed = page.getByRole('listitem').filter({ hasText: after });
  await expect(renamed.getByRole('button', { name: 'Generate draft' })).toBeVisible();
  await renamed.getByRole('button', { name: `Cancel request: ${after}` }).click();
  await renamed.getByRole('alertdialog').getByRole('button', { name: 'Cancel request' }).click();
  await expect(renamed.getByTestId('request-status')).toHaveText('Cancelled');
  await expect(renamed.getByRole('button', { name: 'Generate draft' })).toHaveCount(0);
  await expect(renamed.getByRole('button', { name: `Cancel request: ${after}` })).toHaveCount(0);
});
