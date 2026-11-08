# Phase 02 — Interview step

## Context Links
- Overview: [plan.md](plan.md) — Open Questions 2, 3, 4, 8
- Reference style: `components/Hiring/ScreeningRoom.tsx` lines 418-488 (progress row, centered MicroButton, two cards)
- Current: `components/Interview/InterviewLayout.tsx`, `ChatBox.tsx`, `MicroButton.tsx`, `TimerDisplay.tsx`, `PlannerSignals.tsx`, `InlineCameraWidget.tsx`
- Finish button today: `components/Interview/Sidebar.tsx` lines 532-544

## Overview
- Priority: P2. Status: pending. Blocked by: Phase 1.
- Build a focused interview screen, laid out the same way as ScreeningRoom:
  - a status row (position, Q x/y, timer)
  - a centered MicroButton
  - two answer/question cards
  - one clear "Finish & get report" button.

  The hint, the camera and the AI signals are secondary.

## Key Insights
- Finish & Score only exists in the sidebar footer (an icon button). In the step flow it must be a primary, labeled button in the step itself.
- The hint popover + mobile swipe sheet (InterviewLayout 97-116, 221-302) is about 90 lines inline. Extract it so both layouts share it.
- ScreeningRoom card style: `rounded-2xl border border-theme-border bg-theme-primary p-5`. Labels: `text-xs font-bold uppercase tracking-widest text-blue-500 / text-emerald-500`. ChatBox uses a different, heavier style (`rounded-3xl … backdrop-blur-md`).
- `MicroButton` already supports `testId` and `disabled`. Its `id="tour-step-mic"` is hardcoded. Fine, because only one MicroButton renders per page.
- Keyboard: Space = mic, Ctrl+R = report, Ctrl+, = settings (`useKeyboardShortcuts`). Keep them.

## Requirements
Functional:
- Header row: position@company badge, `TimerDisplay` (timed only), a Settings gear (Open Question 8), a camera toggle (Open Question 4), "New practice" (calls `handleNewChat` after `confirm()`), and "Finish & get report" (calls `handleOpenReport(false)`, disabled while `isGeneratingReport`, shows a spinner).
- Center: `MicroButton` (status, onMicClick, langLabel, `isCompact` when the camera is on, `testId="practice-mic"`).
- Hint: a button next to the mic plus the extracted `HintPanel`.
- Cards: ChatBox restyled to the ScreeningRoom card tokens. Keep the labels "Candidate (You)" / "AI Response" and all behavior (Enter to send, clear, refresh mic, live `tempText`).
- PlannerSignals: render according to Open Question 2. Default plan: a `<details>` element "AI interviewer signals", closed.
- `InlineCameraWidget` above the mic when `isCameraModeOpen` (same rules as today: the close button is hidden in stress mode).

Non-functional: InterviewStep.tsx <200 lines; mobile single column; no new API calls.

## Architecture
`InterviewStep` is presentational. Every prop comes from page.tsx, the same set `InterviewLayout` gets today minus the setup props, plus `onFinish`, `isGeneratingReport`, `onNewPractice`, `onOpenSettings`, `onToggleCamera`.
Data flow is unchanged: mic or typing goes to `userText`, then `actions.handleSend`, then `useChat.sendMessage`, then `aiText`/`analysis`, then the cards and PlannerSignals.

## Related Code Files
Create:
- `components/Interview/steps/InterviewStep.tsx`
- `components/Interview/HintPanel.tsx` (desktop popover + mobile sheet with swipe-to-dismiss, moved from InterviewLayout)

Modify:
- `components/Interview/InterviewLayout.tsx`: replace the inline hint markup + swipe state with `<HintPanel>` (DRY; legacy behavior identical)
- `components/Interview/ChatBox.tsx`: swap the card classes to ScreeningRoom tokens; add `data-testid="practice-answer"` and `data-testid="practice-ai-text"`. This also restyles the legacy layout, which is acceptable.
- `app/interview/page.tsx`: render `<InterviewStep>` for `step==="interview"`, replacing the temporary InterviewLayout

Delete: none.

## Implementation Steps
1. Create `HintPanel.tsx`.
   - Props: `hint`, `onClose`.
   - Move the swipe state/handlers (InterviewLayout 97-116), the desktop popover (221-239) and the mobile modal (261-302) verbatim.
   - Keep `role="dialog"`, `aria-modal`, `aria-label`.
2. Use `HintPanel` in `InterviewLayout.tsx`. Diff check: the legacy hint still opens and closes on desktop and on mobile swipe.
3. Restyle `ChatBox.tsx` (classes only; no logic change). Add the testids.
4. Create `InterviewStep.tsx`.
   - Layout: `max-w-4xl mx-auto space-y-4 p-4`.
   - Order: header row, `InlineCameraWidget?`, mic block (`flex flex-col items-center gap-10 py-4` like ScreeningRoom), hint button, ChatBox, PlannerSignals `<details>`.
   - Finish button: `data-testid="finish-practice"`, style `rounded-xl bg-blue-600 px-5 py-3 font-bold text-white`.
5. In page.tsx, pass the props.
   - `onToggleCamera={() => setIsCameraModeOpen(v => !v)}`
   - `onOpenSettings={() => toggleModal("settings", true)}`
   - `onNewPractice={() => confirm("Discard this practice and start over?") && actions.handleNewChat()}`
6. Run `npx tsc --noEmit` and `npm run lint`.

## Todo List
- [ ] HintPanel extracted, used by InterviewLayout
- [ ] ChatBox restyled + testids
- [ ] InterviewStep built
- [ ] page.tsx wired
- [ ] tsc + lint clean

## Success Criteria
- Interview step shows no sidebar, no setup form and no Tools menu.
- The mic toggles Listening/Ready. Clicking during Processing/AI Speaking interrupts (existing `onMicClick`).
- Timed mode: Q x/y + countdown are visible. Time-out auto-sends (existing `onTimeUp`). The last question auto-opens the report.
- The Finish button opens the report step. While scoring, the button is disabled and shows a spinner.
- The hint works on desktop (popover) and mobile (sheet, swipe to close).
- Side by side with ScreeningRoom: same card radius, border, label style and mic placement.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| ChatBox restyle changes legacy look | H x L | Intended; style-only change. Flag-off rollback still works functionally. |
| Hint extraction breaks the mobile swipe | L x M | Verbatim move; manual mobile check in phase 5. |
| `confirm()` on New practice blocks the Ctrl+N shortcut | L x L | Shortcut keeps calling `handleNewChat` directly, as today. |

## Security Considerations
None new. Webcam stream stays local (`WebcamView`), as today.

## Next Steps
Phase 3: report step.
