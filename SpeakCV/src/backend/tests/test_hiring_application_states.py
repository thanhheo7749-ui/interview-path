"""States an application can reach when something outside it goes wrong, and what HR and the candidate can do there."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.ai.types import AIProviderError, TranscriptResult, Usage
from app.database.database import SessionLocal
from app.database.sql_models import (
    AIUsageLog, Application, AuditLog, Consent, CultureNote, CvClaim, Notification, RequirementResult, VoiceSession, VoiceTurn,
)
from app.hiring import analysis, board, consents, cv_processing, decisions, recordings, voice
from app.hiring.state import InvalidTransition, advance
from app.main import create_app
from tests.helpers import auth_header
from tests.helpers_board import CANDIDATE_EMAIL, add_claims, make_application, make_session, make_world

CANDIDATE = auth_header(CANDIDATE_EMAIL)
ANSWER = "I built an API with FastAPI at my last job"


@pytest.fixture(autouse=True)
def _recordings(tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))


@pytest.fixture(autouse=True)
def scheduled(monkeypatch):
    calls = []
    monkeypatch.setattr(voice, "schedule_analysis", calls.append)
    return calls


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def api():
    return TestClient(create_app())


def _url(world, tail):
    return f"/api/companies/{world['company'].id}{tail}"


def _hr(world):
    return world["people"]["hr"]["headers"]


def _fresh(db, application_id):
    db.rollback()
    db.expire_all()
    return db.get(Application, application_id)


def _board(api, world):
    response = api.get(_url(world, f"/jobs/{world['job'].id}/board"), headers=_hr(world))
    assert response.status_code == 200, response.text
    return response.json()


def _lane(api, world, name):
    return [card["id"] for card in _board(api, world)["lanes"][name]]


def _in_any_cell(api, world, application_id):
    return any(card["id"] == application_id for cards in _board(api, world)["cells"].values() for card in cards)


def _heard(text):
    return TranscriptResult(text=text, language="en", provider="fake", model="m", usage=Usage(audio_seconds=4.0), latency_ms=1)


def _stt(monkeypatch, *items):
    """Each call takes the next item, and the last repeats. An Exception is raised instead. Returns the call log."""
    calls, queue = [], list(items)

    def transcribe(audio, mime_type, languages, feature, company_id=None):
        calls.append({"audio": audio, "mime": mime_type, "languages": languages, "feature": feature, "company_id": company_id})
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return _heard(item)

    monkeypatch.setattr(voice.gateway, "transcribe", transcribe)
    return calls


def _paid_analysis_calls(db):
    db.rollback()
    return db.query(AIUsageLog).filter_by(feature="session_analysis").count()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _go_idle(db, session_id, **delta):
    db.rollback()
    db.expire_all()
    db.get(VoiceSession, session_id).last_activity_at = _now() - timedelta(**delta)
    db.commit()


def _running_session(db, world, audio=True, answered=()):
    """A running session as the real upload path leaves it after an STT outage on its current question."""
    application = make_application(db, world["job"], stage="session_in_progress", cv_status="meets")
    session = VoiceSession(company_id=application.company_id, purpose="screening", application_id=application.id,
                           owner_user_id=application.candidate_user_id, language="en", status="paused",
                           plan=[{"text": "Q1", "source": "role", "source_ref": "role:0", "why": "w"},
                                 {"text": "Q2", "source": "role", "source_ref": "role:1", "why": "w"},
                                 {"text": "Q3", "source": "role", "source_ref": "role:2", "why": "w"}],
                           started_at=_now(), last_activity_at=_now(), active_seconds=30)
    db.add(session)
    db.commit()
    position = 1
    for text in answered:
        db.add(VoiceTurn(session_id=session.id, position=position, question_text="Q", question_source="role",
                         transcript=text, transcript_status="transcribed"))
        position += 1
    path = recordings.save_turn_audio(application.company_id, application.id, position, b"voice", ".webm") if audio else None
    db.add(VoiceTurn(session_id=session.id, position=position, question_text="Q", question_source="role",
                     transcript_status="failed", stt_failures=2, audio_path=path))
    db.commit()
    return application, session


# I-8: the outage scenario, through the real routes


def _consented_start(api, db, world):
    application = make_application(db, world["job"], stage="invited", cv_status="meets")
    response = api.post(f"/api/screening/{application.id}/start", headers=CANDIDATE,
                        json={"consent_version": consents.VERSION, "language": "en"})
    assert response.status_code == 200, response.text
    return application, response.json()["session_id"]


def _upload(api, session_id, position=1):
    return api.post(f"/api/screening/{session_id}/turns/{position}/answer", headers=CANDIDATE,
                    files={"file": ("a.webm", ANSWER.encode(), "audio/webm")})


def test_an_stt_outage_is_a_technical_problem_and_not_a_candidate_who_skipped_the_interview(db, world, api, monkeypatch, scheduled):
    application, session_id = _consented_start(api, db, world)
    _stt(monkeypatch, AIProviderError("down"))
    for _ in range(2):
        assert _upload(api, session_id).json()["notice"] == "retry"
    _go_idle(db, session_id, hours=25)

    calls = _stt(monkeypatch, AIProviderError("still down"))
    assert voice.sweep_abandoned(db) == 1

    assert len(calls) == 1  # the sweep retries once
    row = _fresh(db, application.id)
    assert row.stage == "ready_for_hr" and row.analysis_status == "transcription_failed"
    assert row.interview_band is None
    assert db.get(VoiceSession, session_id).status == "completed"
    assert scheduled == [] and _paid_analysis_calls(db) == 0
    assert application.id in _lane(api, world, "transcription_failed")
    assert not _in_any_cell(api, world, application.id)
    detail = api.get(_url(world, f"/applications/{application.id}"), headers=_hr(world)).json()
    assert detail["interview_note"] is None and detail["transcript"][0]["has_audio"] is True
    assert db.query(AuditLog).filter_by(action="voice_session_abandoned", target_id=session_id).count() == 0
    assert db.query(AuditLog).filter_by(action="transcription_failed", target_id=session_id).count() == 1


def test_the_sweep_goes_on_to_analysis_when_its_retry_works(db, world, monkeypatch, scheduled):
    application, session = _running_session(db, world)
    _go_idle(db, session.id, hours=25)
    calls = _stt(monkeypatch, ANSWER)
    assert voice.sweep_abandoned(db) == 1
    assert len(calls) == 1 and calls[0]["audio"] == b"voice" and calls[0]["mime"] == "audio/webm"
    assert calls[0]["feature"] == "session_stt" and calls[0]["company_id"] == application.company_id
    row = _fresh(db, application.id)
    assert row.stage == "session_completed" and scheduled == [application.id]
    turn = db.query(VoiceTurn).filter_by(session_id=session.id).one()
    assert turn.transcript == ANSWER and turn.transcript_status == "transcribed"


def test_a_retry_that_hears_silence_is_a_session_with_nothing_said(db, world, monkeypatch, scheduled):
    application, session = _running_session(db, world)
    _go_idle(db, session.id, hours=25)
    _stt(monkeypatch, "   ")
    assert voice.sweep_abandoned(db) == 1
    assert _fresh(db, application.id).analysis_status == "not_taken" and scheduled == []
    assert db.get(VoiceSession, session.id).status == "abandoned"


def test_answers_already_given_do_not_hide_a_failed_transcript(db, world, monkeypatch, scheduled):
    application, session = _running_session(db, world, answered=["An earlier answer"])
    _go_idle(db, session.id, hours=25)
    _stt(monkeypatch, AIProviderError("down"))
    assert voice.sweep_abandoned(db) == 1
    row = _fresh(db, application.id)
    assert row.analysis_status == "transcription_failed" and row.stage == "ready_for_hr" and scheduled == []
    assert db.get(VoiceSession, session.id).status == "completed"


def test_the_sweep_stores_nothing_if_the_candidate_came_back_during_its_retry(db, world, monkeypatch, scheduled):
    application, session = _running_session(db, world)
    _go_idle(db, session.id, hours=25)
    session_id = session.id

    def came_back(*_args, **_kwargs):
        other = SessionLocal()
        try:
            other.get(VoiceSession, session_id).last_activity_at = _now()
            other.commit()
        finally:
            other.close()
        return _heard(ANSWER)

    monkeypatch.setattr(voice.gateway, "transcribe", came_back)
    assert voice.sweep_abandoned(db) == 0
    db.rollback()
    db.expire_all()
    turn = db.query(VoiceTurn).filter_by(session_id=session_id).one()
    assert turn.transcript_status == "failed" and turn.transcript is None
    assert db.get(VoiceSession, session_id).status == "paused"
    assert _fresh(db, application.id).stage == "session_in_progress"


def test_the_hard_limit_also_keeps_a_failed_transcript_out_of_analysis(db, world, api, monkeypatch, scheduled):
    application, session = _running_session(db, world, answered=["An earlier answer"])
    db.rollback()
    db.get(VoiceSession, session.id).active_seconds = voice.HARD_LIMIT_SECONDS + 1
    db.commit()
    calls = _stt(monkeypatch, ANSWER)
    response = api.get(f"/api/screening/{session.id}/state", headers=CANDIDATE)
    assert response.json()["status"] == "completed"
    assert _fresh(db, application.id).analysis_status == "transcription_failed"
    assert scheduled == [] and calls == []


def test_a_session_with_no_audio_is_still_not_taken(db, world, scheduled):
    application, session = _running_session(db, world, audio=False)
    _go_idle(db, session.id, hours=25)
    assert voice.sweep_abandoned(db) == 1
    assert _fresh(db, application.id).analysis_status == "not_taken"


def test_an_intake_session_is_not_retried_by_the_sweep(db, world, monkeypatch):
    session = VoiceSession(company_id=world["company"].id, purpose="intake", owner_user_id=world["people"]["hr"]["id"],
                           language="en", status="paused", plan=[{"text": "Q", "source": "role"}],
                           last_activity_at=_now() - timedelta(hours=25))
    db.add(session)
    db.commit()
    path = recordings.save_turn_audio(world["company"].id, f"session-{session.id}", 1, b"voice", ".webm")
    db.add(VoiceTurn(session_id=session.id, position=1, question_text="Q", question_source="role",
                     transcript_status="failed", audio_path=path))
    db.commit()
    calls = _stt(monkeypatch, ANSWER)
    assert voice.sweep_abandoned(db) == 1
    assert calls == []


def _swept(db, world, monkeypatch, answered=()):
    application, session = _running_session(db, world, answered=answered)
    _go_idle(db, session.id, hours=25)
    _stt(monkeypatch, AIProviderError("down"))
    assert voice.sweep_abandoned(db) == 1
    assert _fresh(db, application.id).analysis_status == "transcription_failed"
    return application, session


def _retry(api, world, application):
    return api.post(_url(world, f"/applications/{application.id}/transcription/retry"), headers=_hr(world))


def test_hr_retry_runs_stt_and_then_analysis(db, world, api, monkeypatch):
    application, session = _swept(db, world, monkeypatch)
    calls = _stt(monkeypatch, ANSWER)
    response = _retry(api, world, application)
    assert response.status_code == 202, response.text
    assert len(calls) == 1
    row = _fresh(db, application.id)
    assert row.analysis_status == "done" and row.interview_band == "few"
    assert _paid_analysis_calls(db) == 1
    assert db.query(VoiceTurn).filter_by(session_id=session.id).one().transcript == ANSWER
    assert db.query(AuditLog).filter_by(action="transcription_retried", target_id=application.id).count() == 1
    assert application.id not in _lane(api, world, "transcription_failed")


def test_hr_retry_during_the_outage_pays_for_no_analysis(db, world, api, monkeypatch):
    application, _session = _swept(db, world, monkeypatch)
    calls = _stt(monkeypatch, AIProviderError("still down"))
    assert _retry(api, world, application).status_code == 202
    assert len(calls) == 1
    assert _fresh(db, application.id).analysis_status == "transcription_failed"
    assert _paid_analysis_calls(db) == 0
    assert application.id in _lane(api, world, "transcription_failed")


def test_hr_retry_only_applies_to_a_failed_transcription(db, world, api):
    application = make_application(db, world["job"], analysis_status="failed")
    assert _retry(api, world, application).status_code == 409


def test_a_second_hr_retry_while_one_runs_is_refused(db, world, api, monkeypatch):
    application, _session = _swept(db, world, monkeypatch)
    row = _fresh(db, application.id)
    row.analysis_status = "running"
    db.commit()
    assert _retry(api, world, application).status_code == 409


def test_hr_retry_is_for_hr_of_this_company(db, world, api, monkeypatch):
    application, _session = _swept(db, world, monkeypatch)
    employee = api.post(_url(world, f"/applications/{application.id}/transcription/retry"), headers=world["people"]["emp"]["headers"])
    assert employee.status_code == 403
    foreign = api.post(f"/api/companies/{world['other'].id}/applications/{application.id}/transcription/retry",
                       headers=world["people"]["hr2"]["headers"])
    assert foreign.status_code == 404


def test_hr_retry_of_a_deleted_application_is_refused(db, world, api, monkeypatch):
    application, _session = _swept(db, world, monkeypatch)
    row = _fresh(db, application.id)
    row.anonymized_at = datetime.now(timezone.utc)
    db.commit()
    assert _retry(api, world, application).status_code == 409


def test_hr_retry_discards_stt_if_a_restart_was_granted_meanwhile(db, world, monkeypatch):
    application, session = _swept(db, world, monkeypatch)
    application_id = application.id
    row = _fresh(db, application_id)
    row.analysis_status = "running"
    db.commit()

    def restarted(*_args, **_kwargs):
        other = SessionLocal()
        try:
            found = other.get(Application, application_id)
            found.stage = "invited"
            found.analysis_status = None
            other.commit()
        finally:
            other.close()
        return _heard(ANSWER)

    monkeypatch.setattr(voice.gateway, "transcribe", restarted)
    analysis.retry_transcription(application_id)
    assert _paid_analysis_calls(db) == 0
    assert db.query(VoiceTurn).filter_by(session_id=session.id).one().transcript is None
    assert _fresh(db, application_id).analysis_status is None


def test_bulk_reject_refuses_a_technical_problem(db, world, api, monkeypatch):
    application, _session = _swept(db, world, monkeypatch)
    response = api.post(_url(world, f"/jobs/{world['job'].id}/decisions/bulk"), headers=_hr(world),
                        json={"application_ids": [application.id]})
    assert response.status_code == 409
    assert _fresh(db, application.id).hr_decision == "pending"


def test_hr_may_still_decide_one_technical_problem_by_hand(db, world, api, monkeypatch):
    application, _session = _swept(db, world, monkeypatch)
    response = api.post(_url(world, f"/applications/{application.id}/decision"), headers=_hr(world), json={"decision": "approved"})
    assert response.status_code == 200, response.text


def test_analysis_of_a_session_with_a_failed_transcript_is_not_recorded_as_not_taken(db, world):
    application, session = _running_session(db, world)
    row = _fresh(db, application.id)
    row.stage = "ready_for_hr"
    row.analysis_status = "failed"
    db.get(VoiceSession, session.id).status = "completed"
    db.commit()
    analysis.run(application.id)
    assert _fresh(db, application.id).analysis_status == "transcription_failed"
    assert _paid_analysis_calls(db) == 0


# M-1


def test_a_restart_clears_interview_evidence_and_keeps_the_cv_evidence(db, world, api):
    application = make_application(db, world["job"], band="many", analysis_status="done")
    _session, turns = make_session(db, application, [(1, "Q", "An answer", None)])
    requirement = world["requirements"][0]
    db.add(RequirementResult(application_id=application.id, requirement_id=requirement.id, source="cv", status="met", quote="cv quote"))
    db.add(RequirementResult(application_id=application.id, requirement_id=requirement.id, source="interview", status="evidence",
                             quote="An answer", voice_turn_id=turns[0].id))
    claim = add_claims(db, application, ["Claim"])[0]
    claim.status, claim.evidence_quote, claim.voice_turn_id = "explained", "An answer", turns[0].id
    db.add(CultureNote(application_id=application.id, value_node_id=world["value"].id, note="n", quote="An answer", voice_turn_id=turns[0].id))
    db.commit()

    response = api.post(_url(world, f"/applications/{application.id}/restart"), headers=_hr(world))
    assert response.status_code == 200, response.text

    db.rollback()
    db.expire_all()
    results = db.query(RequirementResult).filter_by(application_id=application.id).all()
    assert [(row.source, row.status, row.quote) for row in results] == [("cv", "met", "cv quote")]
    assert db.query(CultureNote).filter_by(application_id=application.id).count() == 0
    kept = db.query(CvClaim).filter_by(application_id=application.id).one()
    assert (kept.text, kept.quote) == ("Claim", "Claim")
    assert (kept.status, kept.evidence_quote, kept.voice_turn_id) == (None, None, None)


# M-2


def test_recovery_includes_a_retry_a_crash_left_running(db, world):
    stranded = make_application(db, world["job"], "#A1", analysis_status="running")
    make_session(db, stranded, [(1, "Q", "An answer", None)])
    done = make_application(db, world["job"], "#A2", analysis_status="done", band="few")
    assert analysis.requeue_interrupted() == [stranded.id]
    row = _fresh(db, stranded.id)
    assert row.stage == "ready_for_hr" and row.analysis_status == "failed"
    assert _fresh(db, done.id).analysis_status == "done"
    analysis.run(stranded.id)
    assert _fresh(db, stranded.id).analysis_status == "done"


def test_a_running_retry_shows_in_the_analysing_lane(db, world, api):
    application = make_application(db, world["job"], analysis_status="running")
    assert application.id in _lane(api, world, "analyzing")
    assert application.id not in _lane(api, world, "not_interviewed")


# M-9


def _cv_failed(db, world, alias="#A1"):
    return make_application(db, world["job"], alias, stage="cv_failed", cv_status=None, processing_error=cv_processing.TRY_AGAIN)


def _invite(api, world, application):
    return api.post(_url(world, f"/applications/{application.id}/invite-anyway"), headers=_hr(world))


def test_a_cv_that_could_not_be_processed_is_visible_to_hr(db, world, api):
    application = _cv_failed(db, world)
    assert _lane(api, world, "cv_failed") == [application.id]


def test_invite_anyway_opens_the_door_and_leaves_cv_status_empty(db, world, api):
    application = _cv_failed(db, world)
    calls_before = db.query(AIUsageLog).count()
    response = _invite(api, world, application)
    assert response.status_code == 200, response.text
    row = _fresh(db, application.id)
    assert row.stage == "invited" and row.cv_status is None and row.cv_status_reason is None and row.processing_error is None
    assert db.query(AIUsageLog).count() == calls_before
    audit = db.query(AuditLog).filter_by(action="invited_without_cv", target_id=application.id).one()
    assert audit.actor_user_id == world["people"]["hr"]["id"]
    assert application.id in _lane(api, world, "not_interviewed")
    assert application.id not in _lane(api, world, "cv_failed")
    assert db.query(Notification).filter_by(application_id=application.id, kind="invited").count() == 1


def test_invite_anyway_is_for_hr_and_only_from_that_stage(db, world, api):
    application = _cv_failed(db, world)
    employee = api.post(_url(world, f"/applications/{application.id}/invite-anyway"), headers=world["people"]["emp"]["headers"])
    assert employee.status_code == 403
    invited = make_application(db, world["job"], "#A2", stage="invited")
    assert _invite(api, world, invited).status_code == 409
    row = _fresh(db, application.id)
    row.anonymized_at = datetime.now(timezone.utc)
    db.commit()
    assert _invite(api, world, application).status_code == 409


def test_the_candidate_may_withdraw_while_the_cv_could_not_be_processed(db, world, api):
    application = _cv_failed(db, world)
    response = api.post(f"/api/applications/{application.id}/withdraw", headers=CANDIDATE, json={"reason": "No longer looking"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "withdrawn"
    assert _fresh(db, application.id).stage == "withdrawn"
    assert application.id in _lane(api, world, "withdrawn")


def test_cv_failed_transitions():
    for target in ("cv_processing", "invited", "withdrawn"):
        advance(Application(stage="cv_failed"), target)
    with pytest.raises(InvalidTransition):
        advance(Application(stage="cv_failed"), "ready_for_hr")


def test_a_candidate_invited_without_a_cv_label_can_be_interviewed_and_stays_visible(db, world, api):
    application = _cv_failed(db, world)
    assert _invite(api, world, application).status_code == 200
    fit = api.get(f"/api/applications/{application.id}/fit", headers=CANDIDATE)
    assert fit.status_code == 200
    assert {row["fit"] for row in fit.json()["requirements"]} == {"not_assessed"}
    response = api.post(f"/api/screening/{application.id}/start", headers=CANDIDATE,
                        json={"consent_version": consents.VERSION, "language": "en"})
    assert response.status_code == 200, response.text
    assert db.query(Consent).filter_by(application_id=application.id).count() == 1
    assert "does not mention" not in response.json()["question_text"]

    row = _fresh(db, application.id)
    row.stage = "ready_for_hr"
    row.analysis_status = "done"
    row.interview_band = "many"
    db.commit()
    assert application.id in _lane(api, world, "cv_failed")
    assert board.cell_for(_fresh(db, application.id)) is None
    decided = api.post(_url(world, f"/applications/{application.id}/decision"), headers=_hr(world), json={"decision": "approved"})
    assert decided.status_code == 200


def test_the_invitation_without_a_cv_says_nothing_about_the_cv():
    for subject, body in decisions.INVITED_WITHOUT_CV.values():
        assert "{title}" in subject and "{title}" in body
        assert "CV" not in body
