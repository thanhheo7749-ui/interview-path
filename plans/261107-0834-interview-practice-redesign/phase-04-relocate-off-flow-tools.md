# Phase 04 — Relocate off-flow tools (hide, never delete)

## Context Links
- Overview: [plan.md](plan.md) — Open Questions 4-7, 12
- `components/Interview/Sidebar.tsx`: user menu (165-264), Tools menu (266-332), Practice History (334-520), Settings + Finish (522-545)
- Routes: `app/dashboard` and `app/questions` (both gated by `LEGACY_B2C`), `app/profile`, `app/admin`
- Modals mounted in page.tsx: GenCVModal (`cv`), ReviewCVModal (`review`), CVMakeover (`makeover`), SubscriptionModal, CheckoutModal

## Overview
- Priority: P2. Status: pending. Blocked by: Phase 3 and Open Questions 4-7.
- Every Sidebar feature gets a home in the step flow. Nothing is deleted. Sidebar.tsx stays the flag-off UI and gets thinner by reusing the extracted parts.

## Key Insights — placement table (default = recommended answers; adjust after answers)
| Item | Who wants it | New home (flag on) |
|---|---|---|
| Create CV / Review CV / Edit CV | candidate, before practice | Top-bar "Prepare" menu (opens the same modals). Also a "Create one" link in the Setup Master-CV line when no CV exists. |
| My Dashboard, Question Bank | candidate, between sessions | "Prepare" menu (router.push, logged-in only, as today) |
| Camera Interview | candidate option | Setup > Advanced (phase 1) + interview header toggle (phase 2) |
| Practice History (open, rename, delete, new) | candidate | "Recent practice" panel in the Setup step aside |
| Settings | candidate | Setup fields (phase 1) + interview gear (phase 2) |
| Finish & Score | candidate | Interview step button (phase 2) |
| Profile, Subscription, Admin, Logout, token count, Sign in | account | Top-bar user menu |
| "Real interview →" (`?next=`) | HR | Banner on all steps + Report CTA (phase 3) |

## Requirements
- Extract shared parts from Sidebar.tsx, so the Sidebar and the step flow render the same code (DRY):
  - `UserMenu`
  - `PrepareMenuItems` (the former Tools list)
  - `PracticeHistoryList`
- Sidebar keeps identical visuals and behavior.
- History click from Setup goes to `handleLoadOldInterview`, which opens the report step (phase 3). Rename and delete keep their optimistic update + rollback.
- Deleting the active history item still calls `handleRetry`.

## Architecture
```
Sidebar.tsx (legacy)            PracticeTopBar (flag on)          SetupStep aside
 ├ <UserMenu/>                   ├ <PrepareMenu> → <PrepareMenuItems/>   └ <PracticeHistoryList/>
 ├ Tools → <PrepareMenuItems/>   └ <UserMenu compact/>
 └ <PracticeHistoryList/>
```
Callbacks (`toggleModal`, `router.push`, `onOpenSubscription`, `logout`, `handleLoadOldInterview`, `handleRetry`, `setInterviewHistories`) are passed down from page.tsx, unchanged.

## Related Code Files
Create:
- `components/Interview/UserMenu.tsx`: moved from Sidebar 165-264. Props: `user, myProfileData, isAdmin, logout, onOpenSubscription, compact?`
- `components/Interview/PrepareMenuItems.tsx`: moved from Sidebar 284-329. Props: `user, toggleModal, onOpenCameraMode?, onItemClick?`. Show the Camera item only when `onOpenCameraMode` is passed, so the step flow can omit it per Open Question 4.
- `components/Interview/PracticeHistoryList.tsx`: moved from Sidebar 349-519 + `handleRename`/`handleDelete` (95-139) + `LockIcon`
- `components/Interview/steps/PrepareMenu.tsx`: dropdown button "Prepare" wrapping `PrepareMenuItems` (closes on item click / outside click / Escape)

Modify:
- `components/Interview/Sidebar.tsx`: replace the moved blocks with the new components (should drop from 566 to ~150 lines)
- `components/Interview/steps/PracticeTopBar.tsx`: render `<PrepareMenu/>` + `<UserMenu compact/>` in the right slot
- `components/Interview/steps/SetupStep.tsx`: aside = `<PracticeHistoryList/>` titled "Recent practice"; add a "Create one" link in the Master-CV line, calling `toggleModal("cv", true)`
- `app/interview/page.tsx`: pass the callbacks to the TopBar + SetupStep

Delete: none.

## Implementation Steps
1. Extract `PracticeHistoryList` (cut and paste; keep the date grouping, score colors, context menu and `confirm()` on delete). Use it in Sidebar, then check that the legacy sidebar is unchanged.
2. Extract `UserMenu` the same way. The `compact` variant shows only the avatar button and opens the same dropdown, right-aligned.
3. Extract `PrepareMenuItems`, then use it in the Sidebar Tools block.
4. Create `PrepareMenu.tsx` (button + popover; `aria-expanded`, `aria-haspopup="menu"`).
5. Fill the TopBar right slot and the SetupStep aside. On mobile, the aside goes below the form, collapsed in a `<details>`.
6. Open Question 12, only if approved: change the history label "Continue →" to "View report →" in `PracticeHistoryList`. This affects both layouts.
7. Run `npx tsc --noEmit` and `npm run lint`.

## Todo List
- [ ] PracticeHistoryList extracted + used in Sidebar
- [ ] UserMenu extracted + used in Sidebar
- [ ] PrepareMenuItems extracted + used in Sidebar
- [ ] PrepareMenu in TopBar
- [ ] SetupStep aside + Create CV link
- [ ] tsc + lint clean

## Success Criteria
- Every row of the placement table can be reached with the flag on. Click-through checklist in phase 5.
- With the flag off, the Sidebar renders and behaves the same, item by item.
- No feature code removed. `git diff --stat` shows only moves and additions in `components/Interview/*`, `components/Modals/*` and `app/interview/page.tsx`.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| Rename/delete rollback breaks after the move | L x H | Move the handlers together with the list. Test a delete with the network offline (the rollback toast appears). |
| Dropdown z-index under the camera widget / hint | M x L | TopBar `z-40`, popovers `z-50` (same as today's Sidebar). |
| Guests see "Prepare" items that need login | L x L | Keep the `user &&` guard from the Sidebar for Dashboard/Questions/Camera. |

## Security Considerations
The Admin link stays behind `isAdmin` (from `getAdminDashboard` success). Moving it is UI only; the server still enforces access.

## Next Steps
Phase 5: verification.
