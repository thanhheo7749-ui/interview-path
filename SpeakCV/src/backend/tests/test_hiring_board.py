import json
import types

import pytest
from fastapi.testclient import TestClient

from app.database.sql_models import Application, AuditLog, CultureNote, RequirementResult
from app.hiring import board
from app.main import create_app
from tests.helpers_board import (
    CANDIDATE_EMAIL, CANDIDATE_NAME, CONFIDENTIAL, CV_RAW, add_claims, make_application, make_session, make_world,
)


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


def test_board_module_does_not_reference_raw_cv_text():
    import inspect
    assert "cv_text_raw" not in inspect.getsource(board)
    assert types.ModuleType  # keep import used
