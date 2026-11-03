import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { API_URL, NEW_PASSWORD, ONBOARDING_USER, ensurePasswordChanged, fillLogin, hrSession, signIn } from './helpers.js';

// HR approves the candidate and records "hired", then drafts a 30-60-90 plan from the team's knowledge. The department's
// manager edits it, HR approves it, and the hire signs in as an employee, ticks an item and asks Copilot. The manager
// records probation. The data is the "onboarding" company written by e2e/seed_onboarding.py. The AI is the fake provider.
test.describe.configure({ mode: 'serial' });

const WEB_URL = `http://localhost:${process.env.E2E_WEB_PORT || '5199'}`;
const PASSWORD = 'e2e-onboarding-pass-123'; // also written in seed_onboarding.py
const MANAGER = { email: 'manager@onboarding.e2e.test' };
const HIRE = { email: 'hire@onboarding.e2e.test' };
// The fake extraction (e2e/fixtures/extraction.json) yields a node from exactly this line.
const INTERNAL_TITLE = 'Internal quokka lantern guide k7';
const INTERNAL_LINE = 'Zephyrk7 quokka lantern onboarding grants amber badges';
const EDITED_TITLE = 'Day 30: read the lantern guide';

let seed;
let planId;

// HR publishes one internal note, so the plan has knowledge to draw from and the Copilot has something to answer with.
async function publishInternalNote(request, { headers, companyId }) {
  const kb = `${API_URL}/api/companies/${companyId}/kb`;
  const upload = await request.post(`${kb}/documents`, {
    headers,
    multipart: {
      title: INTERNAL_TITLE,
      visibility: 'internal',
      language: 'en',
      file: { name: 'note.txt', mimeType: 'text/plain', buffer: Buffer.from(`${INTERNAL_LINE}\n\nThis note was written for the end-to-end test.`) },
    },
  });
  expect(upload.status()).toBe(201);
  const { document } = await upload.json();
  await expect
    .poll(async () => (await (await request.get(`${kb}/documents`, { headers })).json()).find((d) => d.id === document.id)?.status, { timeout: 30000 })
    .toBe('review');
  const review = await (await request.get(`${kb}/review?document_id=${document.id}`, { headers })).json();
  expect(review.nodes.length).toBeGreaterThan(0);
  const decided = await request.post(`${kb}/review/decide`, {
    headers,
    data: { items: review.nodes.map((n) => ({ action: 'accept', node_id: n.id, visibility: 'internal' })) },
  });
  expect(decided.ok()).toBe(true);
}

test.beforeAll(async ({ request }) => {
  seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'onboarding_seed.json'), 'utf8'));
  await ensurePasswordChanged(request, ONBOARDING_USER);
  await publishInternalNote(request, await hrSession(request, ONBOARDING_USER.email, NEW_PASSWORD));
});

// A second browser session for someone who signs in with a known password. English is chosen so a manager does not get Korean.
async function signInAs(browser, user) {
  const context = await browser.newContext({ baseURL: WEB_URL });
  await context.addInitScript(() => localStorage.setItem('portal_lang', 'en'));
  const page = await context.newPage();
  await page.goto('/login');
  await fillLogin(page, PASSWORD, user);
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
  return page;
}

const phase = (page, days) => page.getByTestId(`phase-${days}`);

test('HR records the hire and drafts a plan whose items show their source', async ({ page }) => {
  await signIn(page, ONBOARDING_USER);
  await page.goto(`/jobs/${seed.job_id}/board`);
  await page.getByTestId('card-#O1').getByRole('button', { name: /#O1/ }).click();
  const panel = page.getByTestId('detail-panel');
  await expect(panel.getByTestId('onboarding-start')).toHaveCount(0);
  await panel.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Approved');
  // The plan is offered only for a hire.
  await expect(panel.getByTestId('onboarding-start')).toHaveCount(0);
  const outcome = panel.getByTestId('outcome-control');
  await outcome.getByRole('button', { name: 'Hired', exact: true }).click();
  await outcome.getByRole('button', { name: 'Yes, record it' }).click();
  await expect(outcome.getByTestId('outcome-recorded')).toHaveText('Recorded: Hired');

  await panel.getByTestId('onboarding-start').getByRole('button', { name: 'Create onboarding plan' }).click();
  await expect(page).toHaveURL(/\/onboarding\/\d+$/);
  planId = Number(page.url().split('/').pop());

  await expect(page.getByRole('heading', { name: 'Onboarding plan' })).toBeVisible();
  await expect(page.getByTestId('plan-status')).toHaveText('Draft, waiting for approval');
  await expect(page.getByText("Built from the team's knowledge only.")).toBeVisible();
  for (const days of [30, 60, 90]) {
    await expect(phase(page, days).getByTestId('plan-item')).toHaveCount(1);
    await expect(phase(page, days).getByTestId('item-source')).toContainText('quokka lantern');
  }

  // The panel now opens the plan instead of drafting another one.
  await page.goto(`/jobs/${seed.job_id}/board`);
  await page.getByTestId('card-#O1').getByRole('button', { name: /#O1/ }).click();
  await expect(page.getByTestId('detail-panel').getByRole('link', { name: 'Open onboarding plan' })).toHaveAttribute('href', `/onboarding/${planId}`);
});

test('the department manager finds the plan from their interviews and edits it', async ({ browser }) => {
  const page = await signInAs(browser, MANAGER);
  await page.getByRole('link', { name: 'My interviews' }).click();
  await page.getByTestId(`interview-${seed.application_id}`).getByRole('link', { name: 'Open onboarding plan' }).click();
  await expect(page).toHaveURL(new RegExp(`/onboarding/${planId}$`));

  await phase(page, 30).getByRole('textbox', { name: 'Item title' }).fill(EDITED_TITLE);
  await phase(page, 90).getByRole('combobox', { name: 'Move to' }).selectOption('60');
  await expect(page.getByRole('button', { name: 'Approve plan' })).toBeDisabled();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(phase(page, 60).getByTestId('plan-item')).toHaveCount(2);
  await expect(phase(page, 90).getByTestId('plan-item')).toHaveCount(0);
  await page.reload();
  await expect(phase(page, 30).getByRole('textbox', { name: 'Item title' })).toHaveValue(EDITED_TITLE);
  await expect(phase(page, 60).getByTestId('plan-item')).toHaveCount(2);
});

test('HR approves the edited plan, and it becomes read-only', async ({ page }) => {
  await signIn(page, ONBOARDING_USER);
  await page.goto(`/onboarding/${planId}`);
  await expect(phase(page, 30).getByRole('textbox', { name: 'Item title' })).toHaveValue(EDITED_TITLE);
  await page.getByRole('button', { name: 'Approve plan' }).click();
  await expect(page.getByRole('alertdialog')).toContainText('The hire becomes an employee');
  await page.getByRole('button', { name: 'Yes, approve' }).click();
  await expect(page.getByTestId('plan-status')).toHaveText('Approved');
  await expect(page.getByRole('textbox', { name: 'Item title' })).toHaveCount(0);
  await expect(phase(page, 30)).toContainText(EDITED_TITLE);
});

test('the hire signs in as an employee, ticks an item and asks Copilot', async ({ browser }) => {
  const page = await signInAs(browser, HIRE);
  await expect(page.getByRole('link', { name: 'Knowledge graph' })).toHaveCount(0);
  await page.getByRole('link', { name: 'My onboarding' }).click();
  await expect(page.getByRole('heading', { name: 'My onboarding' })).toBeVisible();
  await expect(page.getByText('Your manager and HR do not see which items you have done.')).toBeVisible();
  await expect(page.getByTestId('my-item')).toHaveCount(3);

  const item = page.getByRole('checkbox', { name: EDITED_TITLE });
  await expect(item).not.toBeChecked();
  await item.click(); // the box changes when the server has answered, so check() would not wait for it
  await expect(item).toBeChecked();
  await expect(item).toBeDisabled();
  await expect(phase(page, 30)).toContainText('Done on');
  await page.reload();
  await expect(page.getByRole('checkbox', { name: EDITED_TITLE })).toBeChecked();
  // Tick every item: the plan must still look unfinished to HR and the manager.
  for (const box of await page.getByRole('checkbox').all()) {
    if (!(await box.isChecked())) await box.click();
  }
  await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(3);

  // The plan page is for HR and managers: the employee is sent to the Copilot instead.
  await page.goto(`/onboarding/${planId}`);
  await expect(page).toHaveURL(/\/copilot$/);
  await page.goto('/my-onboarding');
  await page.getByRole('link', { name: 'Ask Copilot about your plan' }).click();
  await page.getByLabel('Your question').fill(INTERNAL_LINE);
  await page.getByRole('button', { name: 'Ask' }).click();
  await expect(page.getByTestId('copilot-answer').first()).toHaveAttribute('data-state', 'answered');
});

test('the manager records probation and sees nothing about what the hire ticked', async ({ browser }) => {
  const page = await signInAs(browser, MANAGER);
  // The server's answer to the page, after the hire ticked every item, holds no progress and no "finished" status.
  const answered = page.waitForResponse((r) => r.url().includes('/api/companies/') && r.url().endsWith(`/onboarding/${planId}`) && r.request().method() === 'GET');
  await page.goto(`/onboarding/${planId}`);
  const plan = await (await answered).json();
  expect(plan.items).toHaveLength(3);
  expect(JSON.stringify(plan)).not.toContain('done_at');
  expect(plan.status).toBe('active');
  await expect(page.getByTestId('plan-status')).toHaveText('Approved');
  const control = page.getByTestId('probation-control');
  await control.getByRole('button', { name: 'Passed', exact: true }).click();
  await expect(control.getByRole('alertdialog')).toContainText('Record the probation result as "Passed"?');
  await control.getByRole('button', { name: 'Yes, record it' }).click();
  await expect(control.getByTestId('probation-recorded')).toHaveText('Recorded: Passed');
  await page.reload();
  await expect(page.getByTestId('probation-recorded')).toHaveText('Recorded: Passed');
});
