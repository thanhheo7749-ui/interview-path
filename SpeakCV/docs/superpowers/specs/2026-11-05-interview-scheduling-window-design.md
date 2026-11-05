# Interview Scheduling Window — Design

## Context

The current AI screening flow lets a candidate start the voice interview immediately
after confirming fit (`fit_compass` → `voice_session`, no gate). A proposed v2 flow
(`interview-path-flow-v2.html`, unverified against the codebase) adds a scheduling
step before the interview. This spec covers only that one slice — "mảng D" — chosen
first among five independent sub-projects because it is the largest behavior change
and the foundation the HR-review slice (mảng E) needs real session data from.

Out of scope for this spec, left for later specs: JD/posting pipeline (mảng A),
document classification + knowledge graph + question bank (mảng B), candidate
auto-fill profile + JD binding (mảng C), AI score → HR review → manager final round →
onboarding/exceptions (mảng E).

## Key finding

`app/hiring/planner.py` already merges the job's requirements, the candidate's CV
claims, and company-brain retrieval into per-session question drafts — this is the
v2 "Ghép ngữ cảnh để hỏi" (context) node, already implemented. `app/hiring/voice.py`
and `app/routers/screening.py` already record transcripts/audio per turn and support
a 24-hour resume window — this already covers v2's "Lưu phiên & bằng chứng" (record)
node and most of "Lỗi kỹ thuật / xin thi lại". Nothing in context assembly, interview
execution, or evidence recording needs to change. The only new piece is a time gate
in front of the existing start endpoint.

## Decisions (from brainstorming)

- Scheduling is opt-in per job posting (`scheduling_enabled` flag), not mandatory for
  every recruiting round. Existing jobs default to off and keep today's behavior
  unchanged.
- A "window" is a valid time range during which the candidate may self-start the AI
  interview — not a real appointment. The AI has no concurrency scarcity, so there is
  no per-slot capacity, no reservation, and no double-booking logic.
- No reminder emails for window open/close. No reschedule flow (there is no
  individual appointment to reschedule — HR edits the window directly if it needs to
  change). Device check before starting reuses the existing `MicCheck` component;
  nothing new there.

## Data model

Add three nullable columns to `Job` (`app/database/models_hiring.py`):

| Column | Type | Notes |
|---|---|---|
| `scheduling_enabled` | `Boolean`, default `false` | Existing jobs unaffected. |
| `interview_window_start` | `DateTime(timezone=True)`, nullable | Stored UTC. |
| `interview_window_end` | `DateTime(timezone=True)`, nullable | Stored UTC. |
| `interview_window_timezone` | `String`, nullable | Display only; comparison is always in UTC. |

Alembic migration adds the columns with the stated defaults; no backfill needed.

## Backend changes

- `app/database/models_hiring.py`: add the four columns to `Job`.
- New alembic revision under `alembic/versions/`.
- Job create/update schema and `app/routers/jobs_hr.py`: accept and return the new
  fields. Validate `interview_window_start < interview_window_end` when
  `scheduling_enabled` is true (reject otherwise with 422).
- `app/routers/screening.py::_check_can_start` (currently takes `db, application`):
  load the `Job` for `application.job_id` inside this function and, when
  `scheduling_enabled` is true and `now_utc` is outside
  `[interview_window_start, interview_window_end]`, raise
  `HTTPException(409, detail={"code": "OUTSIDE_INTERVIEW_WINDOW", "window_start":
  ..., "window_end": ..., "timezone": ...})`. Both call sites already route through
  this function (`start()` at line 151 and `_claim_start()` at line 130), so no other
  call site needs to change. The gate only applies at start — a session already
  in progress is never interrupted by the window closing.

## Frontend changes

- `app/applications/[id]/fit/page.tsx`: when the job has `scheduling_enabled`, show
  the window ("Cửa sổ thi: X → Y") and disable the start action outside it, surfacing
  the 409's message. When `scheduling_enabled` is false, behavior is pixel-identical
  to today.
- HR job editor (wherever `jobs_hr.py`'s fields are edited in the frontend): add a
  toggle and two datetime inputs for the window, following the existing form
  patterns in that editor.

## Testing

- Backend, alongside the existing `tests/test_hiring_screening.py` style:
  - Scheduling disabled → behavior unchanged (regression).
  - Enabled, now inside window → start succeeds as today.
  - Enabled, now outside window → 409 with `OUTSIDE_INTERVIEW_WINDOW` and the window
    bounds in the payload.
  - `jobs_hr.py` update rejects `window_start >= window_end` when enabled.
- Migration: round-trips cleanly per the existing `test_migrations.py` pattern.
- No new e2e scenario is required beyond the existing apply→fit→start journey
  covering the disabled-flag path; a scheduling-enabled e2e case can be added if the
  implementer finds the existing Playwright fixtures make it cheap.

## Error handling / compatibility

Out-of-window attempts never silently succeed. The existing `start_claimed_at` claim
logic is untouched. Disabling scheduling mid-round does not affect sessions already
started. Jobs created before this change get `scheduling_enabled=false` and are
byte-for-byte unaffected.
