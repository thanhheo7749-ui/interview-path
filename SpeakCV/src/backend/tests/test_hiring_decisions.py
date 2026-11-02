import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.providers import fake
from app.database.sql_models import Application, AuditLog, Notification, VoiceSession
from app.hiring import decisions
from app.main import create_app
from tests.helpers_board import CANDIDATE_EMAIL, CANDIDATE_NAME, make_application, make_session, make_world

BACKEND = Path(__file__).resolve().parents[1]


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


def _reload(db, application_id):
    db.rollback()
    db.expire_all()
    return db.get(Application, application_id)


def test_only_decisions_module_writes_hr_decision():
    offenders = []
    for path in (BACKEND / "app").rglob("*.py"):
        if path.name == "decisions.py" or path.name.startswith("models_"):
            continue
        if re.search(r"\.hr_decision\s*=[^=]|hr_decision\s*=\s*[\"']", path.read_text(encoding="utf-8")):
            offenders.append(str(path))
    assert offenders == []


def test_a_simulated_decision_is_refused_on_a_real_application(db, world):
    application = make_application(db, world["job"], band="many")
    with pytest.raises(ValueError, match="simulated"):
        decisions.record_simulated(application, "approved", datetime(2026, 9, 1))
    assert application.hr_decision == "pending" and application.hr_decided_at is None


def test_a_simulated_decision_leaves_no_audit_row_or_notification(db, world):
    application = make_application(db, world["job"], "#S1", band="many", is_simulated=True)
    decisions.record_simulated(application, "rejected", datetime(2026, 9, 1))
    db.commit()
    row = _reload(db, application.id)
    assert (row.hr_decision, row.hr_decided_by) == ("rejected", None)
    assert row.hr_decided_at.replace(tzinfo=None) == datetime(2026, 9, 1)
    assert db.query(AuditLog).filter_by(action="hr_decision").count() == 0
    assert db.query(Notification).count() == 0


def test_a_simulated_decision_must_be_a_real_decision_value(db, world):
    application = make_application(db, world["job"], "#S1", band="many", is_simulated=True)
    with pytest.raises(ValueError, match="approved or rejected"):
        decisions.record_simulated(application, "maybe", datetime(2026, 9, 1))


def test_approve_records_who_when_audit_and_notification(db, world, api):
    application = make_application(db, world["job"], band="many")
    response = api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world),
                        json={"decision": "approved", "reason": "great"})
    assert response.status_code == 200, response.text
    row = _reload(db, application.id)
    assert row.hr_decision == "approved"
    assert row.hr_decided_by == world["people"]["hr"]["id"] and row.hr_decided_at is not None
    audit = db.query(AuditLog).filter_by(action="hr_decision", target_id=application.id).one()
    assert audit.actor_user_id == world["people"]["hr"]["id"] and audit.ai_provider is None
    assert audit.payload["decision"] == "approved"
    assert db.query(Notification).filter_by(user_id=row.candidate_user_id, kind="decision").count() == 1


def test_reject_sends_a_generic_notification_with_no_reasons_or_labels(db, world, api):
    application = make_application(db, world["job"], cv_status="not_met", band="few")
    response = api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world),
                        json={"decision": "rejected", "reason": "SECRETREASON lacks Docker"})
    assert response.status_code == 200
    note = db.query(Notification).filter_by(kind="decision").one()
    text = f"{note.subject} {note.body}".lower()
    for forbidden in ("secretreason", "docker", "not_met", "few", "band", "score", "cv"):
        assert forbidden not in text
    assert "Backend" in note.body


def test_deciding_twice_or_in_the_wrong_stage_is_409(db, world, api):
    application = make_application(db, world["job"])
    path = url(world, f"/applications/{application.id}/decision")
    assert api.post(path, headers=hr(world), json={"decision": "approved"}).status_code == 200
    assert api.post(path, headers=hr(world), json={"decision": "rejected"}).status_code == 409
    early = make_application(db, world["job"], alias="#A2", stage="invited")
    assert api.post(url(world, f"/applications/{early.id}/decision"), headers=hr(world),
                    json={"decision": "approved"}).status_code == 409
    assert _reload(db, early.id).hr_decision == "pending"


def test_decision_value_is_validated(db, world, api):
    application = make_application(db, world["job"])
    response = api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world),
                        json={"decision": "maybe"})
    assert response.status_code == 422


def test_other_company_and_non_hr_cannot_decide(db, world, api):
    application = make_application(db, world["job"])
    path = url(world, f"/applications/{application.id}/decision")
    assert api.post(path, headers=world["people"]["emp"]["headers"], json={"decision": "approved"}).status_code == 403
    other_path = f"/api/companies/{world['other'].id}/applications/{application.id}/decision"
    assert api.post(other_path, headers=world["people"]["hr2"]["headers"], json={"decision": "approved"}).status_code == 404
    assert _reload(db, application.id).hr_decision == "pending"


def test_cv_status_needs_a_reason_and_is_logged(db, world, api):
    application = make_application(db, world["job"], cv_status="not_met", band="many")
    path = url(world, f"/applications/{application.id}/cv-status")
    assert api.post(path, headers=hr(world), json={"cv_status": "meets"}).status_code == 422
    assert api.post(path, headers=hr(world), json={"cv_status": "meets", "reason": "   "}).status_code == 422
    assert api.post(path, headers=hr(world), json={"cv_status": "bogus", "reason": "x"}).status_code == 422
    assert _reload(db, application.id).cv_status == "not_met"
    response = api.post(path, headers=hr(world), json={"cv_status": "meets", "reason": "Docker is on page two"})
    assert response.status_code == 200
    row = _reload(db, application.id)
    assert row.cv_status == "meets" and row.cv_status_corrected_by == world["people"]["hr"]["id"]
    assert row.cv_status_correction_reason == "Docker is on page two"
    audit = db.query(AuditLog).filter_by(action="cv_status_corrected", target_id=application.id).one()
    assert audit.payload["from"] == "not_met" and audit.payload["to"] == "meets"


def test_bulk_reject_is_one_transaction(db, world, api):
    first = make_application(db, world["job"], alias="#A1", cv_status="not_met", band="few")
    second = make_application(db, world["job"], alias="#A2", cv_status="not_met", band="few")
    foreign = make_application(db, world["other_job"], alias="#A1", stage="ready_for_hr")
    path = url(world, f"/jobs/{world['job'].id}/decisions/bulk")
    response = api.post(path, headers=hr(world), json={"application_ids": [first.id, second.id, foreign.id]})
    assert response.status_code == 404
    assert _reload(db, first.id).hr_decision == "pending" and _reload(db, second.id).hr_decision == "pending"
    assert db.query(Notification).count() == 0
    response = api.post(path, headers=hr(world), json={"application_ids": [first.id, second.id], "reason": "pool"})
    assert response.status_code == 200 and response.json()["rejected"] == 2
    assert _reload(db, first.id).hr_decision == "rejected" and _reload(db, second.id).hr_decision == "rejected"
    assert db.query(Notification).filter_by(kind="decision").count() == 2
    # an already decided one rolls the whole batch back
    third = make_application(db, world["job"], alias="#A3")
    again = api.post(path, headers=hr(world), json={"application_ids": [third.id, first.id]})
    assert again.status_code == 409
    assert _reload(db, third.id).hr_decision == "pending"


def test_reveal_returns_identity_and_audits_every_time(db, world, api):
    application = make_application(db, world["job"])
    path = url(world, f"/applications/{application.id}/reveal")
    for _ in range(2):
        response = api.post(path, headers=hr(world))
        assert response.status_code == 200
        assert response.json() == {"name": CANDIDATE_NAME, "email": CANDIDATE_EMAIL}
    assert db.query(AuditLog).filter_by(action="identity_revealed", target_id=application.id).count() == 2
    assert api.post(path, headers=world["people"]["emp"]["headers"]).status_code == 403


def test_restart_once_then_409(db, world, api):
    application = make_application(db, world["job"], band=None)
    session, _ = make_session(db, application, [(1, "Q", "ans", "1/1/1.webm")], status="failed")
    path = url(world, f"/applications/{application.id}/restart")
    response = api.post(path, headers=hr(world))
    assert response.status_code == 200, response.text
    row = _reload(db, application.id)
    assert row.stage == "invited"
    old = db.get(VoiceSession, session.id)
    assert old.restart_count == 1
    from app.database.sql_models import VoiceTurn
    assert db.query(VoiceTurn).filter_by(session_id=session.id).one().audio_path == "1/1/1.webm"
    assert db.query(AuditLog).filter_by(action="restart_granted", target_id=application.id).count() == 1
    # the candidate runs it again and it reaches HR again
    row.stage = "ready_for_hr"
    db.commit()
    assert api.post(path, headers=hr(world)).status_code == 409


def test_restart_requires_hr_review_stage(db, world, api):
    application = make_application(db, world["job"], stage="invited")
    assert api.post(url(world, f"/applications/{application.id}/restart"), headers=hr(world)).status_code == 409


def test_fast_track_skips_the_session_without_ai_and_can_be_decided(db, world, api):
    application = make_application(db, world["job"], stage="invited", band=None)
    fake.reset()
    response = api.post(url(world, f"/applications/{application.id}/fast-track"), headers=hr(world))
    assert response.status_code == 200
    row = _reload(db, application.id)
    assert row.stage == "ready_for_hr" and row.fast_tracked is True and row.interview_band is None
    assert fake.last_system() == ""  # no AI call
    assert db.query(AuditLog).filter_by(action="fast_tracked", target_id=application.id).count() == 1
    decide = api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world),
                      json={"decision": "approved"})
    assert decide.status_code == 200
    assert api.post(url(world, f"/applications/{application.id}/fast-track"), headers=hr(world)).status_code == 409


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_the_candidate_sees_the_decision_and_nothing_else_about_the_review(db, world, api, decision):
    from tests.helpers import auth_header

    application = make_application(db, world["job"], cv_status="not_met", band="many")
    before = api.get("/api/me/applications", headers=auth_header(CANDIDATE_EMAIL)).json()[0]
    assert before["status"] == "with_hr" and before["decision"] is None

    api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world), json={"decision": decision})
    response = api.get("/api/me/applications", headers=auth_header(CANDIDATE_EMAIL))

    assert response.json()[0]["status"] == "decided" and response.json()[0]["decision"] == decision
    for word in ("not_met", "cv_status", "interview_band", "many", "hidden"):
        assert word not in response.text
