# Phase 04: HR job editor window fields

## Context Links
- Plan: [plan.md](plan.md), API contract from [phase-02](phase-02-backend-api-start-gate-and-tests.md)
- HR app: `interviewpath/interviewpath-demo` (Vite + React, JSX). SpeakCV frontend has no job editor.
- `interviewpath/interviewpath-demo/src/routes/JobEditorPage.jsx` (397 lines): `applyJob` (~L56), `persist` (~L135),
  `run` validation (~L148), languages fieldset (~L288)
- `interviewpath/interviewpath-demo/src/lib/jobs.js` (`createJob`, `patchJob`; no change needed)
- i18n: `interviewpath/interviewpath-demo/src/i18n/{en,vi,ko}.json` (`jobs.*` namespace ~L426 in en)
- E2E: `interviewpath/interviewpath-demo/e2e/jobs.spec.js`

## Overview
- Priority: P2. Status: pending. Effort: 1.5h. Parallel with phase 03.
- Add toggle + two `datetime-local` inputs to the job editor, extracted as a small component so
  `JobEditorPage.jsx` (already ~400 lines) grows only by state + payload lines.

## Key Insights
- Editor sends full form on create and patch; follow that: always send the 4 fields.
- `datetime-local` gives wall-clock without offset. Backend requires aware datetimes (naive -> 422). Convert with
  `new Date(localValue).toISOString()` (browser local tz -> UTC `Z`). Send
  `interview_window_timezone = Intl.DateTimeFormat().resolvedOptions().timeZone` for candidate display.
- Loading: convert stored UTC ISO back to `datetime-local` string in browser tz
  (`YYYY-MM-DDTHH:mm` from local getters). If HR browser tz differs from stored tz, inputs show HR local time;
  acceptable (instant is identical). Note as shortcut comment.
- Existing `readOnly` flag (closed job / JD Studio) must disable new inputs too.
- Client-side check mirrors backend (`start < end` when enabled) for fast feedback; backend 422 remains authority
  and is surfaced by existing `run` error handling.

## Requirements
Functional:
- Checkbox "Limit when candidates can start the AI interview" (`jobs.schedulingEnabled`).
- When checked: two `datetime-local` inputs (`jobs.windowStart`, `jobs.windowEnd`) + hint line showing timezone
  (`jobs.windowTimezoneHint`).
- When unchecked: inputs hidden; stored bounds preserved (sent back unchanged).
- `run`: if enabled and (missing bound or start >= end) => `setError(t('jobs.windowInvalid'))`, no request.
Non-functional:
- New component < 60 lines, same Tailwind classes as languages fieldset (`inputClass`, `text-sm font-semibold
  text-slate-700`).
- en/vi/ko keys all added (existing app ships 3 locales).

## Architecture
```
JobEditorPage state: schedulingEnabled(bool), windowStart(str local), windowEnd(str local)
applyJob(data) -> isoToLocalInput(data.interview_window_start/end), data.scheduling_enabled
<InterviewWindowFields enabled start end readOnly onChange.../>
persist() -> {..., scheduling_enabled, interview_window_start: localInputToIso(start)|null,
              interview_window_end: ..., interview_window_timezone: browserTz}
backend 422 -> existing error display
```

## Related Code Files
Modify:
- `interviewpath/interviewpath-demo/src/routes/JobEditorPage.jsx`
- `interviewpath/interviewpath-demo/src/i18n/en.json`
- `interviewpath/interviewpath-demo/src/i18n/vi.json`
- `interviewpath/interviewpath-demo/src/i18n/ko.json`
Create:
- `interviewpath/interviewpath-demo/src/components/InterviewWindowFields.jsx` (fields + 2 tiny convert helpers)
Delete: none.

## Implementation Steps
1. Create `InterviewWindowFields.jsx`: export default component (props `enabled`, `start`, `end`, `readOnly`,
   `onEnabled`, `onStart`, `onEnd`) and named exports `isoToLocalInput(iso)`, `localInputToIso(value)`
   (both return `''`/`null` for empty). Fieldset markup copied from languages fieldset pattern.
2. `JobEditorPage.jsx`: add 3 `useState`; set in `applyJob`; render component after languages fieldset;
   extend both payloads in `persist`; add check in `run` after language check.
3. i18n: add `jobs.schedulingEnabled`, `jobs.windowStart`, `jobs.windowEnd`, `jobs.windowTimezoneHint`
   (with `{{tz}}` or the interpolation style the file already uses — check `t()` impl in `src/i18n/index.js`),
   `jobs.windowInvalid` to en, vi, ko.
4. `cd interviewpath/interviewpath-demo && npm run lint && npm run build`.
5. Manual: create job with window off (payload has `scheduling_enabled:false`, nulls); enable + set bounds, save,
   reload, values round-trip; set end before start -> inline error; closed job -> inputs disabled.
6. Run existing `e2e/jobs.spec.js` (Playwright) to confirm no regression; adding a window case optional.

## Todo List
- [ ] `InterviewWindowFields.jsx` with convert helpers
- [ ] Editor state, `applyJob`, render, `persist`, `run` check
- [ ] i18n en/vi/ko
- [ ] lint + build green
- [ ] Manual round-trip check
- [ ] `e2e/jobs.spec.js` still green

## Success Criteria
- Saved window round-trips (save, reload, same instants shown).
- Backend receives aware ISO strings; never naive.
- Window-off job editing unchanged except visible unchecked toggle.

## Risk Assessment
| Risk | L | I | Mitigation |
|------|---|---|-----------|
| DST / tz conversion off by an hour | L | M | Use `Date` local getters only; no manual offset math. |
| Existing e2e selectors break from new fieldset | L | L | New fieldset appended, no changes to existing labels. |
| HR in different tz than candidates confused | M | L | Hint shows tz; candidate page formats in stored tz. |

## Security Considerations
- No new endpoints; uses existing authenticated `api()` wrapper. Server validates all input.

## Next Steps
- After 03 + 04: docs-manager updates `SpeakCV/docs` / changelog if the project tracks them; code-reviewer pass.
