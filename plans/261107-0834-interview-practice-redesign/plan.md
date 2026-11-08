---
title: "/interview practice redesign: Setup -> Interview -> Report"
description: "Split the dense /interview practice page into a 3-step flow; hide (not delete) off-flow tools."
status: pending
priority: P2
effort: 15h
branch: main
tags: [frontend, speakcv, interview, ux, redesign]
created: 2026-11-07
---

# /interview practice redesign

Scope: `SpeakCV/src/frontend` only. ScreeningRoom (`components/Hiring/ScreeningRoom.tsx`) is the visual reference. Do NOT edit it.

## Core idea (no new state machine)
`step = modals.report ? "report" : hasStarted ? "interview" : "setup"` — derived from existing state in `useInterviewState`.
All existing actions (`handleRetry`, `handleNewChat`, `handleOpenReport`, `handleLoadOldInterview`) already flip these flags, so transitions mostly work today.
New render path sits behind a `PRACTICE_STEP_FLOW` flag in `lib/features.ts`. The old `Sidebar` + `InterviewLayout` stays intact as the flag-off path (rollback = env var).

## Phases (sequential — all touch `app/interview/page.tsx`, no parallel work)
| # | Phase | Effort | Status |
|---|---|---|---|
| 1 | [Step shell + Setup step](phase-01-step-shell-and-setup-step.md) | 4h | pending |
| 2 | [Interview step](phase-02-interview-step.md) | 3h | pending |
| 3 | [Report step](phase-03-report-step.md) | 3h | pending |
| 4 | [Relocate off-flow tools (hide, not delete)](phase-04-relocate-off-flow-tools.md) | 3h | pending |
| 5 | [Verification](phase-05-verification.md) | 2h | pending |

Dependencies: 1 -> 2 -> 3 -> 4 -> 5. Phase 4 extracts parts of `Sidebar.tsx`; phases 1-3 must not edit `Sidebar.tsx`.

## Placement principle ("what the candidate needs + what HR wants them to see")
- In flow: role/JD/format setup, mic + answer panels, timer, hint, finish, report, the "go to real interview" CTA (`?next=`, this is the HR-facing link).
- Off flow (still reachable): CV tools, Dashboard, Question Bank, Subscription/Profile/Admin, Practice History. These move to a top-bar "Prepare" menu, a user menu, or a Setup side panel.

## Open Questions for the User (NOT decided — need your answer before Phase 1)
1. **Report step form**: (a) inline full-page step, using the same report content [recommended]; (b) keep the current full-screen overlay modal.
2. **PlannerSignals** (AI reasoning / "HR signals" / Nunchi) during the interview: (a) collapsed behind a "Show AI signals" toggle, default off [recommended]; (b) always visible as today; (c) remove from the interview and show only in the report.
3. **AI Hint button** in the interview step: (a) keep it visible [recommended]; (b) hide it in timed mode only; (c) hide it behind a toggle.
4. **Camera / webcam mode**: (a) "Advanced options" toggle in Setup, default off, plus a camera button in the interview header [recommended]; (b) a main Setup option; (c) only in the Prepare menu.
5. **Practice History**: (a) "Recent practice" panel on the Setup step only [recommended]; (b) a drawer opened from the top bar on every step; (c) only on `/dashboard`.
6. **CV tools** (Create / Review / Edit CV): (a) top-bar "Prepare" menu [recommended]; (b) move to `/profile`; (c) also link "Create CV" from the Setup "No Master CV" status line (can be combined with a).
7. **Dashboard + Question Bank**: (a) in the "Prepare" menu [recommended]; (b) in the user menu.
8. **Settings mid-interview** (voice, JD, mode): (a) keep a gear button in the interview header that opens the existing SettingsModal [recommended]; (b) lock settings once the interview starts.
9. **Old one-page layout**: (a) keep it behind `NEXT_PUBLIC_PRACTICE_STEP_FLOW=false` for one release as rollback [recommended]; (b) wire the new flow without a flag.
10. **Mic check in Setup** (like ScreeningRoom `MicCheck`): (a) skip for v1 [recommended; practice uses Web Speech API, not MediaStream, so a check would test a different path]; (b) build it.
11. **`/interview` is gated by `NEXT_PUBLIC_LEGACY_B2C_ENABLED`** (default `false` in both docker-compose files), so the page 404s in a default deploy. Should the redesign also turn the page on by default? This plan does not change it.
12. **Dead / misleading code found**. Keep as is, or fix?
    - `config.mode === "stress"` can never be set from the UI.
    - `ResumeConfigModal` can never open (nothing sets `pendingResumeData`).
    - History items say "Continue →" but open the report.

    [recommended: hide nothing, relabel "Continue →" to "View report →"; leave the rest untouched]
13. **E2E test location**: the only Playwright harness lives in `interviewpath/interviewpath-demo/e2e` (another project), and it runs SpeakCV without `LEGACY_B2C`. (a) Manual checklist + build/lint only [recommended]; (b) add a spec there and turn the flag on in its config; (c) add Playwright to SpeakCV/frontend.

## Out of scope
ScreeningRoom, backend/API, i18n of `/interview` (still English-only), the ReportModal scoring logic.
