## ADDED Requirements

### Requirement: Camera interview modal activation
The system SHALL provide a "Phỏng vấn Camera" button in the Sidebar tools menu that opens a full-screen camera interview overlay.

#### Scenario: User opens camera interview from tools menu
- **WHEN** user clicks "Phỏng vấn Camera" in the Công cụ dropdown
- **THEN** a full-screen modal overlay SHALL open displaying the camera interview interface

#### Scenario: User closes camera interview
- **WHEN** user clicks the close/end button on the camera interview modal
- **THEN** the modal SHALL close, webcam stream SHALL stop, and user returns to the normal interview interface

### Requirement: Webcam display
The system SHALL display the user's webcam feed in real-time within the camera interview interface.

#### Scenario: Webcam permission granted
- **WHEN** user grants camera permission
- **THEN** the system SHALL display a mirrored live video feed of the user

#### Scenario: Webcam permission denied
- **WHEN** user denies camera permission
- **THEN** the system SHALL display a placeholder avatar instead of webcam feed and the interview SHALL still function normally (audio only)

#### Scenario: Webcam cleanup on close
- **WHEN** user closes the camera interview modal
- **THEN** the system SHALL stop all media tracks from the webcam stream to release the camera

### Requirement: Desktop layout
The system SHALL display the camera interview in a side-by-side layout on desktop screens (≥768px).

#### Scenario: Desktop side-by-side display
- **WHEN** the viewport width is ≥768px
- **THEN** the user webcam SHALL be displayed on the left side and the AI avatar SHALL be displayed on the right side, both equally sized

### Requirement: Mobile layout
The system SHALL display the camera interview in a Zalo-style video call layout on mobile screens (<768px).

#### Scenario: Mobile PiP display
- **WHEN** the viewport width is <768px
- **THEN** the AI avatar SHALL be displayed full-screen and the user webcam SHALL be displayed as a small picture-in-picture overlay in the top-right corner

### Requirement: Interview controls
The system SHALL display interview control buttons at the bottom of the camera interview overlay.

#### Scenario: Microphone control
- **WHEN** user taps the microphone button
- **THEN** the system SHALL toggle recording (same behavior as existing MicroButton)

#### Scenario: End interview control
- **WHEN** user taps the end call button
- **THEN** the system SHALL close the camera interview and trigger the end-interview report flow

### Requirement: Reuse existing interview APIs
The camera interview mode SHALL reuse the existing backend APIs without modifications.

#### Scenario: Audio transcription
- **WHEN** user speaks during camera interview
- **THEN** the system SHALL send audio to `/api/transcribe` (same as current flow)

#### Scenario: AI response
- **WHEN** transcription is complete
- **THEN** the system SHALL send the text to `/api/chat` and play the TTS audio response (same as current flow)
