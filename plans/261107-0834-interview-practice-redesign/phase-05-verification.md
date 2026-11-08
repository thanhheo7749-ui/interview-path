# Phase 05 — Verification

## Context Links
- Overview: [plan.md](plan.md) — Open Question 13 (where automated tests live)
- `SpeakCV/src/frontend/package.json`: scripts `build` (`next build --webpack`) and `lint`. No unit-test runner exists.
- Playwright harness (other project): `interviewpath/interviewpath-demo/playwright.config.js`. It starts SpeakCV with `next dev` on port 3199 WITHOUT `NEXT_PUBLIC_LEGACY_B2C_ENABLED`, so `/interview` 404s there today.

## Overview
- Priority: P2. Status: pending. Blocked by: Phases 1-4.
- Prove: (1) the code compiles; (2) the step flow works end to end; (3) the flag-off path is unchanged; (4) no feature became unreachable.

## Key Insights
- Adding vitest or jest to SpeakCV/frontend just for this would be new infra (YAGNI) unless the user picks it (Open Question 13c).
- All new logic is UI wiring. The only new branching is the derived `step` and `handleStart`, which the manual matrix covers.
- Phases 1-4 added testids for a later spec: `practice-step-*`, `start-practice`, `practice-mic`, `practice-answer`, `practice-ai-text`, `finish-practice`, `practice-report`, `report-*`.

## Requirements
- `npx tsc --noEmit`, `npm run lint` and `npm run build` must all pass. Run them with the flag both on and off: `NEXT_PUBLIC_LEGACY_B2C_ENABLED=true NEXT_PUBLIC_PRACTICE_STEP_FLOW=…`.
- Manual matrix below, on desktop (1440px) and mobile (390px), in light + dark theme.

## Test Matrix
| # | Scenario | Expected |
|---|---|---|
| 1 | Fresh load, logged in | Setup step only; stepper = Setup |
| 2 | Free + Start | Interview step; mic works; typed answer sends; AI text updates |
| 3 | Timed, empty position | Toast, stays on Setup |
| 4 | Timed, 3 questions, 30s | Q 1/3 + countdown; timeout auto-sends; after Q3, auto report |
| 5 | Finish mid-chat | Report loading, then full report |
| 6 | Finish with empty chat | "No Interview Started" + way back |
| 7 | Report > Continue | Back to interview, chat intact |
| 8 | Report > Practice again | Setup, chat cleared |
| 9 | Recent practice click | Report of that history; Back to setup works |
| 10 | Rename / delete history | Optimistic update; offline: rollback toast |
| 11 | Prepare > Create/Review/Edit CV | Same modals open |
| 12 | Prepare > Dashboard / Question Bank | Routes load |
| 13 | Advanced > Camera on + Start | Webcam + avatar shown; header toggle hides it |
| 14 | Hint (desktop popover, mobile swipe) | Shows and dismisses |
| 15 | Gear in interview | SettingsModal opens; voice change applies to the next reply |
| 16 | Reload mid-interview | Lands on interview step with restored AI text |
| 17 | `/interview?next=/applications/1/screening` | Banner on all steps + Report CTA navigates there |
| 18 | `?next=https://evil.com` | No banner (`safeRedirect`) |
| 19 | Guest user | Can practice; Finish shows the login toast; guest 10-message cap still applies |
| 20 | Shortcuts Space / Ctrl+N / Ctrl+R / Ctrl+, / Esc | Same as today |
| 21 | Flag off | Old Sidebar + InterviewLayout, identical behavior |
| 22 | Side by side with `/applications/[id]/screening` | Same mic size, card radius/border, label style |

## Related Code Files
Create (only if Open Question 13 = b): `interviewpath/interviewpath-demo/e2e/practice-flow.spec.js` (cases 1, 2, 5, 8). It also needs `NEXT_PUBLIC_LEGACY_B2C_ENABLED: 'true'` added to the SpeakCV `webServer.env` in `interviewpath/interviewpath-demo/playwright.config.js`. That is a cross-project edit, so it needs your approval.
Modify / Delete: none otherwise.

## Implementation Steps
1. In `SpeakCV/src/frontend`, run `npx tsc --noEmit && npm run lint`.
2. Run `NEXT_PUBLIC_LEGACY_B2C_ENABLED=true npm run build`, then the same with `NEXT_PUBLIC_PRACTICE_STEP_FLOW=false`.
3. Run `NEXT_PUBLIC_LEGACY_B2C_ENABLED=true npm run dev` with the backend up. Walk the matrix and record pass/fail in `reports/verification-<date>.md` in this plan folder.
4. Only if 13b is approved: write the Playwright spec using the testids. Run `npx playwright test e2e/practice-flow.spec.js` from `interviewpath-demo`.
5. Delegate a code review (code-reviewer agent) of the diff.

## Todo List
- [ ] tsc + lint
- [ ] build flag on / off
- [ ] Manual matrix 1-22
- [ ] (optional) Playwright spec
- [ ] Code review

## Success Criteria
- All commands exit 0, and matrix rows 1-22 pass.
- Every Sidebar feature can be reached in the flag-on UI (rows 9-15, 19).
- Flag-off row 21 passes, which proves the rollback.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| Manual matrix is skipped or rushed | M x M | Report file with a row-by-row result is required before marking the plan complete. |
| AI backend unavailable locally | M x M | Rows 2/4/5 need it. Otherwise rows 1, 3, 6, 9-14 and 17-22 still run. |

## Security Considerations
Row 18 covers the open-redirect guard. No secrets in test files.

## Next Steps / Rollback
- Rollback: set `NEXT_PUBLIC_PRACTICE_STEP_FLOW=false` and rebuild. The old UI returns, and no data or API changes need reverting.
- After a stable release, ask the user whether to retire the legacy layout. Do not remove it without a decision (the user's no-delete rule).
