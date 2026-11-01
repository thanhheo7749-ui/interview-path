import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { BRAIN_USER, signIn } from './helpers.js';

const FIXTURES = join(import.meta.dirname, 'fixtures');

async function upload(page, fixture, title) {
  await page.getByRole('link', { name: 'Documents' }).click();
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible();
  await page.getByLabel('File').setInputFiles(join(FIXTURES, fixture));
  await page.getByLabel('Title').fill(title);
  await page.getByLabel('Visibility').selectOption('internal');
  await page.getByRole('button', { name: 'Upload' }).click();
  const row = page.getByRole('row', { name: new RegExp(title) });
  await expect(row.getByText('Ready for review')).toBeVisible({ timeout: 30000 });
}

test('HR uploads, reviews, resolves a conflict and sees an empty gap list', async ({ page }) => {
  await signIn(page, BRAIN_USER);

  // Fake AI slots show the Demo AI notice.
  await expect(page.getByText('Demo AI: answers are simulated')).toBeVisible();

  await upload(page, 'leave.md', 'Leave policy');

  await page.getByRole('link', { name: /^Review/ }).click();
  const item = page.getByRole('article').filter({ hasText: 'Annual leave days' });
  await expect(item.getByText('Full-time employees receive 12 days of paid annual leave per calendar year.')).toBeVisible();
  await expect(item.getByText('Leave policy').first()).toBeVisible();
  await item.getByLabel('Layer').selectOption('confidential');
  await item.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(0);
  await expect(page.getByText('Nothing to review')).toBeVisible();

  await upload(page, 'leave-conflict.md', 'Leave update');

  await page.getByRole('link', { name: /^Conflicts/ }).click();
  const sideA = page.getByTestId('conflict-A');
  const sideB = page.getByTestId('conflict-B');
  await expect(sideA).toContainText('12');
  await expect(sideB).toContainText('15');
  await expect(sideA).toContainText('Full-time employees');
  await page.getByRole('button', { name: 'Keep B' }).click();
  await expect(page.getByTestId('conflict-A')).toHaveCount(0);
  await expect(page.getByText('No open conflicts')).toBeVisible();

  await page.getByRole('link', { name: 'Knowledge gaps' }).click();
  await expect(page.getByRole('heading', { name: 'Documents to write' })).toBeVisible();
  await expect(page.getByText('No unanswered questions')).toBeVisible();
});
