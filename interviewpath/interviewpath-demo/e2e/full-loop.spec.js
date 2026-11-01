import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { BOARD_USER, signIn as signInAs } from './helpers.js';

// The whole hiring loop through three real programs: HR posts a job in the portal, a candidate applies and is
// interviewed in the candidate app, and HR reviews and decides on the board. The AI is the fake provider, and the
// browser has a fake microphone, so the audio is a beep and the transcript is always "fake transcript".
test.describe.configure({ mode: 'serial' });

const API_URL = `http://localhost:${process.env.E2E_API_PORT || '8099'}`;
const CANDIDATE_URL = `http://localhost:${process.env.E2E_CANDIDATE_PORT || '3199'}`;
const SAMPLE_PASSWORD = 'e2e-sample-password-123';
const HR = 'hr@daehan-precision.sample';
const CV = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'cv.pdf');
const CANDIDATE_PASSWORD = 'candidate-pass-12345';
const RUN = Date.now().toString(36);
// None of the words below appear in the CV fixture, so the fake CV reading cannot find this must-have.
const ABSENT = `Kubernetes operator authoring ${RUN}`;
const TITLE = `Loop Backend Developer ${RUN}`;
const FAKE_TRANSCRIPT = 'fake transcript';
const LABELS = /does not meet|not_met|hidden gem|CV meets|\bband\b/i;
const MAX_QUESTIONS = 25;

const state = {};

async function candidateContext(browser) {
  return browser.newContext({ baseURL: CANDIDATE_URL, permissions: ['microphone'] });
}

async function register(page, email) {
  await page.goto('/register');
  await page.getByPlaceholder('VD: Nguyễn Văn').fill('Loop');
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

// Opens the link HR copied, applies with the CV fixture, and agrees to the CV consent.
async function applyThroughLink(page, link) {
  await page.goto(link);
  await expect(page.getByRole('heading', { name: TITLE })).toBeVisible();
  await page.getByRole('button', { name: 'Apply', exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles(CV);
  await expect(page.getByText('How we use your CV')).toBeVisible();
  await page.getByLabel('I have read this and agree to it.').check();
  await page.getByRole('button', { name: 'Send my application' }).click();
  await expect(page).toHaveURL(/\/applications$/);
  await expect(page.getByText(TITLE)).toBeVisible();
}

async function waitForInvitation(page) {
  // The CV is read in the background; the page polls while it does.
  await expect(page.getByText('Next: see how you fit')).toBeVisible({ timeout: 60000 });
}

async function expectNoLabel(page) {
  await expect(page.locator('body')).not.toContainText(LABELS);
}

async function openScreening(page) {
  await page.getByRole('link', { name: 'See how you fit' }).click();
  await expect(page.getByRole('heading', { name: 'Fit Compass' })).toBeVisible();
  await page.getByRole('link', { name: 'Continue to the interview' }).click();
  await expect(page.getByRole('heading', { name: 'Recorded interview' })).toBeVisible();
  await page.getByRole('button', { name: 'Test microphone' }).click();
  await expect(page.getByTestId('mic-level')).toBeVisible();
}

async function portalLogin(page) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(HR);
  await page.getByLabel('Password').fill(SAMPLE_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

// The board does not push updates, so look again until the card shows up in the place wanted.
async function reloadUntil(page, assertion, timeout = 60000) {
  await expect(async () => {
    await page.reload();
    await assertion();
  }).toPass({ timeout, intervals: [1000, 2000, 3000] });
}

const anyCard = (page, scope) => page.locator(`${scope} [data-testid^="card-"]`);

test('1. HR posts a job with a must-have the CV lacks, publishes it and copies the linkedin link', async ({ page }) => {
  await portalLogin(page);
  await page.goto('/jobs/new');
  await page.getByRole('combobox', { name: 'Role' }).selectOption({ label: 'Backend Developer' });
  await expect(page.getByLabel('Job title')).toHaveValue('Backend Developer');
  await expect.poll(() => page.getByTestId('requirement-row').count()).toBeGreaterThan(1);
  await page.getByLabel('Job title').fill(TITLE);
  await page.getByLabel('Requirement 1').fill(ABSENT);
  await page.getByLabel('Must-have 1').check();
  await expect(page.getByLabel('Visibility 1')).toHaveValue('public');
  await page.getByRole('button', { name: 'Publish' }).click();
  await expect(page).toHaveURL(/\/jobs\/\d+$/);
  state.jobId = new URL(page.url()).pathname.split('/').pop();
  await expect(page.getByTestId('job-status')).toContainText('Published');

  const linkedin = page.getByTestId('channel-links').getByTestId('channel-linkedin');
  state.link = (await linkedin.locator('code').innerText()).trim();
  expect(state.link).toMatch(new RegExp(`^${CANDIDATE_URL}/jobs/[a-z0-9-]+\\?src=`));
});

test('2 to 4. a candidate applies, sees only a friendly status and Fit Compass, and records the interview', async ({ browser }) => {
  const context = await candidateContext(browser);
  const page = await context.newPage();
  const email = `loop-a-${RUN}@example.test`;
  await register(page, email);

  await applyThroughLink(page, state.link);
  await waitForInvitation(page);
  await expectNoLabel(page);

  // Fit Compass: the must-have the CV lacks, in the candidate's own words, and a way to ask the company.
  await page.getByRole('link', { name: 'See how you fit' }).click();
  const row = page.getByRole('listitem').filter({ hasText: ABSENT });
  await expect(row).toContainText('Not seen in your CV', { timeout: 30000 });
  await expectNoLabel(page);
  await page.getByPlaceholder('Type your question').fill('How many days of annual leave do employees get?');
  await page.getByRole('button', { name: 'Ask', exact: true }).click();
  const answer = page.locator('section[aria-labelledby="ask-title"] [role="status"]');
  await expect(answer).toBeVisible({ timeout: 30000 });
  await expect(answer).not.toHaveText('');
  await expectNoLabel(page);

  // Continue, check the microphone, consent to recording and answer every question.
  await page.getByRole('link', { name: 'Continue to the interview' }).click();
  await expect(page.getByRole('heading', { name: 'Recorded interview' })).toBeVisible();
  await page.getByRole('button', { name: 'Test microphone' }).click();
  await expect(page.getByTestId('mic-level')).toBeVisible();
  await expect(page.getByTestId('start-session')).toBeDisabled();
  await page.getByTestId('consent-recording').check();
  await expect(page.getByTestId('start-session')).toBeEnabled();
  await page.getByTestId('start-session').click();

  const questionText = page.getByTestId('question-text');
  const complete = page.getByTestId('session-complete');
  await expect(questionText).toBeVisible();
  await expect(page.getByTestId('recording-indicator')).toBeVisible();
  const asked = [];
  for (let n = 0; n < MAX_QUESTIONS && !(await complete.isVisible()); n += 1) {
    const question = (await questionText.innerText()).trim();
    asked.push(question);
    await expectNoLabel(page);
    await page.getByTestId('record-answer').click();
    await expect(page.getByTestId('recording-indicator')).toHaveAttribute('data-recording', 'true');
    await page.waitForTimeout(800);
    await page.getByTestId('stop-answer').click();
    // The next question, or the end, arrives once the answer is stored.
    await expect(async () => {
      const done = await complete.isVisible();
      const next = done ? '' : (await questionText.innerText()).trim();
      expect(done || next !== question).toBe(true);
    }).toPass({ timeout: 30000 });
  }
  await expect(complete).toBeVisible();
  expect(asked.length).toBeGreaterThanOrEqual(8);
  expect(new Set(asked).size).toBe(asked.length);
  // The plan puts the missing must-have first, from the public layer only.
  expect(asked[0]).toContain(ABSENT);
  state.questions = asked.length;
  await expectNoLabel(page);

  await page.getByRole('link', { name: 'Back to my applications' }).click();
  await expect(page.getByText('With HR for review').or(page.getByText(/^Update:/))).toBeVisible();
  state.candidateContext = context;
  state.candidatePage = page;
});

test('5. HR sees the application as an alias on the board, reads the transcript and rejects with the decision bar', async ({ page }) => {
  await portalLogin(page);
  await page.goto(`/jobs/${state.jobId}/board`);
  await expect(page.getByTestId('cell-priority')).toBeVisible();
  // Under analysis first, then in a cell once the analysis finishes.
  await reloadUntil(page, async () => {
    await expect(anyCard(page, '[data-testid^="cell-"]')).toHaveCount(1);
  });
  const card = anyCard(page, '[data-testid^="cell-"]').first();
  const alias = (await card.getAttribute('data-testid')).replace('card-', '');
  expect(alias).toMatch(/^#[A-Z]\d+$/);
  state.alias = alias;
  await expect(page.locator('body')).not.toContainText(/Loop Candidate/);
  await expect(page.locator('body')).not.toContainText('example.test');

  await card.getByRole('button', { name: new RegExp(alias) }).click();
  const panel = page.getByTestId('detail-panel');
  await expect(panel.getByRole('heading', { name: alias })).toBeVisible();
  await expect(panel.getByTestId('transcript')).toContainText(FAKE_TRANSCRIPT);
  await expect(panel.getByTestId('evidence-table')).toContainText(FAKE_TRANSCRIPT);
  // The CV did not meet the must-have, and HR sees that label.
  await expect(card).toContainText('CV does not meet');

  await panel.getByRole('button', { name: 'Reject', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Rejected');
});

test('6. the candidate sees a decision with a generic message and no label', async () => {
  const page = state.candidatePage;
  await page.goto('/applications');
  await expect(page.getByText('the hiring team has decided not to move forward')).toBeVisible();
  await expectNoLabel(page);
  await expect(page.locator('body')).not.toContainText(/reject|score|alias|#[A-Z]\d/i);
  // The data the page was built from holds no label either.
  const body = await page.evaluate(async (api) => {
    const response = await fetch(`${api}/api/me/applications`, {
      headers: { Authorization: `Bearer ${sessionStorage.getItem('token')}` },
    });
    return response.text();
  }, `${API_URL}`);
  expect(body).not.toMatch(/not_met|cv_status|meets|band|hidden/i);
  expect(JSON.parse(body)[0].decision).toBe('rejected');
  await state.candidateContext.close();
});

test('7. a candidate who declines recording lands in the refused lane and is not rejected', async ({ browser, page }) => {
  const context = await candidateContext(browser);
  const candidate = await context.newPage();
  await register(candidate, `loop-b-${RUN}@example.test`);
  await applyThroughLink(candidate, state.link);
  await waitForInvitation(candidate);
  await openScreening(candidate);
  await candidate.getByTestId('decline-recording').click();
  await candidate.getByTestId('confirm-decline').click();
  await expect(candidate.getByText('You declined recording.')).toBeVisible();
  await expectNoLabel(candidate);
  await context.close();

  await portalLogin(page);
  await page.goto(`/jobs/${state.jobId}/board`);
  await expect(page.getByTestId('cell-priority')).toBeVisible();
  await reloadUntil(page, async () => {
    await expect(page.getByTestId('count-refused_recording')).toHaveText('1');
  });
  const lane = page.getByTestId('lane-refused_recording');
  const refused = lane.locator('[data-testid^="card-"]');
  await expect(refused).toHaveCount(1);
  // Declining is not a rejection: nothing is decided, and the first candidate's rejection is the only one.
  await expect(refused.getByTestId('decided-badge')).toHaveCount(0);
  await expect(page.getByTestId('decided-badge')).toHaveCount(1);
  await expect(lane.getByRole('heading', { name: 'Refused recording' })).toBeVisible();
  await expect(refused).not.toContainText(state.alias);
  // HR can still decide on it.
  await refused.getByRole('button').click();
  await expect(page.getByTestId('detail-panel').getByRole('button', { name: 'Approve' })).toBeEnabled();
});

test('8. a Hidden Gem keeps its "CV does not meet" label, and only HR sees it', async ({ page }) => {
  const seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'board_seed.json'), 'utf8'));
  await signInAs(page, BOARD_USER);
  await page.goto(`/jobs/${seed.gem_job_id}/board`);
  const gem = page.getByTestId('cell-hidden_gem');
  await expect(gem.getByRole('heading', { name: 'Hidden Gem' })).toBeVisible();
  const card = gem.getByTestId('card-#H1');
  await expect(card).toBeVisible();
  await expect(card).toContainText('CV does not meet');
  // Opening it and reading the evidence does not change the label.
  await card.getByRole('button', { name: /#H1/ }).click();
  const panel = page.getByTestId('detail-panel');
  await expect(panel.getByTestId('transcript')).toContainText('I taught myself the whole stack in a month.');
  await expect(card).toContainText('CV does not meet');
  await expect(gem.getByTestId('card-#H1')).toBeVisible();
});
