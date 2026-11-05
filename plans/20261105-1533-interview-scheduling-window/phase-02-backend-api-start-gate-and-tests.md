# Phase 02: Backend API, start gate, tests

## Context Links
- Plan: [plan.md](plan.md), prior: [phase-01](phase-01-data-model-migration-and-window-helper.md)
- `SpeakCV/src/backend/app/routers/jobs_hr.py`: `_out` (~L43), `create_job` (~L85), `patch_job` (~L127)
- `SpeakCV/src/backend/app/routers/screening.py`: `_check_can_start` (~L109), `_claim_start` (~L130), `start` (~L151)
- `SpeakCV/src/backend/app/routers/applications.py`: `ApplicationOut` (~L48), `_out` (~L111)
- Start tests live in `SpeakCV/src/backend/tests/test_hiring_voice.py` (fixtures `world`, `start`, `started`),
  NOT `test_hiring_screening.py` (that file tests CV assessment, no start endpoint).
- Job API tests: `SpeakCV/src/backend/tests/test_hiring_jobs.py` (fixtures `api`, `world`, helpers `url`, `make_job`)

## Overview
- Priority: P2. Status: pending. Effort: 2.5h.
- Wire 4 fields through HR create/patch/out, expose window to candidate in `ApplicationOut`, add gate in
  `_check_can_start`, add tests.

## Key Insights
- Both start paths call `_check_can_start`: `start()` (pre-check, no lock) and `_claim_start()` (under row lock).
  Extending this one function covers both; no new call site.
- Resume path runs BEFORE `_check_can_start` in both callers (`_resume` returns running session). So a session
  already in progress is never interrupted by window close. Matches spec. Do not reorder.
- `start()` already does `db.get(Job, application.job_id)` after the check; `db.get` hits identity map, so loading
  Job inside `_check_can_start` costs no extra query on second call.
- Order inside `_check_can_start`: consent check, stage check, then window check. A non-invited candidate keeps
  getting today's stage error; window is only reported to someone who could otherwise start.
- Frontend `ScreeningRoom.handleStart` treats any 409 with object detail as "consent version changed" unless a
  known `code` matches first. So detail MUST carry `code` and `message` (house shape, like `CV_CONSENT_WITHDRAWN`);
  phase 03 adds the code branch.
- `HiringError` uses `detail.message` as error text: include human `message` in 409.
- `patch_job` does AI work, then `db.rollback()` and re-locks the job. Window validation must run on merged
  values AFTER the re-lock (stored values may have changed), and before any write.

## Requirements
Functional:
- `create_job`: validate via `interview_window.check(...)` before first write (before `check_requirements`, which can
  call AI, so bad input fails cheap). Assign fields with `to_utc`.
- `patch_job`: merge `body.model_fields_set` over stored job values; `check(...)` on merged; assign only fields set.
  Run a cheap pre-check before AI call too (on merged-with-unlocked-job values) so invalid input never pays for AI;
  re-check after re-lock.
- `_out` (jobs_hr): add 4 keys; datetimes via `as_aware`.
- `ApplicationOut`: `interview_window: dict | None = None` (or small `InterviewWindowOut` model); `_out` sets
  `interview_window.payload(job)`.
- `_check_can_start`: `job = db.get(Job, application.job_id)`; if not `is_open(job, now_utc)` raise
  `HTTPException(409, detail={"code": "OUTSIDE_INTERVIEW_WINDOW", "message": "...", "window_start": iso,
  "window_end": iso, "timezone": tz})`.
Non-functional:
- Disabled job: zero behavior change; existing tests pass unmodified.
- No change to `start_claimed_at` logic, `_release_start_claim`, `_plan_and_start`.

## Architecture
```
HR PATCH/POST --> jobs_hr (schema parse, AwareDatetime) --> interview_window.check (422) --> to_utc --> jobs row
Candidate GET /applications/{id} --> applications._out --> interview_window.payload(job) --> fit page (phase 03)
Candidate POST /screening/{id}/start
   -> _resume? (running session: return, no gate)
   -> _check_can_start: consent -> stage -> is_open(job, now) ? ok : 409 OUTSIDE_INTERVIEW_WINDOW
   -> _claim_start (lock) -> _resume? -> _check_can_start again (same gate, under lock) -> plan
```
Constants: `OUTSIDE_INTERVIEW_WINDOW = "OUTSIDE_INTERVIEW_WINDOW"` defined in `app/hiring/interview_window.py`
(phase 01 module) and imported by screening router.

## Related Code Files
Modify:
- `SpeakCV/src/backend/app/routers/jobs_hr.py`
- `SpeakCV/src/backend/app/routers/screening.py`
- `SpeakCV/src/backend/app/routers/applications.py`
- `SpeakCV/src/backend/tests/test_hiring_voice.py` (append start-gate tests, reuse `world`/`start`)
- `SpeakCV/src/backend/tests/test_hiring_jobs.py` (append HR validation tests, reuse `make_job`/`url`)
- `SpeakCV/src/backend/app/hiring/interview_window.py` (add constant only, if not done in 01)
Create:
- `SpeakCV/src/backend/tests/test_hiring_interview_window.py` (pure unit tests of helper; no fixtures needed)
Delete: none.

## Implementation Steps
1. `screening.py`: import `interview_window`. In `_check_can_start`, after stage check:
   `job = db.get(Job, application.job_id)`; `if not interview_window.is_open(job, datetime.now(timezone.utc)):`
   raise 409 with detail per Requirements (`**interview_window.payload(job)` mapped to `window_start`/`window_end`/
   `timezone`, values `.isoformat()`). Message: "The interview window for this job is not open now."
   Update function to keep docstring style (one-line docstring if adding one).
2. `jobs_hr.py` `_out`: add `"scheduling_enabled": bool(job.scheduling_enabled)`,
   `"interview_window_start": as_aware(...)`, `"interview_window_end": as_aware(...)`,
   `"interview_window_timezone": job.interview_window_timezone`.
3. `create_job`: before `_check_department`... or right after it, call
   `interview_window.check(body.scheduling_enabled, body.interview_window_start, body.interview_window_end,
   body.interview_window_timezone)`. Pass fields into `Job(...)` with `to_utc`.
4. `patch_job`: small local `_merged_window(job, body)` returning the 4 merged values
   (`getattr(body, f) if f in fields else getattr(job, f)`; `scheduling_enabled` None in body means unchanged).
   Call `check(*merged)` once before AI work and once after `_lock_job` re-read; on 422 after lock, `db.rollback()`
   first (same pattern as "closed" branch). Assign set fields with `to_utc`.
5. `applications.py`: add `interview_window` field to `ApplicationOut`; in `_out` add
   `"interview_window": interview_window.payload(job)`.
6. Tests, `test_hiring_interview_window.py` (pure):
   - `is_open` disabled -> True regardless of bounds/None.
   - `is_open` with naive bounds and aware `now` (and vice versa) -> no TypeError, correct result.
   - Edges: `now == start` and `now == end` -> open (closed interval per spec).
   - `check` raises 422: enabled + missing start; enabled + `start == end`; enabled + `start > end`; bad tz name.
   - `check` passes: disabled + anything; enabled + valid.
7. Tests, `test_hiring_voice.py` (append; set window on `world.job_id` row via `db`, relative to `datetime.now(UTC)`):
   - `test_start_unchanged_when_scheduling_is_off` (explicit regression: flag false, bounds in past -> 200).
   - `test_start_inside_the_window_starts_the_session` (now-1h..now+1h -> 200, session created).
   - `test_start_before_the_window_gets_409_with_the_window` (now+1h..now+2h -> 409, `detail.code`,
     `window_start`, `window_end`, `timezone` present; no `VoiceSession` row; `start_claimed_at` still None).
   - `test_start_after_the_window_gets_409` (now-2h..now-1h).
   - `test_a_running_session_resumes_after_the_window_closes` (use `started`, then move window into past,
     call `start` again -> 200 same session id).
   - `test_application_shows_the_window_only_when_scheduling_is_on` (GET application: `interview_window` null
     when off; dict when on).
8. Tests, `test_hiring_jobs.py` (append):
   - create with enabled + `start >= end` -> 422; enabled + missing end -> 422; naive datetime -> 422.
   - create valid with `+07:00` offset -> 201; response `interview_window_start` equals same instant in UTC.
   - patch: enable on job with no bounds -> 422; patch only end earlier than stored start -> 422 (merge check).
   - patch `scheduling_enabled=false` on enabled job -> 200, bounds kept, flag off.
   - default job from `make_job` returns `scheduling_enabled is False` and null bounds.
9. Run `cd SpeakCV/src/backend && pytest -q` (full suite; regression guard).

## Todo List
- [ ] Gate in `_check_can_start` with 409 detail (code, message, bounds, timezone)
- [ ] jobs_hr `_out` returns 4 fields
- [ ] `create_job` validates + stores UTC
- [ ] `patch_job` merged validation pre-AI and post-lock, stores UTC
- [ ] `ApplicationOut.interview_window`
- [ ] `test_hiring_interview_window.py` unit tests
- [ ] Start-gate tests in `test_hiring_voice.py`
- [ ] HR validation tests in `test_hiring_jobs.py`
- [ ] Full backend suite green

## Success Criteria
- All new tests pass; all pre-existing backend tests pass unmodified.
- `curl` 409 body matches contract in plan.md exactly.
- Outside-window attempt leaves no `VoiceSession`, no consent row, no `start_claimed_at`, no AI call.

## Risk Assessment
| Risk | L | I | Mitigation |
|------|---|---|-----------|
| 409 object detail hits frontend consent-reset branch | H | M | `code` in detail + phase 03 branch before generic 409 handling. |
| Patch race: window edited between pre-check and lock | L | L | Re-check after `_lock_job`. |
| Consent recorded before gate rejects | L | M | Gate is in `_check_can_start`, which runs before `_plan_and_start` (where consent is recorded); test asserts no consent row. |
| Clock skew between app servers | L | L | Single source `datetime.now(timezone.utc)`; window granularity is minutes. |
| Window close mid-planning (between pre-check and lock) | L | L | Lock-path re-check rejects; claim released by existing `finally`. Acceptable per spec (gate at start only). |

## Security Considerations
- 409 payload exposes only window bounds + tz, which the candidate already sees via `ApplicationOut`; no HR-only data.
- Ownership check (`_owned_application`) still runs first, so other users get 404, never the window.
- Writes remain HR-only, company-scoped via `_get_job`/`_lock_job`.

## Next Steps
- Phases 03 and 04 start in parallel once the API contract in plan.md is green in tests.
