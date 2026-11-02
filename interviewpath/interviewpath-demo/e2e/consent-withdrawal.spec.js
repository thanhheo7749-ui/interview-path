import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { API_URL } from './helpers.js';

// A candidate withdraws recording consent during a real interview. The candidate app says so with no retry, My data
// says what each withdrawal does, and HR finds the application in Not enough evidence, to decide on it alone.
test.describe.configure({ mode: 'serial' });

const SAMPLE_PASSWORD = 'e2e-sample-password-123';
const HR = 'hr@sori-labs.sample';
const CANDIDATE_URL = `http://localhost:${process.env.E2E_CANDIDATE_PORT || '3199'}`;
const CV = readFileSync(join(import.meta.dirname, 'fixtures', 'trust-cv.docx'));
const PASSWORD = 'e2e-candidate-password-123';
const email = `withdraw-${Date.now()}@example.test`;
const auth = (token) => ({ Authorization: `Bearer ${token}` });
const state = {};

async function login(request, who, password) {
  const response = await request.post(`${API_URL}/api/login`, { data: { email: who, password } });
  expect(response.ok()).toBe(true);
  return (await response.json()).access_token;
}

test.beforeAll(async ({ request }) => {
  const hrToken = await login(request, HR, SAMPLE_PASSWORD);
  const me = await (await request.get(`${API_URL}/api/me`, { headers: auth(hrToken) })).json();
  const companyId = me.memberships[0].company_id;
  const jobs = await (await request.get(`${API_URL}/api/companies/${companyId}/jobs`, { headers: auth(hrToken) })).json();
  const job = jobs.find((item) => item.status === 'published');
  expect((await request.post(`${API_URL}/api/register`, { data: { email, password: PASSWORD, full_name: 'Withdraw Zebrawski' } })).ok()).toBe(true);
  const token = await login(request, email, PASSWORD);
  const shown = await (await request.get(`${API_URL}/api/consents/cv_processing`, { headers: auth(token) })).json();
  const applied = await request.post(`${API_URL}/api/public/jobs/${job.slug}/apply`, {
    headers: auth(token),
    multipart: {
      consent_version: shown.version,
      consent_language: shown.language,
      file: { name: 'cv.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: CV },
    },
  });
  expect(applied.status()).toBe(201);
  const application = await applied.json();
  const url = `${API_URL}/api/applications/${application.id}`;
  await expect.poll(async () => (await (await request.get(url, { headers: auth(token) })).json()).status, { timeout: 60000 }).toBe('invited');

  const consent = await (await request.get(`${url}/consents/recording_screening?language=en`, { headers: auth(token) })).json();
  // The text states this company's retention period, in the wording the candidate agrees to.
  expect(consent.text).toContain('days after the decision');
  expect(consent.language).toBe('en');
  const started = await request.post(`${API_URL}/api/screening/${application.id}/start`, {
    headers: auth(token),
    data: { consent_version: consent.version, language: application.interview_languages[0], consent_language: consent.language },
  });
  expect(started.ok()).toBe(true);
  Object.assign(state, { token, jobId: job.id, alias: application.alias, applicationId: application.id });
});

async function candidatePage(browser) {
  const context = await browser.newContext({ baseURL: CANDIDATE_URL, permissions: ['microphone'] });
  const page = await context.newPage();
  await page.goto('/login');
  await page.getByPlaceholder('email@example.com').fill(email);
  await page.getByPlaceholder('••••••••').fill(PASSWORD);
  await page.getByRole('button', { name: 'Đăng Nhập' }).click();
  await expect(page).toHaveURL(/\/profile/);
  return page;
}

test('an answer sent after the withdrawal gets a specific message and no way to retry', async ({ browser, request }) => {
  const page = await candidatePage(browser);
  await page.goto(`/applications/${state.applicationId}/screening`);
  await expect(page.getByTestId('question-text')).toBeVisible();
  await page.getByRole('button', { name: 'Test microphone' }).click();
  await expect(page.getByTestId('mic-level')).toBeVisible();
  await page.getByTestId('record-answer').click();
  await expect(page.getByTestId('stop-answer')).toBeVisible();

  const consents = await (await request.get(`${API_URL}/api/me/consents`, { headers: auth(state.token) })).json();
  const recording = consents.find((row) => row.purpose === 'recording_screening');
  const withdrawn = await request.post(`${API_URL}/api/me/consents/${recording.id}/withdraw`, { headers: auth(state.token) });
  expect(withdrawn.ok()).toBe(true);

  await page.getByTestId('stop-answer').click();
  await expect(page.getByText('You withdrew consent to recording')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send again' })).toHaveCount(0);
  await expect(page.getByTestId('record-answer')).toHaveCount(0);
  await page.context().close();
});

test('My data says what withdrawing CV consent does and points to deletion', async ({ browser }) => {
  const page = await candidatePage(browser);
  await page.goto('/my-data');
  const row = page.getByRole('listitem').filter({ hasText: 'cv_processing' });
  await row.getByRole('button', { name: 'Withdraw consent' }).click();
  await expect(page.getByText('We will stop all further AI work on your CV.')).toBeVisible();
  await expect(page.getByText('To erase everything, use Delete my application below.')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.context().close();
});

test('HR sees the neutral note in Not enough evidence, cannot select it in bulk or restart it, and can still decide', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(HR);
  await page.getByLabel('Password').fill(SAMPLE_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
  await page.goto(`/jobs/${state.jobId}/board`);
  const card = page.getByTestId('cell-not_enough_evidence').getByTestId(`card-${state.alias}`);
  await expect(card.getByTestId('interview-note')).toHaveText('Withdrew consent to recording');
  await expect(card.getByRole('checkbox')).toHaveCount(0);
  await card.getByRole('button', { name: new RegExp(state.alias) }).click();
  const panel = page.getByTestId('detail-panel');
  await expect(panel.getByTestId('interview-note')).toHaveText('Withdrew consent to recording');
  await expect(panel.getByRole('button', { name: 'Approve' })).toBeVisible();
  await expect(panel.getByRole('button', { name: /restart/i })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Reject', exact: true }).click();
  await panel.getByRole('button', { name: 'Yes, reject', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Rejected');
});
