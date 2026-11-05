---
title: "Interview scheduling window (mang D)"
description: "Opt-in per-job time window gating when a candidate may start the AI screening interview."
status: pending
priority: P2
effort: 6.5h
branch: n/a (work context is not a git repo)
tags: [hiring, screening, jobs, alembic, frontend, backend]
created: 2026-11-05
---

# Interview scheduling window

Source of truth: `SpeakCV/docs/superpowers/specs/2026-11-05-interview-scheduling-window-design.md`

Start-time gate only. No slots, reservations, capacity, reminder emails, reschedule UI, new tables.
`scheduling_enabled=false` (default for every existing job) => byte-for-byte today's behavior.

## Phases

| # | Phase | Status | Effort | Blocked by | Owns |
|---|-------|--------|--------|------------|------|
| 01 | [Data model, migration, window helper](phase-01-data-model-migration-and-window-helper.md) | pending | 1h | - | model, alembic 0010, `app/hiring/interview_window.py`, `schemas/jobs.py` |
| 02 | [Backend API + start gate + tests](phase-02-backend-api-start-gate-and-tests.md) | pending | 2.5h | 01 | `routers/jobs_hr.py`, `routers/screening.py`, `routers/applications.py`, backend tests |
| 03 | [Candidate UI (SpeakCV frontend)](phase-03-candidate-fit-page-and-screening-room.md) | pending | 1.5h | 02 | `services/hiring.ts`, fit `page.tsx`, `ScreeningRoom.tsx`, `lib/i18n.ts` |
| 04 | [HR job editor (interviewpath-demo)](phase-04-hr-job-editor-window-fields.md) | pending | 1.5h | 02 | `JobEditorPage.jsx`, new `InterviewWindowFields.jsx`, `i18n/*.json` |

03 and 04 run in parallel (disjoint files, both consume phase-02 API contract).

## Dependency graph

```
01 -> 02 -> 03
         \-> 04
```

## API contract (frozen at end of 02)

- `JobCreate` / `JobPatch` accept: `scheduling_enabled: bool`, `interview_window_start: AwareDatetime|null`,
  `interview_window_end: AwareDatetime|null`, `interview_window_timezone: IANA str|null`.
- `JobOut` returns same 4 fields; datetimes serialized UTC with offset (`+00:00`).
- `ApplicationOut.interview_window`: `{start, end, timezone}` when job has scheduling on, else `null`.
- `POST /api/screening/{id}/start` outside window => `409 {"code":"OUTSIDE_INTERVIEW_WINDOW","message",
  "window_start","window_end","timezone"}`. Resume of running session never gated.
- Invalid window when enabled (missing bound or `start >= end`) => `422`.

## Rollback

Each phase revertible alone. 03/04: revert frontend files, backend ignores omitted fields (defaults keep feature off).
02: revert routers, columns stay unused. 01: `alembic downgrade 0009_reality_thresholds` drops 4 columns (no data loss
for pre-existing behavior; window settings lost).

## Success criteria (whole feature)

- Full backend suite green incl. `test_migrations.py::test_head_matches_models`.
- New tests: disabled regression, inside passes, before/after window 409 w/ code+bounds, 422 on bad window (create+patch).
- `npm run lint` + `npm run build` pass in both frontends.
- Disabled job: fit page and HR editor unchanged except new (off) toggle in HR editor.

## Deviations from spec (deliberate, see phase files)

1. `scheduling_enabled` is NOT NULL + server_default false (spec table says nullable); removes tri-state.
2. Fit page never calls `/start` (it links to `/screening`), so it reads the window from `ApplicationOut`,
   not the 409. The 409 is handled in `ScreeningRoom.tsx`, which does call `/start`.
3. HR editor lives in `interviewpath/interviewpath-demo` (Vite app), not SpeakCV frontend.
