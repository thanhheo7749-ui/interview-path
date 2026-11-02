"""Application states that only MySQL can show: column widths, and a session reading what another session committed."""
import os
import threading
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs a MySQL server: run make test-mysql", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.types import AIProviderError  # noqa: E402
from app.database.database import SessionLocal  # noqa: E402
from app.database.sql_models import (  # noqa: E402
    Application, Company, CompanyMember, Job, JobRequirement, Notification, RequirementResult, VoiceSession, VoiceTurn,
)
from app.hiring import analysis, cv_processing, jobs, notify, recordings, voice  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.helpers import auth_header, make_user  # noqa: E402

LONG_TITLE = "T" * 255
HR = "hr@example.test"


@pytest.fixture
def world(db, tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(voice, "schedule_analysis", lambda _application_id: None)
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title=LONG_TITLE, slug="long", status="published", version=1, interview_languages=["en"])
    db.add(job)
    db.commit()
    requirement = JobRequirement(company_id=company.id, job_id=job.id, text="FastAPI", must_have=True, position=0)
    db.add(requirement)
    hr = make_user(db, HR)
    candidate = make_user(db, "candidate@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    db.commit()
    return {"company_id": company.id, "job_id": job.id, "candidate_id": candidate.id, "requirement_id": requirement.id}


def _application(db, world, **fields):
    row = Application(company_id=world["company_id"], job_id=world["job_id"], job_version=1, alias="#A1",
                      candidate_user_id=world["candidate_id"], **fields)
    db.add(row)
    db.commit()
    return row


def test_a_255_character_title_fits_every_notification_subject(db, world):
    """The enqueue itself raised DataError on MySQL, which SQLite never shows."""
    subject = f"An update on {LONG_TITLE}"
    row = notify.enqueue(db, world["company_id"], world["candidate_id"], "decision", "en", subject, "body")
    db.commit()
    db.expire_all()
    stored = db.get(Notification, row.id).subject
    assert len(stored) == Notification.subject.type.length and subject.startswith(stored)


def test_a_255_character_title_does_not_break_an_hr_decision(db, world):
    application = _application(db, world, stage="ready_for_hr", cv_status="meets")
    api = TestClient(create_app())
    response = api.post(f"/api/companies/{world['company_id']}/applications/{application.id}/decision",
                        headers=auth_header(HR), json={"decision": "rejected"})
    assert response.status_code == 200, response.text


def test_a_255_character_title_does_not_fail_cv_processing(db, world, tmp_path, monkeypatch):
    from app.core import storage

    path = storage.save_bytes(world["company_id"], "cv", ".pdf", b"unused")
    application = _application(db, world, stage="submitted", cv_file_path=path, cv_suffix=".pdf")
    extracted = type("Extracted", (), {"text": "Built FastAPI services", "hidden_detected": False})
    monkeypatch.setattr(cv_processing, "extract_cv", lambda _data, _suffix: extracted)
    cv_processing.run(application.id)
    db.rollback()
    db.expire_all()
    row = db.get(Application, application.id)
    assert row.stage == "invited" and row.processing_error is None


def test_requirements_for_sees_results_another_session_committed(db, world):
    """A session that read before the other session's commit ends its transaction first, as every caller's route does."""
    application = _application(db, world, stage="invited", cv_status="meets")
    assert [row.id for row in jobs.requirements_for(db, application)] == [world["requirement_id"]]
    other = SessionLocal()
    try:
        other.add(RequirementResult(application_id=application.id, requirement_id=world["requirement_id"], source="cv", status="met"))
        other.commit()
    finally:
        other.close()
    db.rollback()
    assert [row.id for row in jobs.requirements_for(db, application)] == [world["requirement_id"]]


def _failed_turn_session(db, world):
    application = _application(db, world, stage="session_in_progress", cv_status="meets")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = VoiceSession(company_id=world["company_id"], purpose="screening", application_id=application.id,
                           owner_user_id=world["candidate_id"], language="en", status="paused",
                           plan=[{"text": "Q", "source": "role"}], started_at=now,
                           last_activity_at=now - timedelta(hours=25), active_seconds=30)
    db.add(session)
    db.commit()
    path = recordings.save_turn_audio(world["company_id"], application.id, 1, b"voice", ".webm")
    db.add(VoiceTurn(session_id=session.id, position=1, question_text="Q", question_source="role",
                     transcript_status="failed", stt_failures=2, audio_path=path))
    db.commit()
    return application, session


def test_the_sweep_sees_a_candidate_who_came_back_during_its_stt_retry(db, world, monkeypatch):
    """The re-read after the slow call must not come from the snapshot taken before it, or the candidate loses their session."""
    application, session = _failed_turn_session(db, world)
    application_id, session_id = application.id, session.id

    def came_back(*_args, **_kwargs):
        def work():
            other = SessionLocal()
            try:
                other.get(VoiceSession, session_id).last_activity_at = datetime.now(timezone.utc).replace(tzinfo=None)
                other.commit()
            finally:
                other.close()

        thread = threading.Thread(target=work)
        thread.start()
        thread.join()
        raise AIProviderError("down")

    monkeypatch.setattr(voice.gateway, "transcribe", came_back)
    assert voice.sweep_abandoned(db) == 0
    db.rollback()
    db.expire_all()
    assert db.get(VoiceSession, session_id).status == "paused"
    assert db.get(Application, application_id).stage == "session_in_progress"


def test_transcription_failed_fits_its_column_and_recovery_finds_a_stranded_retry(db, world, monkeypatch):
    application, session = _failed_turn_session(db, world)
    application_id = application.id
    monkeypatch.setattr(voice.gateway, "transcribe", lambda *_args, **_kwargs: (_ for _ in ()).throw(AIProviderError("down")))
    assert voice.sweep_abandoned(db) == 1
    db.rollback()
    db.expire_all()
    row = db.get(Application, application_id)
    assert row.analysis_status == "transcription_failed" and row.stage == "ready_for_hr"

    row.analysis_status = "running"  # a crash during HR's retry
    db.commit()
    assert analysis.requeue_interrupted() == [application_id]
    analysis.run(application_id)
    db.rollback()
    db.expire_all()
    assert db.get(Application, application_id).analysis_status == "transcription_failed"
