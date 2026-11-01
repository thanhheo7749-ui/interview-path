import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { defineConfig } from '@playwright/test';

// One directory per run, shared by the backend script and the spec through E2E_TMP.
process.env.E2E_TMP ||= mkdtempSync(join(tmpdir(), 'portal-e2e-'));

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://localhost:5199' },
  webServer: [
    {
      command: 'bash e2e/start-backend.sh',
      url: 'http://localhost:8099/docs',
      reuseExistingServer: false,
      timeout: 60000,
      env: { E2E_TMP: process.env.E2E_TMP },
    },
    {
      command: 'VITE_API_URL=http://localhost:8099 npx vite --port 5199 --strictPort',
      url: 'http://localhost:5199',
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
