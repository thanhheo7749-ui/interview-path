## ADDED Requirements

### Requirement: Inline camera widget rendering
The system SHALL display the camera and AI avatar as an inline widget within the main interview layout rather than a full-screen modal overlay.

#### Scenario: User enables camera mode
- **WHEN** user clicks "Phỏng vấn Camera" from the Tools menu in the sidebar
- **THEN** the inline camera widget SHALL appear smoothly above the microphone button, pushing the microphone and chat box downwards.

#### Scenario: User disables camera mode
- **WHEN** user clicks the close (X) button inside the inline camera widget
- **THEN** the widget SHALL disappear, and the microphone and chat box SHALL animate back to their original positions.

### Requirement: Compact desktop layout
The system SHALL display the inline camera widget in a side-by-side layout with limited height on desktop to preserve vertical space.

#### Scenario: Desktop side-by-side view
- **WHEN** the viewport width is ≥768px (desktop/tablet)
- **THEN** the widget SHALL display the user's webcam and the AI avatar side-by-side within a contained, rounded frame with a maximum height limit.

### Requirement: Mobile layout
The system SHALL display the inline camera widget in a compact Picture-in-Picture layout on mobile devices.

#### Scenario: Mobile PiP view
- **WHEN** the viewport width is <768px (mobile)
- **THEN** the widget SHALL display the AI avatar prominently with the user's webcam rendered as a smaller picture-in-picture overlay.
