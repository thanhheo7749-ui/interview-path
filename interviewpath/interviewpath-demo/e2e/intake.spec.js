import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { API_URL, HR_EMAIL, LOGIN_USER, NEW_PASSWORD, ensurePasswordChanged, signIn } from './helpers.js';

// HR opens a hiring request for a manager, the manager answers the voice intake in Korean through a fake microphone,
// and HR then finds the drafts made from the transcript in Review. The AI is the fake provider.
const WEB_URL = `http://localhost:${process.env.E2E_WEB_PORT || '5199'}`;
const RUN = Date.now().toString(36);
const MANAGER_EMAIL = `intake-mgr-${RUN}@e2e.test`;
const MANAGER_PASSWORD = 'intake-manager-pass-123';
const TITLE = `Intake Backend Lead ${RUN}`;
const MAX_QUESTIONS = 15;
const KO_NO_NAMES = '특정 개인의 이름은 말씀하지 말아 주세요';

const json = (token) => ({ Authorization: `Bearer ${token}` });

async function login(request, email, password) {
  const response = await request.post(`${API_URL}/api/login`, { data: { email, password } });
  expect(response.ok()).toBe(true);
  return (await response.json()).access_token;
}

// HR adds a manager through the API and the manager picks their own password, as the forced-change screen would.
async function addManager(request) {
  await ensurePasswordChanged(request, LOGIN_USER);
  const hrToken = await login(request, HR_EMAIL, NEW_PASSWORD);
  const me = await (await request.get(`${API_URL}/api/me`, { headers: json(hrToken) })).json();
  const companyId = me.memberships.find((m) => m.role === 'hr').company_id;
  const added = await request.post(`${API_URL}/api/companies/${companyId}/members`, {
    headers: json(hrToken),
    data: { email: MANAGER_EMAIL, full_name: 'Intake Manager', role: 'manager' },
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

test('HR opens a request, the manager records the intake in Korean, and HR reviews the drafts', async ({ page, browser }) => {
  await addManager(page.request);

  // HR opens the request in the portal.
  await signIn(page);
  await page.getByRole('link', { name: 'Hiring requests' }).click();
  await expect(page.getByRole('heading', { name: 'Hiring requests', exact: true })).toBeVisible();
  await page.getByLabel('Role to hire').fill(TITLE);
  await page.getByLabel('Hiring manager').selectOption({ label: 'Intake Manager' });
  await page.getByRole('button', { name: 'Create request' }).click();
  const hrRow = page.getByRole('listitem').filter({ hasText: TITLE });
  await expect(hrRow).toBeVisible();
  await expect(hrRow.getByTestId('request-status')).toContainText("Waiting for the manager's intake");
  await expect(hrRow.getByRole('link')).toHaveCount(0); // only the manager starts the intake

  // The manager signs in in their own browser session.
  const context = await browser.newContext({ baseURL: WEB_URL, permissions: ['microphone'] });
  // Remember every microphone stream the page opens, to check that all of them are released.
  await context.addInitScript(() => {
    window.__streams = [];
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      const stream = await original(constraints);
      window.__streams.push(stream);
      return stream;
    };
  });
  const manager = await context.newPage();
  await manager.goto('/login');
  await manager.getByLabel('Email').fill(MANAGER_EMAIL);
  await manager.getByLabel('Password').fill(MANAGER_PASSWORD);
  await manager.getByRole('button', { name: 'Sign in' }).click();

  // No language was chosen, so a manager sees Korean.
  await expect(manager.getByRole('heading', { name: '회사 설정' })).toBeVisible();
  await manager.getByRole('link', { name: '채용 요청' }).click();
  const managerRow = manager.getByRole('listitem').filter({ hasText: TITLE });
  await expect(managerRow).toBeVisible();
  await managerRow.getByRole('link', { name: '인테이크 시작' }).click();

  // Before anything is recorded: the plain notice, a mic check, and a start button that waits for both.
  const notice = manager.getByTestId('recording-notice');
  await expect(notice).toContainText('녹음됩니다');
  await expect(notice).toContainText('녹취록은 검토를 위해 HR에 전달됩니다');
  await expect(notice).toContainText('이름은 말씀하지 말아 주세요');
  await expect(manager.getByTestId('start-intake')).toBeDisabled();
  await manager.getByRole('button', { name: '마이크 테스트' }).click();
  await expect(manager.getByTestId('mic-level')).toBeVisible();
  await expect(manager.getByTestId('start-intake')).toBeDisabled();
  await manager.getByTestId('intake-understood').check();
  await expect(manager.getByTestId('start-intake')).toBeEnabled();
  await manager.getByTestId('start-intake').click();

  // The first question carries the no-individuals notice; the recording indicator is always visible.
  const indicator = manager.getByTestId('recording-indicator');
  const questionText = manager.getByTestId('question-text');
  await expect(questionText).toContainText(KO_NO_NAMES);
  await expect(indicator).toBeVisible();
  await expect(indicator).toHaveAttribute('data-recording', 'false');

  const complete = manager.getByTestId('session-complete');
  let answered = 0;
  for (; answered < MAX_QUESTIONS; answered += 1) {
    const progress = await manager.getByTestId('question-progress').innerText();
    await manager.getByTestId('record-answer').click();
    await expect(indicator).toHaveAttribute('data-recording', 'true');
    await manager.waitForTimeout(1200);
    await manager.getByTestId('stop-answer').click();
    await expect(complete.or(manager.getByTestId('question-progress').filter({ hasNotText: progress }))).toBeVisible({ timeout: 30000 });
    if (await complete.isVisible()) break;
  }
  expect(answered).toBeLessThan(MAX_QUESTIONS);
  await expect(complete).toContainText('HR이 검토할 예정입니다');
  await expect(manager.getByRole('link', { name: '채용 요청으로 돌아가기' })).toBeVisible();
  // The microphone is released as soon as the session is over.
  const live = () => manager.evaluate(() => window.__streams.flatMap((s) => s.getTracks()).filter((t) => t.readyState === 'live').length);
  expect(await manager.evaluate(() => window.__streams.length)).toBeGreaterThan(0);
  expect(await live()).toBe(0);

  // The request now says the intake is done.
  await manager.getByRole('link', { name: '채용 요청으로 돌아가기' }).click();
  await expect(managerRow.getByTestId('request-status')).toContainText('인테이크 완료');
  await expect(managerRow.getByRole('link')).toHaveCount(0);
  await context.close();

  // HR finds drafts made from the transcript. The document is read in the background, so look again until it shows.
  await page.getByRole('link', { name: /^Review/ }).click();
  await expect(async () => {
    await page.reload();
    await expect(page.getByRole('article').filter({ hasText: `Manager intake: ${TITLE}` }).first()).toBeVisible();
  }).toPass({ timeout: 60000, intervals: [1000, 2000, 3000] });
});

// The sections used by the manager's pages: sign-in, sidebar, settings, the notices, hiring requests, the intake, and (all under bridges) my interviews, the brief and the scorecard.
const MANAGER_SECTIONS = ['common', 'login', 'nav', 'auth', 'password', 'settings', 'banner', 'demoAi', 'bridges'];
const readLocale = (name) => JSON.parse(readFileSync(join(import.meta.dirname, '..', 'src', 'i18n', `${name}.json`), 'utf8'));

function flatten(value, prefix = '') {
  return Object.entries(value).flatMap(([key, child]) =>
    child !== null && typeof child === 'object' ? flatten(child, `${prefix}${key}.`) : [[`${prefix}${key}`, child]],
  );
}

test('ko.json has a value for every English key used by the manager pages', () => {
  const en = readLocale('en');
  const ko = Object.fromEntries(flatten(readLocale('ko')));
  const missing = [];
  for (const section of MANAGER_SECTIONS) {
    for (const [key, text] of flatten({ [section]: en[section] })) {
      const korean = ko[key];
      if (typeof korean !== 'string' || korean.trim() === '') missing.push(key);
      else if ((text.match(/\{\{\w+\}\}/g) ?? []).sort().join() !== (korean.match(/\{\{\w+\}\}/g) ?? []).sort().join()) missing.push(`${key} (placeholders)`);
    }
  }
  expect(missing).toEqual([]);
});
