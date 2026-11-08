# Phase 03 — Prefill from last practice (server, cross-device)

## Context Links
- Overview: [plan.md](plan.md). Open Questions 1, 3 and 4 shape this phase. The steps assume 1a, 3a and 4a.
- API: `SpeakCV/src/frontend/services/api.ts:55` (`endInterview`, positional args)
- Caller: `hooks/useInterviewActions.ts:223-231` (`endInterview(...)`)
- History already loaded on login: `hooks/useInterviewActions.ts:442-444`, into `interviewHistories` (sorted `created_at desc` by `GET /api/history`)
- Hook from phase 2: `hooks/usePracticePrefill.ts`

## Overview
- Priority: P2. Status: pending. Blocked by: phases 1 and 2.
- Send company/voice/mode to `end-interview`. On mount, prefill from `interviewHistories[0]`. No new endpoint and no new fetch.

## Key Insights
- `interviewHistories` is already fetched for logged-in users. Use it, and do not add another request.
- Resumed sessions update an existing row but keep its `created_at`. "Latest" is therefore by creation time, not by last use. This is an accepted limitation (note it as a `shortcut:` comment).
- Guests have no history, so this source is skipped for them.
- Precedence (OQ 3a):
  - Voice/mode/format: localStorage wins, because it is newer on this device. The history row fills them only when localStorage has no value (new device).
  - Position/company/JD come from the history row, unless `?applicationId` is present (phase 4).

## Requirements
Functional:
- `endInterview` gets an optional trailing object `{ company, voice, mode }`, merged into the body. Existing positional args stay unchanged, so no other callers break.
- `useInterviewActions.ts:223` passes `config.company`, `config.voice`, `config.mode`.
- `usePracticePrefill` adds a source that runs once, when `interviewHistories` first becomes non-empty. Use the newest row:
  - Fill `position`, `company` and `jd` (from `jd_text`) only if each is empty and was not edited by the user.
  - Fill voice/mode only if phase 2 restored nothing for them and they are still at their defaults.
  - Validate voice/mode with the same allow-list as phase 2.
- OQ 4a: when any of position/company/JD was filled from history, show one line in SetupStep: "Filled from your last practice (Company) · Clear". Clear resets those 3 fields to `""`.
Non-functional: legacy flag-off path unchanged (OQ 2a).

## Architecture / Data flow
```
login -> getHistory() -> interviewHistories[0] {position, company, jd_text, voice, mode}
      -> usePracticePrefill (pure resolvePrefill(current, sources, touched)) -> setConfig
finish -> endInterview(..., {company, voice, mode}) -> row stored (phase 1)
```
Keep the merge as a pure function `resolvePrefill` in `lib/practicePrefill.ts`. Phase 4 adds one source to it, so the precedence rule lives in one place.

## Related Code Files
Create: `lib/practicePrefill.ts` (pure merge and precedence, under 80 lines). Optional: `components/Interview/PrefillNotice.tsx` (the one-line notice plus Clear) if SetupStep is near 200 lines.
Modify: `services/api.ts`, `hooks/useInterviewActions.ts`, `hooks/usePracticePrefill.ts`, `components/Interview/steps/SetupStep.tsx` (render the notice), `app/interview/page.tsx` (pass `interviewHistories` to the hook, only if it is not already reachable)
Delete: none

## Implementation Steps
1. Extend `endInterview` with an optional `extra` object and spread it into `bodyData`.
2. Pass the 3 fields from `useInterviewActions.ts:223`.
3. Create `resolvePrefill(current, { app, history, local, cvTitle }, touched)`. It returns a patch and `filledFrom` per field. Move the phase 2 local merge into it.
4. "Touched" tracking: the hook keeps a `touchedRef: Set<string>`, wrapped around the `setConfig` given to SetupForm. Alternatively, compare against the defaults. Pick the smaller diff during implementation; the "only if empty" rule already covers most cases.
5. Render the notice plus Clear.
6. Build and lint.

## Todo List
- [ ] endInterview extra fields
- [ ] caller passes company/voice/mode
- [ ] resolvePrefill pure function
- [ ] history source in hook
- [ ] notice + Clear
- [ ] build + lint

## Success Criteria
- Device A: practice "Backend Dev" at "Acme" with a JD and finish. Device B (or a cleared localStorage): log in and open `/interview`. Position, company, JD, voice and mode are prefilled, and the notice names Acme.
- Type a position before history loads. It is not overwritten.
- Clear empties position, company and JD only.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| History arrives after the user starts typing | M x M | Fill only empty, untouched fields |
| User practices a new role and the old JD silently leaks into the prompt | M x M | Visible notice + Clear (OQ 4) |
| Old rows have null fields | H x L | Null counts as "no value" |

## Rollback
Revert the frontend files. Backend fields that are no longer sent default to null. No data cleanup needed.

## Security Considerations
History data is the user's own and comes from a user-scoped endpoint. Voice and mode are validated before use.

## Next Steps
Phase 4 adds the application source to `resolvePrefill`.
