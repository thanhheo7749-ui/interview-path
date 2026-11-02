import { expect, test } from '@playwright/test';

// A stylesheet from another site holds the page's load event, so one slow third party looks like a hung sign-in page.
test('the login page makes no request to another site and uses the bundled font', async ({ page }) => {
  const own = new Set([`http://localhost:${process.env.E2E_WEB_PORT}`, `http://localhost:${process.env.E2E_API_PORT}`]);
  const foreign = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.protocol === 'data:' || url.protocol === 'blob:') return;
    if (!own.has(url.origin)) foreign.push(request.url());
  });

  await page.goto('/login');
  await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const loaded = await page.evaluate(() => [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family));
  expect(loaded.some((family) => family.includes('Plus Jakarta Sans'))).toBe(true);
  expect(foreign).toEqual([]);
});
