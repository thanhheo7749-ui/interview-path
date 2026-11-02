"""The sweep and HR's transcription retry call STT outside any transaction. See test_ai_outside_transactions.py."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database.database import SessionLocal
from app.database.sql_models import Application, VoiceSession, VoiceTurn
from app.hiring import recordings, voice
from app.main import create_app
from tests.helpers_board import make_application, make_world
from tests.test_ai_outside_transactions import probe  # noqa: F401  # autouse: the file database and its probe


def _failed_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    monkeypatch.setattr(voice, "schedule_analysis", lambda _application_id: None)
    db = SessionLocal()
    world = make_world(db)
    application = make_application(db, world["job"], stage="session_in_progress", cv_status="meets")
    idle = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25)
    session = VoiceSession(company_id=application.company_id, purpose="screening", application_id=application.id,
                           owner_user_id=application.candidate_user_id, language="en", status="paused",
                           plan=[{"text": "Q", "source": "role"}], last_activity_at=idle, active_seconds=30)
    db.add(session)
    db.commit()
    path = recordings.save_turn_audio(application.company_id, application.id, 1, b"voice", ".webm")
    db.add(VoiceTurn(session_id=session.id, position=1, question_text="Q", question_source="role",
                     transcript_status="failed", stt_failures=2, audio_path=path))
    db.commit()
    return db, world, application, session


def test_the_sweep_retries_stt_with_no_write_held(tmp_path, monkeypatch, probe):  # noqa: F811
    db, _world, application, _session = _failed_turn(tmp_path, monkeypatch)
    try:
        probe.start()
        assert voice.sweep_abandoned(db) == 1
        probe.assert_clean("session_stt")
        db.rollback()
        assert db.get(Application, application.id).stage == "session_completed"
    finally:
        db.close()


def test_hr_transcription_retry_calls_stt_and_analysis_with_no_write_held(tmp_path, monkeypatch, probe):  # noqa: F811
    db, world, application, session = _failed_turn(tmp_path, monkeypatch)
    try:
        row = db.get(Application, application.id)
        row.stage = "ready_for_hr"
        row.analysis_status = "transcription_failed"
        session.status = "completed"
        db.commit()
        with TestClient(create_app()) as api:
            probe.start()
            response = api.post(f"/api/companies/{world['company'].id}/applications/{application.id}/transcription/retry",
                                headers=world["people"]["hr"]["headers"])
            assert response.status_code == 202, response.text
        probe.assert_clean("session_stt", "session_analysis")
        db.rollback()
        db.expire_all()
        assert db.get(Application, application.id).analysis_status == "done"
    finally:
        db.close()
