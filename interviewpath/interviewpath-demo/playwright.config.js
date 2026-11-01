import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { defineConfig } from '@playwright/test';

// One directory per run, shared by the backend script and the spec through E2E_TMP.
process.env.E2E_TMP ||= mkdtempSync(join(tmpdir(), 'portal-e2e-'));
// Ports can be overridden so parallel runs do not collide.
process.env.E2E_API_PORT ||= '8099';
process.env.E2E_WEB_PORT ||= '5199';
const apiUrl = `http://localhost:${process.env.E2E_API_PORT}`;
const webUrl = `http://localhost:${process.env.E2E_WEB_PORT}`;

export default defineConfig({
  testDir: './e2e',
  // One backend on SQLite: parallel writers cause 'database is locked' flakes.
  workers: 1,
  use: { baseURL: webUrl },
  webServer: [
    {
      command: 'bash e2e/start-backend.sh',
      url: `${apiUrl}/docs`,
      reuseExistingServer: false,
      timeout: 60000,
      env: { E2E_TMP: process.env.E2E_TMP, E2E_API_PORT: process.env.E2E_API_PORT, E2E_WEB_PORT: process.env.E2E_WEB_PORT, E2E_SEED_SAMPLES: '1', E2E_SEED_BOARD: '1' },
    },
    {
      command: `VITE_API_URL=${apiUrl} npx vite --port ${process.env.E2E_WEB_PORT} --strictPort`,
      url: webUrl,
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
