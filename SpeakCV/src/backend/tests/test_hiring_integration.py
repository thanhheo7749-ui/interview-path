"""Where the voice engine, analysis, retention, the board and the admin routes meet."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.ai.providers import fake
from app.ai.providers.fake import FakeProvider
from app.core import storage
from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, AuditLog, Company, CompanyMember, Consent, CultureNote, CvClaim, Job, JobChannelLink, JobRequirement,
    KbNode, Notification, RequirementResult, ScreeningCache, User, VoiceSession, VoiceTurn,
)
from app.hiring import analysis, consents, cv_processing, decisions, notify, recordings, retention, voice
from app.main import create_app
from tests.helpers import auth_header, make_user

CANDIDATE = "candidate@example.test"
HR = "hr@example.test"
ANSWER = "I built an API with FastAPI at my last job"
QUOTE = "built an API with FastAPI"


@pytest.fixture(autouse=True)
def directories(tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path / "recordings"))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    return tmp_path


@pytest.fixture(autouse=True)
def scheduled(monkeypatch):
    calls = []
    monkeypatch.setattr(voice, "schedule_analysis", calls.append)
    return calls


@pytest.fixture
def clock(monkeypatch):
    state = SimpleNamespace(now=datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0))
    monkeypatch.setattr(voice, "_now", lambda: state.now)
    return state


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme", default_locale="en", retention_days=30)
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend Developer", slug="acme-backend", description="d", status="published",
              version=1, interview_languages=["en", "vi"])
    db.add(job)
    db.flush()
    requirement = JobRequirement(company_id=company.id, job_id=job.id, text="FastAPI", must_have=True, visibility="public",
                                 position=0)
    value = KbNode(company_id=company.id, type="value", title="Candor", body="b", language="en", visibility="public",
                   status="published")
    db.add_all([requirement, value])
    db.flush()
    candidate, hr = make_user(db, CANDIDATE), make_user(db, HR)
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    db.commit()
    world = SimpleNamespace(company_id=company.id, job_id=job.id, requirement_id=requirement.id, value_id=value.id,
                            candidate_id=candidate.id, hr_id=hr.id)
    world.application_id = application(db, world).id
    return world


_aliases = iter(range(1, 100000))


def application(db, world, **columns):
    fields = dict(company_id=world.company_id, job_id=world.job_id, job_version=1, candidate_user_id=world.candidate_id,
                  alias=f"#A{next(_aliases)}", stage="invited", cv_text_blind="blind", cv_status="not_met")
    row = Application(**{**fields, **columns})
    db.add(row)
    db.commit()
    return row


def fresh(db, model, row_id):
    db.rollback()
    db.expire_all()
    return db.get(model, row_id)


def start(client, world, language="en", application_id=None):
    return client.post(f"/api/screening/{application_id or world.application_id}/start",
                       json={"consent_version": consents.VERSION, "language": language}, headers=auth_header(CANDIDATE))


def answer(client, session_id, position, data=ANSWER.encode()):
    return client.post(f"/api/screening/{session_id}/turns/{position}/answer",
                       files={"file": ("a.webm", data, "audio/webm")}, headers=auth_header(CANDIDATE))


def state(client, session_id):
    return client.get(f"/api/screening/{session_id}/state", headers=auth_header(CANDIDATE))


def hr_url(world, tail):
    return f"/api/companies/{world.company_id}{tail}"


def board(client, world):
    response = client.get(hr_url(world, f"/jobs/{world.job_id}/board"), headers=auth_header(HR))
    assert response.status_code == 200, response.text
    return response.json()


def delete_application(application_id):
    """What the candidate's delete does, from another session, as another request would."""
    other = SessionLocal()
    try:
        retention.anonymize_application(other, other.get(Application, application_id), trigger=retention.TRIGGER_CANDIDATE)
    finally:
        other.close()


def audio_files(directories):
    root = directories / "recordings"
    return [path for path in root.rglob("*") if path.is_file()] if root.exists() else []


def finish_interview(client, session_id):
    position = state(client, session_id).json()["position"]
    while position is not None:
        body = answer(client, session_id, position).json()
        position = body["position"]
    return body


# 1. Nothing personal is written after a deletion


def test_a_deletion_during_transcription_discards_the_answer(client, db, world, directories, monkeypatch, scheduled):
    session_id = start(client, world).json()["session_id"]
    real = FakeProvider.transcribe

    def deleting(self, **kwargs):
        delete_application(world.application_id)
        return real(self, **kwargs)

    monkeypatch.setattr(FakeProvider, "transcribe", deleting)
    assert answer(client, session_id, 1).status_code == 404

    db.rollback()
    turns = db.query(VoiceTurn).filter_by(session_id=session_id).all()
    assert len(turns) == 1 and turns[0].transcript is None and turns[0].audio_path is None
    assert turns[0].transcript_status == "pending" and turns[0].audio_seconds is None
    assert audio_files(directories) == []
    assert scheduled == []


def test_a_deletion_during_the_followup_call_discards_the_answer(client, db, world, directories):
    session_id = start(client, world).json()["session_id"]

    def deleting(system, messages, schema):
        delete_application(world.application_id)
        return json.dumps({"needs_followup": True, "question": "Which project was that?"})

    fake.register("session_followup", deleting)
    assert answer(client, session_id, 1).status_code == 404
    db.rollback()
    rows = db.query(VoiceTurn).filter_by(session_id=session_id).all()
    assert len(rows) == 1 and rows[0].transcript is None and rows[0].audio_path is None
    assert audio_files(directories) == []


def test_a_failed_transcription_during_a_deletion_keeps_no_audio(client, db, world, directories, monkeypatch):
    session_id = start(client, world).json()["session_id"]

    def deleting(self, **kwargs):
        delete_application(world.application_id)
        raise voice.AIError("down")

    monkeypatch.setattr(FakeProvider, "transcribe", deleting)
    assert answer(client, session_id, 1).status_code == 404
    assert audio_files(directories) == []


def analysable(db, world, transcript=ANSWER):
    row = application(db, world, stage="session_completed", cv_status="meets", interview_band=None)
    session = VoiceSession(company_id=world.company_id, purpose="screening", application_id=row.id,
                           owner_user_id=world.candidate_id, language="en", status="completed", plan=[{"text": "q"}])
    db.add(session)
    db.flush()
    db.add(VoiceTurn(session_id=session.id, position=1, question_text="q", question_source="requirement",
                     transcript=transcript, transcript_status="transcribed" if transcript else "pending"))
    db.add(CvClaim(application_id=row.id, text="Claim", quote="Claim"))
    db.commit()
    return row.id


def analysis_output(world, claim_id=None):
    return json.dumps({
        "requirements": [{"requirement_id": world.requirement_id, "status": "evidence", "quote": QUOTE, "position": 1}],
        "claims": [{"claim_id": claim_id or 0, "status": "explained", "quote": QUOTE, "position": 1}],
        "culture_notes": [{"value_node_id": world.value_id, "note": "note", "quote": QUOTE, "position": 1}],
        "suggestion": "A suggestion for HR",
    })


def test_a_deletion_during_analysis_discards_the_result(db, world):
    application_id = analysable(db, world)
    claim_id = db.query(CvClaim).filter_by(application_id=application_id).one().id

    def deleting(system, messages, schema):
        delete_application(application_id)
        return analysis_output(world, claim_id)

    fake.register("session_analysis", deleting)
    analysis.run(application_id)

    row = fresh(db, Application, application_id)
    assert row.ai_suggestion is None and row.interview_band is None and row.analysis_status != "done"
    results = db.query(RequirementResult).filter_by(application_id=application_id, source="interview").all()
    assert results == []
    assert db.query(CultureNote).filter_by(application_id=application_id).count() == 0
    claim = db.get(CvClaim, claim_id)
    assert claim.evidence_quote is None and claim.status is None and claim.text == ""
    assert db.query(AuditLog).filter_by(action="interview_analyzed", target_id=application_id).count() == 0


def test_a_failed_analysis_after_a_deletion_marks_nothing(db, world):
    application_id = analysable(db, world)

    def deleting(system, messages, schema):
        delete_application(application_id)
        raise voice.AIError("down")

    fake.register("session_analysis", deleting)
    analysis.run(application_id)
    assert fresh(db, Application, application_id).analysis_status != "failed"


def test_analysis_of_a_deleted_application_makes_no_ai_call(db, world):
    application_id = analysable(db, world)
    delete_application(application_id)
    calls = []
    fake.register("session_analysis", lambda *a: calls.append(1) or analysis_output(world))
    analysis.run(application_id)
    assert calls == []


def cv_job(db, world, monkeypatch):
    path = storage.save_bytes(world.company_id, "cv", ".pdf", b"cv")
    row = application(db, world, stage="submitted", cv_file_path=path, cv_suffix=".pdf", cv_text_blind=None, cv_status=None)
    monkeypatch.setattr(cv_processing, "extract_cv", lambda data, suffix: SimpleNamespace(text="Built FastAPI things", hidden_detected=False))
    return row.id


def test_a_deletion_during_the_cv_assessment_writes_no_cache_row_and_no_results(db, world, monkeypatch):
    application_id = cv_job(db, world, monkeypatch)

    def deleting(system, messages, schema):
        delete_application(application_id)
        return json.dumps({"requirements": [{"requirement_id": world.requirement_id, "status": "met", "quote": "Built FastAPI things"}],
                           "claims": [{"text": "Built things", "quote": "Built FastAPI things"}]})

    fake.register("cv_assess", deleting)
    cv_processing.run(application_id)

    row = fresh(db, Application, application_id)
    assert row.cv_text_raw is None and row.cv_text_blind is None and row.cv_status is None
    assert db.query(ScreeningCache).count() == 0
    assert db.query(RequirementResult).filter_by(application_id=application_id).count() == 0
    assert db.query(CvClaim).filter_by(application_id=application_id).count() == 0
    assert db.query(Notification).count() == 0


def test_a_deletion_during_the_cv_masking_writes_nothing(db, world, monkeypatch):
    from app.hiring import identity

    application_id = cv_job(db, world, monkeypatch)

    def deleting(raw_text, *, company_id, known_terms=()):
        delete_application(application_id)
        return identity.MaskResult(blind_text=raw_text, blind_hash=identity.hash_of(raw_text))

    monkeypatch.setattr(identity, "mask", deleting)
    cv_processing.run(application_id)
    row = fresh(db, Application, application_id)
    assert row.cv_text_raw is None and row.cv_text_blind is None and row.stage == "cv_failed"
    assert row.processing_error is None


def test_a_deleted_application_is_never_claimed_by_a_cv_job(db, world, monkeypatch):
    application_id = cv_job(db, world, monkeypatch)
    delete_application(application_id)
    fresh(db, Application, application_id)
    assert cv_processing._claim(db, application_id) is False


def test_deleting_closes_a_running_session(client, db, world):
    session_id = start(client, world).json()["session_id"]
    delete_application(world.application_id)
    assert fresh(db, VoiceSession, session_id).status not in voice.ACTIVE_STATUSES


# 2. Anonymized rows hold NULLs, and no route falls over them


@pytest.fixture
def quiet_client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def anonymized_with_session(client, db, world):
    session_id = start(client, world).json()["session_id"]
    assert answer(client, session_id, 1).status_code == 200
    row = fresh(db, Application, world.application_id)
    row.stage = "ready_for_hr"
    db.commit()
    delete_application(world.application_id)
    return session_id


def test_voice_routes_on_an_anonymized_application_get_404(client, quiet_client, db, world):
    session_id = anonymized_with_session(client, db, world)
    for response in (
        state(quiet_client, session_id),
        answer(quiet_client, session_id, 2),
        start(quiet_client, world),
        quiet_client.get(f"/api/screening/{session_id}/turns/1/question-audio", headers=auth_header(CANDIDATE)),
    ):
        assert response.status_code == 404, response.text


def test_the_engine_itself_refuses_a_session_of_a_deleted_application(client, db, world):
    session_id = start(client, world).json()["session_id"]
    db.rollback()
    row = db.get(VoiceSession, session_id)
    delete_application(world.application_id)
    with pytest.raises(voice.SessionGone):
        voice.current_state(db, row)
    with pytest.raises(voice.SessionGone):
        voice.submit_answer(db, row, 1, ANSWER.encode(), "audio/webm")


def test_the_board_leaves_out_an_anonymized_application(client, quiet_client, db, world):
    anonymized_with_session(client, db, world)
    body = board(quiet_client, world)
    assert all(card["id"] != world.application_id
               for group in (*body["cells"].values(), *body["lanes"].values()) for card in group)


def test_an_anonymized_interview_in_progress_leaves_no_lane_behind(client, quiet_client, db, world):
    start(client, world)
    delete_application(world.application_id)
    body = board(quiet_client, world)
    assert body["lanes"]["not_interviewed"] == []


def test_the_detail_route_refuses_an_anonymized_application(client, quiet_client, db, world):
    anonymized_with_session(client, db, world)
    response = quiet_client.get(hr_url(world, f"/applications/{world.application_id}"), headers=auth_header(HR))
    assert response.status_code == 404, response.text
    assert ANSWER not in response.text


def test_a_live_application_is_marked_as_not_anonymized(client, world):
    response = client.get(hr_url(world, f"/applications/{world.application_id}"), headers=auth_header(HR))
    assert response.json()["anonymized"] is False


@pytest.mark.parametrize("method,tail,payload,expected", [
    ("post", "decision", {"decision": "rejected"}, 409),
    ("post", "cv-status", {"cv_status": "meets", "reason": "A reason with content"}, 409),
    ("post", "restart", None, 409),
    ("post", "fast-track", None, 409),
    ("post", "reveal", None, 404),
    ("post", "analysis/retry", None, 409),
    ("get", "turns/1/audio", None, 404),
])
def test_hr_actions_on_an_anonymized_application(client, quiet_client, db, world, method, tail, payload, expected):
    anonymized_with_session(client, db, world)
    url = hr_url(world, f"/applications/{world.application_id}/{tail}")
    response = getattr(quiet_client, method)(url, headers=auth_header(HR), **({"json": payload} if payload else {}))
    assert response.status_code == expected, response.text
    row = fresh(db, Application, world.application_id)
    assert row.hr_decision == "pending" and row.stage == "ready_for_hr" and row.cv_status_correction_reason is None


def test_analysis_retry_on_an_anonymized_failed_application_gets_409(client, quiet_client, db, world):
    anonymized_with_session(client, db, world)
    row = fresh(db, Application, world.application_id)
    row.analysis_status = "failed"
    db.commit()
    response = quiet_client.post(hr_url(world, f"/applications/{world.application_id}/analysis/retry"), headers=auth_header(HR))
    assert response.status_code == 409


def test_the_fairness_check_on_an_anonymized_application_gets_404(client, quiet_client, db, world):
    anonymized_with_session(client, db, world)
    response = quiet_client.post(hr_url(world, "/trust/fairness-check"), json={"application_id": world.application_id},
                                 headers=auth_header(HR))
    assert response.status_code == 404


def test_retention_runs_again_over_anonymized_rows_without_harm(client, db, world):
    anonymized_with_session(client, db, world)
    db.rollback()
    assert retention.run(db, now=datetime.now(timezone.utc) + timedelta(days=400)) == 0
    assert retention.send_reminders(db, now=datetime.now(timezone.utc) + timedelta(days=400)) == 0
    assert voice.sweep_abandoned(db, now=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=400)) == 0


def test_a_candidate_lists_nothing_of_an_anonymized_application(client, db, world):
    anonymized_with_session(client, db, world)
    assert client.get("/api/me/applications", headers=auth_header(CANDIDATE)).json() == []
    assert client.get(f"/api/applications/{world.application_id}", headers=auth_header(CANDIDATE)).status_code == 404


# 3. Restarted audio


def restart_flow(client, db, world):
    first = start(client, world).json()["session_id"]
    finish_interview(client, first)
    analysis.run(world.application_id)
    assert fresh(db, Application, world.application_id).stage == "ready_for_hr"
    response = client.post(hr_url(world, f"/applications/{world.application_id}/restart"), headers=auth_header(HR))
    assert response.status_code == 200, response.text
    second = start(client, world).json()["session_id"]
    finish_interview(client, second)
    analysis.run(world.application_id)
    return first, second


def paths_of(db, session_id):
    db.rollback()
    db.expire_all()
    return [turn.audio_path for turn in db.query(VoiceTurn).filter_by(session_id=session_id).order_by(VoiceTurn.position)]


def test_decisions_and_start_agree_on_a_single_restart(client, db, world):
    first, second = restart_flow(client, db, world)
    assert fresh(db, VoiceSession, first).restart_count == 1
    assert fresh(db, VoiceSession, second).restart_count == 1
    assert all("/restart-1/" in path for path in paths_of(db, second))
    assert all("/restart-" not in path for path in paths_of(db, first))
    assert fresh(db, Application, world.application_id).stage == "ready_for_hr"
    again = client.post(hr_url(world, f"/applications/{world.application_id}/restart"), headers=auth_header(HR))
    assert again.status_code == 409


def test_retention_deletes_each_turns_audio_of_a_restarted_session(client, db, world, directories):
    first, second = restart_flow(client, db, world)
    paths = paths_of(db, first) + paths_of(db, second)
    assert audio_files(directories) and len(audio_files(directories)) == len(paths)
    other = recordings.save_turn_audio(world.company_id, 999999, 1, b"another application", ".webm")
    row = fresh(db, Application, world.application_id)
    row.hr_decided_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=31)
    db.commit()
    assert retention.run(db) == 1
    assert [path.read_bytes() for path in audio_files(directories)] == [b"another application"]
    assert recordings.read(other) == b"another application"
    assert all(path is None for path in paths_of(db, first) + paths_of(db, second))


def test_retention_follows_the_stored_path_and_not_a_folder_it_guesses(client, db, world, directories):
    session_id = start(client, world).json()["session_id"]
    moved = recordings.save_turn_audio(world.company_id, "somewhere/else", 7, b"moved", ".webm")
    row = db.query(VoiceTurn).filter_by(session_id=session_id, position=1).one()
    row.audio_path = moved
    db.commit()
    delete_application(world.application_id)
    assert audio_files(directories) == []


# 4. The clock counts active time


def running(client, db, world):
    session_id = start(client, world).json()["session_id"]
    db.rollback()
    return session_id


def set_clock(db, session_id, *, active, idle, started_ago=None):
    row = fresh(db, VoiceSession, session_id)
    row.active_seconds = active
    row.last_activity_at = voice._now() - timedelta(seconds=idle)
    if started_ago is not None:
        row.started_at = voice._now() - timedelta(seconds=started_ago)
    db.commit()


def active_seconds(db, session_id):
    return fresh(db, VoiceSession, session_id).active_seconds


def test_a_new_session_starts_its_clock_at_zero(client, db, world, clock):
    session_id = running(client, db, world)
    row = fresh(db, VoiceSession, session_id)
    assert row.active_seconds == 0 and row.last_activity_at == clock.now


def test_a_candidate_who_drops_at_5_minutes_and_returns_at_20_can_continue(client, db, world, clock, scheduled):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=300, idle=15 * 60, started_ago=20 * 60)
    body = state(client, session_id).json()
    assert body["status"] == "in_progress" and body["position"] == 1
    assert body["time_left_seconds"] == 900 - 300 - 210
    assert active_seconds(db, session_id) == 510
    assert scheduled == []
    assert answer(client, session_id, 1).status_code == 200
    assert fresh(db, VoiceTurn, db.query(VoiceTurn.id).filter_by(session_id=session_id, position=1).scalar()).transcript == ANSWER


def test_a_gap_within_the_cap_counts_in_full_and_a_longer_one_counts_the_cap(client, db, world, clock):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=100, idle=150)
    state(client, session_id)
    assert active_seconds(db, session_id) == 250
    set_clock(db, session_id, active=100, idle=211)
    state(client, session_id)
    assert active_seconds(db, session_id) == 310
    assert fresh(db, VoiceSession, session_id).last_activity_at == clock.now


def test_a_poll_does_not_count_the_same_time_twice(client, db, world, clock):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=100, idle=60)
    for _ in range(3):
        assert state(client, session_id).json()["time_left_seconds"] == 900 - 160
    assert active_seconds(db, session_id) == 160


def test_polls_faster_than_a_second_still_add_up(client, db, world, clock):
    session_id = running(client, db, world)
    for _ in range(10):
        clock.now += timedelta(milliseconds=300)
        state(client, session_id)
    assert active_seconds(db, session_id) == 3


def test_an_answer_counts_time_too(client, db, world, clock):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=100, idle=40)
    assert answer(client, session_id, 1).status_code == 200
    assert active_seconds(db, session_id) == 140


def test_closing_uses_active_time_and_not_the_wall_clock(client, db, world, clock):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=100, idle=0, started_ago=14 * 60)
    assert state(client, session_id).json()["status"] == "in_progress"
    set_clock(db, session_id, active=781, idle=0, started_ago=100)
    assert state(client, session_id).json()["status"] == "closing"


def test_the_hard_stop_uses_active_time_and_not_the_wall_clock(client, db, world, clock, scheduled):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=0, idle=0, started_ago=16 * 60)
    assert state(client, session_id).json()["status"] == "in_progress"
    assert scheduled == []
    set_clock(db, session_id, active=890, idle=20, started_ago=100)
    assert state(client, session_id).json()["status"] == "completed"
    assert scheduled == [world.application_id]


def test_the_limits_live_in_one_table_per_purpose():
    rules = voice.PURPOSES["screening"]
    assert (rules.closing_after_seconds, rules.hard_limit_seconds, rules.resume_hours, rules.max_counted_gap_seconds) == (780, 900, 24, 210)


# 5. Sessions abandoned for 24 hours


DAY = 24 * 60 * 60


def paid_calls():
    calls = []
    fake.register("session_analysis", lambda *a: calls.append(1) or json.dumps(
        {"requirements": [], "claims": [], "culture_notes": [], "suggestion": ""}))
    return calls


def card_of(body, application_id):
    for group in (*body["cells"].values(), *body["lanes"].values()):
        for card in group:
            if card["id"] == application_id:
                return card
    return None


@pytest.mark.parametrize("cv_status", ["meets", "not_met"])
def test_no_answers_after_24_idle_hours_means_abandoned_and_no_analysis(client, db, world, clock, scheduled, cv_status):
    calls = paid_calls()
    row = fresh(db, Application, world.application_id)
    row.cv_status = cv_status
    db.commit()
    session_id = running(client, db, world)
    set_clock(db, session_id, active=30, idle=DAY + 5)

    body = state(client, session_id).json()
    assert body["status"] == "abandoned" and body["question_text"] is None
    assert scheduled == [] and calls == []
    row = fresh(db, Application, world.application_id)
    assert row.stage == "ready_for_hr" and row.interview_band is None and row.cv_status == cv_status
    assert fresh(db, VoiceSession, session_id).status == "abandoned"

    response = board(client, world)
    assert world.application_id in [card["id"] for card in response["cells"]["not_enough_evidence"]]
    assert card_of(response, world.application_id)["interview_note"] == "did not take the interview"
    detail = client.get(hr_url(world, f"/applications/{world.application_id}"), headers=auth_header(HR)).json()
    assert detail["cell"] == "not_enough_evidence" and detail["interview_note"] == "did not take the interview"
    assert db.query(AuditLog).filter_by(action="voice_session_abandoned", target_id=session_id).count() == 1


def test_a_session_within_24_hours_of_its_last_activity_is_not_abandoned(client, db, world, clock):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=30, idle=DAY - 5, started_ago=3 * DAY)
    assert state(client, session_id).json()["status"] == "in_progress"


def test_silent_answers_only_are_zero_answers(client, db, world, clock, scheduled, monkeypatch):
    session_id = running(client, db, world)
    turn = db.query(VoiceTurn).filter_by(session_id=session_id, position=1).one()
    turn.transcript_status = "no_answer"
    db.add(VoiceTurn(session_id=session_id, position=2, question_text="next", question_source="requirement"))
    db.commit()
    set_clock(db, session_id, active=30, idle=DAY + 5)
    assert state(client, session_id).json()["status"] == "abandoned"
    assert scheduled == []


def test_some_answers_after_24_idle_hours_complete_and_go_to_analysis(client, db, world, clock, scheduled):
    session_id = running(client, db, world)
    assert answer(client, session_id, 1).status_code == 200
    set_clock(db, session_id, active=60, idle=DAY + 5)
    upload = answer(client, session_id, 2)
    assert upload.status_code == 200 and upload.json()["status"] == "completed"
    row = fresh(db, VoiceSession, session_id)
    assert row.status == "completed" and row.finished_at is not None
    assert fresh(db, Application, world.application_id).stage == "session_completed"
    assert scheduled == [world.application_id]
    assert db.query(VoiceTurn).filter_by(session_id=session_id, position=2).one().transcript is None


def test_the_band_reflects_the_questions_left_unanswered(client, db, world, clock):
    second = JobRequirement(company_id=world.company_id, job_id=world.job_id, text="Docker", must_have=True, visibility="public", position=1)
    db.add(second)
    db.commit()
    session_id = running(client, db, world)
    assert answer(client, session_id, 1).status_code == 200
    set_clock(db, session_id, active=60, idle=DAY + 5)
    assert state(client, session_id).json()["status"] == "completed"
    # The model claims evidence for the unanswered requirement too; nothing in the transcripts supports it.
    fake.enqueue("session_analysis", json.dumps({
        "requirements": [
            {"requirement_id": world.requirement_id, "status": "evidence", "quote": QUOTE, "position": 1},
            {"requirement_id": second.id, "status": "evidence", "quote": "ran Docker for years", "position": 2},
        ],
        "claims": [], "culture_notes": [], "suggestion": "",
    }))
    analysis.run(world.application_id)
    row = fresh(db, Application, world.application_id)
    assert row.stage == "ready_for_hr" and row.interview_band == "few" and row.analysis_status == "done"


def test_the_daily_sweep_finishes_both_kinds_and_leaves_the_rest(client, db, world, clock, scheduled):
    calls = paid_calls()
    silent = world.application_id
    spoke = application(db, world).id
    recent = application(db, world).id
    silent_session = start(client, world, application_id=silent).json()["session_id"]
    spoke_session = start(client, world, application_id=spoke).json()["session_id"]
    assert answer(client, spoke_session, 1).status_code == 200
    recent_session = start(client, world, application_id=recent).json()["session_id"]
    set_clock(db, silent_session, active=10, idle=DAY + 5)
    set_clock(db, spoke_session, active=10, idle=DAY + 5)
    set_clock(db, recent_session, active=10, idle=DAY - 5)
    db.rollback()

    assert voice.sweep_abandoned(db) == 2
    assert fresh(db, VoiceSession, silent_session).status == "abandoned"
    assert fresh(db, VoiceSession, spoke_session).status == "completed"
    assert fresh(db, VoiceSession, recent_session).status == "in_progress"
    assert scheduled == [spoke]
    assert calls == []
    assert fresh(db, Application, silent).stage == "ready_for_hr"
    assert voice.sweep_abandoned(db) == 0
    assert scheduled == [spoke]


def test_the_daily_pass_runs_the_sweep(monkeypatch):
    calls = []
    monkeypatch.setattr(voice, "sweep_abandoned", lambda _db: calls.append(1))
    monkeypatch.setattr(notify, "send_pending", lambda _db: 0)
    retention._daily_pass()
    assert calls == [1]


def test_an_abandoned_candidate_is_not_invited_again_but_hr_can_restart(client, db, world, clock):
    session_id = running(client, db, world)
    set_clock(db, session_id, active=30, idle=DAY + 5)
    db.rollback()
    assert voice.sweep_abandoned(db) == 1
    db.rollback()
    assert retention.send_reminders(db, now=datetime.now(timezone.utc) + timedelta(days=5)) == 0
    db.rollback()
    assert db.query(Notification).count() == 0
    assert start(client, world).status_code == 409

    response = client.post(hr_url(world, f"/applications/{world.application_id}/restart"), headers=auth_header(HR))
    assert response.status_code == 200, response.text
    row = fresh(db, Application, world.application_id)
    assert row.stage == "invited" and row.analysis_status is None
    fresh_start = start(client, world)
    assert fresh_start.status_code == 200 and fresh_start.json()["session_id"] != session_id
    assert fresh(db, VoiceSession, fresh_start.json()["session_id"]).restart_count == 1


def test_a_finished_session_with_no_answers_never_reaches_the_paid_analysis(db, world):
    calls = paid_calls()
    application_id = analysable(db, world, transcript=None)
    analysis.run(application_id)
    assert calls == []
    row = fresh(db, Application, application_id)
    assert row.stage == "ready_for_hr" and row.interview_band is None and row.ai_suggestion is None


def test_an_analysis_retry_with_no_answers_stays_free(db, world):
    calls = paid_calls()
    application_id = analysable(db, world, transcript=None)
    row = fresh(db, Application, application_id)
    row.stage, row.analysis_status = "ready_for_hr", "failed"
    db.commit()
    analysis.run(application_id)
    assert calls == []
    assert fresh(db, Application, application_id).analysis_status != "failed"


# 6. Startup recovery


def test_recovery_schedules_what_a_crash_left_behind(db, world, monkeypatch, scheduled):
    monkeypatch.setenv("APP_ENV", "production")
    waiting = analysable(db, world)
    running_when_it_crashed = analysable(db, world)
    row = fresh(db, Application, running_when_it_crashed)
    row.stage, row.analysis_status = "analyzing", "running"
    deleted = analysable(db, world)
    db.commit()
    delete_application(deleted)
    finished = application(db, world, stage="ready_for_hr", analysis_status="done").id
    failed = application(db, world, stage="ready_for_hr", analysis_status="failed").id

    assert sorted(analysis.recover_interrupted()) == sorted([waiting, running_when_it_crashed])
    assert sorted(scheduled) == sorted([waiting, running_when_it_crashed])
    assert finished not in scheduled and failed not in scheduled and deleted not in scheduled


def test_a_recovered_analysis_really_runs_to_the_end(db, world):
    application_id = analysable(db, world)
    row = fresh(db, Application, application_id)
    row.stage, row.analysis_status = "analyzing", "running"
    db.commit()
    fake.enqueue("session_analysis", analysis_output(world))
    assert analysis.requeue_interrupted() == [application_id]
    analysis.run(application_id)
    row = fresh(db, Application, application_id)
    assert row.stage == "ready_for_hr" and row.analysis_status == "done"


def test_recovery_does_nothing_under_test(db, world, scheduled):
    analysable(db, world)
    assert analysis.recover_interrupted() == []
    assert scheduled == []


def test_a_failing_schedule_does_not_stop_startup_recovery(db, world, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    first, second = analysable(db, world), analysable(db, world)

    def boom(_):
        raise RuntimeError("no threads")

    monkeypatch.setattr(voice, "schedule_analysis", boom)
    assert sorted(analysis.recover_interrupted()) == sorted([first, second])


def test_the_app_runs_recovery_at_startup(monkeypatch):
    calls = []
    monkeypatch.setattr(analysis, "recover_interrupted", lambda: calls.append(1))
    with TestClient(create_app()):
        assert calls == [1]


# 7. Notifications point at their application


def test_every_sender_fills_in_the_application(client, db, world, monkeypatch):
    application_id = cv_job(db, world, monkeypatch)
    cv_processing.run(application_id)
    invite = db.query(Notification).filter_by(kind="invited").one()
    assert invite.application_id == application_id

    row = fresh(db, Application, application_id)
    row.stage = "ready_for_hr"
    decisions.decide(db, row, "approved", world.hr_id)
    db.commit()
    assert db.query(Notification).filter_by(kind="decision").one().application_id == application_id

    waiting = application(db, world, created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=4)).id
    assert retention.send_reminders(db) == 1
    db.rollback()
    assert db.query(Notification).filter_by(kind="reminder").one().application_id == waiting


def linked_notification(db, world, application_id, subject):
    row = notify.enqueue(db, world.company_id, world.candidate_id, "decision", "en", subject, "body", application_id=application_id)
    db.commit()
    return row.id


def test_deleting_removes_this_applications_notifications_even_with_no_title_in_them(db, world):
    other = application(db, world).id
    generic = linked_notification(db, world, world.application_id, "An update on your application")
    kept = linked_notification(db, world, other, "An update on your application")
    delete_application(world.application_id)
    assert fresh(db, Notification, generic) is None
    assert fresh(db, Notification, kept) is not None


def test_a_linked_notification_naming_the_same_title_survives_for_its_own_application(db, world):
    other = application(db, world).id
    kept = linked_notification(db, world, other, "An update on Backend Developer")
    delete_application(world.application_id)
    assert fresh(db, Notification, kept) is not None


def test_old_rows_with_no_link_still_follow_the_title_rule(db, world):
    application(db, world)
    named = linked_notification(db, world, None, "An update on Backend Developer")
    generic = linked_notification(db, world, None, "Hello")
    delete_application(world.application_id)
    assert fresh(db, Notification, named) is None
    assert fresh(db, Notification, generic) is not None


# 8. Consent listing


def test_a_candidate_lists_their_own_consents_with_the_job_title(client, db, world):
    other_user = make_user(db, "other@example.test")
    db.add(Consent(user_id=other_user.id, company_id=world.company_id, application_id=world.application_id,
                   purpose="cv_processing", text_version="v0", language="en"))
    db.commit()
    shown = client.get(f"/api/applications/{world.application_id}/consents/recording_screening?language=vi",
                       headers=auth_header(CANDIDATE)).json()
    response = client.post(f"/api/screening/{world.application_id}/start", headers=auth_header(CANDIDATE), json={
        "consent_version": shown["version"], "language": "vi", "consent_language": shown["language"],
    })
    assert response.status_code == 200

    response = client.get("/api/me/consents", headers=auth_header(CANDIDATE))
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"id", "purpose", "version", "language", "granted_at", "withdrawn_at", "job_title"}
    assert (row["purpose"], row["version"], row["language"], row["job_title"]) == (
        "recording_screening", consents.VERSION, "vi", "Backend Developer")
    assert row["withdrawn_at"] is None and row["granted_at"]


def test_a_withdrawal_shows_in_the_list(client, db, world):
    start(client, world)
    consent_id = client.get("/api/me/consents", headers=auth_header(CANDIDATE)).json()[0]["id"]
    assert client.post(f"/api/me/consents/{consent_id}/withdraw", headers=auth_header(CANDIDATE)).status_code == 200
    assert client.get("/api/me/consents", headers=auth_header(CANDIDATE)).json()[0]["withdrawn_at"] is not None


def test_consent_listing_needs_a_login_and_holds_a_consent_with_no_application(client, db, world):
    assert client.get("/api/me/consents").status_code == 401
    db.add(Consent(user_id=world.candidate_id, company_id=world.company_id, purpose="cv_processing", text_version="v0"))
    db.commit()
    rows = client.get("/api/me/consents", headers=auth_header(CANDIDATE)).json()
    assert rows[0]["job_title"] is None and rows[0]["language"] is None


def test_an_anonymized_applications_consent_leaves_the_list(client, db, world):
    start(client, world)
    delete_application(world.application_id)
    assert client.get("/api/me/consents", headers=auth_header(CANDIDATE)).json() == []


# 9. Channel links


def test_a_channel_is_unique_per_job(db, world):
    db.add(JobChannelLink(company_id=world.company_id, job_id=world.job_id, channel="linkedin", token="one"))
    db.commit()
    db.add(JobChannelLink(company_id=world.company_id, job_id=world.job_id, channel="linkedin", token="two"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_request_that_loses_the_race_returns_the_winners_link(client, db, world, monkeypatch):
    from app.hiring import jobs

    real = jobs.ensure_channels
    tries = []

    def racing(session, job, channels):
        tries.append(1)
        if len(tries) > 1:
            return real(session, job, channels)
        job_id, company_id = job.id, job.company_id
        other = SessionLocal()
        other.add(JobChannelLink(company_id=company_id, job_id=job_id, channel="linkedin", token="winner"))
        other.commit()
        other.close()
        session.add(JobChannelLink(company_id=company_id, job_id=job_id, channel="linkedin", token="loser"))
        session.flush()

    monkeypatch.setattr(jobs, "ensure_channels", racing)
    response = client.post(hr_url(world, f"/jobs/{world.job_id}/channels"), json={"channels": ["linkedin"]}, headers=auth_header(HR))
    assert response.status_code == 200, response.text
    assert [row["token"] for row in response.json()] == ["winner"]
    assert len(tries) == 2
    db.rollback()
    assert db.query(JobChannelLink).filter_by(job_id=world.job_id).count() == 1


# 10. Admin deletes


def admin(db):
    make_user(db, "root@example.test", role="admin")
    return auth_header("root@example.test")


def test_admin_cannot_delete_a_user_with_personal_data_in_a_live_application(client, db, world):
    headers = admin(db)
    response = client.delete(f"/api/admin/users/{world.candidate_id}", headers=headers)
    assert response.status_code == 409
    assert "anonymize" in response.json()["detail"].lower()
    assert fresh(db, User, world.candidate_id) is not None


def test_admin_can_delete_a_user_once_their_applications_are_anonymized(client, db, world):
    headers = admin(db)
    delete_application(world.application_id)
    db.rollback()
    leftover = notify.enqueue(db, world.company_id, world.candidate_id, "reminder", "en", "Hello", "body")
    db.commit()
    leftover_id = leftover.id
    assert client.delete(f"/api/admin/users/{world.candidate_id}", headers=headers).status_code == 200
    assert fresh(db, User, world.candidate_id) is None
    assert fresh(db, Notification, leftover_id) is None
    assert fresh(db, Application, world.application_id) is not None


@pytest.mark.parametrize("table,column", [
    ("jobs", "created_by"), ("applications", "candidate_user_id"), ("applications", "cv_status_corrected_by"),
    ("applications", "hr_decided_by"), ("voice_sessions", "owner_user_id"), ("consents", "user_id"),
    ("audit_log", "actor_user_id"),
])
def test_nullable_links_to_users_set_null_on_delete(table, column):
    from app.database.database import Base

    keys = list(Base.metadata.tables[table].columns[column].foreign_keys)
    assert [key.ondelete for key in keys] == ["SET NULL"]
