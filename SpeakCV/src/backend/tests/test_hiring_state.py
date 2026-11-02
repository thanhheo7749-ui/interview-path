import pytest

from app.hiring.state import InvalidTransition, advance
from app.database.sql_models import Application

ALLOWED = [
    ("submitted", "cv_processing"), ("cv_processing", "invited"), ("cv_processing", "cv_failed"),
    ("cv_failed", "cv_processing"), ("invited", "session_in_progress"), ("invited", "withdrawn"),
    ("invited", "declined_recording"), ("invited", "ready_for_hr"), ("declined_recording", "ready_for_hr"),
    ("session_in_progress", "session_completed"), ("session_in_progress", "ready_for_hr"),
    ("session_completed", "analyzing"), ("analyzing", "ready_for_hr"), ("analyzing", "session_completed"),
    ("ready_for_hr", "invited"),
]


@pytest.mark.parametrize("start,end", ALLOWED)
def test_allowed_transitions(start, end):
    application = Application(stage=start)
    advance(application, end)
    assert application.stage == end


@pytest.mark.parametrize("start,end", [
    ("submitted", "ready_for_hr"), ("invited", "session_completed"), ("withdrawn", "invited"),
    ("ready_for_hr", "withdrawn"), ("cv_failed", "ready_for_hr"), ("session_completed", "invited"),
])
def test_disallowed_transitions_raise_and_leave_the_stage(start, end):
    application = Application(stage=start)
    with pytest.raises(InvalidTransition):
        advance(application, end)
    assert application.stage == start
