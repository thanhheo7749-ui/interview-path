import { expect, test } from '@playwright/test';

const API_URL = `http://localhost:${process.env.E2E_API_PORT || '8099'}`;
// Sample users are seeded by e2e/start-backend.sh with a known password and no forced password change.
const SAMPLE_PASSWORD = 'e2e-sample-password-123';
const HR = 'hr@daehan-precision.sample';

// Distinct per run, so a retried test never collides with data left by an earlier attempt.
const RUN = Date.now().toString(36);

async function apiLogin(request) {
  const response = await request.post(`${API_URL}/api/login`, { data: { email: HR, password: SAMPLE_PASSWORD } });
  expect(response.ok()).toBe(true);
  const { access_token: token } = await response.json();
  const headers = { Authorization: `Bearer ${token}` };
  const me = await (await request.get(`${API_URL}/api/me`, { headers })).json();
  return { headers, companyId: me.memberships[0].company_id };
}

async function signIn(page) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(HR);
  await page.getByLabel('Password').fill(SAMPLE_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

test('HR builds a job from a role, publishes it, and gets one tracked link per channel', async ({ page, context, request }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  const title = `Platform Engineer ${RUN}-a`;
  const editedText = `Edited requirement ${RUN}-a`;
  const secretText = `CANARY-CONFIDENTIAL-${RUN}-a`;
  const addedText = `Added public requirement ${RUN}-a`;

  await signIn(page);
  await page.getByRole('link', { name: 'Jobs' }).click();
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.getByRole('heading', { name: 'Jobs' })).toBeVisible();
  await page.getByRole('link', { name: 'New job' }).click();
  await expect(page).toHaveURL(/\/jobs\/new$/);

  // Choosing a role pre-fills the department, title, description and requirements.
  await page.getByRole('combobox', { name: 'Role' }).selectOption({ label: 'Backend Developer' });
  await expect(page.getByLabel('Job title')).toHaveValue('Backend Developer');
  await expect(page.getByRole('combobox', { name: 'Department' })).not.toHaveValue('');
  await expect(page.getByLabel('Description')).not.toHaveValue('');
  await expect(page.getByText(/JD Studio.*arrives later/)).toBeVisible();
  const rows = page.getByTestId('requirement-row');
  await expect.poll(() => rows.count()).toBeGreaterThan(1);
  const prefilledCount = await rows.count();
  await expect(page.getByLabel('Requirement 1')).not.toHaveValue('');

  // Edit one requirement, mark another must-have, add a public and a confidential one.
  await page.getByLabel('Job title').fill(title);
  await page.getByLabel('Requirement 1').fill(editedText);
  await page.getByLabel('Must-have 2').check();
  await expect(page.getByLabel('Must-have 2')).toBeChecked();
  await page.getByRole('button', { name: 'Add requirement' }).click();
  await page.getByLabel(`Requirement ${prefilledCount + 1}`).fill(addedText);
  await page.getByRole('button', { name: 'Add requirement' }).click();
  await page.getByLabel(`Requirement ${prefilledCount + 2}`).fill(secretText);
  await page.getByLabel(`Visibility ${prefilledCount + 2}`).selectOption('confidential');

  // Languages: English is on by default; add Vietnamese and make sure Korean is off.
  await page.getByLabel('Vietnamese').check();
  await page.getByLabel('Korean').uncheck();

  await page.getByRole('button', { name: 'Publish' }).click();
  await expect(page).toHaveURL(/\/jobs\/\d+$/);
  await expect(page.getByTestId('job-status')).toContainText('Published');

  // One link per channel, each with a copy button.
  const links = page.getByTestId('channel-links');
  for (const channel of ['company_site', 'linkedin', 'referral']) {
    const item = links.getByTestId(`channel-${channel}`);
    await expect(item).toBeVisible();
    await expect(item).toContainText(/\/jobs\/[a-z0-9-]+\?src=/);
    await expect(item.getByRole('button', { name: `Copy ${channel}` })).toBeVisible();
  }
  const linkedin = links.getByTestId('channel-linkedin');
  const linkText = (await linkedin.locator('code').innerText()).trim();
  await linkedin.getByRole('button', { name: 'Copy linkedin' }).click();
  await expect(linkedin.getByRole('button', { name: 'Copy linkedin' })).toContainText('Copied');
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(linkText);

  // The public API shows the public requirements and nothing confidential.
  const slug = new URL(linkText).pathname.split('/').pop();
  const publicJob = await request.get(`${API_URL}/api/public/jobs/${slug}`);
  expect(publicJob.ok()).toBe(true);
  const body = await publicJob.text();
  expect(body).not.toContain(secretText);
  expect(body).toContain(editedText);
  expect(body).toContain(addedText);
  expect((await publicJob.json()).interview_languages.sort()).toEqual(['en', 'vi']);

  // The job is in the list.
  await page.getByRole('link', { name: 'Jobs' }).click();
  await expect(page.getByRole('link', { name: title })).toBeVisible();
});

test('a draft saves without publishing and shows up in the list as a draft', async ({ page }) => {
  const title = `Draft only ${RUN}-b`;
  await signIn(page);
  await page.goto('/jobs/new');
  await page.getByLabel('Job title').fill(title);
  await page.getByLabel('Description').fill('A draft description.');
  await page.getByRole('button', { name: 'Add requirement' }).click();
  await page.getByLabel('Requirement 1').fill(`Draft requirement ${RUN}-b`);
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page).toHaveURL(/\/jobs\/\d+$/);
  await expect(page.getByTestId('job-status')).toContainText('Draft');
  await expect(page.getByTestId('channel-links')).toHaveCount(0);

  await page.getByRole('link', { name: 'Jobs' }).click();
  await expect(page.getByRole('row', { name: new RegExp(`${title}.*Draft`) })).toBeVisible();
});

test('changing requirements of a published job warns, and saving creates a new version', async ({ page, request }) => {
  const title = `Versioned job ${RUN}-c`;
  const { headers, companyId } = await apiLogin(request);
  const jobs = `${API_URL}/api/companies/${companyId}/jobs`;
  const created = await request.post(jobs, {
    headers,
    data: {
      title, description: 'Version test.', interview_languages: ['en'],
      requirements: [{ text: `Original requirement ${RUN}-c`, must_have: true, visibility: 'public' }],
    },
  });
  expect(created.status()).toBe(201);
  const { id } = await created.json();
  expect((await request.post(`${jobs}/${id}/publish`, { headers })).ok()).toBe(true);

  await signIn(page);
  await page.goto(`/jobs/${id}`);
  await expect(page.getByTestId('job-status')).toContainText('Published');
  const notice = 'Changing requirements creates a new version. Existing applications keep the version they applied to.';
  await expect(page.getByText(notice)).toHaveCount(0);

  await page.getByLabel('Requirement 1').fill(`Changed requirement ${RUN}-c`);
  await expect(page.getByText(notice)).toBeVisible();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Saved.')).toBeVisible();
  await expect(page.getByTestId('job-status')).toContainText('version 2');
  await expect(page.getByText(notice)).toHaveCount(0);
});
