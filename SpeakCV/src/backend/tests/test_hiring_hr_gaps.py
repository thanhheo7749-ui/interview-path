"""HR's side of the interview: long pauses, who can be restarted, and what a decision or a restart sends."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.database.sql_models import Application, Notification, VoiceTurn
from app.hiring import board, notify
from app.main import create_app
from tests.helpers_board import make_application, make_session, make_world


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def api():
    return TestClient(create_app())


def url(world, tail):
    return f"/api/companies/{world['company'].id}{tail}"


def hr(world):
    return world["people"]["hr"]["headers"]


def detail(api, world, application):
    return api.get(url(world, f"/applications/{application.id}"), headers=hr(world)).json()


def set_times(db, rows, gaps):
    """Each turn is asked at some moment and answered `gap` seconds later."""
    for row, gap in zip(rows, gaps):
        asked = row.created_at
        row.answered_at = asked + timedelta(seconds=gap)
    db.commit()


# M-11. A long pause


def test_a_gap_over_ten_minutes_between_question_and_answer_is_noted(db, world, api):
    application = make_application(db, world["job"])
    _, rows = make_session(db, application, [(1, "Q1", "a1", None), (2, "Q2", "a2", None)])
    set_times(db, rows, [30, 601])
    assert detail(api, world, application)["long_pause"] is True


def test_exactly_ten_minutes_or_less_is_not_noted(db, world, api):
    application = make_application(db, world["job"])
    _, rows = make_session(db, application, [(1, "Q1", "a1", None), (2, "Q2", "a2", None)])
    set_times(db, rows, [600, 5])
    assert detail(api, world, application)["long_pause"] is False


def test_unanswered_turns_do_not_count(db, world, api):
    application = make_application(db, world["job"])
    make_session(db, application, [(1, "Q1", "a1", None)])
    assert detail(api, world, application)["long_pause"] is False


def test_a_long_pause_changes_no_label_band_or_cell(db, world, api):
    application = make_application(db, world["job"], band="many")
    _, rows = make_session(db, application, [(1, "Q1", "a1", None)])
    before = detail(api, world, application)
    set_times(db, rows, [3 * 3600])
    after = detail(api, world, application)
    assert after["long_pause"] is True
    for key in ("cv_status", "interview_band", "cell", "analysis_status", "hr_decision", "suggestion", "requirements"):
        assert after[key] == before[key]


# M-13. Restart only where it can work


def test_restart_is_available_for_a_session_awaiting_review_that_was_not_restarted(db, world, api):
    application = make_application(db, world["job"])
    make_session(db, application, [(1, "Q", "ans", None)])
    assert detail(api, world, application)["restart_available"] is True


def test_restart_is_not_offered_to_a_fast_tracked_application(db, world, api):
    application = make_application(db, world["job"], fast_tracked=True)
    assert detail(api, world, application)["restart_available"] is False


def test_restart_is_not_offered_when_there_is_no_session(db, world, api):
    application = make_application(db, world["job"])
    assert detail(api, world, application)["restart_available"] is False


def test_restart_is_not_offered_twice(db, world, api):
    application = make_application(db, world["job"])
    make_session(db, application, [(1, "Q", "ans", None)], restart_count=1)
    assert detail(api, world, application)["restart_available"] is False


def test_restart_is_not_offered_after_a_decision(db, world, api):
    application = make_application(db, world["job"], hr_decision="approved")
    make_session(db, application, [(1, "Q", "ans", None)])
    assert detail(api, world, application)["restart_available"] is False


def test_restart_is_not_offered_before_review(db, world, api):
    application = make_application(db, world["job"], stage="invited")
    make_session(db, application, [(1, "Q", "ans", None)])
    assert detail(api, world, application)["restart_available"] is False


def test_the_flag_agrees_with_what_the_route_accepts(db, world, api):
    application = make_application(db, world["job"])
    make_session(db, application, [(1, "Q", "ans", None)])
    assert detail(api, world, application)["restart_available"] is True
    assert api.post(url(world, f"/applications/{application.id}/restart"), headers=hr(world)).status_code == 200


# M-13. Notifications leave at once, and a restart sends one


@pytest.fixture
def delivered(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "deliver_pending", lambda: calls.append(1))
    return calls


def test_a_decision_delivers_its_notification_at_once(db, world, api, delivered):
    application = make_application(db, world["job"], band="many")
    response = api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world),
                        json={"decision": "approved"})
    assert response.status_code == 200 and delivered == [1]


def test_a_refused_decision_delivers_nothing(db, world, api, delivered):
    application = make_application(db, world["job"], stage="invited")
    response = api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world),
                        json={"decision": "approved"})
    assert response.status_code == 409 and delivered == []


def test_a_bulk_rejection_delivers_once(db, world, api, delivered):
    first = make_application(db, world["job"], alias="#A1")
    second = make_application(db, world["job"], alias="#A2")
    response = api.post(url(world, f"/jobs/{world['job'].id}/decisions/bulk"), headers=hr(world),
                        json={"application_ids": [first.id, second.id]})
    assert response.status_code == 200 and delivered == [1]


def test_a_restart_queues_a_generic_notification_and_delivers_it(db, world, api, delivered):
    application = make_application(db, world["job"], band="many")
    make_session(db, application, [(1, "Q", "ans", None)])
    assert api.post(url(world, f"/applications/{application.id}/restart"), headers=hr(world)).status_code == 200
    row = db.query(Notification).filter_by(application_id=application.id, kind="restart").one()
    assert row.user_id == application.candidate_user_id and row.status == "pending"
    text = f"{row.subject} {row.body}".lower()
    for word in ("band", "priority", "meets", "not_met", "label", "score", "ai"):
        assert word not in text.split()
    assert "interview" in text
    assert delivered == [1]


def test_a_restart_in_the_companys_language(db, world, api):
    world["company"].default_locale = "vi"
    db.commit()
    application = make_application(db, world["job"])
    make_session(db, application, [(1, "Q", "ans", None)])
    api.post(url(world, f"/applications/{application.id}/restart"), headers=hr(world))
    row = db.query(Notification).filter_by(application_id=application.id, kind="restart").one()
    assert row.language == "vi" and "phỏng vấn" in row.body


def test_a_refused_restart_sends_nothing(db, world, api, delivered):
    application = make_application(db, world["job"], fast_tracked=True)
    assert api.post(url(world, f"/applications/{application.id}/restart"), headers=hr(world)).status_code == 409
    assert db.query(Notification).filter_by(kind="restart").count() == 0 and delivered == []
