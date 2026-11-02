"""What withdrawing a consent does. Recording: everything said is gone, and HR is told plainly. CV: no further AI on it."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ai.providers import fake
from app.ai.types import TranscriptResult, Usage
from app.core import storage
from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, AuditLog, CompanyMember, Company, Consent, CultureNote, CvClaim, Job, JobRequirement, KbNode,
    Notification, RequirementResult, VoiceSession, VoiceTurn,
)
from app.hiring import analysis, consents, cv_processing, retention, voice
from app.hiring.board import NOT_ENOUGH_EVIDENCE
from app.hiring.state import CONSENT_WITHDRAWN
from tests.helpers import auth_header, make_user

CANDIDATE = "candidate@example.test"
OTHER = "other@example.test"
HR = "hr@example.test"
SPOKEN = "I ran the billing service for two years"
RECORDING = "recording_screening"
CV = "cv_processing"


@pytest.fixture(autouse=True)
def recordings_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path / "recordings"))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    return tmp_path / "recordings"


@pytest.fixture(autouse=True)
def scheduled(monkeypatch):
    calls = []
    monkeypatch.setattr(voice, "schedule_analysis", calls.append)
    return calls


@pytest.fixture
def forbid_ai(monkeypatch):
    """Call it from the moment AI must stop: starting an interview plans it with AI."""
    def boom(*_args, **_kwargs):
        raise AssertionError("AI must not be called after a withdrawal")

    def forbid():
        for name in ("generate_structured", "transcribe", "synthesize", "embed"):
            monkeypatch.setattr("app.ai.gateway." + name, boom)

    return forbid


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme", default_locale="en", retention_days=30)
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend Developer", slug="acme-backend", description="d", status="published",
              version=1, interview_languages=["en", "vi"])
    db.add(job)
    db.flush()
    requirement = JobRequirement(company_id=company.id, job_id=job.id, text="Docker", must_have=True, visibility="public", position=0)
    node = KbNode(company_id=company.id, type="value", title="Candor", body="b", language="en", visibility="public", status="published")
    db.add_all([requirement, node])
    db.flush()
    hr, user = make_user(db, HR), make_user(db, CANDIDATE)
    make_user(db, OTHER)
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    application = Application(company_id=company.id, job_id=job.id, job_version=1, candidate_user_id=user.id, alias="#A1",
                              stage="invited", cv_text_blind="blind", cv_status="not_met", cv_suffix=".pdf")
    db.add(application)
    db.flush()
    db.add(RequirementResult(application_id=application.id, requirement_id=requirement.id, source="cv", status="not_found",
                             quote="cv quote"))
    db.add(CvClaim(application_id=application.id, text="Claim", quote="Improved speed by 40%"))
    db.add(Consent(user_id=user.id, company_id=company.id, application_id=application.id, purpose=CV, text_version=consents.VERSION))
    db.commit()
    return SimpleNamespace(company_id=company.id, job_id=job.id, application_id=application.id, user_id=user.id,
                           requirement_id=requirement.id, node_id=node.id)


def hr_url(world, tail):
    return f"/api/companies/{world.company_id}{tail}"


def start(client, world):
    response = client.post(f"/api/screening/{world.application_id}/start", json={"consent_version": consents.VERSION, "language": "en"},
                           headers=auth_header(CANDIDATE))
    assert response.status_code == 200, response.text
    return response.json()


def answer(client, session_id, position, data=SPOKEN.encode()):
    return client.post(f"/api/screening/{session_id}/turns/{position}/answer", files={"file": ("a.webm", data, "audio/webm")},
                       headers=auth_header(CANDIDATE))


def consent_id(client, purpose):
    rows = client.get("/api/me/consents", headers=auth_header(CANDIDATE)).json()
    return next(row["id"] for row in rows if row["purpose"] == purpose)


def withdraw(client, purpose, email=CANDIDATE, row_id=None):
    row_id = row_id or consent_id(client, purpose)
    return client.post(f"/api/me/consents/{row_id}/withdraw", headers=auth_header(email))


def application_row(db, world):
    db.rollback()
    db.expire_all()
    return db.get(Application, world.application_id)


def files_in(directory):
    return [path for path in directory.rglob("*") if path.is_file()] if directory.exists() else []


def turns(db, session_id):
    db.rollback()
    db.expire_all()
    return db.query(VoiceTurn).filter_by(session_id=session_id).order_by(VoiceTurn.position).all()


def run_analysis_result(world, claim_id):
    return json.dumps({
        "requirements": [{"requirement_id": world.requirement_id, "status": "evidence", "quote": SPOKEN, "position": 1}],
        "claims": [{"claim_id": claim_id, "status": "explained", "quote": SPOKEN, "position": 1}],
        "culture_notes": [{"value_node_id": world.node_id, "note": "Candid", "quote": SPOKEN, "position": 1}],
        "suggestion": "Talk to them",
    })


@pytest.fixture
def analysed(client, db, world, scheduled):
    """A whole interview: answers, an analysis with quotes, and a brief that holds them."""
    from app.database.sql_models import CandidateBrief

    state = start(client, world)
    session_id = state["session_id"]
    position = state["position"]
    while position is not None:
        body = answer(client, session_id, position).json()
        position = body["position"]
    assert scheduled == [world.application_id]
    claim_id = db.query(CvClaim).filter_by(application_id=world.application_id).one().id
    fake.enqueue("session_analysis", run_analysis_result(world, claim_id))
    analysis.run(world.application_id)
    application = application_row(db, world)
    assert application.analysis_status == "done" and application.interview_band == "many"
    db.add(CandidateBrief(company_id=world.company_id, application_id=world.application_id, language="en",
                          content={"strengths": [{"original_quote": SPOKEN}]}))
    db.commit()
    return SimpleNamespace(session_id=session_id)


# 1. Recording consent, in the middle of an interview


def test_withdrawing_mid_session_ends_it_and_sends_the_application_to_hr(client, db, world, recordings_dir):
    state = start(client, world)
    assert answer(client, state["session_id"], 1).status_code == 200
    assert files_in(recordings_dir)

    response = withdraw(client, RECORDING)

    assert response.status_code == 200
    application = application_row(db, world)
    assert application.stage == "ready_for_hr" and application.analysis_status == CONSENT_WITHDRAWN
    assert db.get(VoiceSession, state["session_id"]).status == voice.ABANDONED
    assert db.get(VoiceSession, state["session_id"]).finished_at is not None
    for turn in turns(db, state["session_id"]):
        assert turn.audio_path is None and turn.transcript is None and turn.audio_seconds is None
    assert files_in(recordings_dir) == []
    assert SPOKEN not in repr([row.transcript for row in db.query(VoiceTurn).all()])


def test_a_follow_up_written_from_the_answer_is_erased_too(client, db, world):
    state = start(client, world)
    fake.enqueue("session_followup", json.dumps({"needs_followup": True, "question": f"You said {SPOKEN}. Which service?"}))
    assert answer(client, state["session_id"], 1).json()["is_followup"] is True
    assert withdraw(client, RECORDING).status_code == 200
    follow_up = next(turn for turn in turns(db, state["session_id"]) if turn.is_followup)
    assert follow_up.question_text == ""


def test_the_sweep_after_a_withdrawal_schedules_no_analysis(client, db, world, scheduled, forbid_ai):
    start(client, world)
    assert withdraw(client, RECORDING).status_code == 200
    forbid_ai()
    assert voice.sweep_abandoned(db, datetime.now(timezone.utc) + timedelta(days=5)) == 0
    assert scheduled == []
    assert application_row(db, world).analysis_status == CONSENT_WITHDRAWN


def test_an_answer_after_a_withdrawal_gets_409_with_a_code_and_no_ai(client, db, world, forbid_ai):
    state = start(client, world)
    assert withdraw(client, RECORDING).status_code == 200
    forbid_ai()
    response = answer(client, state["session_id"], 1)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == consents.RECORDING_CONSENT_WITHDRAWN
    assert turns(db, state["session_id"])[0].audio_path is None


def test_a_withdrawal_during_transcription_stores_nothing_and_gets_the_same_409(client, db, world, monkeypatch, recordings_dir):
    state = start(client, world)
    row_id = consent_id(client, RECORDING)

    def withdraw_meanwhile(*_args, **_kwargs):
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        return TranscriptResult(text=SPOKEN, language="en", provider="fake", model="m", usage=Usage(audio_seconds=4.0), latency_ms=1)

    monkeypatch.setattr(voice.gateway, "transcribe", withdraw_meanwhile)
    response = answer(client, state["session_id"], 1)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == consents.RECORDING_CONSENT_WITHDRAWN
    assert files_in(recordings_dir) == []
    assert turns(db, state["session_id"])[0].transcript is None


# 2. Recording consent, around the analysis


def test_an_analysis_waiting_to_run_is_cancelled(client, db, world, forbid_ai):
    state = start(client, world)
    forbid_ai()
    db.query(VoiceSession).filter_by(id=state["session_id"]).update({"status": voice.COMPLETED})
    db.query(Application).filter_by(id=world.application_id).update({"stage": "session_completed"})
    db.commit()
    assert withdraw(client, RECORDING).status_code == 200
    analysis.run(world.application_id)
    application = application_row(db, world)
    assert application.stage == "ready_for_hr" and application.analysis_status == CONSENT_WITHDRAWN


@pytest.mark.parametrize("stage", ["analyzing", "session_completed"])
def test_withdrawing_while_analysis_waits_or_runs_reaches_hr(client, db, world, stage):
    start(client, world)
    db.query(Application).filter_by(id=world.application_id).update({"stage": stage})
    db.commit()
    assert withdraw(client, RECORDING).status_code == 200
    application = application_row(db, world)
    assert application.stage == "ready_for_hr" and application.analysis_status == CONSENT_WITHDRAWN


def test_a_withdrawal_during_the_analysis_call_keeps_its_result_out(client, db, world, monkeypatch):
    state = start(client, world)
    db.add(VoiceTurn(session_id=state["session_id"], position=2, question_text="q", question_source="role", transcript=SPOKEN,
                     transcript_status="transcribed"))
    db.query(Application).filter_by(id=world.application_id).update({"stage": "session_completed"})
    db.query(VoiceSession).filter_by(id=state["session_id"]).update({"status": voice.COMPLETED})
    db.commit()
    row_id = consent_id(client, RECORDING)
    real = analysis.gateway.generate_structured

    def withdraw_meanwhile(*args, **kwargs):
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        return real(*args, **kwargs)

    monkeypatch.setattr(analysis.gateway, "generate_structured", withdraw_meanwhile)
    fake.enqueue("session_analysis", json.dumps({
        "requirements": [{"requirement_id": world.requirement_id, "status": "evidence", "quote": SPOKEN, "position": 2}],
        "claims": [], "culture_notes": [], "suggestion": "Talk to them",
    }))
    analysis.run(world.application_id)
    application = application_row(db, world)
    assert application.analysis_status == CONSENT_WITHDRAWN
    assert application.interview_band is None and application.ai_suggestion is None
    assert db.query(RequirementResult).filter_by(application_id=world.application_id, source="interview").count() == 0


def test_an_analysis_failing_after_a_withdrawal_does_not_replace_the_marker(client, db, world, monkeypatch):
    state = start(client, world)
    db.add(VoiceTurn(session_id=state["session_id"], position=2, question_text="q", question_source="role", transcript=SPOKEN,
                     transcript_status="transcribed"))
    db.query(Application).filter_by(id=world.application_id).update({"stage": "session_completed"})
    db.commit()
    row_id = consent_id(client, RECORDING)

    def withdraw_and_fail(*_args, **_kwargs):
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        raise RuntimeError("provider down")

    monkeypatch.setattr(analysis.gateway, "generate_structured", withdraw_and_fail)
    analysis.run(world.application_id)
    assert application_row(db, world).analysis_status == CONSENT_WITHDRAWN


def test_withdrawing_after_analysis_blanks_everything_drawn_from_the_interview_and_keeps_the_cv(client, db, world, analysed, recordings_dir):
    from app.database.sql_models import CandidateBrief

    assert withdraw(client, RECORDING).status_code == 200
    application = application_row(db, world)
    assert application.interview_band is None and application.ai_suggestion is None
    assert application.analysis_status == CONSENT_WITHDRAWN
    assert application.cv_status == "not_met" and application.cv_text_blind == "blind"
    results = db.query(RequirementResult).filter_by(application_id=world.application_id).all()
    assert [(row.source, row.quote) for row in results] == [("cv", "cv quote")]
    claim = db.query(CvClaim).filter_by(application_id=world.application_id).one()
    assert (claim.text, claim.status, claim.evidence_quote, claim.voice_turn_id) == ("Claim", None, None, None)
    assert db.query(CultureNote).filter_by(application_id=world.application_id).count() == 0
    assert db.query(CandidateBrief).filter_by(application_id=world.application_id).count() == 0
    assert files_in(recordings_dir) == []


def test_a_brief_being_written_during_a_withdrawal_is_not_stored(client, db, world, analysed, monkeypatch):
    from app.bridges import brief
    from app.database.sql_models import CandidateBrief

    response = client.post(hr_url(world, f"/applications/{world.application_id}/decision"),
                           json={"decision": "approved"}, headers=auth_header(HR))
    assert response.status_code == 200
    row_id = consent_id(client, RECORDING)
    real = brief.gateway.generate_structured

    def withdraw_meanwhile(*args, **kwargs):
        result = real(*args, **kwargs)
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        return result

    monkeypatch.setattr(brief.gateway, "generate_structured", withdraw_meanwhile)
    db.rollback()
    response = client.post(hr_url(world, f"/applications/{world.application_id}/brief"), json={"language": "en"}, headers=auth_header(HR))
    assert response.status_code == 409
    db.rollback()
    assert db.query(CandidateBrief).filter_by(application_id=world.application_id).count() == 0


def test_a_brief_written_after_a_withdrawal_holds_only_the_cv(client, db, world, analysed):
    from app.database.sql_models import CandidateBrief

    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    response = client.post(hr_url(world, f"/applications/{world.application_id}/decision"),
                           json={"decision": "approved"}, headers=auth_header(HR))
    assert response.status_code == 200
    response = client.post(hr_url(world, f"/applications/{world.application_id}/brief"), json={"language": "en"}, headers=auth_header(HR))
    assert response.status_code == 200, response.text
    assert SPOKEN not in response.text
    db.rollback()
    assert db.query(CandidateBrief).filter_by(application_id=world.application_id).count() == 1


# 3. What HR sees and may do


def test_hr_sees_the_application_in_not_enough_evidence_with_a_neutral_note(client, db, world, analysed):
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    board = client.get(hr_url(world, f"/jobs/{world.job_id}/board"), headers=auth_header(HR)).json()
    cards = board["cells"][NOT_ENOUGH_EVIDENCE]
    assert [card["id"] for card in cards] == [world.application_id]
    assert cards[0]["analysis_status"] == CONSENT_WITHDRAWN
    assert cards[0]["interview_note"] == "withdrew consent to recording"
    assert all(not rows for name, rows in board["cells"].items() if name != NOT_ENOUGH_EVIDENCE)


def test_the_detail_holds_nothing_said_and_the_audio_is_gone(client, db, world, analysed):
    audio = hr_url(world, f"/applications/{world.application_id}/turns/1/audio")
    assert client.get(audio, headers=auth_header(HR)).status_code == 200
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    response = client.get(hr_url(world, f"/applications/{world.application_id}"), headers=auth_header(HR))
    assert response.status_code == 200
    body = response.json()
    assert SPOKEN not in response.text
    assert body["transcript"] == [] and body["suggestion"] is None and body["culture_notes"] == []
    assert body["interview_note"] == "withdrew consent to recording"
    assert client.get(audio, headers=auth_header(HR)).status_code == 404


def test_bulk_rejection_refuses_it_and_a_single_decision_stays_free(client, db, world, analysed):
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    bulk = client.post(hr_url(world, f"/jobs/{world.job_id}/decisions/bulk"),
                       json={"application_ids": [world.application_id]}, headers=auth_header(HR))
    assert bulk.status_code == 409
    assert application_row(db, world).hr_decision == "pending"
    decided = client.post(hr_url(world, f"/applications/{world.application_id}/decision"),
                          json={"decision": "approved"}, headers=auth_header(HR))
    assert decided.status_code == 200
    assert application_row(db, world).hr_decision == "approved"


def test_hr_can_neither_restart_nor_retry_after_a_withdrawal(client, db, world, analysed):
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    headers = auth_header(HR)
    assert client.post(hr_url(world, f"/applications/{world.application_id}/restart"), headers=headers).status_code == 409
    assert client.post(hr_url(world, f"/applications/{world.application_id}/analysis/retry"), headers=headers).status_code == 409
    assert application_row(db, world).stage == "ready_for_hr"


def test_a_decision_already_made_is_kept(client, db, world, analysed):
    response = client.post(hr_url(world, f"/applications/{world.application_id}/decision"),
                           json={"decision": "rejected"}, headers=auth_header(HR))
    assert response.status_code == 200
    assert withdraw(client, RECORDING).status_code == 200
    application = application_row(db, world)
    assert application.hr_decision == "rejected" and application.analysis_status == CONSENT_WITHDRAWN
    seen = client.get(f"/api/applications/{world.application_id}", headers=auth_header(CANDIDATE)).json()
    assert seen["decision"] == "rejected"


def test_the_candidate_sees_a_plain_status_with_no_marker(client, db, world):
    start(client, world)
    assert withdraw(client, RECORDING).status_code == 200
    response = client.get(f"/api/applications/{world.application_id}", headers=auth_header(CANDIDATE))
    assert response.json()["status"] == "with_hr"
    assert CONSENT_WITHDRAWN not in response.text


# 4. The route


def test_only_the_owner_can_withdraw_and_a_second_call_changes_nothing(client, db, world):
    start(client, world)
    row_id = consent_id(client, RECORDING)
    assert withdraw(client, RECORDING, email=OTHER, row_id=row_id).status_code == 404
    assert application_row(db, world).stage == "session_in_progress"
    first = withdraw(client, RECORDING, row_id=row_id)
    second = withdraw(client, RECORDING, row_id=row_id)
    assert first.status_code == second.status_code == 200
    assert first.json()["withdrawn_at"] == second.json()["withdrawn_at"]
    db.rollback()
    assert db.query(AuditLog).filter_by(action="consent_withdrawn", target_id=row_id).count() == 1


def test_every_recording_consent_of_the_application_goes_together(client, db, world):
    start(client, world)
    db.add(Consent(user_id=world.user_id, company_id=world.company_id, application_id=world.application_id, purpose=RECORDING,
                   text_version=consents.VERSION))
    db.commit()
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    db.expire_all()
    rows = db.query(Consent).filter_by(application_id=world.application_id, purpose=RECORDING).all()
    assert len(rows) == 2 and all(row.withdrawn_at is not None for row in rows)


def test_a_file_that_cannot_be_deleted_changes_nothing_and_can_be_retried(app, client, db, world, recordings_dir, monkeypatch):
    from fastapi.testclient import TestClient

    from app.hiring import recordings

    state = start(client, world)
    assert answer(client, state["session_id"], 1).status_code == 200
    real = recordings.delete

    def refuse(_path):
        raise PermissionError("no")

    monkeypatch.setattr(recordings, "delete", refuse)
    with TestClient(app, raise_server_exceptions=False) as quiet:
        assert withdraw(quiet, RECORDING).status_code == 503
    application = application_row(db, world)
    assert application.stage == "session_in_progress"
    assert turns(db, state["session_id"])[0].audio_path is not None
    monkeypatch.setattr(recordings, "delete", real)
    assert withdraw(client, RECORDING).status_code == 200
    assert files_in(recordings_dir) == []


# 5. CV consent


def docx_bytes():
    import io

    from docx import Document

    document = Document()
    document.add_paragraph("I built services in Python.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def reupload(client, world):
    return client.post(f"/api/applications/{world.application_id}/reupload",
                       files={"file": ("cv.docx", docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                       headers=auth_header(CANDIDATE))


def test_withdrawing_cv_consent_keeps_existing_results(client, db, world):
    assert withdraw(client, CV).status_code == 200
    application = application_row(db, world)
    assert application.stage == "invited" and application.cv_status == "not_met" and application.cv_text_blind == "blind"
    assert db.query(RequirementResult).filter_by(application_id=world.application_id, source="cv").count() == 1


def test_a_reupload_after_withdrawing_cv_consent_gets_409_with_a_code_and_no_job(client, db, world, monkeypatch):
    db.query(Application).filter_by(id=world.application_id).update({"stage": "cv_failed"})
    db.commit()
    assert withdraw(client, CV).status_code == 200
    ran = []
    monkeypatch.setattr(cv_processing, "run", ran.append)
    response = reupload(client, world)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == consents.CV_CONSENT_WITHDRAWN
    assert ran == []


def test_a_reupload_refused_only_at_the_final_check_stores_nothing(client, db, world, monkeypatch):
    """The candidate withdraws while the file uploads, after the first check passed."""
    from app.routers import applications as routes

    db.query(Application).filter_by(id=world.application_id).update({"stage": "cv_failed"})
    db.commit()
    row_id = consent_id(client, CV)
    real = routes.read_upload

    async def withdraw_meanwhile(*args, **kwargs):
        data = await real(*args, **kwargs)
        other = SessionLocal()
        try:
            other.query(Consent).filter_by(id=row_id).update({"withdrawn_at": datetime.now(timezone.utc)})
            other.commit()
        finally:
            other.close()
        return data

    monkeypatch.setattr(routes, "read_upload", withdraw_meanwhile)
    monkeypatch.setattr(storage, "save_bytes", lambda *_a, **_k: pytest.fail("Nothing may be stored"))
    response = reupload(client, world)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == consents.CV_CONSENT_WITHDRAWN


@pytest.mark.parametrize("stage", ["submitted", "cv_processing"])
def test_withdrawing_while_the_cv_waits_or_is_read_stops_the_job(client, db, world, forbid_ai, stage):
    db.query(Application).filter_by(id=world.application_id).update({"stage": stage, "cv_file_path": "x.pdf"})
    db.commit()
    assert withdraw(client, CV).status_code == 200
    assert application_row(db, world).stage == "cv_failed"
    forbid_ai()
    cv_processing.run(world.application_id)
    assert application_row(db, world).stage == "cv_failed"


def test_a_job_finishing_after_the_withdrawal_gives_way(client, db, world, monkeypatch):
    db.query(Application).filter_by(id=world.application_id).update({"stage": "submitted"})
    db.commit()
    row_id = consent_id(client, CV)
    path = storage.save_bytes(world.company_id, "cv", ".docx", docx_bytes())
    db.query(Application).filter_by(id=world.application_id).update({"cv_file_path": path, "cv_suffix": ".docx"})
    db.commit()

    def withdraw_and_mask(raw, *, company_id, known_terms=()):
        assert withdraw(client, CV, row_id=row_id).status_code == 200
        return SimpleNamespace(blind_text="blind 2", blind_hash="h2")

    monkeypatch.setattr(cv_processing.identity, "mask", withdraw_and_mask)
    cv_processing.run(world.application_id)
    application = application_row(db, world)
    assert application.stage == "cv_failed" and application.cv_text_blind != "blind 2"


def test_a_new_interview_cannot_start_after_withdrawing_cv_consent(client, db, world, forbid_ai):
    assert withdraw(client, CV).status_code == 200
    forbid_ai()
    response = client.post(f"/api/screening/{world.application_id}/start", json={"consent_version": consents.VERSION, "language": "en"},
                           headers=auth_header(CANDIDATE))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == consents.CV_CONSENT_WITHDRAWN
    db.rollback()
    assert db.query(VoiceSession).count() == 0


def test_an_interview_already_running_can_still_be_resumed(client, db, world):
    state = start(client, world)
    assert withdraw(client, CV).status_code == 200
    assert start(client, world)["session_id"] == state["session_id"]


def test_the_fairness_check_stops_after_withdrawing_cv_consent(client, db, world, forbid_ai):
    db.query(Application).filter_by(id=world.application_id).update({"cv_text_raw": "raw"})
    db.commit()
    assert withdraw(client, CV).status_code == 200
    forbid_ai()
    response = client.post(hr_url(world, "/trust/fairness-check"), json={"application_id": world.application_id},
                           headers=auth_header(HR))
    assert response.status_code == 409


def test_no_reminder_invites_to_an_interview_that_can_no_longer_start(client, db, world):
    db.query(Application).filter_by(id=world.application_id).update({"created_at": datetime.now(timezone.utc) - timedelta(days=5)})
    db.commit()
    assert withdraw(client, CV).status_code == 200
    db.rollback()
    assert retention.send_reminders(db) == 0
    assert db.query(Notification).count() == 0


def test_a_cv_consent_never_withdrawn_blocks_nothing(client, db, world):
    assert not consents.was_withdrawn(db, world.application_id, CV)
    start(client, world)


# 6. Beside the technical-problem lane, the cost limits and rejection feedback


def _with_failed_transcript(client, db, world, recordings_dir, analysis_status=None):
    """An answer with audio and no transcript, in a session that has ended."""
    from app.hiring import recordings

    state = start(client, world)
    path = recordings.save_turn_audio(world.company_id, world.application_id, 1, b"spoken", ".webm")
    row = db.query(VoiceTurn).filter_by(session_id=state["session_id"], position=1).one()
    row.audio_path, row.transcript_status = path, voice.STT_FAILED
    db.query(VoiceSession).filter_by(id=state["session_id"]).update({"status": voice.COMPLETED})
    db.query(Application).filter_by(id=world.application_id).update({"stage": "ready_for_hr", "analysis_status": analysis_status})
    db.commit()
    return state


def test_withdrawing_moves_a_transcription_failure_out_of_its_lane_and_retry_is_refused(client, db, world, recordings_dir):
    from app.hiring.state import TRANSCRIPTION_FAILED

    _with_failed_transcript(client, db, world, recordings_dir, TRANSCRIPTION_FAILED)
    db.rollback()
    board = client.get(hr_url(world, f"/jobs/{world.job_id}/board"), headers=auth_header(HR)).json()
    assert [card["id"] for card in board["lanes"]["transcription_failed"]] == [world.application_id]
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    board = client.get(hr_url(world, f"/jobs/{world.job_id}/board"), headers=auth_header(HR)).json()
    assert board["lanes"]["transcription_failed"] == []
    assert [card["id"] for card in board["cells"][NOT_ENOUGH_EVIDENCE]] == [world.application_id]
    retry = client.post(hr_url(world, f"/applications/{world.application_id}/transcription/retry"), headers=auth_header(HR))
    assert retry.status_code == 409
    assert files_in(recordings_dir) == []
    detail = client.get(hr_url(world, f"/applications/{world.application_id}"), headers=auth_header(HR)).json()
    assert detail["restart_available"] is False


def test_a_withdrawal_during_hrs_transcription_retry_keeps_the_marker_and_stores_nothing(client, db, world, monkeypatch, recordings_dir):
    state = _with_failed_transcript(client, db, world, recordings_dir, "running")
    row_id = consent_id(client, RECORDING)

    def withdraw_meanwhile(*_args, **_kwargs):
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        return TranscriptResult(text=SPOKEN, language="en", provider="fake", model="m", usage=Usage(audio_seconds=4.0), latency_ms=1)

    monkeypatch.setattr(voice.gateway, "transcribe", withdraw_meanwhile)
    analysis.retry_transcription(world.application_id)
    assert application_row(db, world).analysis_status == CONSENT_WITHDRAWN
    assert turns(db, state["session_id"])[0].transcript is None
    assert files_in(recordings_dir) == []


def test_analysis_meeting_a_failed_transcript_does_not_replace_the_marker(db, world, client, recordings_dir):
    _with_failed_transcript(client, db, world, recordings_dir, CONSENT_WITHDRAWN)
    analysis._record_transcription_failed(db, world.application_id)
    assert application_row(db, world).analysis_status == CONSENT_WITHDRAWN


def test_a_claim_on_the_position_ends_with_the_withdrawal(client, db, world, monkeypatch):
    state = start(client, world)
    row_id = consent_id(client, RECORDING)

    def withdraw_meanwhile(*_args, **_kwargs):
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        return TranscriptResult(text=SPOKEN, language="en", provider="fake", model="m", usage=Usage(audio_seconds=4.0), latency_ms=1)

    monkeypatch.setattr(voice.gateway, "transcribe", withdraw_meanwhile)
    response = answer(client, state["session_id"], 1)
    assert response.status_code == 409 and response.json()["detail"]["code"] == consents.RECORDING_CONSENT_WITHDRAWN
    assert turns(db, state["session_id"])[0].stt_started_at is None


def question_audio_url(session_id):
    return f"/api/screening/{session_id}/turns/1/question-audio"


def test_cached_question_audio_goes_with_the_recording(client, db, world, recordings_dir):
    state = start(client, world)
    assert client.get(question_audio_url(state["session_id"]), headers=auth_header(CANDIDATE)).status_code == 200
    assert turns(db, state["session_id"])[0].question_audio_path is not None
    assert files_in(recordings_dir)
    assert withdraw(client, RECORDING).status_code == 200
    assert turns(db, state["session_id"])[0].question_audio_path is None
    assert files_in(recordings_dir) == []
    assert client.get(question_audio_url(state["session_id"]), headers=auth_header(CANDIDATE)).status_code == 409


def test_question_audio_being_made_during_a_withdrawal_is_not_kept(client, db, world, monkeypatch, recordings_dir):
    state = start(client, world)
    row_id = consent_id(client, RECORDING)
    real = voice.gateway.synthesize

    def withdraw_meanwhile(*args, **kwargs):
        result = real(*args, **kwargs)
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        return result

    monkeypatch.setattr(voice.gateway, "synthesize", withdraw_meanwhile)
    assert client.get(question_audio_url(state["session_id"]), headers=auth_header(CANDIDATE)).status_code == 409
    assert turns(db, state["session_id"])[0].question_audio_path is None
    assert files_in(recordings_dir) == []


def test_after_a_withdrawal_a_deleted_brief_reads_as_no_brief(client, db, world, analysed):
    response = client.post(hr_url(world, f"/applications/{world.application_id}/decision"),
                           json={"decision": "approved"}, headers=auth_header(HR))
    assert response.status_code == 200
    url = hr_url(world, f"/applications/{world.application_id}")
    assert client.get(url, headers=auth_header(HR)).json()["brief_status"] == "draft"
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    assert client.get(url, headers=auth_header(HR)).json()["brief_status"] is None
    assert client.get(f"{url}/brief", headers=auth_header(HR)).status_code == 404


def _feedback(db, world, status):
    from app.database.sql_models import RejectionFeedback

    db.query(Application).filter_by(id=world.application_id).update({"hr_decision": "rejected", "hr_decided_at": datetime.now(timezone.utc)})
    db.query(RejectionFeedback).filter_by(application_id=world.application_id).delete()
    db.add(RejectionFeedback(company_id=world.company_id, application_id=world.application_id, language="en",
                             draft=f"You said: {SPOKEN}", status=status))
    db.commit()


def test_an_unsent_rejection_message_quoting_the_answers_goes_with_the_recording(client, db, world, analysed):
    from app.database.sql_models import RejectionFeedback

    _feedback(db, world, "draft")
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    assert db.query(RejectionFeedback).filter_by(application_id=world.application_id).count() == 0
    redraft = client.post(hr_url(world, f"/applications/{world.application_id}/feedback/draft"), headers=auth_header(HR))
    assert redraft.status_code == 200, redraft.text
    assert SPOKEN not in redraft.text and redraft.json()["source"] == "template_no_session"


def test_a_sent_rejection_message_keeps_its_status_and_loses_its_quotes(client, db, world, analysed):
    from app.database.sql_models import RejectionFeedback

    _feedback(db, world, "sent")
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    db.expire_all()
    row = db.query(RejectionFeedback).filter_by(application_id=world.application_id).one()
    assert row.status == "sent" and SPOKEN not in row.draft and row.draft


def test_a_rejection_message_being_written_during_a_withdrawal_is_not_stored(client, db, world, analysed, monkeypatch):
    from app.database.sql_models import RejectionFeedback
    from app.posthire import feedback

    db.query(Application).filter_by(id=world.application_id).update({"hr_decision": "rejected", "hr_decided_at": datetime.now(timezone.utc)})
    db.commit()
    row_id = consent_id(client, RECORDING)
    real = feedback._generate

    def withdraw_meanwhile(plan):
        result = real(plan)
        assert withdraw(client, RECORDING, row_id=row_id).status_code == 200
        return result

    monkeypatch.setattr(feedback, "_generate", withdraw_meanwhile)
    response = client.post(hr_url(world, f"/applications/{world.application_id}/feedback/draft"), headers=auth_header(HR))
    assert response.status_code == 409
    db.rollback()
    assert db.query(RejectionFeedback).filter_by(application_id=world.application_id).count() == 0


# 7. Beside the CV lane


def test_cv_consent_withdrawn_shows_in_the_cv_lane_with_no_invitation(client, db, world):
    db.query(Application).filter_by(id=world.application_id).update({"stage": "submitted", "cv_status": None})
    db.commit()
    assert withdraw(client, CV).status_code == 200
    db.rollback()
    board = client.get(hr_url(world, f"/jobs/{world.job_id}/board"), headers=auth_header(HR)).json()
    assert [card["id"] for card in board["lanes"]["cv_failed"]] == [world.application_id]
    detail = client.get(hr_url(world, f"/applications/{world.application_id}"), headers=auth_header(HR)).json()
    assert detail["cv_consent_withdrawn"] is True
    invite = client.post(hr_url(world, f"/applications/{world.application_id}/invite-anyway"), headers=auth_header(HR))
    assert invite.status_code == 409
    assert application_row(db, world).stage == "cv_failed"


def test_the_candidate_is_told_why_the_cv_stopped_and_can_still_withdraw_the_application(client, db, world):
    db.query(Application).filter_by(id=world.application_id).update({"stage": "submitted", "cv_status": None})
    db.commit()
    assert withdraw(client, CV).status_code == 200
    seen = client.get(f"/api/applications/{world.application_id}", headers=auth_header(CANDIDATE)).json()
    assert seen["status"] == "cv_unreadable" and seen["failure_reason"] == "consent_withdrawn"
    assert client.post(f"/api/applications/{world.application_id}/withdraw", headers=auth_header(CANDIDATE)).status_code == 200


def test_a_cv_failure_with_consent_standing_can_still_be_invited(client, db, world):
    db.query(Application).filter_by(id=world.application_id).update({"stage": "cv_failed", "cv_status": None})
    db.commit()
    db.rollback()
    invite = client.post(hr_url(world, f"/applications/{world.application_id}/invite-anyway"), headers=auth_header(HR))
    assert invite.status_code == 200, invite.text


def test_recording_withdrawn_after_an_invitation_without_a_cv_goes_to_not_enough_evidence(client, db, world):
    db.query(Application).filter_by(id=world.application_id).update({"cv_status": None})
    db.commit()
    start(client, world)
    assert withdraw(client, RECORDING).status_code == 200
    db.rollback()
    board = client.get(hr_url(world, f"/jobs/{world.job_id}/board"), headers=auth_header(HR)).json()
    assert [card["id"] for card in board["cells"][NOT_ENOUGH_EVIDENCE]] == [world.application_id]
    assert board["lanes"]["cv_failed"] == []

