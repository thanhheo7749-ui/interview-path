## Why

We want to refine the HR avatar animation to make it look more natural when speaking, enforce a strict environment (mandatory camera) for the "Stress" interview mode, and fully translate the application's UI hardcoded text to English to match a broader target audience, while maintaining the flexibility of choosing interview speaking language in settings.

## What Changes

- Translate all Vietnamese UI text (e.g., in Modals, ChatBox, Layouts, Buttons) to English.
- Implement mandatory camera logic for Stress mode (auto-open and hide the close button).
- Tweak AvatarHR SVG mouth animation to use `translateY` instead of `scaleY` for the bottom lip to improve realism.

## Capabilities

### New Capabilities
- `english-ui-localization`: UI components switch from Vietnamese to English strings.
- `stress-mode-camera`: Enhances "Stress Mode" to make the camera widget mandatory and unclosable.
- `avatar-mouth-animation`: Upgrades the mouth animation to use translateY on the bottom lip.

### Modified Capabilities

## Impact

- `src/frontend/components/Interview/AvatarHR.tsx`
- `src/frontend/components/Interview/InterviewLayout.tsx`
- `src/frontend/components/Interview/InlineCameraWidget.tsx`
- Dozens of UI components containing Vietnamese string literals.
