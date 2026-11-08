# Phase 01 — Step shell + Setup step

## Context Links
- Overview: [plan.md](plan.md) — Open Questions 4, 8, 9, 11 affect this phase
- Orchestrator: `SpeakCV/src/frontend/app/interview/page.tsx`
- State: `SpeakCV/src/frontend/hooks/useInterviewState.ts`, `hooks/useInterviewActions.ts`, `hooks/useInterviewTimer.ts`, `hooks/useChat.ts`
- Current setup UI: `components/Interview/SetupForm.tsx`, `components/Modals/SettingsModal.tsx`
- Flag pattern: `lib/features.ts` (`LEGACY_B2C`)

## Overview
- Priority: P2. Status: pending. Blocked by: answers to the Open Questions.
- Add a derived `step`, a flag, a top bar with a 3-step stepper, and a full Setup step. The Setup step merges SetupForm with the interview-format options that today live only in SettingsModal.

## Key Insights
- Today, Setup only shows for `interviewType === "timed"`. Free mode drops the user straight onto the mic and has no "start" action.
- Format settings (free/timed, question limit, time per question, voice) are hidden in SettingsModal. Rubric mode + JD are duplicated in SetupForm and SettingsModal.
- `hasStarted` is only read by the timer (gated on `timed`), by the setup visibility and by the stress-camera effect. Setting it `true` in free mode is safe (verified in `useInterviewTimer.ts`).
- `useChat` restores `history` from `sessionStorage("interview_session_state")` on reload, but `config` is not persisted. After a reload, the user has a chat but `hasStarted=false`.
- `bootstrapInterviewContext` (page.tsx) must still run before the start, for BOTH modes (today it runs only for timed).

## Requirements
Functional:
- `step` is derived: `modals.report ? "report" : hasStarted ? "interview" : "setup"`.
- Setup step shows these fields:
  - position (required only for timed — keep the current rule), company, JD + JD template picker, rubric mode
  - format (Free / Timed + question limit + time per question), AI voice/language
  - Master CV status line
  - collapsed "Advanced options" (camera mode, per Open Question 4)
  - one Start button.
- Start = `bootstrapInterviewContext()`, then timed: `actions.startTimedInterview()`; free: `actions.startFreeInterview()`.
- Reload with a restored chat history goes to the interview step.
- `?next=` banner stays visible on every step.

Non-functional: each new file <200 lines. Theme tokens (`bg-theme-*`) and card style match ScreeningRoom (`rounded-2xl border border-theme-border bg-theme-primary p-5`).

## Architecture
```
page.tsx
 ├─ PRACTICE_STEP_FLOW=false -> <Sidebar/> + <InterviewLayout/>   (unchanged legacy)
 └─ PRACTICE_STEP_FLOW=true  -> <PracticeTopBar step=…/>
                                 step==="setup"     -> <SetupStep/>      (this phase)
                                 step==="interview" -> <InterviewStep/>  (phase 2; temp: InterviewLayout)
                                 step==="report"    -> <ReportStep/>     (phase 3; temp: ReportModal)
 Modals (Settings, GenCV, ReviewCV, CVMakeover, ResumeConfig, Subscription, Checkout) stay mounted as today.
```
Data flow: SetupStep edits `config` with `setConfig`. Start calls page `handleStart`, which runs `bootstrapInterviewContext` (writes `sessionStorage.interview_context`). Then a start action sets `hasStarted=true`, and the step becomes "interview".

## Related Code Files
Modify:
- `lib/features.ts`: add `export const PRACTICE_STEP_FLOW = process.env.NEXT_PUBLIC_PRACTICE_STEP_FLOW !== "false";` (the default depends on Open Question 9)
- `hooks/useInterviewActions.ts`: add `startFreeInterview` (`setHasStarted(true); resetTimer();`) and return it
- `components/Interview/SetupForm.tsx`: add the format, voice and JD-template sections; add an `advanced` slot (children). Generic copy: drop the "B2B AI Pre-Screening" pill and replace it with a candidate-facing title.
- `components/Modals/SettingsModal.tsx`: move the JD-template `<select>` + fetch into the shared component below, and import it
- `app/interview/page.tsx`: derive `step`, add `handleStart`, add a branch on the flag, add the reload-resume effect

Create:
- `components/Interview/steps/PracticeStepper.tsx`: 3 numbered pills (Setup / Interview / Report). Display only, not clickable.
- `components/Interview/steps/PracticeTopBar.tsx`: SpeakCV logo (link `/`), stepper, theme toggle, right-side slot (Prepare + user menus are added in phase 4)
- `components/Interview/steps/SetupStep.tsx`: wraps SetupForm + the Advanced section + a right-column slot (Recent practice, added in phase 4)
- `components/Interview/JdTemplatePicker.tsx`: extracted from SettingsModal (DRY, used by SetupForm + SettingsModal)

Delete: none.

## Implementation Steps
1. Add `PRACTICE_STEP_FLOW` to `lib/features.ts`.
2. Add `startFreeInterview` to `useInterviewActions.ts` (next to `startTimedInterview`).
3. Extract `JdTemplatePicker` from `SettingsModal.tsx` (lines 27-45 state/fetch + 194-208 select). Props: `onPick(description: string)`. Fetch on mount. Then use it in SettingsModal.
4. Extend `SetupForm.tsx`:
   - Add a Format block, ported from SettingsModal lines 70-134: Free/Timed buttons + 2 range sliders shown when timed.
   - Add a Voice select (SettingsModal 150-164).
   - Add `JdTemplatePicker` above the JD textarea.
   - Add a `children` slot before the Start button for Advanced options.
   - Change the button label to "Start practice". Keep `id="tour-step-start"`, and add `data-testid="start-practice"`.
   - If the file goes over 200 lines, move the format block into `components/Interview/SetupFormatFields.tsx`.
5. Create `PracticeStepper.tsx` (props `step`). Add `data-testid="practice-step-{name}"` and `aria-current="step"` on the active pill.
6. Create `PracticeTopBar.tsx` (props `step`, `right?: ReactNode`). Move the theme toggle out of InterviewLayout's absolute-positioned button (copy only — leave InterviewLayout as is).
7. Create `SetupStep.tsx`.
   - Props: config, setConfig, onStart, masterCv props, cameraMode + setCameraMode, `aside?: ReactNode`.
   - Two-column layout on md+ (form left, aside right); single column on mobile.
   - Advanced: a `<details>` element holding a "Camera mode (webcam + AI avatar)" checkbox.
8. In `page.tsx`:
   - `const step = modals.report ? "report" : hasStarted ? "interview" : "setup";`
   - `handleStart`: `if (!(await bootstrapInterviewContext())) return; config.interviewType === "timed" ? actions.startTimedInterview() : actions.startFreeInterview(); if (cameraMode) setIsCameraModeOpen(true);`
   - Reload-resume effect, run once after mount: `if (history.trim() && !hasStarted) setHasStarted(true)`. Guard it with a ref so it runs only once.
   - Branch on the flag. The flag-on branch renders TopBar + step content. For now, the interview step temporarily renders `<InterviewLayout>` without its setup (phase 2 replaces it). The report step keeps rendering `ReportModal` (phase 3 replaces it).
   - Keep the `nextHref` banner in both branches.
   - Store `cameraMode` in local `useState(false)` in page.tsx. Do NOT add it to `config`: `config` is sent to the API.
9. Run `npx tsc --noEmit` and `npm run lint` in `SpeakCV/src/frontend`.

## Todo List
- [ ] Flag in lib/features.ts
- [ ] startFreeInterview action
- [ ] JdTemplatePicker extracted + used in SettingsModal
- [ ] SetupForm format/voice/template/advanced slot
- [ ] PracticeStepper, PracticeTopBar, SetupStep
- [ ] page.tsx derived step + handleStart + reload resume + flag branch
- [ ] tsc + lint clean

## Success Criteria
- With the flag on, a fresh load shows the Setup step only: no mic, no chat, no sidebar. The stepper shows "Setup" as current.
- Start in Free mode lands on the interview step with no API call before the candidate speaks (same as today). Start in Timed mode calls `startTimedInterview` (the first question is fetched).
- Timed + empty position shows the toast "Please enter the position…" (existing rule).
- Reload mid-interview lands on the interview step with the restored AI text.
- With the flag off, the page is pixel-identical to today.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| Free mode now needs a Start click (one extra click vs today) | M x L | Accepted by the 3-step goal. Free mode needs no required fields, so Start is one click. |
| Reload resume sets `hasStarted` but `config` (position, timed) is lost | M x M | Existing behavior. Show the position badge only if present; the timer only shows if timed. Note: persisting `config` is out of scope. |
| Bootstrap now also runs for free mode, adding latency | L x L | It already no-ops without a Master CV + JD. Spinner text comes from `masterCvStatus`. |
| SettingsModal regression after extracting the picker | L x M | Manual check: the template still fills the JD in the modal. |

## Security Considerations
- `safeRedirect` for `?next=` is unchanged. JD text still only goes to the existing `buildInterviewContext` and `chatWithAI` calls. No new storage keys.

## Next Steps
Phase 2 replaces the temporary `InterviewLayout` inside the interview step.
