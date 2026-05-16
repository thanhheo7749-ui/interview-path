## 1. Component Enhancements

- [x] 1.1 Update `AvatarHR.tsx` SVG paths and adjust the mouth animation to use `transform="translate(0, offset)"` for the bottom lip instead of `scaleY`.
- [x] 1.2 Update `InlineCameraWidget.tsx` to accept an `isStressMode` prop and hide the close button when true.
- [x] 1.3 Update `InterviewLayout.tsx` and `useInterviewActions.ts` (if necessary) to automatically activate the camera and pass `isStressMode` to the widget when `config.mode === 'stress'`.

## 2. English UI Localization

- [x] 2.1 Translate all Vietnamese text in `src/frontend/components/Interview` components (e.g., `MicroButton`, `ChatBox`, `SetupForm`, `Sidebar`, `TimerDisplay`).
- [x] 2.2 Translate all Vietnamese text in `src/frontend/components/Modals` components (e.g., `SettingsModal`, `ReportModal`).
- [x] 2.3 Translate all Vietnamese text in `src/frontend/app/interview/page.tsx`.
- [x] 2.4 Translate any remaining hardcoded strings in related hooks or helper files used in the frontend.
