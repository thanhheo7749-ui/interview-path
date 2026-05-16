## ADDED Requirements

### Requirement: Natural Jaw Translation Animation
The system SHALL animate the AI avatar's mouth by translating the Y coordinate of the bottom lip and interior mouth area based on audio amplitude, rather than scaling the entire mouth grouping.

#### Scenario: AI is speaking
- **WHEN** the `audioAmplitude` increases
- **THEN** the top lip remains static and the bottom lip translates downwards proportionally to the amplitude
