"""The claims, the question-audio cache and the daily budget on a real MySQL.

DATETIME columns keep whole seconds here, so a claim must be compared at whole seconds; the budget's "today" is the
server's calendar day; and REPEATABLE READ means a second request must not read an old snapshot of a claim.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs a MySQL server: run make test-mysql", allow_module_level=True)

from fastapi import HTTPException  # noqa: E402

from app.ai import gateway  # noqa: E402
from app.ai.types import BudgetExceeded  # noqa: E402
from app.ai.usage import spent_today_usd  # noqa: E402
from app.database.database import SessionLocal  # noqa: E402
from app.database.sql_models import AIUsageLog, Application, Company, Job, VoiceSession, VoiceTurn  # noqa: E402
from app.hiring import voice  # noqa: E402
from app.routers import screening  # noqa: E402
from tests.helpers import make_user  # noqa: E402


@pytest.fixture
def world(db, tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.flush()
    job = Job(company_id=company.id, title="Backend", slug="acme-backend", description="d", status="published",
              interview_languages=["en"])
    db.add(job)
    db.flush()
    user = make_user(db, "candidate@example.test")
    application = Application(company_id=company.id, job_id=job.id, candidate_user_id=user.id, alias="#M1",
                              stage="session_in_progress", cv_status="not_met")
    db.add(application)
    db.flush()
    session = voice.create_session(db, company_id=company.id, purpose="screening", owner_user_id=user.id, language="en",
                                   plan=[{"text": "A question", "source": "role"}], application_id=application.id)
    db.commit()
    return company.id, application.id, session.id, user.id


def _turn(db, session_id):
    db.rollback()
    return db.query(VoiceTurn).filter_by(session_id=session_id, position=1).one()


def test_the_transcription_claim_is_cleared_after_a_failure_and_blocks_a_second_upload(db, world, monkeypatch):
    _, _, session_id, _ = world

    def boom(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(voice, "_transcribe", boom)
    with SessionLocal() as upload:
        with pytest.raises(RuntimeError):
            voice.submit_answer(upload, upload.get(VoiceSession, session_id), 1, b"audio", "audio/webm")
    assert _turn(db, session_id).stt_started_at is None  # the equality on a whole-second DATETIME matched

    held = _turn(db, session_id)
    held.stt_started_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(seconds=3)
    db.commit()
    with SessionLocal() as second:
        with pytest.raises(voice.TranscriptionInFlight):
            voice.submit_answer(second, second.get(VoiceSession, session_id), 1, b"audio", "audio/webm")


def test_a_claim_read_through_an_old_snapshot_still_blocks(db, world, monkeypatch):
    """The second upload's login read began its snapshot before the first committed its claim."""
    _, _, session_id, _ = world
    late = SessionLocal()
    try:
        late_session = late.get(VoiceSession, session_id)  # the snapshot is taken here
        row = _turn(db, session_id)
        row.stt_started_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        db.commit()
        with pytest.raises(voice.TranscriptionInFlight):
            voice.submit_answer(late, late_session, 1, b"audio", "audio/webm")
    finally:
        late.close()


def test_a_start_claim_is_taken_once_and_cleared_by_its_owner(db, world):
    _, application_id, _, user_id = world
    row = db.get(Application, application_id)
    row.stage = "invited"
    db.query(VoiceSession).update({VoiceSession.status: "completed"})
    db.commit()
    first, resumed = screening._claim_start(db, user_id, application_id)
    assert first is not None and resumed is None
    with pytest.raises(HTTPException) as caught:
        screening._claim_start(db, user_id, application_id)
    assert caught.value.status_code == 409
    screening._release_start_claim(db, application_id, first)
    db.rollback()
    db.expire_all()
    assert db.get(Application, application_id).start_claimed_at is None


def test_question_audio_is_made_once_and_the_path_survives_a_new_connection(db, world, tmp_path):
    _, _, session_id, _ = world
    with SessionLocal() as first:
        audio, mime = voice.question_audio(first, session_id, 1)
    with SessionLocal() as second:
        again, _ = voice.question_audio(second, session_id, 1)
    assert again == audio and mime == "audio/mpeg"
    db.rollback()  # this session's snapshot began before the other connections committed
    assert db.query(AIUsageLog).filter_by(feature="session_tts").count() == 1
    assert _turn(db, session_id).question_audio_path and list(tmp_path.rglob("*-question.mp3"))


def test_the_daily_budget_counts_todays_rows_on_mysql(db, world):
    company_id = world[0]
    two_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
    db.add(AIUsageLog(company_id=company_id, feature="old", slot="bulk", provider="fake", model="fake", success=True,
                      estimated_cost_usd=100.0, created_at=two_days_ago))
    db.add(AIUsageLog(company_id=company_id, feature="unpriced", slot="bulk", provider="fake", model="fake", success=True))
    db.add(AIUsageLog(company_id=company_id, feature="today", slot="bulk", provider="fake", model="fake", success=True,
                      estimated_cost_usd=24.5))
    db.commit()
    assert spent_today_usd(company_id) == pytest.approx(24.5)
    db.add(AIUsageLog(company_id=company_id, feature="today", slot="bulk", provider="fake", model="fake", success=True,
                      estimated_cost_usd=1.0))
    db.commit()
    with pytest.raises(BudgetExceeded):
        gateway.generate_text("reasoning", "sys", [{"role": "user", "content": "x"}], 10, "unit_test", company_id)
