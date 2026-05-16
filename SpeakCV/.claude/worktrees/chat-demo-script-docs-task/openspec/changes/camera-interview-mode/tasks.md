## 1. Core UI Components

- [x] 1.1 Create `WebcamView` component to handle `getUserMedia` logic and video rendering
- [x] 1.2 Create `AvatarHR` component with SVG illustration and idle animations (blink, breathing)
- [x] 1.3 Create `CameraInterviewModal` component to host the video call UI and manage responsive layout (side-by-side vs PiP)

## 2. Audio Analysis & Lip-sync

- [x] 2.1 Implement `AudioContext` and `AnalyserNode` logic to process TTS audio output
- [x] 2.2 Map audio amplitude data to `scaleY` CSS transform for the avatar's mouth element
- [x] 2.3 Integrate audio analysis hook into the `AvatarHR` component for real-time lip-sync

## 3. Integration & Controls

- [x] 3.1 Update `Sidebar.tsx` to include the "Phỏng vấn Camera" button in the Tools menu
- [x] 3.2 Wire up `CameraInterviewModal` with existing interview state (chat history, audio playback)
- [x] 3.3 Implement interview controls within the modal (Microphone toggle, End call)
- [x] 3.4 Ensure proper cleanup of webcam stream and audio context when the modal is closed
