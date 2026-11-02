import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { BRAIN_USER, signIn } from './helpers.js';

// The discrimination guard in the portal. The extraction fixture holds two requirements that ask for an age, which the
// rules flag, and one whose text carries a marker that makes the fake classifier fail, so the guard cannot check it
// ("unchecked"). The Review page must let HR reject or rewrite the first kind and accept the second only after
// confirming it. Job save warnings use the same marker.
const FIXTURES = join(import.meta.dirname, 'fixtures');
const RUN = Date.now().toString(36);

async function uploadGuardDocument(page) {
  await page.getByRole('link', { name: 'Documents' }).click();
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible();
  await page.getByLabel('File').setInputFiles(join(FIXTURES, 'guard.md'));
  await page.getByLabel('Title').fill(`Guard document ${RUN}`);
  await page.getByLabel('Visibility').selectOption('internal');
  await page.getByRole('button', { name: 'Upload' }).click();
  const row = page.getByRole('row', { name: new RegExp(`Guard document ${RUN}`) });
  await expect(row.getByText('Ready for review')).toBeVisible({ timeout: 30000 });
}

test('a flagged item can only be rejected or rewritten, and an unchecked one needs a confirmation', async ({ page }) => {
  const decisions = [];
  page.on('request', (req) => {
    if (req.method() === 'POST' && req.url().endsWith('/kb/review/decide')) decisions.push(req.postDataJSON().items[0]);
  });
  await signIn(page, BRAIN_USER);
  await uploadGuardDocument(page);
  await page.getByRole('link', { name: /^Review/ }).click();
  const item = (name) => page.getByRole('article').filter({ hasText: name });

  // Nothing here can be accepted in bulk: every item of the document is held by the guard.
  await expect(item('Guardflag9')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Accept all' })).toBeDisabled();

  // Flagged: the category and the reason show, and Accept stays off while the text is unchanged.
  const flagged = item('Guardflag9');
  await expect(flagged.getByTestId('guard-flagged')).toContainText('Blocked: asks for a protected trait (age)');
  await expect(flagged.getByTestId('guard-reason')).toHaveText('The statement sets or prefers an age.');
  await expect(flagged.getByRole('button', { name: 'Accept', exact: true })).toBeDisabled();
  await expect(flagged.getByRole('button', { name: 'Reject' })).toBeEnabled();
  await flagged.getByRole('button', { name: 'Reject' }).click();
  await expect(item('Guardflag9')).toHaveCount(0);

  // Flagged and rewritten: the server checks the new text again. Still asking for an age is refused, a clean text passes.
  const rewrite = item('Guardrewrite9');
  await expect(rewrite.getByTestId('guard-flagged')).toBeVisible();
  await expect(rewrite.getByRole('button', { name: 'Accept', exact: true })).toBeDisabled();
  await rewrite.getByLabel('Body').fill('Candidates must be under 26 years old.');
  await expect(rewrite.getByRole('button', { name: 'Accept', exact: true })).toBeEnabled();
  await rewrite.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Blocked (age)');
  await expect(item('Guardrewrite9')).toBeVisible();
  await rewrite.getByLabel('Title').fill(`Guardrewrite9 candidates need three years of experience ${RUN}`);
  await rewrite.getByLabel('Body').fill('Candidates need three years of backend experience.');
  await rewrite.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.getByRole('article').filter({ hasText: 'Guardrewrite9' })).toHaveCount(0);
  expect(decisions.at(-1)).toMatchObject({ action: 'accept' });
  expect(decisions.at(-1).confirm_unchecked).toBeUndefined();

  // Unchecked: Accept asks for a confirmation first, and Cancel sends nothing.
  const unchecked = item('Guardcheck9');
  await expect(unchecked.getByTestId('guard-unchecked')).toContainText('The automatic discrimination check did not run');
  await expect(page.getByRole('button', { name: 'Accept all' })).toBeDisabled();
  const sent = decisions.length;
  await unchecked.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(unchecked.getByRole('alertdialog')).toBeVisible();
  await unchecked.getByRole('button', { name: 'Cancel' }).click();
  await expect(unchecked.getByRole('alertdialog')).toHaveCount(0);
  expect(decisions.length).toBe(sent);
  await unchecked.getByRole('button', { name: 'Accept', exact: true }).click();
  await unchecked.getByRole('button', { name: 'I reviewed it, accept' }).click();
  await expect(page.getByText('Nothing to review')).toBeVisible();
  expect(decisions.length).toBe(sent + 1);
  expect(decisions.at(-1)).toMatchObject({ action: 'accept', confirm_unchecked: true });
});

test('job save shows the warnings for requirements the check could not read', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await page.getByRole('link', { name: 'Jobs' }).click();
  await page.getByRole('link', { name: 'New job' }).click();
  await page.getByLabel('Job title').fill(`Warning job ${RUN}`);
  await page.getByRole('button', { name: 'Add requirement' }).click();
  await page.getByLabel('Requirement 1').fill(`Writes careful code UNCHECKEDCANARY-${RUN}-a`);
  await page.getByRole('button', { name: 'Add requirement' }).click();
  await page.getByLabel('Requirement 2').fill(`Reviews pull requests ${RUN}`);
  await page.getByRole('button', { name: 'Save draft' }).click();

  // Created: the page moves to the job and still shows what the save returned.
  await expect(page).toHaveURL(/\/jobs\/\d+$/);
  const warnings = page.getByText('Completed with warnings').locator('..');
  await expect(warnings).toContainText(`The discrimination check could not run for: Writes careful code UNCHECKEDCANARY-${RUN}-a`);
  await expect(warnings).not.toContainText('Reviews pull requests');
  await warnings.getByRole('button', { name: 'Dismiss' }).click();
  await expect(page.getByText('Completed with warnings')).toHaveCount(0);

  // Patched: a changed requirement is checked again and its warning shows, next to the saved notice.
  await page.getByLabel('Requirement 1').fill(`Writes tested code UNCHECKEDCANARY-${RUN}-b`);
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  await expect(page.getByText('Completed with warnings').locator('..')).toContainText(`UNCHECKEDCANARY-${RUN}-b`);

  // A save with nothing unreadable shows no warning.
  await page.getByLabel('Requirement 1').fill(`Writes tested code ${RUN}`);
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  await expect(page.getByText('Completed with warnings')).toHaveCount(0);
});
