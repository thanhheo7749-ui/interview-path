import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { BOARD_USER, signIn } from './helpers.js';

// The data is the sample company written by e2e/seed_board.py when the backend starts. Tests change it in
// order (a label is corrected, a candidate is rejected), so they run one after another on the same data.
test.describe.configure({ mode: 'serial' });

let seed;
test.beforeAll(() => {
  seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'board_seed.json'), 'utf8'));
});

async function openBoard(page) {
  await signIn(page, BOARD_USER);
  await page.goto(`/jobs/${seed.job_id}/board`);
  await expect(page.getByTestId('cell-priority')).toBeVisible();
}

const count = (page, key) => page.getByTestId(`count-${key}`);
const card = (page, alias) => page.getByTestId(`card-${alias}`);

async function openCard(page, alias) {
  await card(page, alias).getByRole('button', { name: new RegExp(alias) }).click();
  await expect(page.getByTestId('detail-panel').getByRole('heading', { name: alias })).toBeVisible();
}

test('four cells show their counts and Hidden Gem stands out', async ({ page }) => {
  await openBoard(page);
  await expect(count(page, 'priority')).toHaveText('3 to decide');
  await expect(count(page, 'strong_cv_unclear')).toHaveText('1 to decide');
  await expect(count(page, 'hidden_gem')).toHaveText('2 to decide');
  await expect(count(page, 'not_enough_evidence')).toHaveText('1 to decide');
  const gem = page.getByTestId('cell-hidden_gem');
  await expect(gem.getByRole('heading', { name: 'Hidden Gem' })).toBeVisible();
  await expect(gem.getByText('A CV filter would have missed these.')).toBeVisible();
  await expect(gem).toHaveClass(/border-violet-300/);
  await expect(page.getByTestId('cell-priority').getByRole('heading', { name: 'Priority' })).toBeVisible();
});

test('lanes hold the candidates who are not on the board', async ({ page }) => {
  await openBoard(page);
  await expect(page.getByTestId('lane-not_interviewed').getByRole('heading', { name: 'Not interviewed' })).toBeVisible();
  await expect(count(page, 'not_interviewed')).toHaveText('2');
  await expect(count(page, 'refused_recording')).toHaveText('1');
  await expect(count(page, 'withdrawn')).toHaveText('1');
  await expect(count(page, 'analysis_failed')).toHaveText('1');
  await expect(count(page, 'analyzing')).toHaveText('1');
});

test('cards show aliases and no names', async ({ page }) => {
  await openBoard(page);
  await expect(card(page, '#P1')).toBeVisible();
  await expect(card(page, '#G1')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('Sample Person');
  await expect(page.locator('body')).not.toContainText('example.test');
});

test('the detail panel shows the transcript, evidence side by side, claims, culture notes and the AI suggestion', async ({ page }) => {
  await openBoard(page);
  await openCard(page, '#P1');
  const panel = page.getByTestId('detail-panel');

  // The transcript comes before the evidence.
  const order = await panel.locator('h3').allTextContents();
  expect(order.indexOf('Interview transcript')).toBeGreaterThanOrEqual(0);
  expect(order.indexOf('Interview transcript')).toBeLessThan(order.findIndex((text) => text.startsWith('Requirements')));
  await expect(panel.getByTestId('transcript')).toContainText('I ran a billing service for two years.');

  const table = panel.getByTestId('evidence-table');
  await expect(table.getByRole('columnheader', { name: 'CV evidence' })).toBeVisible();
  await expect(table.getByRole('columnheader', { name: 'Interview evidence' })).toBeVisible();
  const row = table.getByRole('row', { name: /Python services in production/ });
  await expect(row).toContainText('Python billing service');
  await expect(row).toContainText('I ran a billing service for two years.');
  await expect(table.getByRole('row', { name: /Sample confidential requirement/ })).toContainText('Confidential requirement');

  await expect(panel.getByTestId('claims')).toContainText('Not explained');
  await expect(panel.getByTestId('culture-notes')).toContainText('Ownership');
  await expect(panel.getByTestId('ai-suggestion')).toContainText('AI suggestion, for your review');
  await expect(panel.getByTestId('ai-suggestion')).toContainText('Strong Python evidence');
  // No overall score anywhere.
  await expect(panel).not.toContainText(/\bscore\b|\d\s?%/i);
});

test('reveal identity asks first, then shows the name', async ({ page }) => {
  await openBoard(page);
  await openCard(page, '#P1');
  const panel = page.getByTestId('detail-panel');
  await expect(panel).not.toContainText('Sample Person P1');
  await panel.getByRole('button', { name: 'Reveal identity' }).click();
  await expect(panel.getByRole('alertdialog')).toContainText('recorded in the audit log');
  await expect(panel).not.toContainText('Sample Person P1');
  await panel.getByRole('button', { name: 'Reveal', exact: true }).click();
  await expect(panel.getByTestId('revealed-identity')).toContainText('Sample Person P1');
});

test('a cited quote offers audio on demand', async ({ page }) => {
  await openBoard(page);
  await openCard(page, '#P1');
  const panel = page.getByTestId('detail-panel');
  const table = panel.getByTestId('evidence-table');
  await expect(panel.locator('audio')).toHaveCount(0);
  const play = table.getByRole('row', { name: /Python services in production/ }).getByRole('button', { name: 'Play from this moment' });
  await expect(play).toBeVisible();
  await play.click();
  await expect(table.locator('audio')).toHaveCount(1);
});

test('correcting the CV label requires a reason', async ({ page }) => {
  await openBoard(page);
  await openCard(page, '#G1');
  const panel = page.getByTestId('detail-panel');
  await panel.getByRole('button', { name: 'Correct CV label' }).click();
  await panel.getByRole('button', { name: 'Save correction' }).click();
  await expect(panel.getByText('Please give a reason.')).toBeVisible();
  await expect(count(page, 'hidden_gem')).toHaveText('2 to decide');

  await panel.getByLabel('Reason (required)').fill('The CV lists the degree under a different name.');
  await panel.getByRole('button', { name: 'Save correction' }).click();
  await expect(panel.getByText('CV label corrected by HR')).toBeVisible();
  await expect(count(page, 'hidden_gem')).toHaveText('1 to decide');
  await expect(page.getByTestId('cell-priority').getByTestId('card-#G1')).toBeVisible();
});

test('rejecting shows the decided state and leaves the undecided count', async ({ page }) => {
  await openBoard(page);
  await expect(count(page, 'priority')).toHaveText('4 to decide');
  await openCard(page, '#P2');
  const panel = page.getByTestId('detail-panel');
  await panel.getByRole('button', { name: 'Reject', exact: true }).click();
  await expect(panel.getByTestId('decided-state')).toHaveText('Rejected');
  await expect(card(page, '#P2').getByTestId('decided-badge')).toHaveText('Rejected');
  await expect(count(page, 'priority')).toHaveText('3 to decide');
});

test('bulk reject states the count before it runs', async ({ page }) => {
  await openBoard(page);
  const cell = page.getByTestId('cell-priority');
  await cell.getByLabel('Select #P3').check();
  await cell.getByLabel('Select #G1').check();
  await cell.getByRole('button', { name: 'Reject 2 selected' }).click();
  await expect(cell.getByRole('alertdialog')).toContainText('reject 2 candidates');
  await cell.getByRole('button', { name: 'Cancel' }).click();
  await expect(count(page, 'priority')).toHaveText('3 to decide');
  await cell.getByRole('button', { name: 'Reject 2 selected' }).click();
  await cell.getByRole('button', { name: 'Yes, reject 2' }).click();
  await expect(count(page, 'priority')).toHaveText('1 to decide');
});

test('Vietnamese strings are used when the language is switched', async ({ page }) => {
  await openBoard(page);
  await page.evaluate(() => localStorage.setItem('portal_lang', 'vi'));
  await page.reload();
  await expect(page.getByTestId('cell-hidden_gem').getByRole('heading', { name: 'Viên ngọc ẩn' })).toBeVisible();
  await page.evaluate(() => localStorage.setItem('portal_lang', 'en'));
});

test('nothing in src imports the mock candidates', () => {
  const files = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const full = join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else files.push(full);
    }
  };
  walk('src');
  const offenders = files.filter((file) => /mockCandidates|WorkflowPage/.test(readFileSync(file, 'utf8')));
  expect(offenders).toEqual([]);
});
