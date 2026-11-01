import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { API_URL } from './helpers.js';

// Sample users get a known password from the backend script (E2E_SEED_SAMPLES).
const SAMPLE_PASSWORD = 'e2e-sample-password-123';
const HR = { email: 'hr@sori-labs.sample' };
const EMPLOYEE = { email: 'employee@sori-labs.sample' };
const CV = readFileSync(join(import.meta.dirname, 'fixtures', 'trust-cv.docx'));
const CANDIDATE_NAME = 'Trustcheck Zebrawski';
// beforeAll runs again after a failure, so each run uses its own candidate.
const candidateEmail = `trust-${Date.now()}@example.test`;

const auth = (token) => ({ Authorization: `Bearer ${token}` });

async function login(request, email, password) {
  const response = await request.post(`${API_URL}/api/login`, { data: { email, password } });
  expect(response.ok()).toBe(true);
  return (await response.json()).access_token;
}

let applicationId;
let companyId;

test.beforeAll(async ({ request }) => {
  const hrToken = await login(request, HR.email, SAMPLE_PASSWORD);
  const me = await (await request.get(`${API_URL}/api/me`, { headers: auth(hrToken) })).json();
  companyId = me.memberships[0].company_id;
  const jobs = await (await request.get(`${API_URL}/api/companies/${companyId}/jobs`, { headers: auth(hrToken) })).json();
  const job = jobs.find((item) => item.status === 'published');
  expect(job).toBeTruthy();

  // A candidate applies with consent and the CV is read.
  const password = 'e2e-candidate-password-123';
  const registered = await request.post(`${API_URL}/api/register`, {
    data: { email: candidateEmail, password, full_name: CANDIDATE_NAME },
  });
  expect(registered.ok()).toBe(true);
  const candidateToken = await login(request, candidateEmail, password);
  const consent = await (await request.get(`${API_URL}/api/consents/cv_processing`, { headers: auth(candidateToken) })).json();
  const applied = await request.post(`${API_URL}/api/public/jobs/${job.slug}/apply`, {
    headers: auth(candidateToken),
    multipart: {
      consent_version: consent.version,
      file: {
        name: 'cv.docx',
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        buffer: CV,
      },
    },
  });
  expect(applied.status()).toBe(201);
  applicationId = (await applied.json()).id;
  await expect
    .poll(
      async () => (await (await request.get(`${API_URL}/api/applications/${applicationId}`, { headers: auth(candidateToken) })).json()).status,
      { timeout: 30000 },
    )
    .toBe('invited');

  // HR fast-tracks it onto the board and approves it, which writes audit entries.
  const base = `${API_URL}/api/companies/${companyId}/applications/${applicationId}`;
  expect((await request.post(`${base}/fast-track`, { headers: auth(hrToken) })).ok()).toBe(true);
  const decided = await request.post(`${base}/decision`, { headers: auth(hrToken), data: { decision: 'approved', reason: 'Trust Center e2e' } });
  expect(decided.ok()).toBe(true);
});

async function signInAs(page, user) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill(SAMPLE_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

test('HR sees the four Trust Center tabs, aliases without emails, and the audit log with its filter', async ({ page }) => {
  await signInAs(page, HR);
  await page.getByRole('link', { name: 'Trust Center' }).click();
  await expect(page.getByRole('heading', { name: 'Trust Center', exact: true })).toBeVisible();
  await expect(page.getByText('have not had legal review')).toBeVisible();
  for (const name of ['Consents', 'Audit log', 'Retention', 'Fairness check']) {
    await expect(page.getByRole('tab', { name })).toBeVisible();
  }

  // Consents: aliases, and no candidate email or name.
  await expect(page.getByRole('cell', { name: 'CV processing' }).first()).toBeVisible();
  const panel = page.getByRole('tabpanel');
  await expect(panel).toContainText(/#[A-Z0-9]/);
  await expect(panel).not.toContainText(candidateEmail);
  await expect(panel).not.toContainText('Zebrawski');
  await expect(panel).not.toContainText('@');

  // Audit log: the decision shows, and the filter narrows to one action.
  await page.getByRole('tab', { name: 'Audit log' }).click();
  await expect(page.getByRole('cell', { name: 'HR decision' }).first()).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Fast-tracked' }).first()).toBeVisible();
  await page.getByLabel('Action').selectOption('hr_decision');
  await expect(page.getByRole('cell', { name: 'Fast-tracked' })).toHaveCount(0);
  await expect(page.getByRole('cell', { name: 'HR decision' }).first()).toBeVisible();
  await expect(page.getByRole('tabpanel')).toContainText('Page 1 of 1');

  // Retention: real numbers from the API and what is deleted and kept.
  await page.getByRole('tab', { name: 'Retention' }).click();
  await expect(page.getByText('Retention period')).toBeVisible();
  await expect(page.getByText('Awaiting deletion')).toBeVisible();
  await expect(page.getByText('Deleted:')).toBeVisible();
  await expect(page.getByText('Kept:')).toBeVisible();
});

test('HR runs the fairness check and sees both blind texts', async ({ page }) => {
  await signInAs(page, HR);
  await page.getByRole('link', { name: 'Trust Center' }).click();
  await page.getByRole('tab', { name: 'Fairness check' }).click();
  const select = page.getByLabel('Application');
  await expect(select.locator('option')).not.toHaveCount(1);
  await select.selectOption(String(applicationId));
  await page.getByRole('button', { name: 'Run check' }).click();

  await expect(page.getByTestId('fairness-result')).toContainText('the blind text is identical');
  const original = await page.getByTestId('fairness-original').textContent();
  const swapped = await page.getByTestId('fairness-swapped').textContent();
  expect(original.trim().length).toBeGreaterThan(0);
  expect(swapped).toBe(original);
  expect(original).not.toContain('Zebrawski');
  await expect(page.getByText('this reduces bias but does not eliminate it')).toBeVisible();

  // The check is recorded in the audit log.
  await page.getByRole('tab', { name: 'Audit log' }).click();
  await expect(page.getByRole('cell', { name: 'Fairness check' }).first()).toBeVisible();
});

test('A non-HR member is redirected away from the Trust Center', async ({ page }) => {
  await signInAs(page, EMPLOYEE);
  await page.goto('/trust');
  await expect(page).toHaveURL(/\/copilot$/);
  await expect(page.getByRole('link', { name: 'Trust Center' })).toHaveCount(0);
});
