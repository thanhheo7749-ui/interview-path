# Phase 03 — Report step

## Context Links
- Overview: [plan.md](plan.md) — Open Questions 1, 10
- `components/Modals/ReportModal.tsx` (651 lines): helpers `DimensionBar` (31), `VoiceMetricsSection` (94), main body (194-628), footer (632-647)
- `hooks/useInterviewActions.ts`: `handleOpenReport` (192-246), `handleRetry` (248-258), `handleLoadOldInterview` (323-337)
- `app/interview/page.tsx`: inline `hasHistory` expression (382-391)

## Overview
- Priority: P2. Status: pending. Blocked by: Phase 2 and Open Question 1.
- The report becomes step 3, rendered inline (not an overlay). It reuses the exact report rendering, and adds the "next action" choices the candidate and HR care about.

## Key Insights
- `step` is already `"report"` whenever `modals.report` is true. No action changes are needed. Close (`toggleModal("report", false)`) returns to "interview" if `hasStarted`, else to "setup". That covers both "Continue interview" and "back from a history report".
- ReportModal has 3 render states:
  - no history: "No Interview Started"
  - result null while scoring: "Analyzing data…"
  - the full report.

  All 3 must survive.
- The footer "Start New Interview" button is gated by `LEGACY_B2C`. `/interview` itself requires `LEGACY_B2C`, so the button always shows here.
- `?next=` (from `/applications/[id]/fit` "Practice first") is HR's path back to the real recorded interview. The end of practice is the natural place for it as a primary CTA.
- Escape (`useKeyboardShortcuts.onCloseModal`) closes the report, which leaves the step. Acceptable; same as clicking "Continue".

## Requirements
Functional:
- `ReportStep` renders the same content as ReportModal, inline in the page, with no `fixed inset-0` overlay.
- While `isGeneratingReport && !reportData`, show a loading state ("Scoring your answers…") with `role="status"`.
- Actions:
  - "Continue interview": `toggleModal("report", false)`. Show it only when `hasStarted`.
  - "Practice again": `actions.handleRetry`.
  - "Back to setup": shown when the report was opened from history (`!hasStarted`). Same handler as close.
  - When `nextHref` is set: a primary "Go to the real interview →" link (Open Question 10).
- ReportModal keeps working unchanged for the flag-off path.

Non-functional: pure move of JSX. No change to the score fallbacks (`fallbackDecision`, `readiness_level` …).

## Architecture
```
ReportContent.tsx  (moved body: no-history / analyzing / full report, plus DimensionBar, VoiceMetricsSection)
  ├─ ReportModal.tsx  = overlay shell + header X + footer (legacy, unchanged behavior)
  └─ ReportStep.tsx   = inline card shell + loading state + step actions
```
Data: `reportData` (from `endInterview` or `normalizeHistoryReport`) and `hasHistory` (now computed once in page.tsx as a const) go to `ReportContent`.

## Related Code Files
Create:
- `components/Modals/ReportContent.tsx`: props `{ result, hasHistory, voiceMetrics? }`. It holds the body + helpers moved from ReportModal. If it exceeds 200 lines, also move `DimensionBar` and `VoiceMetricsSection` into `components/Modals/ReportSections.tsx` (the move is mechanical; the original is 651 lines).
- `components/Interview/steps/ReportStep.tsx`

Modify:
- `components/Modals/ReportModal.tsx`: render `<ReportContent>` inside the existing overlay/header/footer; no visual change
- `components/Modals/index.ts`: export `ReportContent`
- `app/interview/page.tsx`: hoist the `hasHistory` const. When the flag is on and `step==="report"`, render `<ReportStep>` and do NOT render `<ReportModal>`. The flag-off path still renders the modal.

Delete: none.

## Implementation Steps
1. Create `ReportContent.tsx`. Cut ReportModal lines 31-153 (helpers) and 168-628 (the three states: body only, no overlay or header).
   - Keep the "no history" branch as an inline card. The modal wraps it.
   - Keep `expandedIndex` state inside ReportContent.
   - Move the imports (lucide icons) with the code.
2. Reduce ReportModal: overlay div, header with title + X (lines 270-284), `<ReportContent/>`, footer (632-647). Make sure the no-history overlay variant still looks the same: the wrapper picks the `max-w-lg` vs `max-w-5xl` shell from `hasHistory`.
3. Create `ReportStep.tsx`.
   - Props: `result, hasHistory, isGenerating, hasStarted, nextHref, onContinue, onPracticeAgain, onBack`.
   - Shell: `max-w-5xl mx-auto rounded-2xl border border-theme-border bg-theme-primary`.
   - Sticky footer action bar.
   - testids: `practice-report`, `report-practice-again`, `report-continue`, `report-real-interview`.
4. Wire it in page.tsx (step switch). Pass `isGenerating={actions.isGeneratingReport}`.
5. Optional, only if Open Question 12 says "relabel": no change here (the history label is in phase 4).
6. Run `npx tsc --noEmit` and `npm run lint`.

## Todo List
- [ ] ReportContent extracted (+ ReportSections if needed)
- [ ] ReportModal slimmed, same visuals
- [ ] ReportStep built
- [ ] page.tsx switch + hasHistory hoist
- [ ] tsc + lint clean

## Success Criteria
- Finish during a chat shows the step-3 loading state, then the full report (score, HR banner, dimensions, Q&A accordion).
- Finish with an empty chat shows the "No Interview Started" card with a way back.
- "Practice again" returns to Setup with the chat cleared and the timer reset. "Continue interview" returns to the interview with the chat intact.
- Clicking a history item from Setup shows that report. "Back to setup" works.
- With `?next=` present, the real-interview CTA shows and navigates to `/applications/{id}/screening`.
- Flag off: ReportModal looks and behaves exactly as before.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| Large JSX move drops a section | M x H | Move by cut/paste of whole line ranges. Compare a rendered report before and after with the same `reportData` (phase 5). |
| Guest user (not logged in) hits Finish | L x M | `handleOpenReport` already toasts and returns before opening, so the step does not change. |
| Auto-finish in timed mode while the step switches | L x M | Existing `handleOpenReport(true)` path is unchanged. Only the render target differs. |

## Security Considerations
`nextHref` already passes through `safeRedirect`. Reuse the same variable; never use the raw search param.

## Next Steps
Phase 4: move the off-flow tools.
