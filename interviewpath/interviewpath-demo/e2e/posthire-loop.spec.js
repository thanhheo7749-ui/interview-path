import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { API_URL, NEW_PASSWORD, POSTHIRE_USER, addManager, apiLogin, ensurePasswordChanged, fillLogin, hrSession, publishInternalNote, signIn } from './helpers.js';

// The two post-hire paths through three real programs, in a company of their own.
// Path A: a candidate is interviewed, HR rejects with feedback and approves it, the candidate reads only that, joins the
// talent pool as a separate consent and later leaves, which deletes the CV the company kept.
// Path B: another candidate is approved, briefed, scored and hired; HR approves the onboarding plan; the hire ticks the
// checklist, which stays private, and asks the Copilot. The AI is the fake provider and the microphone is a beep.
test.describe.configure({ mode: 'serial' });

const WEB_URL = `http://localhost:${process.env.E2E_WEB_PORT || '5199'}`;
const CANDIDATE_URL = `http://localhost:${process.env.E2E_CANDIDATE_PORT || '3199'}`;
const CV = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'cv.pdf');
const RUN = Date.now().toString(36);
const CANDIDATE_PASSWORD = 'candidate-pass-12345';
const MANAGER_EMAIL = `posthire-mgr-${RUN}@e2e.test`;
const MANAGER_PASSWORD = 'posthire-manager-pass-123';
const EMAIL_A = `posthire-a-${RUN}@example.test`;
const EMAIL_B = `posthire-b-${RUN}@example.test`;
const TITLE_A = `Posthire Rejected Developer ${RUN}`;
const TITLE_B = `Posthire Hired Developer ${RUN}`;
// None of these words appear in the CV fixture, so the fake CV reading cannot find this must-have.
const ABSENT = `Kubernetes operator authoring ${RUN}`;
const INTERNAL_TITLE = 'Internal quokka lantern guide k7';
const INTERNAL_LINE = 'Zephyrk7 quokka lantern onboarding grants amber badges';
// Words the candidate must never meet: the CV label, its codes, the interview band and the HR-only categories.
const INTERNAL_WORDS = /does not meet|not_met|cv_status|cv meets|hidden gem|not enough evidence|\bband\b|\bscore\b|\balias\b|#[A-Z]\d/i;
const MAX_QUESTIONS = 25;

const state = {};

async function register(page, email) {
  await page.goto('/register');
  await page.getByPlaceholder('VD: Nguyễn Văn').fill('Posthire');
  await page.getByPlaceholder('VD: A').fill(`Candidate ${email.split('@')[0].slice(-6)}`);
  await page.getByPlaceholder('email@example.com').fill(email);
  await page.getByPlaceholder('Ít nhất 10 ký tự').fill(CANDIDATE_PASSWORD);
  await page.getByRole('button', { name: 'Đăng Ký Tài Khoản' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByPlaceholder('email@example.com').fill(email);
  await page.getByPlaceholder('••••••••').fill(CANDIDATE_PASSWORD);
  await page.getByRole('button', { name: 'Đăng Nhập' }).click();
  await expect(page).toHaveURL(/\/profile/);
}

// HR creates and publishes a job through the API (this company has no role templates), and gets the LinkedIn link.
async function publishJob(request, hr, { title, requirements, departmentId = null }) {
  const base = `${API_URL}/api/companies/${hr.companyId}/jobs`;
  const created = await request.post(base, {
    headers: hr.headers, data: { title, description: 'Build and run backend services.', interview_languages: ['en'], department_id: departmentId, requirements },
  });
  expect(created.status()).toBe(201);
  const job = await created.json();
  expect((await request.post(`${base}/${job.id}/publish`, { headers: hr.headers })).ok()).toBe(true);
  const channels = await request.post(`${base}/${job.id}/channels`, { headers: hr.headers, data: { channels: ['linkedin'] } });
  expect(channels.ok()).toBe(true);
  const [{ token }] = await channels.json();
  const { slug } = await (await request.get(`${base}/${job.id}`, { headers: hr.headers })).json();
  return { jobId: job.id, link: `/jobs/${slug}?src=${token}` };
}

// Registers, applies through the link, waits for the CV to be read and records every interview answer.
async function applyAndInterview(browser, email, link, title) {
  const context = await browser.newContext({ baseURL: CANDIDATE_URL, permissions: ['microphone'] });
  const page = await context.newPage();
  await register(page, email);
  await page.goto(link);
  await expect(page.getByRole('heading', { name: title })).toBeVisible();
  await page.getByRole('button', { name: 'Apply', exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles(CV);
  await page.getByLabel('I have read this and agree to it.').check();
  await page.getByRole('button', { name: 'Send my application' }).click();
  await expect(page).toHaveURL(/\/applications$/);
  await expect(page.getByText('Next: see how you fit')).toBeVisible({ timeout: 60000 });
  await page.getByRole('link', { name: 'See how you fit' }).click();
  await page.getByRole('link', { name: 'Continue to the interview' }).click();
  await expect(page.getByRole('heading', { name: 'Recorded interview' })).toBeVisible();
  await page.getByRole('button', { name: 'Test microphone' }).click();
  await expect(page.getByTestId('mic-level')).toBeVisible();
  await page.getByTestId('consent-recording').check();
  await page.getByTestId('start-session').click();
  const questionText = page.getByTestId('question-text');
  const complete = page.getByTestId('session-complete');
  await expect(questionText).toBeVisible();
  for (let n = 0; n < MAX_QUESTIONS && !(await complete.isVisible()); n += 1) {
    const question = (await questionText.innerText()).trim();
    await page.getByTestId('record-answer').click();
    await expect(page.getByTestId('recording-indicator')).toHaveAttribute('data-recording', 'true');
    await page.waitForTimeout(800);
    await page.getByTestId('stop-answer').click();
    await expect(async () => {
      const done = await complete.isVisible();
      const next = done ? '' : (await questionText.innerText()).trim();
      expect(done || next !== question).toBe(true);
    }).toPass({ timeout: 30000 });
  }
  await expect(complete).toBeVisible();
  return { context, page };
}

// The board does not push updates, so look again until the card shows up.
async function openOnlyCard(page, jobId) {
  await page.goto(`/jobs/${jobId}/board`);
  const cards = page.locator('[data-testid^="cell-"] [data-testid^="card-"]');
  await expect(async () => {
    await page.reload();
    await expect(cards).toHaveCount(1);
  }).toPass({ timeout: 60000, intervals: [1000, 2000, 3000] });
  const card = cards.first();
  const alias = (await card.getAttribute('data-testid')).replace('card-', '');
  await card.getByRole('button', { name: new RegExp(alias) }).click();
  return { card, alias, panel: page.getByTestId('detail-panel') };
}

// What the candidate app itself fetches, with the candidate's own token.
const candidateJson = async (page, path) =>
  JSON.parse(await page.evaluate(async ([api, route]) => {
    const response = await fetch(`${api}${route}`, { headers: { Authorization: `Bearer ${sessionStorage.getItem('token')}` } });
    return response.text();
  }, [API_URL, path]));

const matchesOf = (request, jobId) =>
  request.get(`${API_URL}/api/companies/${state.hr.companyId}/jobs/${jobId}/talent-matches`, { headers: state.hr.headers });

test.beforeAll(async ({ request }) => {
  await ensurePasswordChanged(request, POSTHIRE_USER);
  await publishInternalNote(request, await hrSession(request, POSTHIRE_USER.email, NEW_PASSWORD), { title: INTERNAL_TITLE, line: INTERNAL_LINE });
});

test.afterAll(async () => {
  await state.contextA?.close();
  await state.contextManager?.close();
});

test('1. HR publishes two jobs, one with a must-have the CV lacks', async ({ page }) => {
  state.hr = await hrSession(page.request, POSTHIRE_USER.email, NEW_PASSWORD);
  // The hire's job belongs to a department with a manager, so the manager can score and the hire joins it.
  const department = await page.request.post(`${API_URL}/api/companies/${state.hr.companyId}/departments`, {
    headers: state.hr.headers, data: { name: `Posthire Engineering ${RUN}` },
  });
  expect(department.ok()).toBe(true);
  const departmentId = (await department.json()).id;
  await addManager(page.request, state.hr, { email: MANAGER_EMAIL, fullName: 'Posthire Manager', password: MANAGER_PASSWORD, departmentId });
  state.a = await publishJob(page.request, state.hr, { title: TITLE_A, requirements: [{ text: ABSENT, must_have: true }] });
  state.b = await publishJob(page.request, state.hr, {
    title: TITLE_B, departmentId, requirements: [{ text: 'Write clean backend code', must_have: false }],
  });
});

test('2. path A: a candidate is interviewed, HR rejects, and the draft waits for HR', async ({ browser, page }) => {
  const a = await applyAndInterview(browser, EMAIL_A, state.a.link, TITLE_A);
  state.contextA = a.context;
  state.pageA = a.page;

  await signIn(page, POSTHIRE_USER);
  const { card, alias, panel } = await openOnlyCard(page, state.a.jobId);
  state.aliasA = alias;
  // HR sees the label that the candidate must never see.
  await expect(card).toContainText('CV does not meet');
  await panel.getByRole('button', { name: 'Reject', exact: true }).click();
  await panel.getByRole('button', { name: 'Yes, reject', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Rejected');
  const editor = panel.getByTestId('feedback-editor');
  await expect(editor.getByTestId('feedback-status')).toContainText('Waiting for your approval');
  await expect(editor.getByTestId('feedback-ai-marker')).toHaveText('AI-written draft, please read it');
  state.draft = await editor.getByRole('textbox', { name: 'Feedback message' }).inputValue();
  expect(state.draft).toContain('[Demo AI]');
});

test('3. before HR approves the feedback, the candidate sees the decision and none of it', async () => {
  const page = state.pageA;
  await page.goto('/applications');
  await expect(page.getByText('the hiring team has decided not to move forward')).toBeVisible();
  await expect(page.getByTestId('pool-offer')).toBeVisible();
  const body = page.locator('body');
  await expect(body).not.toContainText(INTERNAL_WORDS);
  await expect(body).not.toContainText('Demo AI');
  await expect(page.getByTestId('feedback-block').getByRole('heading')).toHaveCount(0);
  const applications = await candidateJson(page, '/api/me/applications');
  expect(applications[0].decision).toBe('rejected');
  expect(applications[0].feedback ?? null).toBeNull();
  expect(JSON.stringify(applications)).not.toMatch(/Demo AI|not_met|cv_status|band|hidden/i);
});

test('4. HR approves the feedback, and the candidate reads that message with no internal wording', async ({ page }) => {
  await signIn(page, POSTHIRE_USER);
  const { panel } = await openOnlyCard(page, state.a.jobId);
  const editor = panel.getByTestId('feedback-editor');
  await expect(editor.getByTestId('feedback-status')).toContainText('Waiting for your approval');
  await editor.getByRole('button', { name: 'Approve and send' }).click();
  await expect(editor.getByTestId('feedback-status')).toContainText('Sent to the candidate');

  const candidate = state.pageA;
  await candidate.goto('/applications');
  const block = candidate.getByTestId('feedback-block');
  await expect(block.getByRole('heading', { name: 'Message from the hiring team' })).toBeVisible();
  await expect(block).toContainText('[Demo AI]');
  await expect(candidate.locator('body')).not.toContainText(INTERNAL_WORDS);
  const applications = await candidateJson(candidate, '/api/me/applications');
  expect(applications[0].feedback.message).toBe(state.draft);
  expect(JSON.stringify(applications)).not.toMatch(/not_met|cv_status|"band"|hidden|interview_band/i);
});

test('5. ticking the talent pool is a separate consent that the company can then use', async ({ page }) => {
  const candidate = state.pageA;
  const consentsBefore = await candidateJson(candidate, '/api/me/consents');
  expect(consentsBefore.filter((c) => c.purpose === 'talent_pool')).toHaveLength(0);
  expect(await candidateJson(candidate, '/api/me/talent-pool')).toEqual([]);

  // Reading the page and the feedback does not join anything, and the join button waits for the tick.
  await candidate.goto('/applications');
  const offer = candidate.getByTestId('pool-offer');
  const join = offer.getByRole('button', { name: 'Join the talent pool' });
  await expect(offer.getByRole('checkbox')).not.toBeChecked();
  await expect(join).toBeDisabled();
  expect(await candidateJson(candidate, '/api/me/talent-pool')).toEqual([]);

  // The server also refuses a join without the current consent text.
  const applicationId = (await candidateJson(candidate, '/api/me/applications'))[0].id;
  const refused = await candidate.evaluate(async ([api, id]) => {
    const response = await fetch(`${api}/api/applications/${id}/talent-pool`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${sessionStorage.getItem('token')}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ consent_version: 'not-the-current-text' }),
    });
    return response.status;
  }, [API_URL, applicationId]);
  expect(refused).toBe(422);
  expect(await candidateJson(candidate, '/api/me/talent-pool')).toEqual([]);

  await offer.getByRole('checkbox').check();
  await join.click();
  await expect(candidate.getByTestId('pool-joined')).toBeVisible();
  const consentsAfter = await candidateJson(candidate, '/api/me/consents');
  const pool = consentsAfter.filter((c) => c.purpose === 'talent_pool');
  expect(pool).toHaveLength(1);
  expect(pool[0].withdrawn_at).toBeNull();
  // The earlier consents are untouched: the new one is its own row.
  expect(consentsAfter.filter((c) => c.purpose !== 'talent_pool')).toEqual(consentsBefore);
  const entries = await candidateJson(candidate, '/api/me/talent-pool');
  expect(entries).toHaveLength(1);
  expect(entries[0].status).toBe('active');
  expect(entries[0].consent_id).toBe(pool[0].id);
  state.entryId = entries[0].id;

  // Another job of the company finds the kept CV, by alias only.
  const matches = await matchesOf(page.request, state.b.jobId);
  expect(matches.ok()).toBe(true);
  const found = await matches.json();
  expect(found.map((m) => m.entry_id)).toEqual([state.entryId]);
  expect(found[0].alias).toBe(state.aliasA);
  expect(JSON.stringify(found)).not.toContain(EMAIL_A);
});

test('6. leaving the talent pool deletes the CV the company kept', async ({ page }) => {
  const candidate = state.pageA;
  await candidate.goto('/my-data');
  await expect(candidate.getByTestId('pool-status-active')).toBeVisible();
  await candidate.getByRole('button', { name: 'Leave talent pool' }).click();
  await candidate.getByRole('dialog', { name: 'Leave the talent pool?' }).getByRole('button', { name: 'Leave talent pool' }).click();
  await expect(candidate.getByTestId('pool-status-left')).toBeVisible();

  const entries = await candidateJson(candidate, '/api/me/talent-pool');
  expect(entries.map((e) => e.status)).toEqual(['left']);
  const consents = await candidateJson(candidate, '/api/me/consents');
  expect(consents.find((c) => c.purpose === 'talent_pool').withdrawn_at).not.toBeNull();
  // The company can no longer find the person: the matching that found the copy before now finds nothing.
  const matches = await matchesOf(page.request, state.b.jobId);
  expect(matches.ok()).toBe(true);
  expect(await matches.json()).toEqual([]);
  const invited = await page.request.post(`${API_URL}/api/companies/${state.hr.companyId}/talent-pool/${state.entryId}/invite`, {
    headers: state.hr.headers, data: { job_id: state.b.jobId },
  });
  expect(invited.status()).toBe(409);
  await expect(candidate.locator('body')).not.toContainText(INTERNAL_WORDS);
});

test('7. path B: a candidate is approved, briefed, scored by the manager and hired', async ({ browser, page }) => {
  const b = await applyAndInterview(browser, EMAIL_B, state.b.link, TITLE_B);
  await b.context.close();

  await signIn(page, POSTHIRE_USER);
  const { alias, panel } = await openOnlyCard(page, state.b.jobId);
  await panel.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Approved');
  const workflow = panel.getByTestId('brief-workflow');
  await workflow.getByRole('button', { name: 'Generate brief' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'draft');
  await workflow.getByRole('button', { name: 'Save wording and mark reviewed' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'reviewed');
  await workflow.getByRole('button', { name: 'Send to the hiring manager' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'sent');

  // The manager reads the brief in Korean and scores every requirement.
  state.contextManager = await browser.newContext({ baseURL: WEB_URL });
  const manager = await state.contextManager.newPage();
  await manager.goto('/login');
  await fillLogin(manager, MANAGER_PASSWORD, { email: MANAGER_EMAIL });
  await expect(manager.getByRole('heading', { name: '회사 설정' })).toBeVisible();
  await manager.getByRole('link', { name: '내 면접', exact: true }).click();
  const row = manager.getByRole('listitem').filter({ hasText: TITLE_B });
  await expect(row).toContainText(alias);
  await row.getByRole('link', { name: '브리프 열기' }).click();
  const form = manager.getByTestId('scorecard-form');
  const scores = form.getByLabel(/^점수/);
  await expect(scores.first()).toBeVisible();
  for (const select of await scores.all()) await select.selectOption('4');
  await form.getByLabel('채용 추천', { exact: true }).check();
  await form.getByRole('button', { name: '평가서 제출' }).click();
  await expect(form.getByTestId('scorecard-submitted')).toBeVisible();

  await page.reload();
  await page.getByTestId(`card-${alias}`).getByRole('button', { name: new RegExp(alias) }).click();
  await expect(panel.getByTestId('scorecard-recommendation')).toHaveText('Recommends hiring');
  const outcome = panel.getByTestId('outcome-control');
  await outcome.getByRole('button', { name: 'Hired', exact: true }).click();
  await outcome.getByRole('button', { name: 'Yes, record it' }).click();
  await expect(outcome.getByTestId('outcome-recorded')).toHaveText('Recorded: Hired');
  state.aliasB = alias;
});

test('8. HR drafts the onboarding plan from the team knowledge and approves it', async ({ page }) => {
  await signIn(page, POSTHIRE_USER);
  await page.goto(`/jobs/${state.b.jobId}/board`);
  await page.getByTestId(`card-${state.aliasB}`).getByRole('button', { name: new RegExp(state.aliasB) }).click();
  await page.getByTestId('detail-panel').getByTestId('onboarding-start').getByRole('button', { name: 'Create onboarding plan' }).click();
  await expect(page).toHaveURL(/\/onboarding\/\d+$/);
  state.planId = Number(page.url().split('/').pop());
  await expect(page.getByTestId('plan-status')).toHaveText('Draft, waiting for approval');
  await expect(page.getByTestId('plan-item').first().getByTestId('item-source')).toContainText('quokka lantern');
  await page.getByRole('button', { name: 'Approve plan' }).click();
  await page.getByRole('button', { name: 'Yes, approve' }).click();
  await expect(page.getByTestId('plan-status')).toHaveText('Approved');
});

test('9. the hire ticks the checklist, which stays private, and asks the Copilot', async ({ browser, page }) => {
  const context = await browser.newContext({ baseURL: WEB_URL });
  await context.addInitScript(() => localStorage.setItem('portal_lang', 'en'));
  const hire = await context.newPage();
  await hire.goto('/login');
  await fillLogin(hire, CANDIDATE_PASSWORD, { email: EMAIL_B });
  await expect(hire.getByRole('heading', { name: 'Company settings' })).toBeVisible();
  await expect(hire.getByRole('link', { name: 'Knowledge graph' })).toHaveCount(0);
  await hire.getByRole('link', { name: 'My onboarding' }).click();
  await expect(hire.getByText('Your manager and HR do not see which items you have done.')).toBeVisible();
  await expect(hire.getByTestId('my-item').first()).toBeVisible();
  const boxes = hire.getByRole('checkbox');
  const total = await boxes.count();
  expect(total).toBeGreaterThan(0);
  for (const box of await boxes.all()) {
    await box.click(); // the box changes when the server has answered, so check() would not wait for it
    await expect(box).toBeChecked();
  }
  await hire.reload();
  await expect(hire.getByRole('checkbox', { checked: true })).toHaveCount(total);

  // HR and the manager read the plan after every item was ticked: no tick time, and the plan is not "done".
  const managerToken = await apiLogin(page.request, MANAGER_EMAIL, MANAGER_PASSWORD);
  for (const headers of [state.hr.headers, { Authorization: `Bearer ${managerToken}` }]) {
    const response = await page.request.get(`${API_URL}/api/companies/${state.hr.companyId}/onboarding/${state.planId}`, { headers });
    expect(response.ok()).toBe(true);
    const text = await response.text();
    expect(text).not.toContain('done_at');
    expect(JSON.parse(text).items).toHaveLength(total);
    expect(JSON.parse(text).status).toBe('active');
  }

  // The hire asks the Copilot and gets an answer from the demo AI.
  await hire.getByRole('link', { name: 'Ask Copilot about your plan' }).click();
  await hire.getByLabel('Your question').fill(INTERNAL_LINE);
  await hire.getByRole('button', { name: 'Ask' }).click();
  await expect(hire.getByTestId('copilot-answer').first()).toHaveAttribute('data-state', 'answered');
  await context.close();
});
