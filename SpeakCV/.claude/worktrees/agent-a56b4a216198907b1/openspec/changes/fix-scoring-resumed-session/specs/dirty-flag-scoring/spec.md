## ADDED Requirements

### Requirement: Dirty flag invalidates cached report on new messages
The system SHALL maintain a `hasNewMessages` boolean flag that tracks whether new interview Q&A has occurred since the last session load or reset. When `hasNewMessages` is true, the system MUST call the backend `endInterview()` API to re-score the entire history, ignoring any cached `savedReport`.

#### Scenario: User resumes old session and continues interview
- **WHEN** user loads an old interview session, then sends one or more new messages
- **THEN** `hasNewMessages` flag SHALL be set to `true`

#### Scenario: User requests report after sending new messages
- **WHEN** user clicks "Kết thúc" (end interview) AND `hasNewMessages` is `true`
- **THEN** system SHALL ignore `savedReport` and call `endInterview()` API with the full accumulated history (old + new)

#### Scenario: User requests report without new messages
- **WHEN** user loads an old session and clicks "Kết thúc" WITHOUT sending any new messages
- **THEN** system SHALL display the cached `savedReport` immediately (fast display)

### Requirement: Flag resets on session boundaries
The system SHALL reset `hasNewMessages` to `false` at every session boundary to prevent stale state.

#### Scenario: Starting a new chat
- **WHEN** user clicks "Phỏng vấn mới" (new chat)
- **THEN** `hasNewMessages` SHALL be reset to `false`

#### Scenario: Retrying after report
- **WHEN** user clicks retry/start over from the report modal
- **THEN** `hasNewMessages` SHALL be reset to `false`

#### Scenario: Loading a different old session
- **WHEN** user loads a different old interview session via `handleConfirmResume`
- **THEN** `hasNewMessages` SHALL be reset to `false`
