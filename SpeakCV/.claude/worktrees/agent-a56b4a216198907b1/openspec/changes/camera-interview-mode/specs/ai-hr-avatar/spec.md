## ADDED Requirements

### Requirement: AI HR avatar display
The system SHALL display an SVG-based AI HR avatar character with a professional, cartoon-style appearance (wearing a suit/vest, neat hair, serious but friendly expression).

#### Scenario: Avatar visible in camera interview
- **WHEN** the camera interview modal is open
- **THEN** the AI HR avatar SHALL be displayed in the designated area (right side on desktop, full-screen on mobile)

### Requirement: Lip-sync animation
The system SHALL animate the AI avatar's mouth in sync with the TTS audio output using Web Audio API amplitude analysis.

#### Scenario: AI is speaking
- **WHEN** TTS audio is playing
- **THEN** the avatar's mouth SHALL open and close proportionally to the audio amplitude, updated via requestAnimationFrame

#### Scenario: AI is silent
- **WHEN** no TTS audio is playing
- **THEN** the avatar's mouth SHALL remain in a neutral closed position

### Requirement: Idle animations
The system SHALL display idle animations on the AI avatar when not speaking to create a lifelike appearance.

#### Scenario: Blinking animation
- **WHEN** the avatar is displayed (regardless of speaking state)
- **THEN** the avatar SHALL perform a blinking animation at random intervals (every 2-5 seconds)

#### Scenario: Breathing animation
- **WHEN** the avatar is displayed
- **THEN** the avatar SHALL have a subtle continuous breathing motion (slight vertical scale oscillation)

### Requirement: Audio analyser connection
The system SHALL connect the TTS audio output to a Web Audio API AnalyserNode for real-time amplitude data.

#### Scenario: TTS audio plays through analyser
- **WHEN** the AI responds with TTS audio in camera interview mode
- **THEN** the audio SHALL be routed through an AudioContext AnalyserNode AND still play audibly to the user

#### Scenario: Analyser cleanup
- **WHEN** the camera interview modal is closed
- **THEN** the AudioContext and AnalyserNode SHALL be properly disconnected and closed
