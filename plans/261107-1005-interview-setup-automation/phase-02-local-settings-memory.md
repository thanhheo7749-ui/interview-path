# Phase 02 — Remember settings in localStorage

## Context Links
- Overview: [plan.md](plan.md). Open Questions 2, 5 and 6 shape this phase. The steps assume 2a, 5a and 6a.
- State: `SpeakCV/src/frontend/hooks/useInterviewState.ts:25-35` (config is in memory only; defaults: voice `vi-VN-HoaiMyNeural`, mode `technical`, interviewType `free`, 5 questions, 120s)
- Start handler: `app/interview/page.tsx` (`handleStart` from the redesign plan)
- Storage precedent: `lib/i18n.ts:293-320` (read localStorage after mount, guarded for SSR)
- Flag: `lib/features.ts` (`PRACTICE_STEP_FLOW`)

## Overview
- Priority: P2. Status: pending. Can run in parallel with phase 1.
- On Start, save voice, mode, interviewType, questionLimit and timeLimit. On mount, restore them into `config`.

## Key Insights
- Values read from storage are untrusted, because a user or an old version can write anything there. Accept only known values: voice must be one of the `<option>`s in `SetupFormatFields.tsx:56-58`, mode one of `SetupForm.tsx:82-87`, interviewType `free|timed`, and the limits must be integers inside the slider range. Anything else falls back to the default.
- Reading must happen after mount (`useEffect`), never during render. This avoids a Next.js hydration mismatch.
- These settings are not position/company/JD, so they never conflict with phase 4 job context.

## Requirements
Functional:
- Key `speakcv_practice_settings_v1`, JSON `{voice, mode, interviewType, questionLimit, timeLimit}`.
- Restore once on mount. Restore a field only if it is still at its default (the user has not touched it).
- Save on Start (`handleStart`), before the interview begins.
- Only when `PRACTICE_STEP_FLOW` is on (OQ 2a). With the flag off, nothing is read or written.
Non-functional: private-mode and quota errors are caught and ignored (try/catch). Each file is under 200 lines.

## Architecture / Data flow
```
mount -> usePracticePrefill -> loadPracticeSettings() -> validate -> setConfig(merge)
Start -> handleStart -> savePracticeSettings(config) -> localStorage
```

## Related Code Files
Create:
- `lib/practiceSettingsStorage.ts`: `loadPracticeSettings()` and `savePracticeSettings(config)`, with allow-list validation (about 50 lines)
- `hooks/usePracticePrefill.ts`: `usePracticePrefill({ config, setConfig, enabled })`. This phase adds only the localStorage source. Phases 3 and 4 extend it.
Modify:
- `app/interview/page.tsx`: call `usePracticePrefill(...)` once, and call `savePracticeSettings(config)` in `handleStart`. Keep the edit to a few lines, because the file is already 562 lines.
Delete: none

## Implementation Steps
1. Write `practiceSettingsStorage.ts`. Put the allow-lists in it, so the option lists are not copied (DRY): export a `VOICES` array that `SetupFormatFields.tsx` maps over instead of hard-coded `<option>`s. Only do this if it is a small edit. Otherwise keep a local allow-list with a one-line comment: `keep in sync with SetupFormatFields`.
2. Write `usePracticePrefill.ts` with one effect, guarded by a ref and by `enabled`.
3. Wire it into `page.tsx`.
4. Run `npm run build` and `npm run lint` in `SpeakCV/src/frontend`.

## Todo List
- [ ] storage helper with validation
- [ ] prefill hook (local source)
- [ ] save on Start
- [ ] build + lint

## Success Criteria
- Pick an English voice, Behavioral, Timed, 8 questions, then Start. Reload `/interview`. Setup shows the same 5 values.
- Write a garbage value by hand to the key. Reload. The defaults show and there is no crash.
- With the flag off, the key is never written. Check this in DevTools.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| Hydration mismatch | M x M | Read only inside `useEffect` |
| Stale voice id after options change | L x L | Allow-list drops unknown ids |
| Overwrites a value the user picked before mount finished | L x L | Restore only if the field is still at its default |

## Rollback
Revert the 3 files. A leftover localStorage key is harmless.

## Security Considerations
No secrets are stored. Validation prevents values injected through storage from reaching the AI voice or mode parameters.

## Next Steps
Phase 3 adds the server source to the same hook.
