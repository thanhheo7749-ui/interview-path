STAGES = (
    "submitted", "missing_contact", "cv_processing", "cv_failed", "cv_hold",
    "invited", "withdrawn", "declined_recording",
    "session_in_progress", "session_completed", "analyzing", "ready_for_hr",
)
TRANSITIONS = {
    "submitted": {"cv_processing", "missing_contact"},
    "missing_contact": {"cv_processing", "withdrawn"},
    "cv_processing": {"invited", "cv_hold", "cv_failed", "missing_contact"},
    "cv_failed": {"cv_processing", "invited", "withdrawn"},  # invited by HR's hand only: the CV gave no label
    "cv_hold": {"invited", "ready_for_hr", "withdrawn"},
    "invited": {"session_in_progress", "withdrawn", "declined_recording", "ready_for_hr"},
    "declined_recording": {"ready_for_hr"},
    "session_in_progress": {"session_completed", "ready_for_hr"},
    "session_completed": {"analyzing"},
    "analyzing": {"ready_for_hr", "session_completed"},  # back to waiting only when a crash stopped the analysis
    "ready_for_hr": {"invited"},
    "withdrawn": set(),
}
# `analysis_status` when there was nothing to analyse: the candidate said nothing.
NOT_TAKEN = "not_taken"
# `analysis_status` once the candidate withdrew recording consent: nothing said is kept, and none of it is analysed.
CONSENT_WITHDRAWN = "consent_withdrawn"
# `analysis_status` when the candidate spoke and speech-to-text could not hear it: a technical problem, for HR to retry.
TRANSCRIPTION_FAILED = "transcription_failed"


class InvalidTransition(ValueError):
    pass


def advance(application, to_stage: str) -> None:
    if to_stage not in TRANSITIONS.get(application.stage, set()):
        raise InvalidTransition(f"Cannot move from {application.stage} to {to_stage}")
    application.stage = to_stage
