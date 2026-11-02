import json
import types
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database.sql_models import Application, AuditLog, CompanyMember, CultureNote, RequirementResult
from app.hiring import board
from app.main import create_app
from tests.helpers_board import (
    CANDIDATE_EMAIL, CANDIDATE_NAME, CONFIDENTIAL, CV_RAW, add_claims, make_application, make_session, make_world,
)
from tests.helpers import auth_header, make_user


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


@pytest.mark.parametrize("cv,band,expected", [
    ("meets", "many", "priority"), ("meets", "few", "strong_cv_unclear"),
    ("not_met", "many", "hidden_gem"), ("not_met", "few", "not_enough_evidence"),
])
def test_cells(cv, band, expected):
    assert board.cell_for(Application(stage="ready_for_hr", cv_status=cv, interview_band=band)) == expected


def test_cell_is_none_without_both_labels_or_before_review():
    assert board.cell_for(Application(stage="ready_for_hr", cv_status="meets", interview_band=None)) is None
    assert board.cell_for(Application(stage="invited", cv_status="meets", interview_band="many")) is None


def _populate(db, world):
    job = world["job"]
    apps = {
        "priority": make_application(db, job, "#A1", cv_status="meets", band="many"),
        "gem": make_application(db, job, "#A2", cv_status="not_met", band="many"),
        "unclear": make_application(db, job, "#A3", cv_status="meets", band="few"),
        "weak": make_application(db, job, "#A4", cv_status="not_met", band="few"),
        "invited": make_application(db, job, "#A5", stage="invited"),
        "progress": make_application(db, job, "#A6", stage="session_in_progress"),
        "fast": make_application(db, job, "#A7", fast_tracked=True, band=None),
        "refused": make_application(db, job, "#A8", stage="declined_recording"),
        "withdrawn": make_application(db, job, "#A9", stage="withdrawn"),
        "failed": make_application(db, job, "#A10", analysis_status="failed"),
        "processing": make_application(db, job, "#A11", stage="cv_processing", cv_status=None),
        "simulated": make_application(db, job, "#A12", band="many", is_simulated=True),
        "other_job": make_application(db, world["other_job"], "#A1", band="many"),
    }
    return apps


def _ids(items):
    return sorted(item["id"] for item in items)


def test_board_cells_and_lanes(db, world, api):
    apps = _populate(db, world)
    response = api.get(url(world, f"/jobs/{world['job'].id}/board"), headers=hr(world))
    assert response.status_code == 200, response.text
    body = response.json()
    assert _ids(body["cells"]["priority"]) == [apps["priority"].id]
    assert _ids(body["cells"]["hidden_gem"]) == [apps["gem"].id]
    assert _ids(body["cells"]["strong_cv_unclear"]) == [apps["unclear"].id]
    assert _ids(body["cells"]["not_enough_evidence"]) == [apps["weak"].id]
    assert _ids(body["lanes"]["not_interviewed"]) == sorted(
        [apps["invited"].id, apps["progress"].id, apps["fast"].id])
    assert _ids(body["lanes"]["refused_recording"]) == [apps["refused"].id]
    assert _ids(body["lanes"]["withdrawn"]) == [apps["withdrawn"].id]
    assert _ids(body["lanes"]["analysis_failed"]) == [apps["failed"].id]
    everything = json.dumps(body)
    assert f'"id": {apps["processing"].id},' not in everything
    assert f'"id": {apps["simulated"].id},' not in everything
    assert f'"id": {apps["other_job"].id},' not in everything


def test_a_simulated_application_is_not_on_the_board_and_its_detail_is_404(db, world, api):
    simulated = make_application(db, world["job"], "#S1", band="many", is_simulated=True)
    real = make_application(db, world["job"], "#A2", band="many")
    body = board.job_board(db, world["company"].id, world["job"].id)
    assert _ids(body["cells"]["priority"]) == [real.id]
    assert api.get(url(world, f"/applications/{simulated.id}"), headers=hr(world)).status_code == 404
    assert api.get(url(world, f"/applications/{real.id}"), headers=hr(world)).status_code == 200


def test_board_cards_hide_identity_and_cv_text(db, world, api):
    apps = _populate(db, world)
    add_claims(db, apps["priority"], ["Improved latency"])
    raw = api.get(url(world, f"/jobs/{world['job'].id}/board"), headers=hr(world)).text
    for identifier in (CANDIDATE_NAME, CANDIDATE_EMAIL, "Canary", CV_RAW, "CANARY-RAW", "Built a FastAPI", "cv_text"):
        assert identifier not in raw
    assert "#A1" in raw and "alias" in raw


def test_board_other_company_job_is_404_and_non_hr_403(db, world, api):
    assert api.get(url(world, f"/jobs/{world['other_job'].id}/board"), headers=hr(world)).status_code == 404
    assert api.get(url(world, f"/jobs/{world['job'].id}/board"), headers=world["people"]["emp"]["headers"]).status_code == 403


def test_hidden_gem_keeps_cv_status_not_met(db, world, api):
    gem = make_application(db, world["job"], "#A2", cv_status="not_met", band="many")
    body = api.get(url(world, f"/jobs/{world['job'].id}/board"), headers=hr(world)).json()
    card = body["cells"]["hidden_gem"][0]
    assert card["id"] == gem.id and card["cv_status"] == "not_met" and card["interview_band"] == "many"
    db.rollback()
    db.expire_all()
    assert db.get(Application, gem.id).cv_status == "not_met"


def test_decided_application_shows_its_decision(db, world, api):
    application = make_application(db, world["job"], band="many")
    api.post(url(world, f"/applications/{application.id}/decision"), headers=hr(world), json={"decision": "approved"})
    body = api.get(url(world, f"/jobs/{world['job'].id}/board"), headers=hr(world)).json()
    assert body["cells"]["priority"][0]["hr_decision"] == "approved"


def test_a_candidate_who_declined_recording_through_the_route_is_in_the_refused_lane(db, world, api):
    from app.database.sql_models import User
    from tests.helpers import auth_header

    declined = make_application(db, world["job"], "#A2", stage="invited", cv_status="meets", band=None)
    fast = make_application(db, world["job"], "#A3", stage="ready_for_hr", cv_status="meets", band=None, fast_tracked=True)
    email = db.get(User, declined.candidate_user_id).email
    declined_id, fast_id = declined.id, fast.id

    response = api.post(f"/api/applications/{declined_id}/decline-recording", headers=auth_header(email))
    assert response.status_code == 200, response.text
    body = api.get(url(world, f"/jobs/{world['job'].id}/board"), headers=hr(world)).json()

    assert _ids(body["lanes"]["refused_recording"]) == [declined_id]
    assert _ids(body["lanes"]["not_interviewed"]) == [fast_id]
    # Declining is not a rejection: HR can still decide this application.
    assert body["lanes"]["refused_recording"][0]["hr_decision"] == "pending"


def _detail_setup(db, world):
    application = make_application(db, world["job"], "#A1", cv_status="meets", band="many",
                                   ai_suggestion="Solid.", analysis_status="done")
    _, turns = make_session(db, application, [(1, "Tell us about FastAPI", "I built a FastAPI service", "x/1.webm"),
                                              (2, "Docker?", "Docker in production", None)])
    reqs = world["requirements"]
    db.add_all([
        RequirementResult(application_id=application.id, requirement_id=reqs[0].id, source="cv", status="met",
                          quote="FastAPI service"),
        RequirementResult(application_id=application.id, requirement_id=reqs[0].id, source="interview",
                          status="evidence", quote="built a FastAPI service", voice_turn_id=turns[0].id),
        RequirementResult(application_id=application.id, requirement_id=reqs[1].id, source="cv", status="not_found"),
        RequirementResult(application_id=application.id, requirement_id=reqs[3].id, source="cv", status="not_found"),
        CultureNote(application_id=application.id, value_node_id=world["value"].id, note="Owns outcomes",
                    quote="Docker in production", voice_turn_id=turns[1].id),
    ])
    db.commit()
    add_claims(db, application, ["Improved latency by 40%"])
    return application


def test_detail_has_everything_for_hr_and_no_identity(db, world, api):
    application = _detail_setup(db, world)
    response = api.get(url(world, f"/applications/{application.id}"), headers=hr(world))
    assert response.status_code == 200, response.text
    body = response.json()
    raw = response.text
    assert body["alias"] == "#A1" and body["cv_text_blind"].startswith("[NAME]")
    for identifier in (CANDIDATE_NAME, CANDIDATE_EMAIL, CV_RAW, "cv_text_raw"):
        assert identifier not in raw
    by_id = {r["requirement_id"]: r for r in body["requirements"]}
    first = by_id[world["requirements"][0].id]
    assert first["cv"]["status"] == "met" and first["interview"]["status"] == "evidence"
    assert first["interview"]["position"] == 1
    assert by_id[world["requirements"][1].id]["interview"] is None
    assert CONFIDENTIAL in raw  # HR sees confidential requirements
    assert body["claims"][0]["text"] == "Improved latency by 40%"
    assert body["culture_notes"][0]["value"] == "Ownership" and body["culture_notes"][0]["position"] == 2
    assert [t["position"] for t in body["transcript"]] == [1, 2]
    assert body["transcript"][0]["has_audio"] is True and body["transcript"][1]["has_audio"] is False
    assert "x/1.webm" not in raw  # storage paths are not exposed
    assert body["suggestion"] == {"text": "Solid.", "source": "ai"}
    assert body["hr_decision"] == "pending"


def test_detail_other_company_and_non_hr(db, world, api):
    application = _detail_setup(db, world)
    other = f"/api/companies/{world['other'].id}/applications/{application.id}"
    assert api.get(other, headers=world["people"]["hr2"]["headers"]).status_code == 404
    assert api.get(url(world, f"/applications/{application.id}"),
                   headers=world["people"]["emp"]["headers"]).status_code == 403


def test_audio_plays_audits_and_hides_other_companies(db, world, api, monkeypatch):
    from app.hiring import recordings
    served = {"x/1.webm": b"AUDIO-BYTES"}

    def fake_read(path):
        if path not in served:
            raise FileNotFoundError(path)
        return served[path]

    monkeypatch.setattr(recordings, "read", fake_read, raising=False)
    application = _detail_setup(db, world)
    path = url(world, f"/applications/{application.id}/turns/1/audio")
    for _ in range(2):
        response = api.get(path, headers=hr(world))
        assert response.status_code == 200 and response.content == b"AUDIO-BYTES"
        assert response.headers["content-type"].startswith("audio/webm")
    assert db.query(AuditLog).filter_by(action="audio_played", company_id=world["company"].id).count() == 2
    assert api.get(url(world, f"/applications/{application.id}/turns/2/audio"), headers=hr(world)).status_code == 404
    assert api.get(url(world, f"/applications/{application.id}/turns/9/audio"), headers=hr(world)).status_code == 404
    other = f"/api/companies/{world['other'].id}/applications/{application.id}/turns/1/audio"
    assert api.get(other, headers=world["people"]["hr2"]["headers"]).status_code == 404
    served.clear()  # the file is gone from disk
    assert api.get(path, headers=hr(world)).status_code == 404
    assert api.get(path, headers=world["people"]["emp"]["headers"]).status_code == 403
    assert db.query(AuditLog).filter_by(action="audio_played").count() == 2


def test_real_audio_is_served_then_gone_after_retention(db, world, api, tmp_path, monkeypatch):
    """No stand-in: the real route and the real recordings.read, on a real file, before and after retention."""
    from app.hiring import recordings, retention

    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    reads = []
    real_read = recordings.read
    monkeypatch.setattr(recordings, "read", lambda path: reads.append(path) or real_read(path))
    application = make_application(db, world["job"], alias="#A7")
    stored = recordings.save_turn_audio(world["company"].id, f"{application.id}/restart-1", 1, b"REAL-AUDIO", ".webm")
    make_session(db, application, [(1, "Question", "Answer", stored)], restart_count=1)
    application.hr_decided_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=world["company"].retention_days + 1)
    db.commit()
    application_id = application.id
    path = url(world, f"/applications/{application_id}/turns/1/audio")

    served = api.get(path, headers=hr(world))
    assert served.status_code == 200 and served.content == b"REAL-AUDIO"
    assert reads == [stored]

    db.rollback()
    assert retention.run(db) == 1
    assert not (tmp_path / stored).exists()
    db.rollback()
    gone = api.get(path, headers=hr(world))
    assert gone.status_code == 404 and gone.json() == {"detail": "Recording not found"}
    assert reads == [stored]  # the path was cleared, so nothing tried to read a file that is gone


def test_a_file_lost_from_disk_gets_404_from_the_real_read(db, world, api, tmp_path, monkeypatch):
    from app.hiring import recordings

    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    application = make_application(db, world["job"], alias="#A8")
    stored = recordings.save_turn_audio(world["company"].id, application.id, 1, b"REAL-AUDIO", ".webm")
    make_session(db, application, [(1, "Question", "Answer", stored)])
    recordings.delete(stored)
    response = api.get(url(world, f"/applications/{application.id}/turns/1/audio"), headers=hr(world))
    assert response.status_code == 404 and response.json() == {"detail": "Recording not found"}


def test_board_module_does_not_reference_raw_cv_text():
    import inspect
    assert "cv_text_raw" not in inspect.getsource(board)
    assert types.ModuleType  # keep import used


# Before a reveal, what the candidate said reaches HR masked (I-13)


SPOKEN = f"My name is {CANDIDATE_NAME}, call me on 0901234567 or at canary.candidate@example.test. I built billing."
PLAIN_QUOTE = "I built billing."
IDENTIFYING_QUOTE = "call me on 0901234567"


def _spoken_world(db, world):
    application = make_application(db, world["job"], "#A1", cv_status="meets", band="many", ai_suggestion="Ask Nguyen about 0901234567")
    _, turns = make_session(db, application, [(1, "Tell me about Nguyen?", SPOKEN, None)])
    db.add_all([
        RequirementResult(application_id=application.id, requirement_id=world["requirements"][0].id, source="interview",
                          status="evidence", quote=PLAIN_QUOTE, voice_turn_id=turns[0].id),
        CultureNote(application_id=application.id, value_node_id=world["value"].id, note="Nguyen is candid",
                    quote=IDENTIFYING_QUOTE, voice_turn_id=turns[0].id),
    ])
    claim = add_claims(db, application, ["A claim"])[0]
    claim.status, claim.evidence_quote, claim.voice_turn_id = "explained", "0901234", turns[0].id  # cuts the number in half
    db.commit()
    return application


def _detail(api, world, application, headers=None):
    response = api.get(url(world, f"/applications/{application.id}"), headers=headers or hr(world))
    assert response.status_code == 200, response.text
    return response


def test_before_a_reveal_transcripts_and_quotes_are_masked(api, db, world):
    application = _spoken_world(db, world)
    response = _detail(api, world, application)
    for secret in ("0901234567", "canary.candidate", "Nguyen", "Canary Candidate"):
        assert secret not in response.text, secret
    body = response.json()
    assert body["identity_masked"] is True
    assert "[NAME]" in body["transcript"][0]["transcript"] and "[ID]" in body["transcript"][0]["transcript"]
    assert body["suggestion"]["text"] == "Ask [NAME] about [ID]"


def test_a_masked_quote_still_matches_the_masked_transcript(api, db, world):
    application = _spoken_world(db, world)
    body = _detail(api, world, application).json()
    transcript = body["transcript"][0]["transcript"]
    interview = next(item["interview"] for item in body["requirements"] if item["interview"])
    assert interview["quote"] == PLAIN_QUOTE and interview["quote"] in transcript
    culture_quote = body["culture_notes"][0]["quote"]
    assert culture_quote == "call me on [ID]" and culture_quote in transcript


def test_a_quote_that_cannot_match_after_masking_is_not_shown(api, db, world):
    """The AI cut the phone number in half. Masking it alone would leave digits next to a transcript showing [ID]."""
    application = _spoken_world(db, world)
    response = _detail(api, world, application)
    claim = response.json()["claims"][0]
    assert claim["evidence_quote"] is None and claim["position"] == 1
    assert "0901234" not in response.text


def test_after_a_logged_reveal_this_member_reads_the_raw_text(api, db, world):
    application = _spoken_world(db, world)
    assert api.post(url(world, f"/applications/{application.id}/reveal"), headers=hr(world)).status_code == 200
    body = _detail(api, world, application).json()
    assert body["identity_masked"] is False
    assert body["transcript"][0]["transcript"] == SPOKEN
    assert body["culture_notes"][0]["quote"] == IDENTIFYING_QUOTE
    assert body["claims"][0]["evidence_quote"] == "0901234"
    db.rollback()
    assert db.query(AuditLog).filter_by(action="identity_revealed", target_id=application.id).count() == 1


def test_another_hr_member_stays_masked_until_they_reveal_too(api, db, world):
    application = _spoken_world(db, world)
    second = make_user(db, "second-hr@example.test")
    db.add(CompanyMember(company_id=world["company"].id, user_id=second.id, role="hr"))
    db.commit()
    assert api.post(url(world, f"/applications/{application.id}/reveal"), headers=hr(world)).status_code == 200
    body = _detail(api, world, application, headers=auth_header("second-hr@example.test")).json()
    assert body["identity_masked"] is True
    assert "0901234567" not in body["transcript"][0]["transcript"]


def test_a_reveal_of_another_application_does_not_count(api, db, world):
    application = _spoken_world(db, world)
    other = make_application(db, world["job"], "#A2", cv_status="meets", band="many")
    assert api.post(url(world, f"/applications/{other.id}/reveal"), headers=hr(world)).status_code == 200
    assert _detail(api, world, application).json()["identity_masked"] is True


def test_the_hr_audio_and_detail_routes_refuse_an_anonymized_application(api, db, world, tmp_path, monkeypatch):
    from app.hiring import recordings

    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    application = make_application(db, world["job"], "#A1", cv_status="meets", band="many")
    path = recordings.save_turn_audio(world["company"].id, application.id, 1, b"a late answer", ".webm")
    make_session(db, application, [(1, "q", "t", path)])
    application_url = url(world, f"/applications/{application.id}")
    assert api.get(f"{application_url}/turns/1/audio", headers=hr(world)).status_code == 200
    db.query(Application).filter_by(id=application.id).update({"anonymized_at": datetime.now(timezone.utc)})
    db.commit()
    assert api.get(application_url, headers=hr(world)).status_code == 404
    assert api.get(f"{application_url}/turns/1/audio", headers=hr(world)).status_code == 404
