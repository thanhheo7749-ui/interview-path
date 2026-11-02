"""Block 4 final review, group Y: stored rejected lines, dismissed proposals, channel content on republish, the draft's
title, the five small gaps and the acknowledge audit row."""
import pytest
from fastapi.testclient import TestClient

from app.ai.providers import fake
from app.brain import fake_demo
from app.bridges import jd_studio
from app.database.sql_models import AuditLog, ChannelContent, CompanyMember, Job, JobDraft
from app.main import create_app
from tests.helpers import auth_header
from tests.helpers_jd import ai_line, generate_json, line, make_draft, make_world

HR = auth_header("hr@acme.test")
MANAGER = auth_header("mgr@acme.test")
OTHER_HR = auth_header("hr@other.test")


@pytest.fixture(autouse=True)
def _demo_responders():
    fake_demo.install()


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def api(db, world):
    with TestClient(create_app()) as client:
        yield client


def _url(world, tail):
    return f"/api/companies/{world.company.id}{tail}"


# --- M-4: the lines code removed stay on the draft --------------------------------------------------------------

def test_rejected_lines_are_stored_on_the_draft_and_read_back(api, db, world):
    fake.enqueue("jd_generate", generate_json([
        ai_line("l1", [world.role.id], en="We build the APIs of our hiring platform"),
        ai_line("l2", [world.python.id], en="You earn 50 million VND", vi="Luong 50 trieu", ko="Yeonbong 50"),
    ]))
    created = api.post(_url(world, f"/hiring-requests/{world.request.id}/drafts"), headers=HR, json={})
    assert created.status_code == 200, created.text
    assert [r["line_id"] for r in created.json()["rejected"]] == ["l2"]
    got = api.get(_url(world, f"/job-drafts/{created.json()['id']}"), headers=HR)
    assert [r["line_id"] for r in got.json()["rejected"]] == ["l2"]
    assert got.json()["rejected"][0]["reason"] and got.json()["rejected"][0]["text"]["en"] == "You earn 50 million VND"
    assert got.json()["rejected"][0]["code"] == "unsupported_numbers" and got.json()["rejected"][0]["detail"] == ["50"]


# --- M-5: a dismissed proposal stays gone ------------------------------------------------------------------------

def _draft_with_a_proposal(db, world):
    draft = make_draft(db, world.company.id, [line("l1", [world.role.id], en="We build the APIs", vi="API", ko="API")],
                       world.request.id)
    result = jd_studio.revise(db, draft, "add the salary", world.hr.id)
    db.commit()
    return draft, result.needs_confirmation[0]["id"]


def test_dismissing_a_proposal_removes_it_for_good(api, db, world):
    draft, proposal_id = _draft_with_a_proposal(db, world)
    path = _url(world, f"/job-drafts/{draft.id}/proposals/{proposal_id}/dismiss")
    assert [p["id"] for p in api.get(_url(world, f"/job-drafts/{draft.id}"), headers=HR).json()["proposals"]] == [proposal_id]
    assert api.post(path, headers=MANAGER).status_code == 403
    foreign = f"/api/companies/{world.other.id}/job-drafts/{draft.id}/proposals/{proposal_id}/dismiss"
    assert api.post(foreign, headers=OTHER_HR).status_code == 404
    response = api.post(path, headers=HR)
    assert response.status_code == 200 and response.json()["proposals"] == []
    assert api.get(_url(world, f"/job-drafts/{draft.id}"), headers=HR).json()["proposals"] == []
    confirm = api.post(_url(world, f"/job-drafts/{draft.id}/lines/{proposal_id}/confirm"), headers=HR)
    assert confirm.status_code == 404  # a dismissed proposal cannot be confirmed
    assert api.post(path, headers=HR).status_code == 404
    assert db.query(AuditLog).filter_by(action="job_draft.proposal_dismissed", target_id=draft.id).count() == 1


# --- M-8: the title is stored on the draft -----------------------------------------------------------------------

def _publish(api, world, draft_id):
    assert api.post(_url(world, f"/job-drafts/{draft_id}/submit"), headers=HR).status_code == 200
    version = {"version": api.get(_url(world, f"/job-drafts/{draft_id}"), headers=HR).json()["version"]}
    assert api.post(_url(world, f"/job-drafts/{draft_id}/approve"), headers=MANAGER, json=version).status_code == 200
    response = api.post(_url(world, f"/job-drafts/{draft_id}/publish"), headers=HR, json=version)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_draft_made_from_a_role_keeps_its_title_through_publishing(api, db, world):
    fake.enqueue("jd_generate", generate_json([
        ai_line("l1", [world.role.id], en="We build the APIs of our hiring platform"),
        ai_line("l2", [world.python.id], en="You have 3 years of Python experience", is_requirement=True, must_have=True),
    ]))
    created = api.post(_url(world, "/job-drafts"), headers=HR,
                       json={"role_node_id": world.role.id, "title": "Senior Backend Engineer"})
    assert created.status_code == 200, created.text
    assert db.get(JobDraft, created.json()["id"]).title == "Senior Backend Engineer"
    published = _publish(api, world, created.json()["id"])
    db.expire_all()
    assert db.get(Job, published["job"]["id"]).title == "Senior Backend Engineer"


# --- M-6: stored channel content does not outlive a new version --------------------------------------------------

def test_channel_content_is_deleted_when_a_new_version_is_published(api, db, world):
    draft = make_draft(db, world.company.id, [
        line("l1", [world.role.id], en="We build the APIs of our hiring platform", vi="Xay dung API", ko="API"),
        line("l2", [world.python.id], en="You have 3 years of Python experience", vi="3 nam Python", ko="Python 3",
             is_requirement=True, must_have=True),
    ], world.request.id)
    _publish(api, world, draft.id)
    assert api.post(_url(world, f"/job-drafts/{draft.id}/channels/generate"), headers=HR).status_code == 200
    assert db.query(ChannelContent).count() == 6
    api.patch(_url(world, f"/job-drafts/{draft.id}"), headers=HR,
              json={"lines": [{"id": "l1", "text": {"en": "We build great APIs"}}]})
    _publish(api, world, draft.id)
    db.expire_all()
    assert db.query(ChannelContent).count() == 0
    assert api.get(_url(world, f"/job-drafts/{draft.id}/channels"), headers=HR).json()["channels"] == []


# --- M-11: the acknowledge audit row -----------------------------------------------------------------------------

def test_acknowledging_an_unchecked_line_writes_an_audit_row(api, db, world):
    draft = make_draft(db, world.company.id, [line("l1", [world.role.id], en="We build APIs")], world.request.id)

    def boom(*_):
        raise RuntimeError("down")

    fake.register("discrimination_check", boom)
    api.post(_url(world, f"/job-drafts/{draft.id}/lint"), headers=HR)
    response = api.post(_url(world, f"/job-drafts/{draft.id}/lint/acknowledge"), headers=HR, json={"line_id": "l1"})
    assert response.status_code == 200
    row = db.query(AuditLog).filter_by(action="job_draft.unchecked_acknowledged", target_id=draft.id).one()
    assert row.actor_user_id == world.hr.id and row.payload["line_ids"] == ["l1"]
    assert "We build" not in str(row.payload)
