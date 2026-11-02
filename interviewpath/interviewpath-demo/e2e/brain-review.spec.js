import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { BRAIN_USER, CORS, SWITCH_USER, signIn } from './helpers.js';

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
  await expect(page.getByTestId('demo-ai-notice')).toContainText('Demo AI');

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
  // The real route returns each side's sources.
  await expect(sideA).toContainText('Full-time employees receive 12 days of paid annual leave per calendar year.');
  await expect(sideA).toContainText('Leave policy');
  await expect(sideB).toContainText('Leave update');
  await page.getByRole('button', { name: 'Keep B' }).click();
  await expect(page.getByTestId('conflict-A')).toHaveCount(0);
  await expect(page.getByText('No open conflicts')).toBeVisible();

  await page.getByRole('link', { name: 'Knowledge gaps' }).click();
  await expect(page.getByRole('heading', { name: 'Documents to write' })).toBeVisible();
  await expect(page.getByText('No unanswered questions')).toBeVisible();
});

// Stubbed lists: failed jobs, failed sections and a withdrawn document cannot be made with the fixture.
const jsonOf = (body, status = 200) => ({ status, headers: CORS, json: body });
const job = (id, document_id, extra = {}) => ({
  id, document_id, status: 'done', progress: 100, error: null, dropped_items: 0, failed_chunks: 0, failed_chunk_ids: [],
  contradiction_check_failed: false, ...extra,
});
const doc = (id, title, status, jobExtra) => ({
  id, title, language: 'en', source_type: 'txt', visibility: 'internal', department_id: null, effective_date: null,
  created_at: '2026-01-01T00:00:00', status, job: job(id * 10, id, jobExtra),
});

async function stubDocuments(page, documents) {
  await page.route('**/kb/documents', (route) => (route.request().method() === 'GET' ? route.fulfill(jsonOf(documents)) : route.continue()));
}

async function uploadText(page, title, text) {
  await page.getByLabel('File').setInputFiles({ name: `${title}.txt`, mimeType: 'text/plain', buffer: Buffer.from(text) });
  await page.getByLabel('Title').fill(title);
  await page.getByRole('button', { name: 'Upload' }).click();
}

test('the retry button sends one request on a double-click, and a 409 reads as a message', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await stubDocuments(page, [
    doc(901, 'Stub failed once', 'failed', { status: 'failed', error: 'Reading failed', progress: 30 }),
    doc(902, 'Stub withdrawn failed', 'withdrawn', { status: 'failed', error: 'Old failure' }),
    doc(903, 'Stub stale', 'failed', { status: 'failed', error: 'Reading failed' }),
  ]);
  let retries = 0;
  await page.route('**/kb/jobs/9010/retry', async (route) => {
    retries += 1;
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.fulfill(jsonOf(job(9011, 901, { status: 'queued', progress: 0 })));
  });
  await page.route('**/kb/jobs/9030/retry', (route) => route.fulfill(jsonOf({ detail: 'Only the latest job can be retried' }, 409)));
  await page.getByRole('link', { name: 'Documents' }).click();

  const failedRow = page.getByRole('row', { name: /Stub failed once/ });
  await failedRow.getByRole('button', { name: 'Retry', exact: true }).dblclick();
  await expect(failedRow.getByText('Queued')).toBeVisible();
  expect(retries).toBe(1);

  // A withdrawn document cannot be retried.
  const withdrawnRow = page.getByRole('row', { name: /Stub withdrawn failed/ });
  await expect(withdrawnRow.getByText('Withdrawn', { exact: true })).toBeVisible();
  await expect(withdrawnRow.getByRole('button')).toHaveCount(0);

  await page.getByRole('row', { name: /Stub stale/ }).getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('has changed since the page loaded');
  await expect(page.getByRole('alert')).toContainText('Only the latest job can be retried');
});

test('Retry failed sections shows for failed sections or a failed contradiction check, and sends one request', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await stubDocuments(page, [
    doc(911, 'Stub sections', 'review', { status: 'review', failed_chunks: 1, failed_chunk_ids: [4] }),
    doc(912, 'Stub check', 'review', { status: 'review', failed_chunks: 1, contradiction_check_failed: true }),
    doc(913, 'Stub clean', 'review', { status: 'review' }),
  ]);
  let calls = 0;
  await page.route('**/kb/jobs/9110/retry-failed', async (route) => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.fulfill(jsonOf(job(9110, 911, { status: 'queued', progress: 0 })));
  });
  await page.getByRole('link', { name: 'Documents' }).click();
  await expect(page.getByRole('row', { name: /Stub check/ }).getByRole('button', { name: 'Retry failed sections' })).toBeVisible();
  await expect(page.getByRole('row', { name: /Stub clean/ }).getByRole('button')).toHaveCount(0);
  const row = page.getByRole('row', { name: /Stub sections/ });
  await row.getByRole('button', { name: 'Retry failed sections' }).dblclick();
  await expect(row.getByText('Queued')).toBeVisible();
  expect(calls).toBe(1);
});

test('Publish anyway states what was dropped, asks first, and publishes once', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  const held = (id, title, hold, extra = {}) => ({
    ...doc(id, title, 'review', { status: 'review', dropped_items: hold.dropped_items, failed_chunks: hold.failed_chunks, ...extra }),
    publish_hold: hold,
  });
  await stubDocuments(page, [
    held(921, 'Stub dropped', { dropped_items: 3, failed_chunks: 0, contradiction_check_failed: false, pending_drafts: false }),
    held(922, 'Stub with drafts', { dropped_items: 1, failed_chunks: 0, contradiction_check_failed: false, pending_drafts: true }),
    doc(923, 'Stub complete', 'review', { status: 'review' }),
  ]);
  const decisions = [];
  await page.route('**/kb/review/decide', async (route) => {
    decisions.push(route.request().postDataJSON());
    await route.fulfill(jsonOf({ ok: true, applied: 1, warnings: [] }));
  });
  await page.getByRole('link', { name: 'Documents' }).click();

  const row = page.getByRole('row', { name: /Stub dropped/ });
  await expect(row.getByText('3 items were dropped')).toBeVisible();
  await expect(page.getByRole('row', { name: /Stub with drafts/ }).getByRole('button', { name: 'Publish anyway' })).toHaveCount(0);
  await expect(page.getByRole('row', { name: /Stub complete/ }).getByRole('button')).toHaveCount(0);

  await row.getByRole('button', { name: 'Publish anyway' }).click();
  await expect(row.getByRole('alertdialog')).toContainText('3 items');
  expect(decisions).toEqual([]);
  await row.getByRole('button', { name: 'Cancel' }).click();
  await expect(row.getByRole('alertdialog')).toHaveCount(0);

  await row.getByRole('button', { name: 'Publish anyway' }).click();
  await row.getByRole('button', { name: 'Publish document' }).dblclick();
  await expect(row.getByText('Published', { exact: true })).toBeVisible();
  expect(decisions).toEqual([{ items: [{ action: 'publish_document', document_id: 921 }] }]);
  await expect(row.getByRole('button', { name: 'Publish anyway' })).toHaveCount(0);
});

test('Retry shows only on a failed document, not on a failed section retry', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await stubDocuments(page, [
    doc(931, 'Stub whole failure', 'failed', { status: 'failed', error: 'Reading failed' }),
    doc(932, 'Stub section retry failed', 'published', { status: 'failed', error: 'Retry failed', failed_chunks: 1, failed_chunk_ids: [4] }),
  ]);
  await page.getByRole('link', { name: 'Documents' }).click();
  await expect(page.getByRole('row', { name: /Stub whole failure/ }).getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
  const row = page.getByRole('row', { name: /Stub section retry failed/ });
  await expect(row.getByRole('button', { name: 'Retry failed sections' })).toBeVisible();
  await expect(row.getByRole('button', { name: 'Retry', exact: true })).toHaveCount(0);
  await expect(row.getByText('Retry failed', { exact: true })).toBeVisible();
});

test('a node back from a withdrawn document says why, and a cleared body is warned about', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  const node = (id, title, reason) => ({
    id, type: 'policy', title, body: 'Body', visibility: 'internal', language: 'en', fact_kind: null, fact_value: null, fact_unit: null,
    scope_text: null, department_id: null, guard_category: null, guard_reason: null, review_reason: reason, sources: [],
  });
  await page.route('**/kb/review', (route) => route.fulfill(jsonOf({
    nodes: [node(941, 'Came back', 'document_withdrawn'), node(942, 'Ordinary draft', null)], edges: [], merge_proposals: [],
  })));
  await page.route('**/kb/review/decide', (route) => route.fulfill(jsonOf({
    ok: true, applied: 1, warnings: ['The body of "Came back" was cleared because it stated the old value.'],
  })));
  await page.getByRole('link', { name: /^Review/ }).click();
  const back = page.getByRole('article').filter({ hasText: 'document it also came from was withdrawn' });
  await expect(back).toHaveCount(1);
  await expect(back.getByLabel('Title')).toHaveValue('Came back');
  await back.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.getByText('was cleared because it stated the old value')).toBeVisible();
});

test('the upload form sends a language only when one is chosen', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await page.getByRole('link', { name: 'Documents' }).click();
  const bodies = [];
  await page.route('**/kb/documents', (route) => {
    if (route.request().method() === 'POST') bodies.push(route.request().postData() ?? '');
    return route.continue();
  });
  await expect(page.getByLabel('Language').locator('option')).toHaveText(['Auto', 'Vietnamese', 'English', 'Korean']);
  await uploadText(page, 'Lang auto doc', 'Language test auto body text');
  await expect(page.getByRole('row', { name: /Lang auto doc/ })).toBeVisible();
  await page.getByLabel('Language').selectOption('ko');
  await uploadText(page, 'Lang korean doc', 'Language test korean body text');
  await expect(page.getByRole('row', { name: /Lang korean doc/ })).toBeVisible();
  expect(bodies[0]).not.toContain('name="language"');
  expect(bodies[1]).toMatch(/name="language"\r\n\r\nko\r\n/);
});

test('HR edits a fact before accepting, and sees the warnings the server returns', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await page.getByRole('link', { name: 'Documents' }).click();
  await uploadText(page, 'Probation policy', 'Probation period lasts 60 days for new engineers.\n');
  await expect(page.getByRole('row', { name: /Probation policy/ }).getByText('Ready for review')).toBeVisible({ timeout: 30000 });

  await page.getByRole('link', { name: /^Review/ }).click();
  const item = page.getByRole('article').filter({ hasText: 'Probation period lasts 60 days' });
  await expect(item.getByLabel('Fact value')).toHaveValue('60');
  await expect(item.getByLabel('Fact unit')).toHaveValue('days');
  await expect(item.getByLabel('Applies to')).toHaveValue('New engineers');
  await item.getByLabel('Fact unit').fill('working days');
  await item.getByLabel('Applies to').fill('Engineers hired in Q2');

  // The first answer is stubbed to carry a warning, so nothing is accepted yet.
  const payloads = [];
  await page.route('**/kb/review/decide', (route) => {
    payloads.push(route.request().postDataJSON().items[0]);
    if (payloads.length > 1) return route.continue();
    return route.fulfill(jsonOf({ ok: true, applied: 1, warnings: ['The edit to node 7 was saved, but its contradiction check did not finish.'] }));
  });
  await item.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.getByText('contradiction check did not finish')).toBeVisible();
  expect(payloads[0]).toMatchObject({ action: 'accept', fact_value: '60', fact_unit: 'working days', scope_text: 'Engineers hired in Q2' });

  const again = page.getByRole('article').filter({ hasText: 'Probation period lasts 60 days' });
  // The queue reloads after a decision, which drops unsaved edits.
  await expect(again.getByLabel('Fact unit')).toHaveValue('days');
  await again.getByLabel('Fact unit').fill('working days');
  await again.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(again).toHaveCount(0, { timeout: 30000 });
  expect(payloads[1]).toMatchObject({ fact_unit: 'working days' });
});

test('HR withdraws a published document after a confirmation', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await page.getByRole('link', { name: 'Documents' }).click();
  await uploadText(page, 'Cafeteria note', 'Zephyrw9 lanterns glow at dusk in the cafeteria\n');
  const row = page.getByRole('row', { name: /Cafeteria note/ });
  await expect(row.getByText('Ready for review')).toBeVisible({ timeout: 30000 });
  await expect(row.getByRole('button', { name: 'Withdraw' })).toHaveCount(0);

  await page.getByRole('link', { name: /^Review/ }).click();
  await page.getByRole('article').filter({ hasText: 'Zephyrw9' }).getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.getByRole('article').filter({ hasText: 'Zephyrw9' })).toHaveCount(0);

  await page.getByRole('link', { name: 'Documents' }).click();
  await expect(row.getByText('Published')).toBeVisible();
  await row.getByRole('button', { name: 'Withdraw' }).click();
  const dialog = row.getByRole('alertdialog');
  await expect(dialog).toContainText('stops being used');
  await expect(dialog).toContainText('no other source document are removed');
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(row.getByText('Published')).toBeVisible();

  await row.getByRole('button', { name: 'Withdraw' }).click();
  await row.getByRole('button', { name: 'Withdraw document' }).click();
  await expect(row.getByText('Withdrawn', { exact: true })).toBeVisible();
  await expect(row.getByRole('button')).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('Document withdrawn');
});

test('the conflict screen shows each side with document, page and effective date', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  const side = (id, value, sources) => ({
    id, title: 'Leave days', status: 'published', fact_kind: 'number', fact_value: value, fact_unit: 'days', scope_text: 'Everyone', visibility: 'internal', sources,
  });
  const handbook = { quote: 'Everyone receives 12 days of leave.', page: 3, document_title: 'Handbook 2025', effective_date: '2025-01-15' };
  await page.route('**/kb/conflicts', (route) =>
    route.fulfill(jsonOf([{
      id: 77, status: 'open', resolution: null, created_at: '2026-01-01T00:00:00',
      node_a: side(1, '12', [handbook, handbook]),
      node_b: side(2, '15', [{ quote: 'Everyone receives 15 days of leave.', page: null, document_title: 'Memo', effective_date: null }]),
    }])),
  );
  await page.getByRole('link', { name: /^Conflicts/ }).click();
  const a = page.getByTestId('conflict-A');
  await expect(a).toContainText('Everyone receives 12 days of leave.');
  await expect(a).toContainText('Handbook 2025, page 3, effective 2025-01-15');
  // An overlap makes the same quote arrive twice; it shows once.
  await expect(a.locator('blockquote')).toHaveCount(1);
  const b = page.getByTestId('conflict-B');
  await expect(b).toContainText('Memo');
  await expect(b).not.toContainText('page');
  await expect(b).not.toContainText('effective');
});

test('the Vietnamese upload form has the language field', async ({ page }) => {
  await signIn(page, BRAIN_USER);
  await page.getByRole('button', { name: 'Tiếng Việt' }).click();
  await page.getByRole('link', { name: 'Tài liệu' }).click();
  await expect(page.getByLabel('Ngôn ngữ').locator('option')).toHaveText(['Tự động', 'Tiếng Việt', 'Tiếng Anh', 'Tiếng Hàn']);
});

test('switching company drops the previous company data, even when the new request fails', async ({ page }) => {
  await signIn(page, SWITCH_USER);
  await page.getByRole('link', { name: 'Documents' }).click();
  await uploadText(page, 'Alpha only handbook', 'Alpha only content');
  await expect(page.getByRole('row', { name: /Alpha only handbook/ })).toBeVisible();

  await page.route('**/kb/documents', (route) =>
    route.request().method() === 'GET' ? route.fulfill(jsonOf({ detail: 'Beta is unavailable' }, 500)) : route.continue(),
  );
  await page.getByLabel('Company', { exact: true }).selectOption({ label: 'Switch Beta' });
  await expect(page.getByRole('alert')).toContainText('Beta is unavailable');
  await expect(page.getByText('Alpha only handbook')).toHaveCount(0);
});
