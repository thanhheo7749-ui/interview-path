"""The voice clock's grace for an answer already under way, and the cost limits on the candidate's AI routes."""
from datetime import datetime, timedelta, timezone

import pytest

from app.ai.providers import fake
from app.ai.types import AIProviderError, TranscriptResult, Usage
from app.core import rate_limit
from app.core.rate_limit import limiter
from app.database.database import SessionLocal
from app.database.sql_models import AIUsageLog, Application, VoiceSession, VoiceTurn
from app.hiring import planner, voice
from app.routers import screening as screening_router
from tests.helpers import auth_header
from tests.test_hiring_voice import (  # noqa: F401  (fixtures are used by name)
    ANSWER, CANDIDATE, OTHER, _recordings, answer, followup, go_idle, question_audio, scheduled, session_row, spend_time,
    stage, started, start, state, stt_returning, transcript_result, turn, world,
)


def _count(limit: str) -> int:
    return int(limit.split("/")[0])


@pytest.fixture
def rate_limited():
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


def _long_ago(**delta):
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(**delta)


# I-2. An answer begun before the limit


def test_an_answer_to_a_question_open_before_the_limit_is_taken_for_210_seconds_past_it(client, world, db, started, monkeypatch, scheduled):
    session_id = started["session_id"]
    spend_time(db, session_id, minutes=14, seconds=55)
    go_idle(db, session_id, seconds=150)  # 5 seconds before the limit, plus 150 seconds of talking and uploading
    calls = stt_returning(monkeypatch, ANSWER)
    fake.enqueue("session_followup", followup())
    response = answer(client, session_id, 1)
    body = response.json()
    assert response.status_code == 200 and body["status"] == "completed" and body["notice"] is None
    assert len(calls) == 1
    row = turn(db, session_id, 1)
    assert row.transcript == ANSWER and row.audio_path
    assert turn(db, session_id, 2) is None  # no follow-up this late
    assert stage(db, world) == "session_completed" and scheduled == [world.application_id]


def test_an_answer_arriving_later_than_that_is_refused_with_the_audio_discarded_and_the_candidate_told(client, world, db, started, monkeypatch, scheduled, _recordings):
    session_id = started["session_id"]
    spend_time(db, session_id, minutes=14, seconds=55)
    go_idle(db, session_id, seconds=300)
    calls = stt_returning(monkeypatch, ANSWER)
    body = answer(client, session_id, 1).json()
    assert body["status"] == "completed" and body["notice"] == "time_up"
    assert calls == []
    row = turn(db, session_id, 1)
    assert row.transcript is None and row.audio_path is None
    assert not any(path.is_file() for path in _recordings.rglob("*") if path.suffix == ".webm")
    assert stage(db, world) == "session_completed" and scheduled == [world.application_id]


def test_an_answer_for_a_question_opened_after_the_limit_is_refused_with_a_notice(client, world, db, started, monkeypatch):
    session_id = started["session_id"]
    spend_time(db, session_id, minutes=15, seconds=5)
    calls = stt_returning(monkeypatch, ANSWER)
    body = answer(client, session_id, 1).json()
    assert body["status"] == "completed" and body["notice"] == "time_up" and calls == []


def test_a_state_read_after_the_limit_ends_the_session_without_that_notice(client, world, db, started):
    spend_time(db, started["session_id"], minutes=20)
    assert state(client, started["session_id"]).json()["notice"] is None


# I-10. Question audio


def test_question_audio_is_made_once_per_turn_and_kept_on_disk(client, world, db, started, _recordings):
    first = question_audio(client, started["session_id"], 1)
    second = question_audio(client, started["session_id"], 1)
    assert first.status_code == second.status_code == 200
    assert first.content == second.content == b"FAKEAUDIO:" + started["question_text"].encode()
    assert second.headers["content-type"] == "audio/mpeg"
    assert db.query(AIUsageLog).filter_by(feature="session_tts").count() == 1
    path = turn(db, started["session_id"], 1).question_audio_path
    assert path and (_recordings / path).read_bytes() == first.content


def test_question_audio_is_refused_for_a_finished_session_even_if_it_is_cached(client, world, db, started):
    question_audio(client, started["session_id"], 1)
    row = session_row(db, started["session_id"])
    row.status = "completed"
    db.commit()
    assert question_audio(client, started["session_id"], 1).status_code == 409
    assert db.query(AIUsageLog).filter_by(feature="session_tts").count() == 1


def test_question_audio_for_an_abandoned_session_is_refused_too(client, world, db, started):
    row = session_row(db, started["session_id"])
    row.status = "abandoned"
    db.commit()
    assert question_audio(client, started["session_id"], 1).status_code == 409


def test_a_failed_tts_is_not_cached(client, world, db, started, monkeypatch):
    def down(*_args, **_kwargs):
        raise AIProviderError("down")

    monkeypatch.setattr(screening_router.gateway, "synthesize", down)
    assert question_audio(client, started["session_id"], 1).status_code == 204
    monkeypatch.undo()
    assert question_audio(client, started["session_id"], 1).status_code == 200


# I-10. Rate limits


def test_question_audio_has_a_per_user_limit(client, world, started, rate_limited):
    limit = _count(rate_limit.VOICE_QUESTION_AUDIO_LIMIT)
    codes = [question_audio(client, started["session_id"], 1).status_code for _ in range(limit + 1)]
    assert codes == [200] * limit + [429]
    assert question_audio(client, started["session_id"], 1, email=OTHER).status_code == 404  # another bucket


def test_answer_uploads_have_a_per_user_limit(client, world, started, rate_limited):
    limit = _count(rate_limit.VOICE_ANSWER_LIMIT)
    codes = [answer(client, started["session_id"], 1, content_type="text/plain").status_code for _ in range(limit + 1)]
    assert codes == [415] * limit + [429]


def test_start_has_a_per_user_limit(client, world, rate_limited):
    limit = _count(rate_limit.VOICE_START_LIMIT)
    codes = [start(client, world, version="old").status_code for _ in range(limit + 1)]
    assert codes == [409] * limit + [429]


def test_a_normal_interview_stays_inside_the_limits():
    """A 15 minute interview is a dozen answers at most, a few retries and one audio request per question."""
    assert _count(rate_limit.VOICE_ANSWER_LIMIT) >= 30
    assert _count(rate_limit.VOICE_QUESTION_AUDIO_LIMIT) >= 40
    assert _count(rate_limit.VOICE_START_LIMIT) >= 10


# I-10. Length of an answer


def test_an_upload_larger_than_200_seconds_of_audio_can_hold_gets_a_readable_413(client, world, db, started, monkeypatch):
    calls = stt_returning(monkeypatch, ANSWER)
    too_big = voice.max_audio_bytes("audio/webm") + 1
    response = answer(client, started["session_id"], 1, data=b"\x00" * too_big)
    assert response.status_code == 413 and "3 minutes" in response.json()["detail"]
    assert calls == [] and turn(db, started["session_id"], 1).audio_path is None


def test_a_fifteen_megabyte_upload_is_refused_for_every_type(client, world, db, started, monkeypatch):
    calls = stt_returning(monkeypatch, ANSWER)
    for mime, size in (("audio/webm", 15 * 1024 * 1024), ("audio/mp4", 15 * 1024 * 1024), ("audio/wav", 15 * 1024 * 1024 + 1)):
        assert answer(client, started["session_id"], 1, data=b"\x00" * size, content_type=mime).status_code == 413
    assert calls == []


def test_a_codec_sized_upload_just_inside_the_cap_is_taken(client, world, db, started, monkeypatch):
    stt_returning(monkeypatch, ANSWER)
    data = b"\x00" * voice.max_audio_bytes("audio/webm")
    assert answer(client, started["session_id"], 1, data=data).status_code == 200


def test_the_provider_duration_over_200_seconds_refuses_the_answer_and_stores_nothing(client, world, db, started, monkeypatch):
    def long_answer(audio, mime_type, languages, feature, company_id=None):
        return TranscriptResult(text=ANSWER, language="en", provider="fake", model="m", usage=Usage(audio_seconds=201.0), latency_ms=1)

    monkeypatch.setattr(voice.gateway, "transcribe", long_answer)
    response = answer(client, started["session_id"], 1)
    assert response.status_code == 413 and "3 minutes" in response.json()["detail"]
    row = turn(db, started["session_id"], 1)
    assert row.transcript is None and row.audio_path is None and row.stt_started_at is None
    assert state(client, started["session_id"]).json()["position"] == 1


def test_the_provider_duration_of_exactly_200_seconds_is_taken(client, world, db, started, monkeypatch):
    def at_the_cap(audio, mime_type, languages, feature, company_id=None):
        return TranscriptResult(text=ANSWER, language="en", provider="fake", model="m", usage=Usage(audio_seconds=200.0), latency_ms=1)

    monkeypatch.setattr(voice.gateway, "transcribe", at_the_cap)
    assert answer(client, started["session_id"], 1).status_code == 200


# I-10. One transcription in flight per position


def test_an_upload_while_the_position_is_being_transcribed_gets_409_and_pays_nothing(client, world, db, started, monkeypatch):
    row = turn(db, started["session_id"], 1)
    row.stt_started_at = _long_ago(seconds=5)
    db.commit()
    calls = stt_returning(monkeypatch, ANSWER)
    response = answer(client, started["session_id"], 1)
    assert response.status_code == 409 and "still" in response.json()["detail"]
    assert calls == [] and turn(db, started["session_id"], 1).stt_started_at is not None


def test_a_claim_left_by_a_crash_expires(client, world, db, started, monkeypatch):
    row = turn(db, started["session_id"], 1)
    row.stt_started_at = _long_ago(seconds=voice.STT_CLAIM_SECONDS + 5)
    db.commit()
    stt_returning(monkeypatch, ANSWER)
    assert answer(client, started["session_id"], 1).status_code == 200


def test_the_claim_is_held_during_the_stt_call_and_cleared_after(client, world, db, started, monkeypatch):
    session_id = started["session_id"]
    seen = {}

    def watching(audio, mime_type, languages, feature, company_id=None):
        with SessionLocal() as other:
            seen["claimed"] = other.query(VoiceTurn.stt_started_at).filter_by(session_id=session_id, position=1).scalar()
            with pytest.raises(voice.TranscriptionInFlight):
                voice.submit_answer(other, other.get(VoiceSession, session_id), 1, b"second", "audio/webm")
        return transcript_result(ANSWER)

    monkeypatch.setattr(voice.gateway, "transcribe", watching)
    assert answer(client, session_id, 1).status_code == 200
    assert seen["claimed"] is not None
    assert turn(db, session_id, 1).stt_started_at is None


def test_the_claim_is_cleared_when_stt_fails(client, world, db, started, monkeypatch):
    stt_returning(monkeypatch, AIProviderError("down"))
    body = answer(client, started["session_id"], 1).json()
    assert body["notice"] == "retry"
    assert turn(db, started["session_id"], 1).stt_started_at is None


def test_the_claim_is_cleared_when_the_call_blows_up(client, world, db, started, monkeypatch):
    stt_returning(monkeypatch, RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        answer(client, started["session_id"], 1)
    assert turn(db, started["session_id"], 1).stt_started_at is None


def test_an_upload_that_finishes_first_wins_when_a_claim_had_expired(client, world, db, started, monkeypatch, _recordings):
    """The claim is the guard. If it ever expires under a slow call, the check under the lock still keeps one winner."""
    session_id = started["session_id"]
    inner = {"ran": False}

    def racing(audio, _mime_type, _languages, _feature, _company_id=None):
        if inner["ran"]:
            return transcript_result(audio.decode())
        inner["ran"] = True
        with SessionLocal() as other:
            other.query(VoiceTurn).filter_by(session_id=session_id, position=1).update({"stt_started_at": _long_ago(hours=1)})
            other.commit()
            voice.submit_answer(other, other.get(VoiceSession, session_id), 1, b"winner audio", "audio/webm")
        return transcript_result("loser transcript")

    monkeypatch.setattr(voice.gateway, "transcribe", racing)
    response = answer(client, session_id, 1, data=b"loser audio", content_type="audio/ogg")
    assert response.status_code == 200 and response.json()["position"] == 2
    assert turn(db, session_id, 1).transcript == "winner audio"


# I-10. A start pays for planning once


def test_a_start_while_another_is_planning_gets_409_and_does_not_plan(client, world, db, monkeypatch):
    claimed = db.get(Application, world.application_id)
    claimed.start_claimed_at = _long_ago(seconds=5)
    db.commit()
    planned = []
    monkeypatch.setattr(screening_router.planner, "build_plan", lambda *args: planned.append(args))
    response = start(client, world)
    assert response.status_code == 409 and "being prepared" in response.json()["detail"]
    assert planned == []


def test_a_planning_claim_left_by_a_crash_expires(client, world, db):
    claimed = db.get(Application, world.application_id)
    claimed.start_claimed_at = _long_ago(seconds=screening_router.START_CLAIM_SECONDS + 5)
    db.commit()
    assert start(client, world).status_code == 200


def test_the_start_claim_is_held_while_planning_and_cleared_after(client, world, db, monkeypatch):
    real = planner.build_plan
    seen = {}

    def watching(session_db, application, language):
        with SessionLocal() as other:
            seen["claimed"] = other.query(Application.start_claimed_at).filter_by(id=world.application_id).scalar()
        return real(session_db, application, language)

    monkeypatch.setattr(screening_router.planner, "build_plan", watching)
    assert start(client, world).status_code == 200
    assert seen["claimed"] is not None
    db.rollback()
    db.expire_all()
    assert db.get(Application, world.application_id).start_claimed_at is None


def test_the_start_claim_is_cleared_when_planning_fails(client, world, db, monkeypatch):
    def broken(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(screening_router.planner, "build_plan", broken)
    with pytest.raises(RuntimeError):
        start(client, world)
    db.rollback()
    db.expire_all()
    assert db.get(Application, world.application_id).start_claimed_at is None
    monkeypatch.undo()
    assert start(client, world).status_code == 200


def test_resuming_a_running_session_does_not_need_or_leave_a_claim(client, world, db, started):
    assert start(client, world).status_code == 200
    db.rollback()
    db.expire_all()
    assert db.get(Application, world.application_id).start_claimed_at is None
