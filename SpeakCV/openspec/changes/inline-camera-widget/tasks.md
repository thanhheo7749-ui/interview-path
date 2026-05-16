## 1. Widget Component Creation

- [x] 1.1 Create `InlineCameraWidget.tsx` component
- [x] 1.2 Move and adapt `WebcamView` and `AvatarHR` into `InlineCameraWidget` with side-by-side (desktop) and PiP (mobile) layout
- [x] 1.3 Implement the close (X) button logic within the widget to toggle `isCameraModeOpen`

## 2. Layout Integration

- [x] 2.1 Pass `isCameraModeOpen` and `setIsCameraModeOpen` props down to `InterviewLayout`
- [x] 2.2 Import and render `InlineCameraWidget` inside `InterviewLayout` directly above `MicroButton`
- [x] 2.3 Add layout animation (`animate-in slide-in-from-top`) to the widget to push content down smoothly

## 3. Cleanup

- [x] 3.1 Remove `CameraInterviewModal` from `src/frontend/app/interview/page.tsx`
- [x] 3.2 Delete `CameraInterviewModal.tsx` file as it's no longer used
