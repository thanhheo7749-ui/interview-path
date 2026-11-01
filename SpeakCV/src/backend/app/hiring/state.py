STAGES = (
    "submitted", "cv_processing", "cv_failed", "invited", "withdrawn", "declined_recording",
    "session_in_progress", "session_completed", "analyzing", "ready_for_hr",
)
TRANSITIONS = {
    "submitted": {"cv_processing"},
    "cv_processing": {"invited", "cv_failed"},
    "cv_failed": {"cv_processing"},
    "invited": {"session_in_progress", "withdrawn", "declined_recording", "ready_for_hr"},
    "declined_recording": {"ready_for_hr"},
    "session_in_progress": {"session_completed", "ready_for_hr"},
    "session_completed": {"analyzing"},
    "analyzing": {"ready_for_hr"},
    "ready_for_hr": {"invited"},
    "withdrawn": set(),
}


class InvalidTransition(ValueError):
    pass


def advance(application, to_stage: str) -> None:
    if to_stage not in TRANSITIONS.get(application.stage, set()):
        raise InvalidTransition(f"Cannot move from {application.stage} to {to_stage}")
    application.stage = to_stage
