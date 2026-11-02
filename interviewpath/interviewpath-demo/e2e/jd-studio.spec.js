import { expect, test } from '@playwright/test';
import { API_URL, addManager, hrSession } from './helpers.js';

// The sample company has a knowledge graph with roles, which the draft is written from. Its HR signs in with a known
// password and is never forced to change it.
const SAMPLE_PASSWORD = 'e2e-sample-password-123';
const HR = 'hr@daehan-precision.sample';

// HR drafts a job description from a hiring request, shapes it with the assistant, passes the lint, and sends it to the
// manager, who reads it in Korean and approves. HR then publishes it and gets copy-and-paste text for each channel.
// The AI is the fake provider: it writes every line the same in all three languages and returns the lines unchanged on
// a revision, so a Korean-only edit is how the test tells the Korean version apart.
const WEB_URL = `http://localhost:${process.env.E2E_WEB_PORT || '5199'}`;
const RUN = Date.now().toString(36);
const MANAGER_EMAIL = `jd-mgr-${RUN}@e2e.test`;
const MANAGER_PASSWORD = 'jd-manager-pass-123';
const TITLE = `JD Backend Lead ${RUN}`;
const KOREAN_LINE = `한국어 설명 ${RUN}`;
const CHANNELS = ['LinkedIn', 'Facebook', 'ITviec', 'TopCV', 'University email', 'University post'];

test('HR drafts, the manager approves in Korean, HR publishes and copies channel content', async ({ page, browser, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  const hr = await hrSession(page.request, HR, SAMPLE_PASSWORD);
  const roles = await (await page.request.get(`${API_URL}/api/companies/${hr.companyId}/jobs/role-options`, { headers: hr.headers })).json();
  const role = roles.find((r) => r.title === 'Backend Developer');
  expect(role).toBeTruthy();
  const managerId = await addManager(page.request, hr, {
    email: MANAGER_EMAIL, fullName: 'JD Manager', password: MANAGER_PASSWORD, departmentId: role.department_id,
  });
  const created = await page.request.post(`${API_URL}/api/companies/${hr.companyId}/hiring-requests`, {
    headers: hr.headers, data: { title: TITLE, manager_user_id: managerId, department_id: role.department_id },
  });
  expect(created.ok()).toBe(true);

  // HR generates the draft from the request.
  await page.goto('/login');
  await page.getByLabel('Email').fill(HR);
  await page.getByLabel('Password').fill(SAMPLE_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
  await page.getByRole('link', { name: 'Hiring requests' }).click();
  const row = page.getByRole('listitem').filter({ hasText: TITLE });
  await row.getByLabel(`Role to write about: ${TITLE}`).selectOption({ label: 'Backend Developer' });
  await row.getByRole('button', { name: 'Generate draft' }).click();
  await expect(page).toHaveURL(/\/jd-studio\/\d+$/);
  const draftId = page.url().match(/\/jd-studio\/(\d+)$/)[1];
  await expect(page.getByRole('heading', { name: 'JD Studio' })).toBeVisible();

  // The lines show in three language tabs, each with its source chips.
  const lines = page.getByTestId('jd-lines').getByRole('listitem');
  await expect.poll(() => lines.count()).toBeGreaterThan(1);
  await expect(page.getByTestId('draft-status')).toContainText('Draft');
  await expect(lines.first().getByTestId('source-chip').first()).toBeVisible();
  await expect(lines.first().getByTestId('unsourced-mark')).toHaveCount(0);
  for (const tab of ['English', 'Tiếng Việt', '한국어']) {
    await page.getByRole('tab', { name: tab }).click();
    await expect(page.getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true');
    await expect(lines.first().getByTestId('jd-line-text')).toContainText('[Demo AI]');
  }
  await page.getByRole('tab', { name: 'English' }).click();
  await expect(page.getByTestId('lint-clear')).toBeVisible();

  // Make it shorter: a new version and the assistant's summary.
  const version = async () => Number(await page.getByTestId('draft-version').getAttribute('data-version'));
  const before = await version();
  await page.getByLabel('Message to the assistant').fill('Make it shorter');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByTestId('assistant-assistant')).toContainText('Demo AI revision');
  await expect(page.getByTestId('assistant-user')).toContainText('Make it shorter');
  expect(await version()).toBeGreaterThan(before);

  // A salary is not in the knowledge graph, so it is only proposed. Dismiss hides a proposal.
  await page.getByLabel('Message to the assistant').fill('Add a salary line');
  await page.getByRole('button', { name: 'Send' }).click();
  const proposal = page.getByTestId('proposal');
  await expect(proposal).toHaveCount(1);
  await expect(proposal).toContainText('Salary to be confirmed by HR');
  await expect(proposal.getByRole('button', { name: 'Confirm' })).toBeVisible();
  await expect(proposal.getByRole('button', { name: 'Dismiss' })).toBeVisible();
  await expect(page.getByTestId('confirmed-label')).toHaveCount(0);
  await proposal.getByRole('button', { name: 'Confirm' }).click();
  await expect(page.getByTestId('proposal')).toHaveCount(0);
  await expect(page.getByTestId('confirmed-label')).toHaveCount(1);
  await expect(page.getByTestId('confirmed-label')).toHaveText('Confirmed by HR');
  await page.getByLabel('Message to the assistant').fill('Add a salary line again');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByTestId('proposal')).toHaveCount(1);
  await page.getByTestId('proposal').getByRole('button', { name: 'Dismiss' }).click();
  await expect(page.getByTestId('proposal')).toHaveCount(0);

  // The Korean version is written by hand so the manager's page can be told apart from the English one.
  await page.getByRole('tab', { name: '한국어' }).click();
  await page.getByRole('button', { name: 'Edit line 1', exact: true }).click();
  await page.getByLabel('Text of line 1', { exact: true }).fill(KOREAN_LINE);
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(lines.first().getByTestId('jd-line-text')).toHaveText(KOREAN_LINE);
  await page.getByRole('tab', { name: 'English' }).click();

  // A discriminatory edit shows a blocking issue and disables Publish and Submit. Putting the text back clears it.
  const original = await lines.nth(1).getByTestId('jd-line-text').innerText();
  await page.getByRole('button', { name: 'Edit line 2', exact: true }).click();
  await page.getByLabel('Text of line 2', { exact: true }).fill('Under 30 years old');
  await page.getByRole('button', { name: 'Save' }).click();
  const lint = page.getByTestId('lint-panel');
  await expect(lint.getByTestId('lint-block')).toHaveCount(1);
  await expect(lint.getByTestId('lint-block')).toContainText('Discrimination');
  await expect(lint.getByTestId('lint-block')).toContainText('line 2');
  await expect(page.getByRole('button', { name: 'Publish', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Submit to manager' })).toBeDisabled();
  await page.getByRole('button', { name: 'Edit line 2', exact: true }).click();
  await page.getByLabel('Text of line 2', { exact: true }).fill(original);
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(lint.getByTestId('lint-clear')).toBeVisible();
  await expect(lint.getByTestId('lint-block')).toHaveCount(0);

  // A job needs a requirement to be published: HR marks the first line as a must-have requirement.
  await page.getByLabel('Line 1 is a requirement', { exact: true }).click();
  await expect(page.getByLabel('Line 1 is a requirement', { exact: true })).toBeChecked();
  await page.getByLabel('Line 1 is a must-have', { exact: true }).click();
  await expect(page.getByLabel('Line 1 is a must-have', { exact: true })).toBeChecked();

  // HR submits.
  await page.getByRole('button', { name: 'Submit to manager' }).click();
  await expect(page.getByTestId('draft-status')).toContainText('Waiting for the manager');
  await expect(page.getByRole('button', { name: 'Publish', exact: true })).toBeDisabled();

  // The manager signs in in their own session, sees Korean, reads the Korean version and approves.
  const managerContext = await browser.newContext({ baseURL: WEB_URL });
  const manager = await managerContext.newPage();
  await manager.goto('/login');
  await manager.getByLabel('Email').fill(MANAGER_EMAIL);
  await manager.getByLabel('Password').fill(MANAGER_PASSWORD);
  await manager.getByRole('button', { name: 'Sign in' }).click();
  await expect(manager.getByRole('heading', { name: '회사 설정' })).toBeVisible();
  await manager.goto(`/jd-studio/${draftId}`);
  await expect(manager.getByRole('heading', { name: 'JD 스튜디오' })).toBeVisible();
  await expect(manager.getByRole('tab', { name: '한국어' })).toHaveAttribute('aria-selected', 'true');
  await expect(manager.getByTestId('jd-lines').getByRole('listitem').first().getByTestId('jd-line-text')).toHaveText(KOREAN_LINE);
  await expect(manager.getByTestId('draft-status')).toContainText('매니저 검토 대기');
  await expect(manager.getByRole('button', { name: /^수정$|^보내기$/ })).toHaveCount(0); // a manager reads; HR edits
  await manager.getByRole('button', { name: '승인', exact: true }).click();
  await expect(manager.getByTestId('draft-status')).toContainText('승인됨');
  await expect(manager.getByRole('button', { name: '승인', exact: true })).toHaveCount(0);
  await managerContext.close();

  // HR publishes. Channel content shows for every channel, with a link and a copy button and nothing that posts.
  await page.reload();
  await expect(page.getByTestId('draft-status')).toContainText('Approved');
  const [published] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/job-drafts/${draftId}/publish`)),
    page.getByRole('button', { name: 'Publish', exact: true }).click(),
  ]);
  expect(published.status(), await published.text()).toBe(200);
  await expect(page.getByTestId('draft-status')).toContainText('Published');
  const content = page.getByTestId('channel-content');
  await expect(content.getByTestId('manual-post-notice')).toHaveText('Copy and post by hand. This system does not post to job boards.');
  await expect(content.getByRole('tab')).toHaveText(CHANNELS);
  for (const name of CHANNELS) {
    await content.getByRole('tab', { name }).click();
    await expect(content.getByTestId('channel-body')).toContainText('[Demo AI]');
    await expect(content.getByTestId('channel-link')).toHaveAttribute('href', /\/jobs\/[a-z0-9-]+\?src=/);
    await expect(content.getByRole('button', { name: /^Copy link / })).toBeVisible();
    await expect(content.getByRole('button', { name: /^Copy text / })).toBeVisible();
  }
  // Only tabs and copy buttons: no button posts, sends or publishes anywhere.
  const buttons = await content.getByRole('button').allInnerTexts();
  expect(buttons.filter((text) => !/^Copy/.test(text.trim()) && !CHANNELS.includes(text.trim()))).toEqual([]);
  await content.getByRole('tab', { name: 'LinkedIn' }).click();
  await content.getByRole('button', { name: /^Copy link / }).click();
  await expect(content.getByText('Copied', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toMatch(/\/jobs\/[a-z0-9-]+\?src=/);
});
