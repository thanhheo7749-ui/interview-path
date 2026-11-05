# Phase 03: Candidate UI (fit page + screening room)

## Context Links
- Plan: [plan.md](plan.md), API contract from [phase-02](phase-02-backend-api-start-gate-and-tests.md)
- `SpeakCV/src/frontend/app/applications/[id]/fit/page.tsx` (170 lines; start action is a `<Link>` to `/screening`)
- `SpeakCV/src/frontend/components/Hiring/ScreeningRoom.tsx` (`handleStart` ~L159, resume path ~L118)
- `SpeakCV/src/frontend/services/hiring.ts` (`HiringError`, `errorCode`, `CV_CONSENT_WITHDRAWN`, `Application`)
- `SpeakCV/src/frontend/lib/i18n.ts` (`en`/`vi` page strings, `screeningEn`/`screeningVi`)

## Overview
- Priority: P2. Status: pending. Effort: 1.5h. Parallel with phase 04.
- Fit page: show window line + disable start outside window, only when `application.interview_window` non-null.
- Screening room: handle `OUTSIDE_INTERVIEW_WINDOW` 409 explicitly (deep link / stale tab / window closed while
  on preflight).

## Key Insights
- Fit page never POSTs `/start`; it links to `/applications/{id}/screening`. A 409 cannot drive it. Source of truth
  for fit page = `Application.interview_window` from `getApplication` (already fetched). Backend 409 still the real
  gate; fit page UI is advisory.
- `ScreeningRoom.handleStart` generic branch: 409 + object detail => resets `agreed`, refetches consent. Without a
  code branch, an out-of-window 409 would wrongly look like a consent change. Add `errorCode(e) ===
  OUTSIDE_INTERVIEW_WINDOW` branch next to the `CV_CONSENT_WITHDRAWN` branch.
- Resume path (`interview_in_progress` -> `startSession`) never gated server-side; no change needed there.
- i18n has two locales (`en`, `vi`) in `lib/i18n.ts`; `Strings` type derived from `en`, so `vi` must get every key.
- Client clock may be wrong. Fit page compares with `Date.now()` for display only; server decides.

## Requirements
Functional:
- `Application` type: `interview_window?: { start: string; end: string; timezone: string | null } | null`.
- Export `OUTSIDE_INTERVIEW_WINDOW = "OUTSIDE_INTERVIEW_WINDOW"` in `services/hiring.ts`.
- Fit page, when `interview_window` non-null:
  - Show `t.interviewWindow` formatted "Cua so thi: {start} -> {end}" (vi: "Cửa sổ thi: {start} → {end}").
  - Outside window: render start action as disabled `<button disabled aria-disabled>` with label
    `t.windowNotOpen` (before start) or `t.windowClosed` (after end); withdraw button unchanged.
  - Inside window: same `<Link>` as today.
- Fit page, when null: markup identical to today (no new nodes).
- ScreeningRoom: on `OUTSIDE_INTERVIEW_WINDOW` call `endWith(text.outsideWindow)` (message phase), do not reset consent.
Non-functional:
- Format with `Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tz ?? undefined })`;
  invalid tz should not crash: wrap in try/catch, fall back to no `timeZone`.
- fit page stays < 200 lines: put formatting + open/closed check in a small helper if needed
  (`lib/interviewWindow.ts`, ~20 lines).

## Architecture
```
getApplication -> application.interview_window
   null  -> today's UI
   {..}  -> windowState(now) in {before, open, after} -> line + Link | disabled button
ScreeningRoom.handleStart -> startSession -> 409 code OUTSIDE_INTERVIEW_WINDOW -> endWith(text.outsideWindow)
```

## Related Code Files
Modify:
- `SpeakCV/src/frontend/services/hiring.ts`
- `SpeakCV/src/frontend/app/applications/[id]/fit/page.tsx`
- `SpeakCV/src/frontend/components/Hiring/ScreeningRoom.tsx`
- `SpeakCV/src/frontend/lib/i18n.ts`
Create:
- `SpeakCV/src/frontend/lib/interviewWindow.ts` (format + `windowState`), only if fit page would exceed ~200 lines.
Delete: none.

## Implementation Steps
1. `services/hiring.ts`: add field to `Application`, export `OUTSIDE_INTERVIEW_WINDOW` beside `CV_CONSENT_WITHDRAWN`.
2. `lib/i18n.ts`: add to `en` + `vi`: `interviewWindow` (template with `{start}`/`{end}`, use existing `format`),
   `windowNotOpen`, `windowClosed`. Add to `screeningEn` + `screeningVi`: `outsideWindow`.
3. `lib/interviewWindow.ts` (if created): `formatWindowTime(iso, tz, locale)`, `windowState(w, now)`.
4. Fit page: compute `const win = application?.interview_window`; `const state = win ? windowState(win, Date.now()) : "open"`.
   Render window `<p>` only when `win`. In the action block swap `<Link>` for disabled button when `state !== "open"`.
5. ScreeningRoom `handleStart`: after `CV_CONSENT_WITHDRAWN` branch add
   `if (errorCode(e) === OUTSIDE_INTERVIEW_WINDOW) { endWith(text.outsideWindow); return; }`; add import.
6. `cd SpeakCV/src/frontend && npm run lint && npm run build`.
7. Manual check: job with window off (unchanged), future window (disabled + line), open window (link works),
   past window via direct `/screening` URL (message shown, no consent reset).
8. Check `tests/test_no_fake_claims_frontend.py` still passes (it scans frontend text) — run backend pytest for it.

## Todo List
- [ ] `Application.interview_window` type + `OUTSIDE_INTERVIEW_WINDOW` const
- [ ] i18n keys en + vi (page + screening)
- [ ] Fit page window line + disabled state
- [ ] ScreeningRoom 409 code branch
- [ ] lint + build green
- [ ] Manual 4-case check
- [ ] `pytest tests/test_no_fake_claims_frontend.py` green

## Success Criteria
- Disabled job: fit page DOM identical (diff of rendered HTML for a sample application shows no change).
- Enabled + outside: start disabled, window shown in job timezone; enabled + inside: link works as today.
- Direct `/screening` outside window shows `outsideWindow` message; no consent refetch loop.

## Risk Assessment
| Risk | L | I | Mitigation |
|------|---|---|-----------|
| Client clock wrong shows wrong state | M | L | Server gate authoritative; ScreeningRoom message covers mismatch. |
| Invalid tz string crashes `Intl` | L | M | Backend validates IANA; try/catch fallback anyway. |
| Window opens while page open, button stays disabled | M | L | Accept (refresh fixes). No timers (YAGNI). |
| Missing `vi` key breaks TS build | M | L | `Strings` type enforces; build step catches. |

## Security Considerations
- Display only; no new write paths. No HR-only fields shown (payload limited to bounds + tz).

## Next Steps
- Optional: Playwright case in SpeakCV e2e if fixtures make it cheap (spec allows skip).
