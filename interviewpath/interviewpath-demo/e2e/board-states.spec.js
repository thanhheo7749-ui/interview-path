import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { API_URL, BOARD_USER, NEW_PASSWORD, apiLogin, signIn } from './helpers.js';

// A technical failure and an unreadable CV each have their own lane, and neither can be rejected in bulk from there.
let seed;
test.beforeAll(() => {
  seed = JSON.parse(readFileSync(join(process.env.E2E_TMP, 'board_seed.json'), 'utf8'));
});

test('an STT outage shows as a technical problem HR can retry, and is not in a cell', async ({ page }) => {
  await signIn(page, BOARD_USER);
  await page.goto(`/jobs/${seed.states_job_id}/board`);
  const lane = page.getByTestId('lane-transcription_failed');
  await expect(lane.getByRole('heading', { name: 'Technical problem: audio available' })).toBeVisible();
  const card = lane.getByTestId('card-#T1');
  await expect(card).toBeVisible();
  await expect(card.getByRole('checkbox')).toHaveCount(0);
  await expect(page.getByTestId('cell-not_enough_evidence').getByTestId('card-#T1')).toHaveCount(0);

  await card.getByRole('button', { name: /#T1/ }).click();
  const panel = page.getByTestId('detail-panel');
  await expect(panel.getByTestId('transcription-note')).toBeVisible();
  await panel.getByRole('button', { name: 'Retry transcription' }).click();
  await expect(lane.getByTestId('card-#T1')).toHaveCount(0);
});

test('a CV that could not be processed reaches HR, who can invite the candidate anyway', async ({ page }) => {
  await signIn(page, BOARD_USER);
  await page.goto(`/jobs/${seed.states_job_id}/board`);
  const lane = page.getByTestId('lane-cv_failed');
  await expect(lane.getByRole('heading', { name: 'CV could not be processed' })).toBeVisible();
  await lane.getByRole('button', { name: /#C1/ }).click();
  const panel = page.getByTestId('detail-panel');
  await expect(panel.getByTestId('cv-failed-note')).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Approve' })).toHaveCount(0);
  await expect(panel.getByRole('button', { name: 'Reject' })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Invite to interview anyway' }).click();
  await expect(page.getByTestId('lane-not_interviewed').getByTestId('card-#C1')).toBeVisible();
  await expect(lane.getByTestId('card-#C1')).toHaveCount(0);
});

test('publishing a job with no public requirement warns HR', async ({ page, request }) => {
  await signIn(page, BOARD_USER);
  const headers = { Authorization: `Bearer ${await apiLogin(request, BOARD_USER.email, NEW_PASSWORD)}` };
  const api = `${API_URL}/api/companies/${seed.company_id}/jobs`;
  const created = await request.post(api, {
    headers,
    data: {
      title: `Confidential only ${Date.now().toString(36)}`, description: 'A sample job.', interview_languages: ['en'],
      requirements: [{ text: 'Sample secret requirement', must_have: true, visibility: 'confidential' }],
    },
  });
  expect(created.ok()).toBe(true);
  await page.goto(`/jobs/${(await created.json()).id}`);
  await page.getByRole('button', { name: 'Publish' }).click();
  await expect(page.getByText('This job has no public requirement.')).toBeVisible();
  await expect(page.getByTestId('job-status')).toContainText('Published');
});
