import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

const password = () => readFileSync(join(process.env.E2E_TMP, 'portal_e2e_password'), 'utf8');

async function signIn(page) {
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email').fill('hr@e2e.test');
  await page.getByLabel('Password').fill(password());
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

test('wrong password shows an error and stays on login', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('hr@e2e.test');
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test('HR manages departments and members in the real database', async ({ page }) => {
  await signIn(page);
  await expect(page.getByText('Sample data')).toBeVisible();

  await page.getByLabel('New department name').fill('Engineering');
  await page.getByRole('button', { name: 'Add department' }).click();
  await expect(page.getByRole('treeitem', { name: /Engineering/ })).toBeVisible();

  await page.getByLabel('Member email').fill('new.employee@e2e.test');
  await page.getByLabel('Member role').selectOption('employee');
  await page.getByRole('button', { name: 'Add member' }).click();
  await expect(page.getByRole('cell', { name: 'new.employee@e2e.test' })).toBeVisible();
  await expect(page.getByText(/temporary password/i)).toBeVisible();

  await page.reload();
  await expect(page.getByRole('treeitem', { name: /Engineering/ })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'new.employee@e2e.test' })).toBeVisible();
});

test('language switches to Vietnamese', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: 'Tiếng Việt' }).click();
  await expect(page.getByRole('heading', { name: 'Cài đặt công ty' })).toBeVisible();
});

test('an expired token lands on the login page', async ({ page }) => {
  await signIn(page);
  await page.evaluate(() => sessionStorage.setItem('portal_token', 'not-a-valid-token'));
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
});

test('no page mentions the removed demo features', async ({ page }) => {
  await signIn(page);
  await expect(page.getByText(/n8n/i)).toHaveCount(0);
  await expect(page.getByRole('link', { name: /RAG Knowledge Graph|Workflow/ })).toHaveCount(0);
});
