# Phase 01 — Backend: migration 0011, history fields, job_slug

## Context Links
- Overview: [plan.md](plan.md). Open Questions 1, 7 and 11 shape this phase. The steps below assume the recommended answers (1a, 7a, 11a). If 1b or 7b/c is chosen, rewrite this phase before starting.
- Model: `SpeakCV/src/backend/app/database/sql_models.py:67-80` (`InterviewHistory`)
- Migration template: `backend/alembic/versions/0010_interview_window.py` (additive `op.add_column`)
- Migration runner: `backend/app/database/migrate.py` (upgrades to head at startup)
- Report endpoint: `backend/app/routers/interview.py:528` (`end_interview`), row write at about `:600-640`
- Request model: `backend/app/models.py:62` AND `:2505`. `ReportRequest` is defined twice, and the second definition wins at import.
- Application output: `backend/app/routers/applications.py:48-71` (`ApplicationOut`), `:113-150` (`_out`), `:156-167` (`_owned`), `:233-235` (`GET /api/applications/{id}`)
- Tests: `backend/tests/test_migrations.py` (`test_head_matches_models`, single-head test), `backend/tests/test_hiring_application_states.py`

## Overview
- Priority: P2. Status: pending. Blocked by: OQ 1, 7.
- Store company / jd_text / voice / mode on each finished practice. Expose the job slug on the candidate's own application.

## Key Insights
- `interview_history` rows are created or updated only in `end_interview`. That makes "last used" equal to "last scored practice".
- `jd_text` is already sent to `end-interview`, but it is not stored. Today `company`, `voice` and `mode` are never sent.
- Production uses MySQL (`tests/mysql`). String length limits matter, so pydantic `max_length` must match the column sizes. Otherwise a long input causes a DB error.
- `test_head_matches_models` compares the ORM with the migrations. The column definitions in the model and in 0011 must be identical.
- `Job.slug` is set at publish. Applications exist only for published jobs, but the type is `str | None` for safety.

## Requirements
Functional:
- Migration `0011_practice_context`, down_revision `0010_interview_window`. Add nullable columns to `interview_history`: `company String(255)`, `jd_text Text`, `voice String(64)`, `mode String(32)`. Downgrade drops them in reverse order.
- `ReportRequest`: add `company: Optional[str] = Field(None, max_length=255)`, `voice: Optional[str] = Field(None, max_length=64)`, `mode: Optional[str] = Field(None, max_length=32)`. Make the edit in both copies.
- `end_interview`: write `company`, `jd_text` (from `request.jd_text`, `None` if blank), `voice` and `mode` on both the new-row path and the existing-row path.
- `ApplicationOut`: add `job_slug: str | None = None`. Set it in `_out` from `job.slug`.
Non-functional: additive only. Old clients that don't send the new fields keep working (all fields optional). `GET /api/history` returns the new columns automatically, because it returns ORM rows.

## Architecture / Data flow
```
Setup config -> POST /api/end-interview {..., company, voice, mode, jd_text}
            -> interview_history row (+4 cols) -> GET /api/history -> frontend (phase 3)
GET /api/applications/{id} (owner only via _owned) -> {..., job_slug} -> frontend (phase 4)
```

## Related Code Files
Create: `backend/alembic/versions/0011_practice_context.py`
Modify: `app/database/sql_models.py`, `app/models.py` (2 places), `app/routers/interview.py`, `app/routers/applications.py`, `tests/test_migrations.py` (only if a test pins the head name), `tests/test_hiring_application_states.py` or a new `tests/test_practice_context.py`
Delete: none

## Implementation Steps
1. Copy the 0010 file shape into 0011. Use the same 4 columns in the `InterviewHistory` model.
2. Extend both `ReportRequest` copies with the same 3 fields.
3. In `end_interview`, set the 4 attributes in both branches. Use one small helper, `_apply_context(row, request)`, so the code is not repeated.
4. Add `job_slug` to `ApplicationOut` and to `_out`.
5. Tests (new `tests/test_practice_context.py`, under 200 lines):
   - Migration upgrade, then downgrade, on SQLite tmp_path. Follow the `test_migrations.py` style.
   - `end_interview` stores company/jd_text/voice/mode. Stub the AI call the same way the existing interview tests stub it (check `test_cv_routes.py:134` for the route-level pattern).
   - `GET /api/applications/{id}` returns `job_slug` for the owner.
   - **Security**: user B asks for user A's application id and gets 404. No title, company or slug leaks.
6. Run `pytest backend/tests -q`. All tests must pass, including `test_head_matches_models`.

## Todo List
- [ ] 0011 migration + model columns
- [ ] ReportRequest fields (both copies)
- [ ] end_interview writes fields (both branches)
- [ ] ApplicationOut.job_slug
- [ ] tests: migration, persist, job_slug, cross-user 404
- [ ] full pytest green

## Success Criteria
- `alembic upgrade head`, then `downgrade -1`, then `upgrade head` is clean on SQLite (and on MySQL if the `tests/mysql` harness is run).
- `GET /api/history` rows include the 4 new keys. Old rows have `null`.
- The cross-user application test returns 404.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| Model/migration drift breaks `test_head_matches_models` | M x M | Same types/sizes in both; run the test |
| Editing only one `ReportRequest` copy | M x H | Edit both; the test posts the new fields through the real route |
| Large JD text bloats `GET /api/history` | L x L | Already returns `details` JSON; Text is fine |
| Downgrade loses stored context | L x L | Data is convenience-only |

## Rollback
`alembic downgrade 0010_interview_window`, then revert the code. The frontend treats missing fields as empty, so the steps can be reverted in either order.

## Security Considerations
- The new history columns are only read through user-scoped queries (`user_id == current_user.id`). They are already scoped this way.
- `job_slug` is public data. `_owned` still blocks reading other users' applications.
- `jd_text` is the user's own input, and later HR-authored public JD text. It reaches the AI prompt exactly as a pasted JD does today. No new risk.

## Next Steps
Phase 3 reads the history fields. Phase 4 reads `job_slug`.
