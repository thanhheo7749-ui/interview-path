import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { BOARD_USER, CORS, signIn } from './helpers.js';

// These two cases (a candidate who never took the interview, and a deleted candidate) come from backend
// timing and retention, so those responses are shaped here and everything else stays real.
let seed;
test.beforeAll(() => {
  seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'board_seed.json'), 'utf8'));
});

const NOT_TAKEN = {
  id: 90001, alias: '#N1', stage: 'ready_for_hr', cv_status: 'meets', interview_band: null, hr_decision: 'pending',
  fast_tracked: false, analysis_status: 'not_taken', interview_note: 'did not take the interview',
  hidden_text_detected: false, created_at: null,
};

test('a candidate who did not take the interview sits in Not enough evidence with a note', async ({ page }) => {
  await signIn(page, BOARD_USER);
  await page.route('**/api/companies/*/jobs/*/board', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.cells.not_enough_evidence.push(NOT_TAKEN);
    await route.fulfill({ response, json: body, headers: { ...response.headers(), ...CORS } });
  });
  await page.route('**/api/companies/*/applications/90001', (route) =>
    route.fulfill({
      headers: CORS,
      json: {
        ...NOT_TAKEN, anonymized: false, job: { id: seed.job_id, title: 'Job' }, cell: 'not_enough_evidence',
        cv_status_reason: null, cv_status_corrected: false, cv_status_correction_reason: null, hr_decided_at: null,
        cv_text_blind: null, requirements: [], claims: [], culture_notes: [], transcript: [], suggestion: null,
      },
    }));
  await page.goto(`/jobs/${seed.job_id}/board`);
  const cell = page.getByTestId('cell-not_enough_evidence');
  await expect(cell.getByTestId('card-#N1').getByTestId('interview-note')).toHaveText('Did not take the interview');
  await cell.getByTestId('card-#N1').getByRole('button', { name: /#N1/ }).click();
  await expect(page.getByTestId('detail-panel').getByTestId('interview-note')).toHaveText('Did not take the interview');
});

test('an anonymized candidate shows a plain notice and no actions', async ({ page }) => {
  await signIn(page, BOARD_USER);
  await page.route('**/api/companies/*/applications/*', async (route) => {
    if (!/applications\/\d+$/.test(route.request().url()) || route.request().method() !== 'GET') return route.fallback();
    const response = await route.fetch();
    const body = await response.json();
    return route.fulfill({
      headers: CORS,
      json: { ...body, anonymized: true, transcript: [], requirements: [], claims: [], culture_notes: [], suggestion: null, cv_status: null },
    });
  });
  await page.goto(`/jobs/${seed.job_id}/board`);
  await page.getByTestId('cell-priority').getByRole('button', { name: /#P1/ }).click();
  const panel = page.getByTestId('detail-panel');
  await expect(panel.getByTestId('anonymized-notice')).toBeVisible();
  await expect(panel.getByTestId('decision-bar')).toHaveCount(0);
  await expect(panel.getByRole('alert')).toHaveCount(0);
});
