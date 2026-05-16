## Context

Currently, the web application UI is completely hardcoded in Vietnamese. The HR Avatar animation utilizes a basic `scaleY` approach for the mouth opening which distorts the lip thickness when speaking loudly. Finally, the "Stress" interview mode doesn't feel much different from the regular mode in terms of environment. The user wishes to translate the entire UI to English, make the camera mandatory and unclosable in stress mode, and improve the mouth animation using a more natural downward translation of the jaw rather than stretching the whole mouth group.

## Goals / Non-Goals

**Goals:**
- Completely translate all hardcoded Vietnamese text in the UI to English.
- Implement UI restrictions for `config.mode === 'stress'` to enforce the camera widget being open and unclosable.
- Adjust SVG paths and grouping in `AvatarHR.tsx` to allow `translateY` for the bottom lip instead of `scaleY`.

**Non-Goals:**
- Implementing a dynamic localization library (like `next-intl` or `react-i18next`). The translation will be a direct hardcoded replacement, as per the user's direction.
- Modifying the AI's spoken language logic or backend prompts (this is already controlled via the user's voice/language settings).
- Handling browser camera permission denial explicitly with custom fallbacks (we will rely on standard browser behaviors for blocked cameras).

## Decisions

1. **Hardcoded Translation**: We will perform a direct find-and-replace across all React components to change Vietnamese strings to English. This avoids adding a heavyweight i18n context or library, keeping the codebase simple and performant.
2. **AvatarHR Animation**: We will use a `transform="translate(0, offset)"` on the bottom lip and mouth interior based on `audioAmplitude`. The top lip will remain static. This prevents the lips from artificially thickening when the mouth is wide open, mimicking natural jaw movement.
3. **Stress Mode Camera**: We will pass `isStressMode` to `InlineCameraWidget`. When `true`, the `onClose` callback and the close "X" button will simply not render. In `InterviewLayout`, starting a timed interview in stress mode will automatically set `isCameraModeOpen` to `true`.

## Risks / Trade-offs

- **Risk**: Hardcoding English text makes reverting to Vietnamese difficult later.
  - **Mitigation**: This is explicitly requested by the user ("cứ để là tiếng anh hết đi").
- **Risk**: SVG translation might cause the bottom lip to clip out of the chin if the multiplier is too high.
  - **Mitigation**: We will set a reasonable upper bound for the translation offset (e.g., maximum 10-15px) to ensure the lip stays within the face bounds.
