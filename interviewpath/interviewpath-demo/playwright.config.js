import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { defineConfig } from '@playwright/test';

// One directory per run, shared by the backend script and the spec through E2E_TMP.
process.env.E2E_TMP ||= mkdtempSync(join(tmpdir(), 'portal-e2e-'));
// Ports can be overridden so parallel runs do not collide.
process.env.E2E_API_PORT ||= '8099';
process.env.E2E_WEB_PORT ||= '5199';
// The candidate app (SpeakCV frontend), run with `next dev` so the API address needs no build.
process.env.E2E_CANDIDATE_PORT ||= '3199';
const apiUrl = `http://localhost:${process.env.E2E_API_PORT}`;
const webUrl = `http://localhost:${process.env.E2E_WEB_PORT}`;
const candidateUrl = `http://localhost:${process.env.E2E_CANDIDATE_PORT}`;

export default defineConfig({
  testDir: './e2e',
  // One backend on SQLite: parallel writers cause 'database is locked' flakes.
  workers: 1,
  // The full-loop spec has a candidate answer several questions through a real browser, one after another.
  timeout: 240000,
  use: {
    baseURL: webUrl,
    // A page that does not load fails here, not after the whole test timeout.
    navigationTimeout: 30000,
    // A fake microphone, allowed without a prompt, so the screening room can record real audio in CI.
    launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
    permissions: ['microphone'],
  },
  webServer: [
    {
      command: 'bash e2e/start-backend.sh',
      url: `${apiUrl}/docs`,
      reuseExistingServer: false,
      timeout: 60000,
      env: {
        E2E_TMP: process.env.E2E_TMP, E2E_API_PORT: process.env.E2E_API_PORT, E2E_WEB_PORT: process.env.E2E_WEB_PORT,
        E2E_CANDIDATE_PORT: process.env.E2E_CANDIDATE_PORT, E2E_SEED_SAMPLES: '1', E2E_SEED_BOARD: '1',
      },
    },
    {
      // The portal builds job links on the candidate app's address.
      command: `VITE_API_URL=${apiUrl} VITE_SPEAKCV_URL=${candidateUrl} npx vite --port ${process.env.E2E_WEB_PORT} --strictPort`,
      url: webUrl,
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: `NEXT_PUBLIC_API_URL=${apiUrl} npx next dev --port ${process.env.E2E_CANDIDATE_PORT}`,
      cwd: '../../SpeakCV/src/frontend',
      url: candidateUrl,
      reuseExistingServer: false,
      timeout: 120000,
      env: { NEXT_TELEMETRY_DISABLED: '1' },
    },
  ],
});
