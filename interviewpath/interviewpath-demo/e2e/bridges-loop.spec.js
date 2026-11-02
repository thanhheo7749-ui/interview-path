import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { API_URL, LOOP_USER, NEW_PASSWORD, addManager, ensurePasswordChanged, hrSession, signIn } from './helpers.js';

// The whole Bridges loop through three real programs, in one company of its own: HR opens a request, the manager
// records the intake in Korean, HR publishes what the transcript says, drafts the job description from it, the manager
// approves it in Korean, HR publishes the job, a candidate applies through the channel link and is interviewed, HR
// approves, sends the brief, the manager scores in Korean and HR records the outcome. The AI is the fake provider and
// the microphone is a beep, so every transcript is "fake transcript".
test.describe.configure({ mode: 'serial' });

const WEB_URL = `http://localhost:${process.env.E2E_WEB_PORT || '5199'}`;
const CANDIDATE_URL = `http://localhost:${process.env.E2E_CANDIDATE_PORT || '3199'}`;
const CV = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'cv.pdf');
const RUN = Date.now().toString(36);
const MANAGER_EMAIL = `loop-mgr-${RUN}@e2e.test`;
const MANAGER_PASSWORD = 'loop-manager-pass-123';
const CANDIDATE_PASSWORD = 'candidate-pass-12345';
const TITLE = `Bridges Loop Engineer ${RUN}`;
const MAX_QUESTIONS = 25;
const KO_NO_NAMES = '특정 개인의 이름은 말씀하지 말아 주세요';

const state = {};

const hrBrowserSession = async (page) => {
  await signIn(page, LOOP_USER);
};

async function managerSignIn(page) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(MANAGER_EMAIL);
  await page.getByLabel('Password').fill(MANAGER_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: '회사 설정' })).toBeVisible();
}

async function recordAnswers(page, indicator) {
  const complete = page.getByTestId('session-complete');
  const questionText = page.getByTestId('question-text');
  const asked = [];
  for (let n = 0; n < MAX_QUESTIONS && !(await complete.isVisible()); n += 1) {
    const question = (await questionText.innerText()).trim();
    asked.push(question);
    await page.getByTestId('record-answer').click();
    await expect(indicator).toHaveAttribute('data-recording', 'true');
    await page.waitForTimeout(800);
    await page.getByTestId('stop-answer').click();
    await expect(async () => {
      const done = await complete.isVisible();
      const next = done ? '' : (await questionText.innerText()).trim();
      expect(done || next !== question).toBe(true);
    }).toPass({ timeout: 30000 });
  }
  await expect(complete).toBeVisible();
  return asked;
}

test('1. HR opens a request and the manager records the intake in Korean', async ({ page, browser }) => {
  await ensurePasswordChanged(page.request, LOOP_USER);
  state.hr = await hrSession(page.request, LOOP_USER.email, NEW_PASSWORD);
  const department = await page.request.post(`${API_URL}/api/companies/${state.hr.companyId}/departments`, {
    headers: state.hr.headers, data: { name: `Loop Engineering ${RUN}` },
  });
  expect(department.ok()).toBe(true);
  state.departmentName = `Loop Engineering ${RUN}`;
  await addManager(page.request, state.hr, {
    email: MANAGER_EMAIL, fullName: 'Loop Manager', password: MANAGER_PASSWORD, departmentId: (await department.json()).id,
  });

  await hrBrowserSession(page);
  await page.getByRole('link', { name: 'Hiring requests' }).click();
  await page.getByLabel('Role to hire').fill(TITLE);
  await page.getByLabel('Hiring manager').selectOption({ label: 'Loop Manager' });
  await page.getByLabel('Department').selectOption({ label: state.departmentName });
  await page.getByRole('button', { name: 'Create request' }).click();
  await expect(page.getByRole('listitem').filter({ hasText: TITLE })).toBeVisible();

  state.managerContext = await browser.newContext({ baseURL: WEB_URL, permissions: ['microphone'] });
  const manager = await state.managerContext.newPage();
  state.manager = manager;
  await managerSignIn(manager);
  await manager.getByRole('link', { name: '채용 요청' }).click();
  const row = manager.getByRole('listitem').filter({ hasText: TITLE });
  await row.getByRole('link', { name: '인테이크 시작' }).click();
  await manager.getByRole('button', { name: '마이크 테스트' }).click();
  await expect(manager.getByTestId('mic-level')).toBeVisible();
  await manager.getByTestId('intake-understood').check();
  await manager.getByTestId('start-intake').click();
  await expect(manager.getByTestId('question-text')).toContainText(KO_NO_NAMES);
  await recordAnswers(manager, manager.getByTestId('recording-indicator'));
  await expect(manager.getByTestId('session-complete')).toContainText('HR이 검토할 예정입니다');
});

test('2. HR publishes the intake knowledge as public and drafts the job description from it', async ({ page }) => {
  await hrBrowserSession(page);
  await page.getByRole('link', { name: /^Review/ }).click();
  // The item that quotes the manager's answer ("fake transcript") in this request's intake document.
  const item = page.getByRole('article').filter({ hasText: `Manager intake: ${TITLE}` }).filter({ hasText: 'fake transcript' });
  // The transcript is read in the background, so look again until its items show.
  await expect(async () => {
    await page.reload();
    await expect(item).toHaveCount(1);
  }).toPass({ timeout: 60000, intervals: [1000, 2000, 3000] });
  await item.getByLabel('Title').fill(`Manager intake answer ${RUN}`);
  await item.getByLabel('Layer').selectOption('public');
  await item.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(item).toHaveCount(0);

  await page.getByRole('link', { name: 'Hiring requests' }).click();
  const row = page.getByRole('listitem').filter({ hasText: TITLE });
  await expect(row.getByTestId('open-draft')).toHaveCount(0);
  await row.getByRole('button', { name: 'Generate draft' }).click();
  await expect(page).toHaveURL(/\/jd-studio\/\d+$/);
  state.draftId = page.url().match(/\/jd-studio\/(\d+)$/)[1];

  const lines = page.getByTestId('jd-lines').getByRole('listitem');
  await expect.poll(() => lines.count()).toBeGreaterThan(0);
  await expect(lines.first().getByTestId('source-chip').first()).toContainText(`Manager intake answer ${RUN}`);
  await expect(page.getByTestId('lint-clear')).toBeVisible();

  // The assistant revises the draft, then HR marks the line as a must-have and sends it to the manager.
  const before = Number(await page.getByTestId('draft-version').getAttribute('data-version'));
  await page.getByLabel('Message to the assistant').fill('Make it shorter');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByTestId('assistant-assistant')).toContainText('Demo AI revision');
  expect(Number(await page.getByTestId('draft-version').getAttribute('data-version'))).toBeGreaterThan(before);
  await page.getByLabel('Line 1 is a requirement', { exact: true }).click();
  await expect(page.getByLabel('Line 1 is a requirement', { exact: true })).toBeChecked();
  await page.getByLabel('Line 1 is a must-have', { exact: true }).click();
  await expect(page.getByLabel('Line 1 is a must-have', { exact: true })).toBeChecked();
  await page.getByRole('button', { name: 'Submit to manager' }).click();
  await expect(page.getByTestId('draft-status')).toContainText('Waiting for the manager');
});

test('3. the manager opens the draft from the request list and approves it in Korean, then HR publishes', async ({ page }) => {
  const manager = state.manager;
  await manager.goto('/hiring-requests');
  const managerRow = manager.getByRole('listitem').filter({ hasText: TITLE });
  await expect(managerRow.getByTestId('awaiting-approval')).toHaveText('승인 대기 중');
  await managerRow.getByTestId('open-draft').click();
  await expect(manager).toHaveURL(new RegExp(`/jd-studio/${state.draftId}$`));
  await expect(manager.getByRole('heading', { name: 'JD 스튜디오' })).toBeVisible();
  const chip = manager.getByTestId('source-chip').first();
  await expect(chip).toContainText(`Manager intake answer ${RUN}`); // public knowledge: the title is readable
  await manager.getByRole('button', { name: '승인', exact: true }).click();
  await expect(manager.getByTestId('draft-status')).toContainText('승인됨');

  await hrBrowserSession(page);
  await page.goto(`/jd-studio/${state.draftId}`);
  await expect(page.getByTestId('draft-status')).toContainText('Approved');
  await page.getByRole('button', { name: 'Publish', exact: true }).click();
  await expect(page.getByTestId('draft-status')).toContainText('Published');
  const content = page.getByTestId('channel-content');
  await content.getByRole('tab', { name: 'LinkedIn' }).click();
  const href = await content.getByTestId('channel-link').getAttribute('href');
  expect(href).toMatch(/\/jobs\/[a-z0-9-]+\?src=/);
  // The API builds the link on the address configured for the deployed candidate app; the test candidate app is local.
  const url = new URL(href);
  state.link = `${url.pathname}${url.search}`;
});

test('4. a candidate applies through the channel link and records the interview', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: CANDIDATE_URL, permissions: ['microphone'] });
  const page = await context.newPage();
  const email = `loop-c-${RUN}@example.test`;
  await page.goto('/register');
  await page.getByPlaceholder('VD: Nguyễn Văn').fill('Loop');
  await page.getByPlaceholder('VD: A').fill(`Candidate ${RUN.slice(-4)}`);
  await page.getByPlaceholder('email@example.com').fill(email);
  await page.getByPlaceholder('Ít nhất 10 ký tự').fill(CANDIDATE_PASSWORD);
  await page.getByRole('button', { name: 'Đăng Ký Tài Khoản' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByPlaceholder('email@example.com').fill(email);
  await page.getByPlaceholder('••••••••').fill(CANDIDATE_PASSWORD);
  await page.getByRole('button', { name: 'Đăng Nhập' }).click();
  await expect(page).toHaveURL(/\/profile/);

  await page.goto(state.link);
  await expect(page.getByRole('heading', { name: TITLE })).toBeVisible();
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
  await expect(page.getByTestId('question-text')).toBeVisible();
  const asked = await recordAnswers(page, page.getByTestId('recording-indicator'));
  expect(asked.length).toBeGreaterThanOrEqual(1);
  await context.close();
});

test('5. HR approves the candidate, sends the brief, the manager scores it and HR records the outcome', async ({ page }) => {
  await hrBrowserSession(page);
  // The request now points at the job that publishing made.
  const requests = await (await page.request.get(`${API_URL}/api/companies/${state.hr.companyId}/hiring-requests`, { headers: state.hr.headers })).json();
  const request = requests.find((r) => r.title === TITLE);
  expect(request.status).toBe('published');
  expect(request.job_id).toBeTruthy();
  await page.goto(`/jobs/${request.job_id}/board`);
  const anyCard = page.locator('[data-testid^="cell-"] [data-testid^="card-"]');
  await expect(async () => {
    await page.reload();
    await expect(anyCard).toHaveCount(1);
  }).toPass({ timeout: 60000, intervals: [1000, 2000, 3000] });
  const alias = (await anyCard.first().getAttribute('data-testid')).replace('card-', '');
  await anyCard.first().getByRole('button', { name: new RegExp(alias) }).click();
  const panel = page.getByTestId('detail-panel');
  await panel.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Approved');

  const workflow = panel.getByTestId('brief-workflow');
  await workflow.getByRole('button', { name: 'Generate brief' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'draft');
  await expect(workflow.getByTestId('brief-strengths').getByTestId('original-quote').first()).toHaveText('fake transcript');
  await workflow.getByRole('button', { name: 'Save wording and mark reviewed' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'reviewed');
  await workflow.getByRole('button', { name: 'Send to the hiring manager' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'sent');

  // The manager reads the brief in Korean and scores the requirement.
  const manager = state.manager;
  await manager.goto('/');
  await manager.getByRole('link', { name: '내 면접', exact: true }).click();
  const row = manager.getByRole('listitem').filter({ hasText: TITLE });
  await expect(row).toContainText(alias);
  await expect(row.getByTestId('scored-state')).toHaveText('평가서 미제출');
  await row.getByRole('link', { name: '브리프 열기' }).click();
  await expect(manager.getByTestId('manager-brief').getByTestId('brief-strengths')).toBeVisible();
  const form = manager.getByTestId('scorecard-form');
  const scores = form.getByLabel(/^점수/);
  await expect(scores).toHaveCount(1);
  await scores.selectOption('4');
  await form.getByLabel('채용 추천', { exact: true }).check();
  await form.getByRole('button', { name: '평가서 제출' }).click();
  await expect(form.getByTestId('scorecard-submitted')).toBeVisible();

  // HR sees the scorecard as advice and records the outcome.
  await page.reload();
  await anyCard.first().getByRole('button', { name: new RegExp(alias) }).click();
  const card = panel.getByTestId('hr-scorecard');
  await expect(card.getByTestId('scorecard-manager')).toHaveText('Loop Manager');
  await expect(card.getByTestId('scorecard-recommendation')).toHaveText('Recommends hiring');
  const outcome = panel.getByTestId('outcome-control');
  await outcome.getByRole('button', { name: 'Hired', exact: true }).click();
  await outcome.getByRole('button', { name: 'Yes, record it' }).click();
  await expect(outcome.getByTestId('outcome-recorded')).toHaveText('Recorded: Hired');
});

test.afterAll(async () => {
  await state.managerContext?.close();
});
