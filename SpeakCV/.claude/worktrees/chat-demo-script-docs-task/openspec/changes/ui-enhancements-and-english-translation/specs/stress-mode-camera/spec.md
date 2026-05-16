## ADDED Requirements

### Requirement: Mandatory Camera in Stress Mode
The system SHALL automatically display the inline camera widget and prevent the user from closing it when the interview mode is set to "stress".

#### Scenario: User starts an interview in Stress mode
- **WHEN** the interview session begins with `config.mode` equal to "stress"
- **THEN** the `isCameraModeOpen` state is forced to true, and the inline camera widget's close button is hidden.
