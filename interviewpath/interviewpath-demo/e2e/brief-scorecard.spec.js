import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { API_URL, BOARD_USER, NEW_PASSWORD, ensurePasswordChanged, signIn } from './helpers.js';

// HR approves the candidate, drafts a Korean brief from the evidence, reviews it and sends it. The hiring manager
// reads it in Korean, scores each requirement and recommends. HR then records the outcome. The AI is the fake provider.
// The data is the "brief" job written by e2e/seed_board.py: candidate #B1, whose second answer starts 02:13 into the recording.
test.describe.configure({ mode: 'serial' });

const WEB_URL = `http://localhost:${process.env.E2E_WEB_PORT || '5199'}`;
const RUN = Date.now().toString(36);
const MANAGER_EMAIL = `brief-mgr-${RUN}@e2e.test`;
const MANAGER_PASSWORD = 'brief-manager-pass-123';
const QUOTE_FIRST = '저는 결제 서비스를 2년 동안 운영했습니다.';
const QUOTE_SECOND = '장애 회고를 매달 직접 진행했습니다.';
const json = (token) => ({ Authorization: `Bearer ${token}` });

let seed;
test.beforeAll(() => {
  seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'board_seed.json'), 'utf8'));
});

async function login(request, email, password) {
  const response = await request.post(`${API_URL}/api/login`, { data: { email, password } });
  expect(response.ok()).toBe(true);
  return (await response.json()).access_token;
}

// HR adds a manager of the brief job's department; the manager picks their own password.
async function addManager(request) {
  await ensurePasswordChanged(request, BOARD_USER);
  const hrToken = await login(request, BOARD_USER.email, NEW_PASSWORD);
  const added = await request.post(`${API_URL}/api/companies/${seed.company_id}/members`, {
    headers: json(hrToken),
    data: { email: MANAGER_EMAIL, full_name: 'Brief Manager', role: 'manager', department_id: seed.brief_department_id },
  });
  expect(added.ok()).toBe(true);
  const { temporary_password: temporary } = await added.json();
  const token = await login(request, MANAGER_EMAIL, temporary);
  const changed = await request.post(`${API_URL}/api/me/password`, {
    headers: json(token),
    data: { current_password: temporary, new_password: MANAGER_PASSWORD },
  });
  expect(changed.ok()).toBe(true);
}

async function openCandidate(page) {
  await signIn(page, BOARD_USER);
  await page.goto(`/jobs/${seed.brief_job_id}/board`);
  await page.getByTestId('card-#B1').getByRole('button', { name: /#B1/ }).click();
  await expect(page.getByTestId('detail-panel').getByRole('heading', { name: '#B1' })).toBeVisible();
}

test('HR approves, drafts a Korean brief, reviews it and sends it; the manager scores in Korean; HR records the outcome', async ({ page, browser }) => {
  await addManager(page.request);
  await openCandidate(page);
  const panel = page.getByTestId('detail-panel');

  // No brief or outcome controls until HR has approved: the AI never moves a candidate forward.
  await expect(panel.getByTestId('brief-workflow')).toHaveCount(0);
  await expect(panel.getByTestId('outcome-control')).toHaveCount(0);
  await panel.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Approved');

  // Draft the brief in Korean from the evidence.
  const workflow = panel.getByTestId('brief-workflow');
  await expect(workflow.getByLabel('Brief language')).toHaveValue('ko');
  await workflow.getByRole('button', { name: 'Generate brief' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'draft');
  const strengths = workflow.getByTestId('brief-strengths');
  const clarify = workflow.getByTestId('brief-to-clarify');
  await expect(strengths.getByTestId('original-quote')).toHaveText(QUOTE_FIRST);
  await expect(clarify.getByTestId('original-quote')).toHaveText(QUOTE_SECOND);
  await expect(workflow.getByTestId('brief-questions').getByTestId('original-quote')).toHaveText(QUOTE_SECOND);
  await expect(strengths.getByTestId('recording-time')).toContainText('00:00');
  await expect(clarify.getByTestId('recording-time')).toContainText('02:13');

  // The audio is per answer, so the button says it plays the answer from its start, not from 02:13.
  const listen = clarify.getByRole('button', { name: 'Play answer 2 from its start' });
  await expect(listen).toBeVisible();
  await expect(workflow.getByRole('button', { name: /Listen from/ })).toHaveCount(0);
  await listen.click();
  await expect(clarify.locator('audio')).toHaveCount(1);

  // Sending waits for HR's review, and editing the wording takes the review away again.
  const send = workflow.getByRole('button', { name: 'Send to the hiring manager' });
  await expect(send).toBeDisabled();
  await expect(workflow.getByTestId('send-blocked')).toBeVisible();
  const wording = clarify.getByRole('textbox').first();
  await wording.fill('HR wording for the manager.');
  await workflow.getByRole('button', { name: 'Save wording and mark reviewed' }).click();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'reviewed');
  await expect(send).toBeEnabled();
  await wording.fill('HR wording, edited again.');
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'draft');
  await expect(send).toBeDisabled();
  await workflow.getByRole('button', { name: 'Save wording and mark reviewed' }).click();
  await expect(send).toBeEnabled();
  // The quote is the evidence's, not the wording's.
  await expect(clarify.getByTestId('original-quote')).toHaveText(QUOTE_SECOND);
  await send.click();
  await expect(workflow.getByTestId('brief-sent')).toBeVisible();
  await expect(workflow.getByTestId('brief-status')).toHaveAttribute('data-status', 'sent');
  await expect(workflow.getByRole('button', { name: 'Generate brief' })).toHaveCount(0);

  // The manager signs in in their own session and sees Korean.
  const context = await browser.newContext({ baseURL: WEB_URL });
  const manager = await context.newPage();
  await manager.goto('/login');
  await manager.getByLabel('Email').fill(MANAGER_EMAIL);
  await manager.getByLabel('Password').fill(MANAGER_PASSWORD);
  await manager.getByRole('button', { name: 'Sign in' }).click();
  await expect(manager.getByRole('heading', { name: '회사 설정' })).toBeVisible();
  await manager.getByRole('link', { name: '내 면접', exact: true }).click();
  await expect(manager.getByRole('heading', { name: '내 면접', exact: true })).toBeVisible();
  const row = manager.getByRole('listitem').filter({ hasText: 'Sample Brief Engineer' });
  await expect(row).toContainText('#B1');
  await expect(row).not.toContainText('Sample Person'); // the list shows the alias only
  await expect(row.getByTestId('scored-state')).toHaveText('평가서 미제출');
  await row.getByRole('link', { name: '브리프 열기' }).click();

  // The brief page: identity (HR approved), the same structure, original Korean quotes and the recording time.
  await expect(manager.getByTestId('candidate-identity')).toContainText('Sample Person B1');
  const brief = manager.getByTestId('manager-brief');
  await expect(brief.getByRole('heading', { name: '강점' })).toBeVisible();
  await expect(brief.getByRole('heading', { name: '확인이 필요한 점' })).toBeVisible();
  await expect(brief.getByRole('heading', { name: '물어볼 질문' })).toBeVisible();
  await expect(brief.getByTestId('brief-to-clarify')).toContainText('HR wording, edited again.');
  await expect(brief.getByTestId('brief-strengths').getByTestId('original-quote')).toHaveText(QUOTE_FIRST);
  await expect(brief.getByTestId('brief-to-clarify').getByTestId('original-quote')).toHaveText(QUOTE_SECOND);
  await expect(brief.getByTestId('brief-to-clarify').getByTestId('recording-time')).toContainText('02:13');
  // The recording route is HR's; the manager is told so instead of being shown a button that cannot work.
  await expect(brief.getByRole('button')).toHaveCount(0);
  await expect(brief.locator('audio')).toHaveCount(0);
  await expect(brief).toContainText('녹음은 HR이 보관합니다');

  // The scorecard has one row per requirement; submitting waits until each is scored and a recommendation is chosen.
  const form = manager.getByTestId('scorecard-form');
  await expect(form.getByRole('listitem')).toHaveCount(2);
  const submit = form.getByRole('button', { name: '평가서 제출' });
  await expect(submit).toBeDisabled();
  await form.getByLabel('점수: Run services in production').selectOption('4');
  await form.getByLabel('점수: Lead incident reviews').selectOption('2');
  await expect(submit).toBeDisabled();
  await form.getByLabel('채용 추천', { exact: true }).check();
  await form.getByLabel('메모 (선택)').fill('강한 운영 경험.');
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(form.getByTestId('scorecard-submitted')).toBeVisible();
  await expect(form.getByLabel('점수: Run services in production')).toHaveValue('4');

  await manager.getByRole('link', { name: '내 면접으로 돌아가기' }).click();
  await expect(manager.getByRole('listitem').filter({ hasText: 'Sample Brief Engineer' }).getByTestId('scored-state')).toHaveText('평가서 제출됨');
  await context.close();

  // HR records the outcome, after confirming it. The scorecard has no HR read route yet (reported), so it is not shown here.
  const outcome = panel.getByTestId('outcome-control');
  await outcome.getByRole('button', { name: 'Hired', exact: true }).click();
  await expect(outcome.getByRole('alertdialog')).toContainText('Record the outcome as "Hired"?');
  await outcome.getByRole('button', { name: 'Cancel' }).click();
  await expect(outcome.getByTestId('outcome-recorded')).toHaveCount(0);
  await outcome.getByRole('button', { name: 'Hired', exact: true }).click();
  await outcome.getByRole('button', { name: 'Yes, record it' }).click();
  await expect(outcome.getByTestId('outcome-recorded')).toHaveText('Recorded: Hired');
});

test('the brief keys exist in English, Vietnamese and Korean with the same placeholders', () => {
  const read = (name) => JSON.parse(readFileSync(join(import.meta.dirname, '..', 'src', 'i18n', `${name}.json`), 'utf8'));
  const flat = (value, prefix = '') =>
    Object.entries(value).flatMap(([key, child]) =>
      child !== null && typeof child === 'object' ? flat(child, `${prefix}${key}.`) : [[`${prefix}${key}`, child]],
    );
  const keys = (locale) => Object.fromEntries(flat(read(locale).bridges).filter(([key]) => /^(brief|interviews|scorecard|outcome|nav\.myInterviews)/.test(key)));
  const en = keys('en');
  expect(Object.keys(en).length).toBeGreaterThan(40);
  for (const locale of ['vi', 'ko']) {
    const other = keys(locale);
    expect(Object.keys(other).sort()).toEqual(Object.keys(en).sort());
    for (const [key, text] of Object.entries(en)) {
      expect((other[key].match(/\{\{\w+\}\}/g) ?? []).sort(), key).toEqual((text.match(/\{\{\w+\}\}/g) ?? []).sort());
    }
  }
});
