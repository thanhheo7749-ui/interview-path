"""Manager Intake: requests, the plan, the voice routes for a manager, and the way a transcript reaches HR review."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.ai import gateway
from app.ai.providers import fake
from app.ai.types import AIProviderError
from app.bridges import intake
from app.database.sql_models import (
    Application, Company, CompanyMember, Department, HiringRequest, Job, KbChunk, KbDocument, KbIngestionJob, KbNode,
    VoiceSession, VoiceTurn,
)
from app.hiring import analysis, retention, voice
from tests.helpers import auth_header, iter_routes, make_user, route_path
from tests.helpers_jd import make_world

HR = "hr@acme.test"
MANAGER = "mgr@acme.test"
OTHER_MANAGER = "mgr2@acme.test"
OUTSIDER = "hr@other.test"
CANDIDATE = "cand@example.test"
ANSWER = "We need someone who ships on time without supervision."


@pytest.fixture(autouse=True)
def _dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path / "rec"))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "store"))


@pytest.fixture(autouse=True)
def scheduled(monkeypatch):
    calls = []
    monkeypatch.setattr(voice, "schedule_intake", calls.append)
    monkeypatch.setattr(voice, "schedule_analysis", lambda application_id: calls.append(("analysis", application_id)))
    return calls


@pytest.fixture
def world(db):
    return make_world(db)


def base(world):
    return f"/api/companies/{world.company.id}/hiring-requests"


def start(client, world, email=MANAGER, body=None, request_id=None):
    return client.post(f"{base(world)}/{request_id or world.request.id}/intake/start", json=body or {},
                       headers=auth_header(email))


def answer(client, session_id, position, text=ANSWER, email=MANAGER, content_type="audio/webm"):
    return client.post(f"/api/voice/{session_id}/turns/{position}/answer",
                       files={"file": ("a.bin", text.encode(), content_type)}, headers=auth_header(email))


def answer_all(client, session_id, state, text=ANSWER, email=MANAGER):
    while state["status"] in ("in_progress", "closing", "paused") and state["position"] is not None:
        state = answer(client, session_id, state["position"], text, email).json()
    return state


def session_row(db, session_id):
    db.rollback()
    db.expire_all()
    return db.get(VoiceSession, session_id)


def finished_session(client, db, world, text=ANSWER, language="en"):
    state = start(client, world, body={"language": language}).json()
    state = answer_all(client, state["session_id"], state, text)
    assert state["status"] == "completed"
    return session_row(db, state["session_id"])


# --- 1, 2: requests ---------------------------------------------------------------------------------------------

def test_hr_creates_a_request(client, world, db):
    response = client.post(base(world), json={"title": "Backend Developer", "manager_user_id": world.manager.id,
                                              "department_id": world.eng.id}, headers=auth_header(HR))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "open" and body["manager_user_id"] == world.manager.id
    assert body["department_id"] == world.eng.id


def test_manager_must_be_a_manager_of_this_company(client, world, db):
    hr_id, outsider = world.hr.id, world.outsider.id
    for user_id in (hr_id, outsider, 99999):
        response = client.post(base(world), json={"title": "X", "manager_user_id": user_id}, headers=auth_header(HR))
        assert response.status_code == 422


def test_department_of_another_company_is_404(client, world, db):
    foreign = Department(company_id=world.other.id, name="Foreign")
    db.add(foreign)
    db.commit()
    response = client.post(base(world), json={"title": "X", "manager_user_id": world.manager.id,
                                              "department_id": foreign.id}, headers=auth_header(HR))
    assert response.status_code == 404


def test_only_hr_creates(client, world):
    body = {"title": "X", "manager_user_id": world.manager.id}
    assert client.post(base(world), json=body, headers=auth_header(MANAGER)).status_code == 403
    assert client.post(base(world), json=body, headers=auth_header(OUTSIDER)).status_code == 403


def test_manager_lists_only_their_requests_and_employee_is_refused(client, world, db):
    db.add(HiringRequest(company_id=world.company.id, department_id=world.sales.id, title="Sales Lead",
                         manager_user_id=world.other_manager.id, created_by=world.hr.id))
    employee = make_user(db, "emp@acme.test")
    db.add(CompanyMember(company_id=world.company.id, user_id=employee.id, role="employee"))
    db.commit()
    mine = client.get(base(world), headers=auth_header(MANAGER)).json()
    assert [row["title"] for row in mine] == ["Backend Developer"]
    assert len(client.get(base(world), headers=auth_header(HR)).json()) == 2
    assert client.get(base(world), headers=auth_header("emp@acme.test")).status_code == 403
    other_id = db.query(HiringRequest.id).filter_by(title="Sales Lead").scalar()
    assert client.get(f"{base(world)}/{other_id}", headers=auth_header(MANAGER)).status_code == 404
    assert client.get(f"{base(world)}/{other_id}", headers=auth_header(HR)).status_code == 200


# --- 3: starting ------------------------------------------------------------------------------------------------

def test_only_the_assigned_manager_starts(client, world):
    assert start(client, world, email=HR).status_code == 403
    assert start(client, world, email=OTHER_MANAGER).status_code == 403
    assert start(client, world, email=CANDIDATE).status_code in (401, 403)


def test_start_creates_an_intake_session_and_is_idempotent(client, world, db):
    first = start(client, world)
    assert first.status_code == 200, first.text
    row = session_row(db, first.json()["session_id"])
    assert row.purpose == "intake" and row.application_id is None
    assert row.owner_user_id == world.manager.id and row.language == "ko"
    request = db.get(HiringRequest, world.request.id)
    assert request.status == "intake_in_progress" and request.intake_session_id == row.id
    again = start(client, world)
    assert again.json()["session_id"] == first.json()["session_id"]
    assert db.query(VoiceSession).count() == 1


def test_start_unknown_request_is_404(client, world):
    assert start(client, world, request_id=99999).status_code == 404


# --- 4: the plan ------------------------------------------------------------------------------------------------

def plan_texts(db, world, language="en"):
    request = db.get(HiringRequest, world.request.id)
    return {item.source_ref: item.text for item in intake.build_plan(db, request, language)}


def test_default_plan_has_six_topics_in_order(db, world):
    plan = intake.build_plan(db, db.get(HiringRequest, world.request.id), "en")
    assert [item.source_ref for item in plan] == [f"topic:{t}" for t in intake.TOPICS]
    assert all(item.source == "intake" and item.why for item in plan)


def test_first_question_asks_not_to_name_individuals(db, world):
    for language in ("ko", "vi", "en"):
        first = intake.build_plan(db, db.get(HiringRequest, world.request.id), language)[0]
        assert intake.NOTICE[language] in first.text


def test_first_question_keeps_the_notice_when_ai_rewords_it(db, world):
    fake.enqueue("intake_plan", json.dumps({"questions": [{"source_ref": "topic:why_hire", "text": "Why this hire?"}]}))
    first = intake.build_plan(db, db.get(HiringRequest, world.request.id), "en")[0]
    assert first.text.endswith("Why this hire?") and intake.NOTICE["en"] in first.text


def test_graph_data_changes_the_plan(db, world):
    texts = plan_texts(db, world)
    assert "Python experience" in texts["topic:non_negotiable"]
    assert "What is missing" in texts["topic:non_negotiable"]
    assert "topic:team_works" in texts
    world.builder.node("Speak up early", type="value")
    assert "topic:team_works" not in plan_texts(db, world)


def test_empty_graph_asks_the_plain_question(db):
    company = Company(slug="empty", name="Empty")
    db.add(company)
    db.commit()
    request = HiringRequest(company_id=company.id, title="Chef")
    db.add(request)
    db.commit()
    plan = {item.source_ref: item.text for item in intake.build_plan(db, request, "en")}
    assert plan["topic:non_negotiable"] == intake.TEMPLATES["en"]["non_negotiable"]
    assert len(plan) == 6


@pytest.mark.parametrize("language", ["ko", "vi", "en"])
def test_ai_failure_falls_back_to_templates(db, world, language, monkeypatch):
    def broken(*args, **kwargs):
        raise AIProviderError("down")

    monkeypatch.setattr(gateway, "generate_structured", broken)
    plan = intake.build_plan(db, db.get(HiringRequest, world.request.id), language)
    assert len(plan) == 6
    assert intake.TEMPLATES[language]["best_person"] in plan[1].text


def test_invalid_ai_output_falls_back_to_templates(db, world):
    fake.enqueue("intake_plan", "this is not json")
    plan = intake.build_plan(db, db.get(HiringRequest, world.request.id), "en")
    assert intake.TEMPLATES["en"]["best_person"] == plan[1].text


def test_planning_does_not_show_the_manager_a_private_layer(db, world):
    from tests.helpers_jd import CANARY
    assert not any(CANARY in item.text for item in intake.build_plan(db, db.get(HiringRequest, world.request.id), "en"))


# --- 5: duration ------------------------------------------------------------------------------------------------

def test_limits_per_purpose():
    assert voice.PURPOSE_LIMITS["intake"] == (6 * 60, 7 * 60 + 30)
    assert voice.PURPOSE_LIMITS["screening"] == (13 * 60, 15 * 60)
    assert voice.PURPOSES["intake"].closing_after_seconds == 360
    assert voice.PURPOSES["intake"].hard_limit_seconds == 450


def test_closing_after_six_minutes_and_hard_limit_at_seven_and_a_half(client, world, db):
    state = start(client, world).json()
    assert state["status"] == "in_progress" and state["time_left_seconds"] == 450
    session_id = state["session_id"]
    row = session_row(db, session_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row.active_seconds, row.last_activity_at = 361, now
    db.commit()
    closing = client.get(f"/api/voice/{session_id}/state", headers=auth_header(MANAGER)).json()
    assert closing["status"] == "closing" and closing["time_left_seconds"] <= 450 - 361
    row = session_row(db, session_id)
    row.active_seconds, row.last_activity_at = 451, now
    db.commit()
    done = answer(client, session_id, closing["position"]).json()
    assert done["status"] == "completed"
    assert session_row(db, session_id).status == "completed"


# --- 6: turn routes ---------------------------------------------------------------------------------------------

def test_another_user_gets_404_for_an_intake_session(client, world, db):
    state = start(client, world).json()
    session_id = state["session_id"]
    candidate = make_user(db, CANDIDATE)
    for email in (CANDIDATE, OTHER_MANAGER, HR):
        headers = auth_header(email)
        assert client.get(f"/api/voice/{session_id}/state", headers=headers).status_code == 404
        assert answer(client, session_id, 1, email=email).status_code == 404
        assert client.get(f"/api/voice/{session_id}/turns/1/question-audio", headers=headers).status_code == 404
    # The screening aliases serve screening sessions only.
    assert client.get(f"/api/screening/{session_id}/state", headers=auth_header(MANAGER)).status_code == 404
    assert candidate is not None


def test_manager_submits_audio_and_gets_the_next_question(client, world, db):
    state = start(client, world, body={"language": "en"}).json()
    session_id = state["session_id"]
    assert client.get(f"/api/voice/{session_id}/state", headers=auth_header(MANAGER)).json()["position"] == 1
    assert client.get(f"/api/voice/{session_id}/turns/1/question-audio", headers=auth_header(MANAGER)).status_code == 200
    nxt = answer(client, session_id, 1)
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["position"] == 2 and body["status"] == "in_progress"
    assert intake.TEMPLATES["en"]["best_person"] == body["question_text"]
    assert answer(client, session_id, 1).json()["position"] == 2  # idempotent
    assert answer(client, session_id, 5).status_code == 409


def test_screening_session_is_reachable_through_the_generic_route_by_its_owner_only(client, db, world):
    candidate = make_user(db, CANDIDATE)
    job = Job(company_id=world.company.id, title="J", slug="j", description="d", status="published", version=1)
    db.add(job)
    db.flush()
    application = Application(company_id=world.company.id, job_id=job.id, job_version=1, candidate_user_id=candidate.id,
                              alias="#A1", stage="session_in_progress")
    db.add(application)
    db.flush()
    session = voice.create_session(db, company_id=world.company.id, purpose="screening", owner_user_id=candidate.id,
                                   language="en", plan=[{"text": "Q?", "source": "role", "source_ref": "role:0", "why": "w"}],
                                   application_id=application.id)
    db.commit()
    assert client.get(f"/api/voice/{session.id}/state", headers=auth_header(CANDIDATE)).status_code == 200
    assert client.get(f"/api/voice/{session.id}/state", headers=auth_header(MANAGER)).status_code == 404
    assert client.get(f"/api/screening/{session.id}/state", headers=auth_header(CANDIDATE)).status_code == 200


def test_no_voice_route_is_open_without_login(app):
    for route in iter_routes(app):
        if route_path(route).startswith("/api/voice/"):
            names = {d.call.__name__ for d in route.dependant.dependencies}
            assert "get_authenticated_user" in names


# --- 7: completing ----------------------------------------------------------------------------------------------

def test_finishing_schedules_completion_not_analysis(client, world, db, scheduled):
    session = finished_session(client, db, world)
    assert scheduled == [session.id]


def test_complete_masks_names_and_stores_a_confidential_document(client, world, db):
    fake.enqueue("intake_mask", json.dumps({"names": ["Kim Minjun"]}))
    session = finished_session(client, db, world, text="Kim Minjun left in March, call 0912345678 or kim@acme.test.")
    document = intake.complete(db, session)
    assert document.source_type == "intake" and document.visibility == "confidential"
    assert document.department_id == world.eng.id and document.language == "en"
    from app.core import storage
    stored = storage.read_bytes(document.file_path).decode()
    assert "Kim Minjun" not in stored and "[NAME]" in stored
    assert "0912345678" not in stored and "kim@acme.test" not in stored
    assert "[Q1] " in stored and "[Q6] " in stored
    request = db.get(HiringRequest, world.request.id)
    assert request.intake_document_id == document.id and request.status == "intake_done"
    assert db.query(KbIngestionJob).filter_by(document_id=document.id, status="queued").count() == 1


def test_complete_is_idempotent(client, world, db):
    session = finished_session(client, db, world)
    first = intake.complete(db, session)
    second = intake.complete(db, session)
    assert first.id == second.id and db.query(KbDocument).filter_by(source_type="intake").count() == 1


def failing_mask(monkeypatch):
    real = gateway.generate_structured

    def failing(tier, system, messages, schema, tokens, feature, company_id):
        if feature == "intake_mask":
            raise AIProviderError("down")
        return real(tier, system, messages, schema, tokens, feature, company_id)

    monkeypatch.setattr(gateway, "generate_structured", failing)
    return real


def test_masking_failure_keeps_patterns_and_marks_the_document(client, world, db, monkeypatch):
    failing_mask(monkeypatch)
    session = finished_session(client, db, world, text="Mail kim@acme.test about the role. Ships on time.")
    document = intake.complete(db, session)
    from app.core import storage
    assert "kim@acme.test" not in storage.read_bytes(document.file_path).decode()
    assert document.masking_note == intake.MASK_FAILED
    # The job clears its own error when it starts: the note lives on the document, so it cannot be lost.
    fake.enqueue("kb_extract", json.dumps({"nodes": [], "edges": []}))
    intake.run_completion(session.id)
    db.expire_all()
    assert db.get(KbDocument, document.id).masking_note == intake.MASK_FAILED


# --- I-13: HR sees the masking note, publishing is held, and masking can be retried ------------------------------

def hr_get(client, world, tail):
    return client.get(f"/api/companies/{world.company.id}/kb{tail}", headers=auth_header(HR))


def hr_post(client, world, tail, body=None):
    return client.post(f"/api/companies/{world.company.id}/kb{tail}", json=body or {}, headers=auth_header(HR))


def unmasked_document(client, world, db, monkeypatch, text="Kim Minjun ships on time without supervision."):
    real = failing_mask(monkeypatch)
    session = finished_session(client, db, world, text=text)
    fake.enqueue("kb_extract", json.dumps({"nodes": [], "edges": []}))
    intake.run_completion(session.id)
    monkeypatch.setattr(gateway, "generate_structured", real)
    db.expire_all()
    return session, db.query(KbDocument).filter_by(source_type="intake").one()


def test_the_masking_note_shows_in_documents_and_review_and_holds_bulk_publishing(client, world, db, monkeypatch):
    session, document = unmasked_document(client, world, db, monkeypatch)
    assert document.status == "review"  # nothing to review, yet the chunks are not published
    listed = {d["id"]: d for d in hr_get(client, world, "/documents").json()}[document.id]
    assert listed["masking_note"] == "names_unchecked" and listed["publish_hold"]["masking_failed"] is True
    queue = hr_get(client, world, "/review").json()
    assert [d["id"] for d in queue["held_documents"]] == [document.id]
    refused = hr_post(client, world, "/review/decide", {"items": [{"action": "publish_document", "document_id": document.id}]})
    assert refused.status_code == 409
    db.expire_all()
    assert db.get(KbDocument, document.id).status == "review"


def test_raw_transcript_is_kept_until_masking_succeeds(client, world, db, monkeypatch, tmp_path):
    session, document = unmasked_document(client, world, db, monkeypatch)
    assert any(t.transcript for t in raw_turns(db, session.id))
    intake.complete(db, session)  # a repeat of the completion must not erase it either
    assert any(t.transcript for t in raw_turns(db, session.id)) and recording_files(tmp_path)


def test_retrying_masking_clears_the_note_rebuilds_the_document_and_erases_raw_data(client, world, db, monkeypatch, tmp_path):
    from app.core import storage
    session, document = unmasked_document(client, world, db, monkeypatch)
    assert "Kim Minjun" in storage.read_bytes(document.file_path).decode()
    fake.enqueue("intake_mask", json.dumps({"names": ["Kim Minjun"]}))
    fake.enqueue("kb_extract", json.dumps({"nodes": [], "edges": []}))
    response = hr_post(client, world, f"/documents/{document.id}/retry-masking")
    assert response.status_code == 200, response.text
    db.expire_all()
    document = db.get(KbDocument, document.id)
    stored = storage.read_bytes(document.file_path).decode()
    assert document.masking_note is None and "Kim Minjun" not in stored and "[NAME]" in stored
    assert all(t.transcript is None and t.audio_path is None for t in raw_turns(db, session.id))
    assert recording_files(tmp_path) == []
    assert db.query(KbIngestionJob).filter_by(document_id=document.id).count() == 2


def test_a_retry_that_cannot_mask_keeps_the_note_and_the_raw_data(client, world, db, monkeypatch):
    session, document = unmasked_document(client, world, db, monkeypatch)
    failing_mask(monkeypatch)
    response = hr_post(client, world, f"/documents/{document.id}/retry-masking")
    assert response.status_code == 503
    db.expire_all()
    assert db.get(KbDocument, document.id).masking_note == "names_unchecked"
    assert any(t.transcript for t in raw_turns(db, session.id))


def test_retry_masking_is_hr_only_company_scoped_and_needs_a_note(client, world, db, monkeypatch):
    session, document = unmasked_document(client, world, db, monkeypatch)
    path = f"/api/companies/{world.company.id}/kb/documents/{document.id}/retry-masking"
    assert client.post(path, headers=auth_header(MANAGER)).status_code == 403
    other = f"/api/companies/{world.other.id}/kb/documents/{document.id}/retry-masking"
    assert client.post(other, headers=auth_header(OUTSIDER)).status_code == 404
    document.masking_note = None
    db.commit()
    assert client.post(path, headers=auth_header(HR)).status_code == 409


def test_the_daily_sweep_erases_a_held_transcript_after_seven_days(client, world, db, monkeypatch, tmp_path):
    session, document = unmasked_document(client, world, db, monkeypatch)
    assert intake.sweep_terminal(db) == 0 and recording_files(tmp_path)
    later = datetime.now(timezone.utc) + timedelta(days=8)
    assert intake.sweep_terminal(db, now=later) == 1
    assert all(t.transcript is None and t.audio_path is None for t in raw_turns(db, session.id))
    assert recording_files(tmp_path) == []


# --- I-14: raw data does not survive in follow-up questions, plans or abandoned sessions ------------------------

def test_erase_raw_also_blanks_follow_up_questions_their_audio_and_the_plan(client, world, db, tmp_path):
    from app.hiring import recordings
    session = finished_session(client, db, world)
    path = recordings.save_question_audio(world.company.id, f"session-{session.id}", 7, b"spoken", ".mp3")
    db.add(VoiceTurn(session_id=session.id, position=7, question_text="What did Kim Chulsoo do wrong?",
                     question_source="followup", is_followup=True, parent_position=1, question_audio_path=path))
    db.commit()
    intake.complete(db, session)
    turns = raw_turns(db, session.id)
    followups = [t for t in turns if t.is_followup]
    assert followups and all(t.question_text == "" and t.question_audio_path is None for t in followups)
    assert all(t.question_text for t in turns if not t.is_followup)
    assert not (tmp_path / "rec" / path).exists()
    assert not session_row(db, session.id).plan


def stale_session_with_failed_stt(client, world, db, monkeypatch):
    def down(*args, **kwargs):
        raise AIProviderError("down")

    monkeypatch.setattr(voice.gateway, "transcribe", down)
    state = start(client, world).json()
    answer(client, state["session_id"], 1, text="Kim Chulsoo was the problem")
    row = session_row(db, state["session_id"])
    row.last_activity_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=30)
    db.commit()
    return state["session_id"]


def test_an_abandoned_intake_erases_the_audio_it_saved(client, world, db, monkeypatch, tmp_path):
    session_id = stale_session_with_failed_stt(client, world, db, monkeypatch)
    assert recording_files(tmp_path)
    response = client.get(f"/api/voice/{session_id}/state", headers=auth_header(MANAGER))
    assert response.json()["status"] == "abandoned"
    assert recording_files(tmp_path) == []
    assert all(t.audio_path is None and t.transcript is None for t in raw_turns(db, session_id))


def test_the_daily_sweep_erases_terminal_intake_sessions_that_nothing_links_to(client, world, db, monkeypatch, tmp_path):
    session_id = stale_session_with_failed_stt(client, world, db, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(intake, "erase_raw", lambda sid: None)  # the abandon hook "missed" it
        assert voice.sweep_abandoned(db) == 1
    assert recording_files(tmp_path)
    request = db.get(HiringRequest, world.request.id)
    request.intake_session_id = None  # starting again overwrote the link: the old session is orphaned
    db.commit()
    assert intake.sweep_terminal(db) == 1
    assert recording_files(tmp_path) == []
    assert intake.sweep_terminal(db) == 0


def test_the_sweep_leaves_a_finished_intake_alone_until_its_document_exists(client, world, db, tmp_path):
    finished_session(client, db, world)
    assert intake.sweep_terminal(db) == 0 and recording_files(tmp_path)
    assert intake.sweep_terminal(db, now=datetime.now(timezone.utc) + timedelta(days=8)) == 1


def test_the_daily_pass_runs_the_intake_sweep():
    import inspect
    assert "intake.sweep_terminal" in inspect.getsource(retention._daily_pass)


# --- M-9: a wholly silent intake makes no document and can be started again -------------------------------------

def test_a_wholly_silent_intake_is_marked_without_a_document_and_can_restart(client, world, db, tmp_path, monkeypatch):
    from types import SimpleNamespace

    def silence(*args, **kwargs):
        return SimpleNamespace(text="", language="en", provider="fake", model="m", latency_ms=1,
                               usage=SimpleNamespace(audio_seconds=1.0, input_tokens=0, output_tokens=0))

    monkeypatch.setattr(voice.gateway, "transcribe", silence)
    state = start(client, world).json()
    session_id = state["session_id"]
    for _ in range(40):
        if state["status"] not in ("in_progress", "closing", "paused") or state["position"] is None:
            break
        state = answer(client, session_id, state["position"], text="...").json()
    assert session_row(db, session_id).status == "completed"
    intake.run_completion(session_id)
    db.expire_all()
    request = db.get(HiringRequest, world.request.id)
    assert request.status == "intake_empty" and request.intake_document_id is None
    assert db.query(KbDocument).filter_by(source_type="intake").count() == 0
    assert recording_files(tmp_path) == []
    listed = client.get(base(world), headers=auth_header(MANAGER)).json()[0]
    assert listed["status"] == "intake_empty"
    again = start(client, world)
    assert again.status_code == 200 and again.json()["session_id"] != session_id


# --- M-1: planning never fails because embeddings are unavailable ------------------------------------------------

@pytest.mark.parametrize("error", [AIProviderError("embeddings down"), "missing"])
def test_planning_with_embeddings_down_or_missing_uses_plain_templates(client, world, db, monkeypatch, error):
    from app.brain import retriever

    def broken(*args, **kwargs):
        raise retriever.NoEmbeddingsError("run reembed") if error == "missing" else error

    monkeypatch.setattr(retriever, "search", broken)
    response = start(client, world)
    assert response.status_code == 200, response.text
    plan = intake.build_plan(db, world.request, "en")
    assert len(plan) == 6 and all("already recorded" not in item.text for item in plan)


def requirement_item(title, quote, node_type="requirement"):
    return {"ref": title, "type": node_type, "title": title, "body": quote, "quote": quote, "fact_kind": "none",
            "fact_value": "", "fact_unit": "", "scope_text": "", "effective_date": ""}


def queue_extraction(*items):
    fake.enqueue("kb_extract", json.dumps({"nodes": list(items), "edges": []}, ensure_ascii=False))


def test_the_job_runs_through_the_pipeline_with_verified_quotes(client, world, db):
    queue_extraction(requirement_item("Ships on time", "ships on time without supervision"),
                     requirement_item("Invented", "this sentence was never said by anyone"))
    session = finished_session(client, db, world)
    intake.run_completion(session.id)
    db.expire_all()
    document = db.query(KbDocument).filter_by(source_type="intake").one()
    job = db.query(KbIngestionJob).filter_by(document_id=document.id).one()
    assert job.status == "review" and job.dropped_items == 1
    node = db.query(KbNode).filter_by(title="Ships on time").one()
    assert node.status == "draft" and node.visibility == "confidential" and node.guard_category is None
    assert db.query(KbNode).filter_by(title="Invented").count() == 0


def test_the_review_queue_cites_the_document_and_a_transcript_moment(client, world, db):
    queue_extraction(requirement_item("Ships on time", "ships on time without supervision"))
    session = finished_session(client, db, world)
    intake.run_completion(session.id)
    document_id = db.query(KbDocument.id).filter_by(source_type="intake").scalar()
    response = client.get(f"/api/companies/{world.company.id}/kb/review?document_id={document_id}",
                          headers=auth_header(HR))
    assert response.status_code == 200
    (node,) = [n for n in response.json()["nodes"] if n["title"] == "Ships on time"]
    (source,) = node["sources"]
    assert source["document_title"].startswith("Manager intake") and "ships on time" in source["quote"]
    chunk_text = " ".join(row.text for row in db.query(KbChunk).filter_by(document_id=document_id))
    for position in range(1, 7):
        assert f"[Q{position}]" in chunk_text


# --- 8: discrimination, end to end ------------------------------------------------------------------------------

def test_a_discriminatory_requirement_ends_flagged_and_blocked(client, world, db):
    queue_extraction(requirement_item("Age preference", "30세 이하 선호"))
    session = finished_session(client, db, world, text="신입은 30세 이하 선호합니다. 팀은 빠르게 일합니다.", language="ko")
    intake.run_completion(session.id)
    db.expire_all()
    node = db.query(KbNode).filter_by(title="Age preference").one()
    assert node.guard_category == "age" and node.status == "draft"
    document_id = db.query(KbDocument.id).filter_by(source_type="intake").scalar()
    response = client.post(
        f"/api/companies/{world.company.id}/kb/review/decide",
        json={"items": [{"action": "accept", "node_id": node.id}]}, headers=auth_header(HR))
    assert response.status_code == 409
    queue = client.get(f"/api/companies/{world.company.id}/kb/review?document_id={document_id}", headers=auth_header(HR)).json()
    assert [n["guard_category"] for n in queue["nodes"] if n["title"] == "Age preference"] == ["age"]
    assert db.get(KbDocument, document_id).language == "ko"


# --- 10: disconnect and resume ----------------------------------------------------------------------------------

def test_resume_after_disconnect_returns_the_same_question(client, world, db):
    state = start(client, world, body={"language": "en"}).json()
    session_id = state["session_id"]
    answer(client, session_id, 1)
    resumed = client.get(f"/api/voice/{session_id}/state", headers=auth_header(MANAGER)).json()
    assert resumed["position"] == 2 and resumed["status"] == "in_progress"
    again = start(client, world)
    assert again.json()["session_id"] == session_id and again.json()["position"] == 2


def test_a_finished_intake_cannot_be_started_again(client, world, db):
    finished_session(client, db, world)
    assert start(client, world).status_code == 409


def test_an_abandoned_intake_can_be_started_again(client, world, db):
    state = start(client, world).json()
    row = session_row(db, state["session_id"])
    stale = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=30)
    row.last_activity_at = stale
    db.commit()
    assert voice.sweep_abandoned(db) == 1
    assert session_row(db, state["session_id"]).status == "abandoned"
    second = start(client, world).json()
    assert second["session_id"] != state["session_id"]


# --- nothing else trips over an intake session ------------------------------------------------------------------

def test_other_jobs_leave_an_intake_session_alone(client, world, db):
    session = finished_session(client, db, world)
    session_id, turns = session.id, db.query(VoiceTurn).filter_by(session_id=session.id).count()
    assert analysis.requeue_interrupted() == []
    assert retention.run(db, now=datetime.now(timezone.utc) + timedelta(days=4000)) == 0
    assert voice.sweep_abandoned(db) == 0
    row = session_row(db, session_id)
    assert row.status == "completed" and row.owner_user_id == world.manager.id
    paths = [t.audio_path for t in db.query(VoiceTurn).filter_by(session_id=session_id)]
    assert len(paths) == turns and all(paths)


def test_abandoning_an_intake_with_no_answer_touches_no_application(client, world, db):
    state = start(client, world).json()
    row = session_row(db, state["session_id"])
    row.last_activity_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=30)
    db.commit()
    response = client.get(f"/api/voice/{state['session_id']}/state", headers=auth_header(MANAGER))
    assert response.status_code == 200 and response.json()["status"] == "abandoned"


def test_startup_completes_a_finished_intake_that_has_no_document(client, world, db, scheduled, monkeypatch):
    session = finished_session(client, db, world)
    scheduled.clear()
    assert intake.recover_interrupted() == []  # off under test
    monkeypatch.setenv("APP_ENV", "dev")
    assert intake.recover_interrupted() == [session.id] and scheduled == [session.id]
    intake.complete(db, session)
    scheduled.clear()
    assert intake.recover_interrupted() == []


# --- 9: raw intake data is erased once the masked document exists -----------------------------------------------

def raw_turns(db, session_id):
    db.rollback()
    db.expire_all()
    return db.query(VoiceTurn).filter_by(session_id=session_id).order_by(VoiceTurn.position).all()


def recording_files(tmp_path):
    root = tmp_path / "rec"
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


def test_raw_audio_and_transcripts_are_erased_after_the_document_exists(client, world, db, tmp_path):
    fake.enqueue("intake_mask", json.dumps({"names": ["Kim Minjun"]}))
    session = finished_session(client, db, world, text="Kim Minjun ships on time without supervision.")
    assert recording_files(tmp_path) and any(t.transcript for t in raw_turns(db, session.id))
    document = intake.complete(db, session)
    turns = raw_turns(db, session.id)
    assert turns and all(t.transcript is None and t.audio_path is None for t in turns)
    assert recording_files(tmp_path) == []
    from app.core import storage
    stored = storage.read_bytes(document.file_path).decode()
    assert "[NAME]" in stored and "Kim Minjun" not in stored and "[Q1] " in stored and "[Q6] " in stored
    # The finished session can still be read, and a second completion neither fails nor makes another document.
    response = client.get(f"/api/voice/{session.id}/state", headers=auth_header(MANAGER))
    assert response.status_code == 200 and response.json()["status"] == "completed"
    assert intake.complete(db, session).id == document.id
    assert db.query(KbDocument).filter_by(source_type="intake").count() == 1


def test_citations_still_point_to_position_markers_after_the_erase(client, world, db):
    queue_extraction(requirement_item("Ships on time", "ships on time without supervision"))
    session = finished_session(client, db, world)
    intake.run_completion(session.id)
    assert all(t.transcript is None for t in raw_turns(db, session.id))
    document_id = db.query(KbDocument.id).filter_by(source_type="intake").scalar()
    chunk_text = " ".join(row.text for row in db.query(KbChunk).filter_by(document_id=document_id))
    for position in range(1, 7):
        assert f"[Q{position}]" in chunk_text
    assert "ships on time without supervision" in chunk_text


def test_a_failed_document_keeps_raw_data_and_the_retry_cleans_up(client, world, db, tmp_path, monkeypatch):
    from app.brain import ingestion
    session = finished_session(client, db, world)
    real = ingestion.create_document

    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ingestion, "create_document", broken)
    with pytest.raises(RuntimeError):
        intake.complete(db, session)
    turns = raw_turns(db, session.id)
    assert all(t.transcript and t.audio_path for t in turns) and recording_files(tmp_path)
    monkeypatch.setattr(ingestion, "create_document", real)
    intake.complete(db, session)
    assert all(t.transcript is None and t.audio_path is None for t in raw_turns(db, session.id))
    assert recording_files(tmp_path) == []


def test_a_missing_audio_file_is_not_an_error(client, world, db, tmp_path):
    session = finished_session(client, db, world)
    for path in recording_files(tmp_path)[:2]:
        path.unlink()
    intake.complete(db, session)
    assert all(t.transcript is None and t.audio_path is None for t in raw_turns(db, session.id))
    assert recording_files(tmp_path) == []


def test_a_screening_session_keeps_its_audio_and_transcript(client, db, world, tmp_path):
    from app.hiring import recordings
    session = VoiceSession(company_id=world.company.id, purpose="screening", status=voice.COMPLETED, language="en")
    db.add(session)
    db.flush()
    path = recordings.save_turn_audio(world.company.id, f"session-{session.id}", 1, b"audio", ".webm")
    db.add(VoiceTurn(session_id=session.id, position=1, question_text="Q?", question_source="x",
                     audio_path=path, transcript="kept words", transcript_status="transcribed"))
    db.commit()
    intake.erase_raw(session.id)
    (turn,) = raw_turns(db, session.id)
    assert turn.transcript == "kept words" and turn.audio_path == path and recording_files(tmp_path)


def test_recovery_erases_what_a_crash_left_and_a_second_run_is_a_no_op(client, world, db, scheduled, tmp_path, monkeypatch):
    session = finished_session(client, db, world)
    with monkeypatch.context() as patch:
        patch.setattr(intake, "erase_raw", lambda session_id: None)
        intake.complete(db, session)  # the document exists; the erase "crashed"
    assert recording_files(tmp_path)
    scheduled.clear()
    monkeypatch.setenv("APP_ENV", "dev")
    assert intake.recover_interrupted() == [session.id] and scheduled == [session.id]
    intake.run_completion(session.id)
    assert recording_files(tmp_path) == [] and db.query(KbDocument).filter_by(source_type="intake").count() == 1
    scheduled.clear()
    assert intake.recover_interrupted() == [] and scheduled == []


def test_a_manager_who_was_removed_cannot_keep_answering_their_intake(client, world, db):
    state = start(client, world).json()
    member = db.query(CompanyMember).filter_by(company_id=world.company.id, user_id=world.manager.id).one()
    db.delete(member)
    db.commit()
    assert answer(client, state["session_id"], state["position"]).status_code == 404
    assert client.get(f"/api/voice/{state['session_id']}/state", headers=auth_header(MANAGER)).status_code == 404


def test_the_intake_rules_run_on_every_node_type(client, world, db):
    queue_extraction(requirement_item("Team makeup", "30세 이하 선호", node_type="value"))
    session = finished_session(client, db, world, text="우리 팀은 30세 이하 선호합니다. 팀은 빠르게 일합니다.", language="ko")
    intake.run_completion(session.id)
    db.expire_all()
    node = db.query(KbNode).filter_by(title="Team makeup").one()
    assert node.type == "value" and node.guard_category == "age" and node.status == "draft"
    path = f"/api/companies/{world.company.id}/kb/review/decide"
    blocked = client.post(path, json={"items": [{"action": "accept", "node_id": node.id}]}, headers=auth_header(HR))
    assert blocked.status_code == 409 and "age" in blocked.text
    reworded = client.post(path, headers=auth_header(HR), json={"items": [
        {"action": "accept", "node_id": node.id, "title": "Team makeup", "body": "Under 30 years old only"}]})
    assert reworded.status_code == 409  # an edit is checked again by the rules
    clean = client.post(path, headers=auth_header(HR), json={"items": [
        {"action": "accept", "node_id": node.id, "title": "Team style", "body": "We value fast, careful work"}]})
    assert clean.status_code == 200, clean.text
    db.expire_all()
    assert db.get(KbNode, node.id).status == "published" and db.get(KbNode, node.id).guard_category is None
