# Phase 05 — Verification

## Context Links
- Overview: [plan.md](plan.md). OQ 12 decides whether a frontend unit test is added.
- Backend tests: `SpeakCV/src/backend/tests/` (pytest; `test_migrations.py`, new `test_practice_context.py`)
- Frontend: `SpeakCV/src/frontend` (`npm run build`, `npm run lint`; no test runner)

## Overview
- Priority: P2. Status: pending. Blocked by: phases 1-4.

## Test Matrix
| Layer | What | How |
|---|---|---|
| Unit (backend) | 0011 upgrade/downgrade; model = migration | pytest `test_migrations.py` + new test |
| Integration (backend) | end-interview stores company/jd_text/voice/mode; `GET /api/history` returns them | pytest with stubbed AI |
| Integration (backend, security) | `GET /api/applications/{id}`: owner gets `job_slug`, other user gets 404 | pytest |
| Unit (frontend) | `resolvePrefill` precedence + never-overwrite | OQ 12a: manual cases below. 12b: vitest |
| Build | type + lint | `npm run build && npm run lint` |
| E2E (manual) | checklist below, `LEGACY_B2C=true`, `PRACTICE_STEP_FLOW` on | browser |

## Manual Checklist
1. Fresh user, nothing stored: Setup shows the defaults. The CV title still fills Position (prior behaviour).
2. Start with non-default voice/mode/format, then reload: the values are restored (phase 2).
3. Finish a practice, clear localStorage, log in again: position/company/JD/voice/mode are filled, the notice is shown, and Clear works (phase 3).
4. Type in Position before data loads: the typed text is kept.
5. Fit page, then "Practice first": the job title, company and JD are filled, and the next banner is present (phase 4).
6. Another user's application id in the URL: nothing is filled, the response is 404, and there is no error UI.
7. `PRACTICE_STEP_FLOW=false`: the legacy layout behaves exactly as before. Nothing is read from or written to storage (OQ 2a).
8. Default deploy flags: `/interview` gives 404, and the fit page has no practice link. Both are unchanged.
9. Guest user (if `/interview` is reachable): only the localStorage source runs, with no auth errors.

## Success Criteria
- All pytest green. Build and lint pass.
- Checklist 1-9 pass, recorded in the PR description.
- No file created or edited by this plan grows past about 200 lines, except the `page.tsx` net delta. That file is already 562 lines, so keep its change under about 15 lines.

## Rollback (whole plan)
Revert the frontend phases 4, 3, 2, then `alembic downgrade 0010_interview_window` and revert phase 1. Each phase can be reverted on its own, because missing fields are treated as empty.

## Docs
Update `docs/project-changelog.md` (if it exists in SpeakCV) with the feature note and the flag dependency.
