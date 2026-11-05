# Phase 01: Data model, migration, window helper

## Context Links
- Spec: `SpeakCV/docs/superpowers/specs/2026-11-05-interview-scheduling-window-design.md`
- Plan: [plan.md](plan.md)
- Model: `SpeakCV/src/backend/app/database/models_hiring.py` (`class Job`, ~L18-33)
- Last migration (template): `SpeakCV/src/backend/alembic/versions/0009_reality_thresholds.py`
- Bool server_default precedent: `SpeakCV/src/backend/app/database/sql_models.py:21` (`must_change_password`)
- Schemas: `SpeakCV/src/backend/app/schemas/jobs.py` (`JobCreate`, `JobPatch`, `JobOut`)
- Migration tests: `SpeakCV/src/backend/tests/test_migrations.py`

## Overview
- Priority: P2. Status: pending. Effort: 1h.
- Add 4 columns to `jobs`, alembic revision `0010_interview_window`, schema fields, and one tiny pure helper
  module shared by jobs_hr, applications and screening (DRY: one place for UTC normalization + window checks).

## Key Insights
- SQLite (tests) and MySQL (`tests/mysql`) return naive datetimes for `DateTime(timezone=True)`. House pattern
  stores naive UTC (see `_claim_start` in `routers/screening.py`). Comparing aware `now` against naive DB value
  raises `TypeError`. Helper must normalize both sides.
- MySQL drivers drop tzinfo on write without converting. So inbound aware datetimes must be converted to UTC
  before storing, else a `+07:00` input is stored 7h off.
- `test_head_matches_models` diffs metadata vs migrated DB: model and migration must match exactly
  (types, nullability). `compare_type=False`, server defaults not compared, but keep them identical anyway.
- `test_there_is_one_head...` requires single head: `down_revision='0009_reality_thresholds'`.

## Requirements
Functional:
- `jobs.scheduling_enabled` Boolean NOT NULL, `default=False`, `server_default=false()`.
- `jobs.interview_window_start`, `jobs.interview_window_end`: `DateTime(timezone=True)`, nullable, naive UTC stored.
- `jobs.interview_window_timezone`: `String(64)`, nullable, display only.
- Schemas: optional fields on `JobCreate`/`JobPatch`; returned on `JobOut`.
Non-functional:
- Existing rows get `scheduling_enabled=false` via server default; no backfill script.
- Helper module < 60 lines, no DB access, pure functions.

## Architecture
New module `app/hiring/interview_window.py`:
- `to_utc(dt) -> datetime | None`: aware -> naive UTC; naive (from DB) returned as is. One line per case.
- `as_aware(dt) -> datetime | None`: naive UTC from DB -> aware UTC for JSON output (`+00:00`).
- `check(enabled, start, end, tz) -> None`: raise `HTTPException(422, detail=...)` if enabled and
  (start or end missing, or start >= end), or tz not None and not a valid IANA name (`zoneinfo.ZoneInfo`).
  Detail shape follows house `{"code": ..., "message": ...}` (code `INVALID_INTERVIEW_WINDOW`).
- `is_open(job, now) -> bool`: True if not `job.scheduling_enabled`, else `start <= now <= end` on naive UTC.
- `payload(job) -> dict | None`: `{"start", "end", "timezone"}` aware-UTC values, `None` when disabled.
Data flow: HR JSON (aware ISO) -> pydantic `AwareDatetime` -> `to_utc` -> DB naive UTC -> `as_aware` -> JSON `+00:00`.

Schemas (`schemas/jobs.py`):
- `JobCreate`: `scheduling_enabled: bool = False`, `interview_window_start: Optional[AwareDatetime] = None`,
  `interview_window_end: Optional[AwareDatetime] = None`,
  `interview_window_timezone: Optional[Annotated[str, StringConstraints(max_length=64)]] = None`.
- `JobPatch`: same 4 fields all `Optional[...] = None` (bool too, so omitted means "unchanged").
- `JobOut`: `scheduling_enabled: bool = False`, 3 Optional fields (datetime/str).
- No pydantic `model_validator`: PATCH needs merged validation against stored values, so validation lives in
  `interview_window.check` called by the router (phase 02) for both create and patch. One code path.
- `AwareDatetime` rejects naive input with 422 automatically: no ambiguous wall-clock times accepted.

## Related Code Files
Modify:
- `SpeakCV/src/backend/app/database/models_hiring.py`
- `SpeakCV/src/backend/app/schemas/jobs.py`
Create:
- `SpeakCV/src/backend/alembic/versions/0010_interview_window.py`
- `SpeakCV/src/backend/app/hiring/interview_window.py`
Delete: none.

## Implementation Steps
1. `models_hiring.py`: import `false` from `sqlalchemy.sql` (or `sqlalchemy`); add to `Job` after `interview_languages`:
   `scheduling_enabled = Column(Boolean, nullable=False, default=False, server_default=false())`,
   two `Column(DateTime(timezone=True), nullable=True)`, `interview_window_timezone = Column(String(64), nullable=True)`.
   One-line comment: window stored naive UTC; timezone is display only.
2. Copy `0009_reality_thresholds.py` layout to `0010_interview_window.py`: `revision='0010_interview_window'`,
   `down_revision='0009_reality_thresholds'`, Create Date 2026-11-05.
   `upgrade`: 4x `op.add_column('jobs', ...)`, bool with `server_default=sa.false()`, `nullable=False`.
   `downgrade`: drop in reverse order (same style as 0009).
3. Write `app/hiring/interview_window.py` per Architecture. Module docstring one line, like sibling modules.
4. Update `schemas/jobs.py`: import `AwareDatetime` from pydantic; add fields per Architecture.
5. Run `cd SpeakCV/src/backend && pytest tests/test_migrations.py -q`.
6. Add unit tests for helper in phase 02 test file (keeps test ownership in one phase).

## Todo List
- [ ] Add 4 columns to `Job`
- [ ] Create `0010_interview_window.py` (upgrade + downgrade)
- [ ] Create `app/hiring/interview_window.py` (`to_utc`, `as_aware`, `check`, `is_open`, `payload`)
- [ ] Add fields to `JobCreate`, `JobPatch`, `JobOut`
- [ ] `pytest tests/test_migrations.py` green
- [ ] Manual round trip on a scratch SQLite copy: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`

## Success Criteria
- `test_migrations.py` all green (head matches models, one head, running twice safe, legacy stamp keeps data).
- Downgrade then upgrade on a DB with existing jobs: rows intact, `scheduling_enabled` = 0 for all.
- `python -c "import app.hiring.interview_window"` imports clean.

## Risk Assessment
| Risk | L | I | Mitigation |
|------|---|---|-----------|
| SQLite `drop_column` in downgrade fails on old SQLite | L | M | 0009 already uses same op; same env. |
| Naive/aware compare `TypeError` at runtime | M | H | `to_utc` normalizes both sides; unit tests with naive and aware inputs. |
| MySQL stores aware dt shifted | M | H | Always `to_utc` before assign (phase 02 router steps). |
| Model/migration drift fails head test | M | L | Run `test_head_matches_models` before leaving phase. |

## Security Considerations
- Timezone string validated against `zoneinfo` (trust boundary), length capped 64.
- No PII added. HR-only write path unchanged (`require_member("hr")`).

## Next Steps
- Phase 02 consumes `interview_window` helper and new schema fields.
