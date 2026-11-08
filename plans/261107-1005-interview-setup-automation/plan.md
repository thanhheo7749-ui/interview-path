---
title: "/interview Setup automation: remember settings + prefill from last practice and real job"
description: "Prefill the practice Setup step from localStorage, the last practice row, and the candidate's own application."
status: done
priority: P2
effort: 12h
branch: main
tags: [frontend, backend, speakcv, interview, prefill, alembic]
created: 2026-11-07
---

# /interview Setup automation

Scope: `SpeakCV/src/backend` + `SpeakCV/src/frontend`. Research: `plans/reports/researcher-speakcv-automation-surface.md`, `plans/reports/researcher-interviewpath-job-data.md`.
Prior art (shipped, not re-planned): Position auto-fills once from `master_cv_structured.personal_info.title` (`app/interview/page.tsx:134-143`).

## Corrections to the brief (verified in code 2026-11-07)
- The "practice first" link is in **SpeakCV**: `SpeakCV/src/frontend/app/applications/[id]/fit/page.tsx:154-159`. It is NOT in `interviewpath-demo`, and the IP portal has no link to `/interview`. No IP-side code changes.
- `ApplicationOut` (`backend/app/routers/applications.py:48-71`) has **no job slug**. Feature 4 needs one additive backend field (OQ 7).
- The interview format is Free/**Timed** (`config.interviewType`). The UI cannot set "stress".
- Ownership is enforced: `GET /api/applications/{id}` uses `_owned` (`applications.py:156-167`). A row that belongs to another user gives 404. Phase 1 adds a regression test.

## Default deploy = all of this is inert
`/interview` calls `notFound()` unless `NEXT_PUBLIC_LEGACY_B2C_ENABLED=true` (default `false`). The fit-page link is gated by the same flag. This plan does NOT change that default. Features 2-4 show nothing until that flag is on (and `PRACTICE_STEP_FLOW`, if OQ 2 = a).

## One prefill hook, one precedence rule
New `hooks/usePracticePrefill.ts` owns all prefill. `page.tsx` calls it once. Per field, fill only if the field is still empty and the user has not edited it (ref-guarded, same as the CV-title fill). Sources, from highest to lowest priority (OQ 3):
`?applicationId` job context > last practice row (server) > localStorage (voice/mode/format only) > CV title > defaults.

## Phases
| # | Phase | Effort | Status |
|---|---|---|---|
| 1 | [Backend: migration 0011, history fields, job_slug](phase-01-backend-history-fields-and-job-slug.md) | 3h | done |
| 2 | [Remember settings in localStorage](phase-02-local-settings-memory.md) | 2h | done |
| 3 | [Prefill from last practice (server)](phase-03-last-practice-prefill.md) | 2h | done |
| 4 | [Prefill from the candidate's application + fit link](phase-04-application-context-prefill.md) | 3h | done |
| 5 | [Verification](phase-05-verification.md) | 2h | done (build+lint+pytest only; manual E2E skipped — no local dev stack/API keys) |

Dependencies: phases 1 and 2 can run in parallel (no shared files). Then 3 (needs 1 and 2), then 4 (needs 1 and 3), then 5. Phases 2-4 all edit `usePracticePrefill.ts` and `page.tsx`, so they run in order.

## Decisions (user answered 2026-11-07)
1. **Server-side store**: (a) 4 nullable columns on `interview_history` — DECIDED.
2. **Flag gate**: (b) prefill runs in BOTH layouts (legacy and step-flow), not gated behind `PRACTICE_STEP_FLOW` — DECIDED. Note: legacy's embedded `SetupForm` only renders at all when `config.interviewType === "timed"`; for legacy Free-mode the prefilled `config` values still flow silently into the first chat message/report (no Setup screen to show a notice on) — the OQ4 notice only renders wherever a Setup screen is actually visible (legacy timed Setup panel, or the new `SetupStep`).
4. **Last-practice notice**: (a) show "Filled from your last practice (Company Y) · Clear" — DECIDED.
7. **JD source for application**: (a) add `job_slug` to `ApplicationOut`, call existing public `GET /api/public/jobs/{slug}` — DECIDED.

## Remaining Open Questions — proceeding with [recommended] unless told otherwise
3. **Precedence**: `?applicationId` job context > last practice (server) > localStorage (voice/mode/format only) > CV title > defaults. With `?applicationId`, position/company/JD come only from the application.
5. **localStorage remembers**: voice, rubric mode, interviewType, questionLimit, timeLimit.
6. **localStorage written**: on Start (reflects what was actually used), not on every keystroke.
8. **JD text**: description + public requirements as a bullet list.
9. **Application fetch fails** (404/not-owned/unpublished): silent, console warning only, form stays as-is.
10. **Logged-out visitor with `?applicationId`**: ignore the param (endpoint needs auth).
11. **PATCH config**: do not extend with company/voice/mode (YAGNI, end-interview already writes them).
12. **Tests**: keep precedence logic a small pure function; build+lint+manual checklist, no new test runner.

## Out of scope
Changing `LEGACY_B2C` default; IP portal code; new link/token mechanism (`JobChannelLink` `?src=` tokens are channel attribution, not candidate identity, and the candidate is already logged in); cleanup of the duplicate `ReportRequest` in `models.py` (both copies get edited); i18n.
