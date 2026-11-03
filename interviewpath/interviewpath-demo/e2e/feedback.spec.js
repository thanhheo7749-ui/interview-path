import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { FEEDBACK_USER, signIn } from './helpers.js';

// The "feedback" sample company is written by start-backend.sh: a job with four undecided candidates who have no
// interview (so a rejection gets the standard message), a skill, and one person in the talent pool.
// The tests change the same candidates in order, so they run one after another.
test.describe.configure({ mode: 'serial' });

let seed;
test.beforeAll(() => {
  seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'feedback_seed.json'), 'utf8'));
});

const CELL = 'not_enough_evidence';
const panel = (page) => page.getByTestId('detail-panel');
const editor = (page) => page.getByTestId('feedback-editor');

async function openBoard(page) {
  await signIn(page, FEEDBACK_USER);
  await page.goto(`/jobs/${seed.board_job}/board`);
  await expect(page.getByTestId(`cell-${CELL}`)).toBeVisible();
}

const openCard = async (page, alias) => {
  await page.getByTestId(`card-${alias}`).getByRole('button', { name: alias }).click();
  await expect(panel(page).getByRole('heading', { name: alias })).toBeVisible();
};

async function reject(page, alias) {
  await openCard(page, alias);
  await panel(page).getByRole('button', { name: 'Reject', exact: true }).click();
  await panel(page).getByRole('button', { name: 'Yes, reject', exact: true }).click();
  await expect(panel(page).getByTestId('decided-state')).toHaveText('Rejected');
  await expect(editor(page).getByTestId('feedback-status')).toContainText('Waiting for your approval');
}

test('rejecting makes a draft that waits for HR, with the demo AI notice', async ({ page }) => {
  await openBoard(page);
  await reject(page, '#F1');
  await expect(page.getByTestId('demo-ai-notice')).toContainText('Demo AI');
  await expect(editor(page).getByRole('textbox', { name: 'Feedback message' })).toHaveValue(/Thank you for your time/);
  await expect(editor(page).getByTestId('feedback-learning')).toContainText('No catalogue entry matches');
  await panel(page).getByRole('button', { name: 'Close' }).click();
  await page.reload();
  await expect(page.getByTestId(`feedback-pending-${CELL}`)).toHaveText('Feedback to approve: 1');
  await expect(page.getByTestId('feedback-queue')).toContainText('Feedback drafts waiting: 1');
});

test('the editor shows why a phrase is refused, and approving sends the saved text', async ({ page }) => {
  await openBoard(page);
  await openCard(page, '#F1');
  const message = editor(page).getByRole('textbox', { name: 'Feedback message' });
  await message.fill('Thank you for applying. Other candidates were stronger than you.');
  await editor(page).getByRole('button', { name: 'Save changes' }).click();
  await expect(editor(page).getByRole('alert')).toContainText('This text cannot be sent to a candidate');
  // Unsaved text cannot be approved.
  await expect(editor(page).getByRole('button', { name: 'Approve and send' })).toBeDisabled();

  await message.fill('Thank you for applying. We wish you well in your search.');
  await editor(page).getByRole('button', { name: 'Save changes' }).click();
  await expect(editor(page).getByRole('alert')).toHaveCount(0);
  await editor(page).getByRole('button', { name: 'Approve and send' }).click();
  await expect(editor(page).getByTestId('feedback-status')).toContainText('Sent to the candidate');
  await expect(message).toHaveAttribute('readonly', '');
  await expect(page.getByTestId('feedback-queue')).toHaveCount(0);
});

test('bulk approval lists aliases and previews, and sends only what was picked', async ({ page }) => {
  await openBoard(page);
  await reject(page, '#F2');
  await panel(page).getByRole('button', { name: 'Close' }).click();
  await reject(page, '#F3');
  await panel(page).getByRole('button', { name: 'Close' }).click();
  await page.reload();

  const queue = page.getByTestId('feedback-queue');
  await expect(queue).toContainText('Feedback drafts waiting: 2');
  await expect(queue.getByTestId('draft-#F2')).toContainText('Thank you for your time');
  await expect(queue).not.toContainText('Sample Person');
  await queue.getByRole('checkbox', { name: 'Select feedback for #F2' }).check();
  await queue.getByRole('button', { name: 'Approve 1 selected' }).click();
  await expect(queue.getByRole('alertdialog')).toContainText('Send feedback to 1 candidates now?');
  await queue.getByRole('button', { name: 'Send 1', exact: true }).click();
  await expect(queue).toContainText('Feedback drafts waiting: 1');
  await queue.getByRole('button', { name: 'Select all' }).click();
  await queue.getByRole('button', { name: 'Approve 1 selected' }).click();
  await queue.getByRole('button', { name: 'Send 1', exact: true }).click();
  await expect(queue).toHaveCount(0);
});

test('the learning catalogue accepts a row and refuses a bad link', async ({ page }) => {
  await signIn(page, FEEDBACK_USER);
  await page.goto('/learning');
  await expect(page.getByRole('heading', { name: 'Learning catalogue' })).toBeVisible();
  await expect(page.getByText('The catalogue is empty.')).toBeVisible();
  const form = page.getByRole('form', { name: 'Add a learning resource' });
  await form.getByLabel('Skill').selectOption({ label: seed.skill });
  await form.getByLabel('Title').fill('Docker for services');
  await form.getByLabel('Link').fill('docker-for-services');
  await form.getByRole('button', { name: 'Add to catalogue' }).click();
  await expect(page.getByRole('alert')).toContainText('url must be a complete http or https link');
  await expect(page.getByText('The catalogue is empty.')).toBeVisible();

  await form.getByLabel('Link').fill('https://learn.example.test/docker');
  await form.getByLabel('Provider').fill('Example Learn');
  await form.getByRole('button', { name: 'Add to catalogue' }).click();
  await expect(page.getByRole('link', { name: 'Docker for services' })).toHaveAttribute('href', 'https://learn.example.test/docker');
  await page.reload();
  await expect(page.getByRole('link', { name: 'Docker for services' })).toBeVisible();
});

test('talent matches wait for the button, list aliases only, and invite makes an application', async ({ page }) => {
  const asked = [];
  page.on('request', (request) => { if (request.url().includes('/talent-matches')) asked.push(request.url()); });
  await signIn(page, FEEDBACK_USER);
  await page.goto(`/jobs/${seed.talent_job}/board`);
  const talent = page.getByTestId('talent-matches');
  await expect(talent).toBeVisible();
  await page.waitForLoadState('networkidle');
  expect(asked).toHaveLength(0);
  await expect(talent.getByTestId('match-#P1')).toHaveCount(0);

  await talent.getByRole('button', { name: 'Find matches' }).click();
  const match = talent.getByTestId('match-#P1');
  await expect(match).toBeVisible();
  await expect(talent).not.toContainText('Sample Person');
  expect(asked).toHaveLength(1);

  const response = page.waitForResponse((r) => r.url().includes('/talent-pool/') && r.request().method() === 'POST');
  await match.getByRole('button', { name: 'Invite to apply' }).click();
  const created = await response;
  expect(created.status()).toBe(201);
  const application = await created.json();
  expect(application.job_id).toBe(seed.talent_job);
  expect(application.source_channel).toBe('talent_pool');
  await expect(match).toContainText(`Invited as ${application.alias}`);
});
