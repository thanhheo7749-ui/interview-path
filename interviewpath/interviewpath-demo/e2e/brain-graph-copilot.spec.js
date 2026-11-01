import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

const API_URL = `http://localhost:${process.env.E2E_API_PORT || '8099'}`;
// Sample users are seeded by e2e/start-backend.sh with a known password and no forced password change.
const SAMPLE_PASSWORD = 'e2e-sample-password-123';
const HR = 'hr@daehan-precision.sample';
const EMPLOYEE = 'employee@daehan-precision.sample';

// Fixed marker: the database is fresh per run, and fake embeddings are hash noise, so keep the corpus deterministic.
const RUN = 'k7';
const PUBLIC_TITLE = `Public welcome note ${RUN}`;
const INTERNAL_TITLE = `Internal quokka lantern guide ${RUN}`;
const INTERNAL_LINE = `Zephyr${RUN} quokka lantern onboarding grants amber badges`;
const PUBLIC_LINE = `Zephyr${RUN} welcome note greets visitors at the harbour gate`;
const ABSURD_QUESTION = 'blorptastic frumious quandary';

async function apiLogin(request, email) {
  const response = await request.post(`${API_URL}/api/login`, { data: { email, password: SAMPLE_PASSWORD } });
  expect(response.ok()).toBe(true);
  const { access_token: token } = await response.json();
  const headers = { Authorization: `Bearer ${token}` };
  const me = await (await request.get(`${API_URL}/api/me`, { headers })).json();
  return { headers, companyId: me.memberships[0].company_id };
}

async function uploadAndAccept(request, { headers, companyId }, { title, visibility, line }) {
  const kb = `${API_URL}/api/companies/${companyId}/kb`;
  const upload = await request.post(`${kb}/documents`, {
    headers,
    multipart: {
      title,
      visibility,
      language: 'en',
      file: { name: 'note.txt', mimeType: 'text/plain', buffer: Buffer.from(`${line}\n\nThis note was written for the end-to-end test.`) },
    },
  });
  expect(upload.status()).toBe(201);
  const { document } = await upload.json();

  await expect
    .poll(async () => {
      const documents = await (await request.get(`${kb}/documents`, { headers })).json();
      return documents.find((d) => d.id === document.id)?.status;
    }, { timeout: 30000 })
    .toBe('review');

  const review = await (await request.get(`${kb}/review?document_id=${document.id}`, { headers })).json();
  expect(review.nodes.length).toBeGreaterThan(0);
  const decided = await request.post(`${kb}/review/decide`, {
    headers,
    data: { items: review.nodes.map((n) => ({ action: 'accept', node_id: n.id, visibility })) },
  });
  expect(decided.ok()).toBe(true);
  return review.nodes[0].title;
}

async function signIn(page, email) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(SAMPLE_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

const nodeCount = async (page) => {
  const text = await page.getByTestId('graph-node-count').innerText();
  return text.trim() === '' ? null : Number(text);
};

async function settledNodeCount(page) {
  await expect.poll(() => nodeCount(page)).not.toBeNull();
  return nodeCount(page);
}

let publicNodeTitle;
let internalNodeTitle;

test.beforeAll(async ({ request }) => {
  const hr = await apiLogin(request, HR);
  publicNodeTitle = await uploadAndAccept(request, hr, { title: PUBLIC_TITLE, visibility: 'public', line: PUBLIC_LINE });
  internalNodeTitle = await uploadAndAccept(request, hr, { title: INTERNAL_TITLE, visibility: 'internal', line: INTERNAL_LINE });
});

test('the graph shows real nodes, and View as narrows and restores them', async ({ page }) => {
  await signIn(page, HR);
  await page.getByRole('link', { name: 'Knowledge graph' }).click();
  await expect(page).toHaveURL(/\/graph$/);
  await expect(page.getByRole('heading', { name: 'Knowledge graph' })).toBeVisible();
  await expect(page.getByText(/only simulates what each audience can read/)).toBeVisible();

  const list = page.getByTestId('graph-node-list');
  await expect(list.getByRole('button', { name: new RegExp(internalNodeTitle) })).toBeVisible();
  await expect(list.getByRole('button', { name: new RegExp(publicNodeTitle) })).toBeVisible();
  const hrCount = await settledNodeCount(page);
  expect(hrCount).toBeGreaterThan(0);
  await expect(list.getByRole('button')).toHaveCount(hrCount);

  // Selecting a node shows its type and layer in the side panel.
  await list.getByRole('button', { name: new RegExp(internalNodeTitle) }).click();
  const detail = page.getByTestId('graph-detail');
  await expect(detail).toContainText(internalNodeTitle);
  await expect(detail).toContainText('Internal');

  await page.getByRole('button', { name: 'Candidate' }).click();
  await expect(page.getByRole('button', { name: 'Candidate' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => nodeCount(page)).toBeLessThan(hrCount);
  await expect(list.getByRole('button', { name: new RegExp(internalNodeTitle) })).toHaveCount(0);
  await expect(list.getByRole('button', { name: new RegExp(publicNodeTitle) })).toBeVisible();

  await page.getByRole('button', { name: 'HR (all)' }).click();
  await expect.poll(() => nodeCount(page)).toBe(hrCount);
  await expect(list.getByRole('button', { name: new RegExp(internalNodeTitle) })).toBeVisible();
});

test('the manager view offers a department and asks the server for it', async ({ page }) => {
  await signIn(page, HR);
  await page.goto('/graph');
  await page.getByRole('button', { name: 'Manager' }).click();
  const select = page.getByLabel('Manager department');
  await expect(select).toBeVisible();
  const request = page.waitForRequest((r) => r.url().includes('/kb/graph') && r.url().includes('view_as=manager') && r.url().includes('department_id='));
  await select.selectOption({ index: 1 });
  await request;
  await settledNodeCount(page);
});

test('Copilot answers from the internal document with a citation, and records what it cannot answer', async ({ page, request }) => {
  await signIn(page, HR);
  await page.getByRole('link', { name: 'Copilot' }).click();
  await expect(page.getByRole('heading', { name: 'Copilot' })).toBeVisible();
  await expect(page.getByTestId('demo-ai-notice')).toBeVisible();

  await page.getByLabel('Your question').fill(INTERNAL_LINE);
  await page.getByRole('button', { name: 'Ask' }).click();
  const answered = page.getByTestId('copilot-answer').first();
  await expect(answered).toHaveAttribute('data-state', 'answered');
  await expect(answered.getByTestId('copilot-citation').filter({ hasText: INTERNAL_TITLE })).toBeVisible();

  await page.getByLabel('Your question').fill(ABSURD_QUESTION);
  await page.getByRole('button', { name: 'Ask' }).click();
  const missing = page.getByTestId('copilot-answer').nth(1);
  await expect(missing).toHaveAttribute('data-state', 'not_found');
  await expect(missing).toContainText('We could not find this in the company');
  await expect(missing.getByTestId('copilot-citation')).toHaveCount(0);

  // The unanswered question reaches the HR gap list.
  const hr = await apiLogin(request, HR);
  const gaps = await (await request.get(`${API_URL}/api/companies/${hr.companyId}/kb/gaps`, { headers: hr.headers })).json();
  expect(gaps.map((g) => g.sample_question)).toContain(ABSURD_QUESTION);
});

test('the question box stops at 1,000 characters', async ({ page }) => {
  await signIn(page, HR);
  await page.goto('/copilot');
  await page.getByLabel('Your question').fill('a'.repeat(1200));
  await expect(page.getByLabel('Your question')).toHaveValue('a'.repeat(1000));
});

test('Copilot shows an honest message when the server cannot search yet', async ({ page }) => {
  await signIn(page, HR);
  await page.goto('/copilot');
  await page.route('**/copilot/ask', (route) =>
    route.fulfill({ status: 503, headers: { 'access-control-allow-origin': '*' }, json: { detail: 'not ready' } }),
  );
  await page.getByLabel('Your question').fill('Anything at all?');
  await page.getByRole('button', { name: 'Ask' }).click();
  await expect(page.getByRole('alert')).toContainText('not searchable yet');
  await expect(page.getByTestId('copilot-answer')).toHaveCount(0);
});

test('a conflict answer shows the notice and its sources, marking unshared documents', async ({ page }) => {
  await signIn(page, HR);
  await page.goto('/copilot');
  await page.route('**/copilot/ask', (route) =>
    route.fulfill({
      headers: { 'access-control-allow-origin': '*' },
      json: {
        state: 'conflict',
        answer: 'Two company sources differ on this. HR is confirming which applies.',
        question_id: 1,
        citations: [
          { title: 'Leave policy', page: 3, effective_date: '2026-01-15', shared: true },
          { title: 'Company document (not shared)', page: null, effective_date: null, shared: false },
        ],
      },
    }),
  );
  await page.getByLabel('Your question').fill('How many days of leave?');
  await page.getByRole('button', { name: 'Ask' }).click();
  const answer = page.getByTestId('copilot-answer');
  await expect(answer).toHaveAttribute('data-state', 'conflict');
  await expect(answer.getByRole('note')).toContainText('Nothing is asserted until HR confirms');
  const citations = answer.getByTestId('copilot-citation');
  await expect(citations).toHaveCount(2);
  await expect(citations.first()).toContainText('Leave policy');
  await expect(citations.first()).toContainText('page 3');
  await expect(citations.last()).toContainText('Company document (not shared)');
});

test('an employee gets Copilot but no graph', async ({ page }) => {
  await signIn(page, EMPLOYEE);
  await expect(page.getByRole('link', { name: 'Knowledge graph' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Copilot' })).toBeVisible();
  await page.goto('/graph');
  await expect(page).toHaveURL(/\/copilot$/);

  await page.getByRole('link', { name: 'Copilot' }).click();
  await page.getByLabel('Your question').fill(INTERNAL_LINE);
  await page.getByRole('button', { name: 'Ask' }).click();
  await expect(page.getByTestId('copilot-answer').first()).toHaveAttribute('data-state', 'answered');
});

test('the graph and Copilot pages are available in Vietnamese', async ({ page }) => {
  await signIn(page, HR);
  await page.getByRole('button', { name: 'Tiếng Việt' }).click();
  await page.getByRole('link', { name: 'Đồ thị tri thức' }).click();
  await expect(page.getByRole('heading', { name: 'Đồ thị tri thức' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ứng viên' })).toBeVisible();
  await page.getByRole('link', { name: 'Copilot' }).click();
  await expect(page.getByLabel('Câu hỏi của bạn')).toBeVisible();
});

test('no file under src imports the removed mock graph', () => {
  const offenders = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/mockGraph/.test(readFileSync(path, 'utf8'))) offenders.push(path);
    }
  };
  walk('src');
  expect(offenders).toEqual([]);
});
