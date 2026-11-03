import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { INSIGHTS_USER, signIn } from './helpers.js';

// The "insights" sample company is written by start-backend.sh: simulate-hiring with seed 42 on two jobs, then a few
// real rows. `both` has real and simulated rows, `simulated` only simulated ones, `real` only real ones and no cost.
test.describe.configure({ mode: 'serial' });

let seed;
test.beforeAll(() => {
  seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'insights_seed.json'), 'utf8'));
});

const open = async (page, path) => {
  await signIn(page, INSIGHTS_USER);
  await page.goto(path);
};
const banner = (page) => page.getByTestId('simulated-banner');
const toggle = (page) => page.getByRole('group', { name: 'Data shown' });

test('simulated-only job: banner without a close button, sorted rows, no toggle', async ({ page }) => {
  await open(page, `/jobs/${seed.simulated}/channels`);
  await expect(page.getByRole('heading', { name: 'Channel Intelligence' })).toBeVisible();
  await expect(banner(page)).toContainText('Simulated data');
  await expect(banner(page).getByRole('button')).toHaveCount(0);
  await expect(toggle(page)).toHaveCount(0);

  const applications = async () => (await page.locator('[data-testid^="channel-"] td:nth-child(2)').allTextContents()).map(Number);
  const byDefault = await applications();
  expect(byDefault.length).toBeGreaterThan(3);
  expect(byDefault).toEqual([...byDefault].sort((a, b) => b - a));

  const header = page.getByRole('columnheader', { name: 'Applications' });
  await expect(header).toHaveAttribute('aria-sort', 'none');
  await header.getByRole('button').click();
  await expect(header).toHaveAttribute('aria-sort', 'descending');
  await header.getByRole('button').click();
  await expect(header).toHaveAttribute('aria-sort', 'ascending');
  const ascending = await applications();
  expect(ascending).toEqual([...ascending].sort((a, b) => a - b));

  await expect(page.getByText('Sample too small, treat as a hint').first()).toBeVisible();
  await expect(page.getByTestId('channel-facebook').getByText('Not entered')).toBeVisible();
});

test('commentary is asked for, never shown on load, and the table stands without it', async ({ page }) => {
  await open(page, `/jobs/${seed.simulated}/channels`);
  await expect(page.getByTestId('channel-table')).toBeVisible();
  await expect(page.getByTestId('commentary')).toHaveCount(0);
  await page.getByRole('button', { name: 'Ask for commentary' }).click();
  await expect(page.getByTestId('commentary').or(page.getByText('No commentary is available'))).toBeVisible();
  await expect(page.getByTestId('channel-table')).toBeVisible();
});

test('a job with both kinds of rows has a toggle, and the two are never mixed', async ({ page }) => {
  await open(page, `/jobs/${seed.both}/channels`);
  await expect(toggle(page)).toBeVisible();
  await expect(banner(page)).toHaveCount(0);
  await expect(page.getByTestId('channel-linkedin').locator('td').nth(1)).toHaveText('2');
  await toggle(page).getByRole('button', { name: 'Simulated data' }).click();
  await expect(banner(page)).toBeVisible();
  await expect(page.getByTestId('channel-linkedin').locator('td').nth(1)).not.toHaveText('2');
  await toggle(page).getByRole('button', { name: 'Real data' }).click();
  await expect(banner(page)).toHaveCount(0);
});

test('entering a cost updates that row', async ({ page }) => {
  await open(page, `/jobs/${seed.real}/channels`);
  await expect(toggle(page)).toHaveCount(0);
  await expect(banner(page)).toHaveCount(0);
  const linkedin = page.getByTestId('channel-linkedin');
  await expect(linkedin.getByText('Not entered')).toBeVisible();
  await expect(linkedin.getByText('Sample too small, treat as a hint')).toBeVisible();
  await page.getByLabel('Channel', { exact: true }).fill('linkedin');
  await page.getByLabel('Amount (VND)').fill('3000000');
  await page.getByRole('button', { name: 'Save cost' }).click();
  await expect(linkedin.getByText('Not entered')).toHaveCount(0);
  await expect(linkedin.getByRole('cell', { name: '3,000,000' })).toHaveCount(2); // the cost, and the cost of its one approval
  await expect(page.getByTestId('channel-referral').getByText('Not entered')).toBeVisible();
});

test('Reality Check suggests, says when data is too thin, and links to JD Studio without applying', async ({ page }) => {
  await open(page, `/jobs/${seed.both}/reality-check`);
  await expect(page.getByRole('heading', { name: 'Requirement Reality Check' })).toBeVisible();
  await expect(page.getByText('An extended probation does not count as passed.')).toBeVisible();
  // Real data: too few hires.
  await expect(page.getByText('Not enough data').first()).toBeVisible();
  await expect(banner(page)).toHaveCount(0);

  await toggle(page).getByRole('button', { name: 'Simulated data' }).click();
  await expect(banner(page)).toBeVisible();
  const link = page.getByRole('link', { name: 'Open JD Studio' }).first();
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute('href', `/jd-studio/${seed.draft_id}`);
  await expect(page.getByRole('button', { name: /apply/i })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /apply/i })).toHaveCount(0);

  // No draft for this job: the link goes to the job editor.
  await page.goto(`/jobs/${seed.simulated}/reality-check`);
  const editor = page.getByRole('link', { name: 'Open the job editor' }).first();
  await expect(editor).toHaveAttribute('href', `/jobs/${seed.simulated}`);
});

test('HR edits the thresholds, and a bad pair is refused', async ({ page }) => {
  await open(page, `/jobs/${seed.simulated}/reality-check`);
  const low = page.getByLabel('Low share (%)');
  await expect(low).toHaveValue('30');
  await low.fill('80');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await low.fill('20');
  await page.getByLabel('Minimum hired').fill('5');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Saved')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Low share (%)')).toHaveValue('20');
  await expect(page.getByLabel('Minimum hired')).toHaveValue('5');
});
