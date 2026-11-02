import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.providers import fake
from app.bridges import channels
from app.brain import fake_demo
from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, AuditLog, ChannelContent, HiringRequest, Job, JobChannelLink, JobDraft, JobRequirement,
)
from app.main import create_app
from tests.helpers import auth_header
from tests.helpers_jd import line, make_draft, make_world

HR = auth_header("hr@acme.test")
MANAGER = auth_header("mgr@acme.test")
OTHER_MANAGER = auth_header("mgr2@acme.test")


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


def _lines(world):
    return [
        line("l1", [world.role.id], en="We build the APIs of our hiring platform", vi="Xay dung API", ko="API"),
        line("l2", [world.python.id], en="You have 3 years of Python experience", vi="3 nam Python", ko="Python 3",
             is_requirement=True, must_have=True),
        line("l3", [world.leave.id], en="You get 12 days of annual leave", vi="12 ngay phep", ko="12 il",
             is_requirement=False),
    ]


def _draft(db, world, status="draft", lines=None):
    return make_draft(db, world.company.id, lines or _lines(world), world.request.id, status=status)


def _post(api, world, draft, action, headers=HR):
    # Approve and publish name the version on the page, which is the one stored when the page reads it.
    session = SessionLocal()
    body = {"version": session.get(JobDraft, draft.id).version} if action in ("approve", "publish") else None
    session.close()
    return api.post(_url(world, f"/job-drafts/{draft.id}/{action}"), headers=headers, json=body)


def _approved(api, db, world, lines=None):
    draft = _draft(db, world, lines=lines)
    assert _post(api, world, draft, "submit").status_code == 200
    assert _post(api, world, draft, "approve", MANAGER).status_code == 200
    return draft


def _published(api, db, world):
    draft = _approved(api, db, world)
    response = _post(api, world, draft, "publish")
    assert response.status_code == 200, response.text
    return draft, response.json()


# --- submit and approve --------------------------------------------------------------------------------------------

def test_submit_with_blocking_lint_is_409_with_the_issues(api, db, world):
    draft = _draft(db, world, lines=[*_lines(world), line("l4", [], en="No source here")])
    response = _post(api, world, draft, "submit")
    assert response.status_code == 409
    assert {i["check"] for i in response.json()["detail"]["issues"]} == {"no_source"}
    db.expire_all()
    assert db.get(JobDraft, draft.id).status == "draft"


def test_submit_with_a_failed_language_is_409_and_names_it(api, db, world):
    lines = _lines(world)
    lines[0]["text"]["vi"] = ""
    response = _post(api, world, _draft(db, world, lines=lines), "submit")
    assert response.status_code == 409
    assert response.json()["detail"]["failed_languages"] == ["vi"]
    assert "vi" in response.json()["detail"]["message"]


def test_submit_moves_a_clean_draft_to_manager_review(api, db, world):
    draft = _draft(db, world)
    response = _post(api, world, draft, "submit")
    assert response.status_code == 200 and response.json()["status"] == "manager_review"
    assert _post(api, world, draft, "submit").status_code == 409
    assert _post(api, world, draft, "submit", MANAGER).status_code == 403


def test_only_the_assigned_manager_approves(api, db, world):
    draft = _draft(db, world)
    assert _post(api, world, draft, "submit").status_code == 200
    assert _post(api, world, draft, "approve", OTHER_MANAGER).status_code == 404
    assert _post(api, world, draft, "approve", HR).status_code == 403
    assert _post(api, world, draft, "approve", auth_header("hr@other.test")).status_code == 403
    db.expire_all()
    assert db.get(JobDraft, draft.id).status == "manager_review"

    approved = _post(api, world, draft, "approve", MANAGER)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved" and approved.json()["approved_by"] == world.manager.id


def test_an_employee_cannot_approve(api, db, world):
    from app.database.sql_models import CompanyMember
    from tests.helpers import make_user
    worker = make_user(db, "emp@acme.test")
    db.add(CompanyMember(company_id=world.company.id, user_id=worker.id, role="employee", department_id=world.eng.id))
    db.commit()
    draft = _draft(db, world, status="manager_review")
    assert _post(api, world, draft, "approve", auth_header("emp@acme.test")).status_code == 403


def test_approve_needs_a_submitted_draft(api, db, world):
    # Until the first submit the draft does not exist for a manager. After it, the status decides.
    assert _post(api, world, _draft(db, world), "approve", MANAGER).status_code == 404
    assert _post(api, world, _draft(db, world, status="approved"), "approve", MANAGER).status_code == 409


def _edit_patch(api, world, draft):
    return api.patch(_url(world, f"/job-drafts/{draft.id}"), headers=HR, json={"lines": [
        {"id": "l1", "text": {"en": "We build APIs for hiring"}}]})


def _edit_assistant(api, world, draft):
    return api.post(_url(world, f"/job-drafts/{draft.id}/assistant"), headers=HR, json={"message": "shorter"})


def _edit_confirm(api, world, draft):
    return api.post(_url(world, f"/job-drafts/{draft.id}/lines/l1/confirm"), headers=HR)


@pytest.mark.parametrize("edit", [_edit_patch, _edit_assistant, _edit_confirm])
def test_editing_an_approved_draft_returns_it_to_draft(api, db, world, edit):
    draft = _approved(api, db, world)
    response = edit(api, world, draft)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft" and response.json()["approved_by"] is None
    assert _post(api, world, draft, "publish").status_code == 409


# --- publish -------------------------------------------------------------------------------------------------------

def test_publish_without_approval_is_409(api, db, world):
    assert _post(api, world, _draft(db, world), "publish").status_code == 409
    assert _post(api, world, _draft(db, world, status="manager_review"), "publish").status_code == 409


def test_publish_checks_lint_again(api, db, world):
    draft = _approved(api, db, world)
    draft.lines = [*draft.lines, line("l4", [world.role.id], en="Male candidates only")]
    db.commit()
    response = _post(api, world, draft, "publish")
    assert response.status_code == 409
    assert "discrimination" in {i["check"] for i in response.json()["detail"]["issues"]}
    assert db.query(Job).count() == 0


def test_publish_creates_the_job_from_the_lines(api, db, world):
    draft, body = _published(api, db, world)
    job = db.query(Job).one()
    assert body["status"] == "published" and body["job"]["slug"] == job.slug and job.slug
    assert job.company_id == world.company.id and job.status == "published" and job.version == 1
    assert job.department_id == world.eng.id and job.title == "Backend Developer"
    assert job.description == ("We build the APIs of our hiring platform\nYou have 3 years of Python experience\n"
                               "You get 12 days of annual leave")
    requirement = db.query(JobRequirement).filter_by(job_id=job.id, active=True).one()
    assert (requirement.text, requirement.must_have, requirement.visibility, requirement.node_id) == (
        "You have 3 years of Python experience", True, "public", world.python.id)
    db.expire_all()
    assert db.get(JobDraft, draft.id).job_id == job.id
    audit = db.query(AuditLog).filter_by(action="job_draft.published", target_id=draft.id).one()
    assert audit.actor_user_id == world.hr.id and audit.payload["job_id"] == job.id


def test_publish_uses_the_company_default_language(api, db, world):
    world.company.default_locale = "vi"
    db.commit()
    _published(api, db, world)
    job = db.query(Job).one()
    assert job.description.splitlines()[0] == "Xay dung API" and job.interview_languages == ["vi"]


def test_publishing_links_the_hiring_request(api, db, world):
    _, body = _published(api, db, world)
    db.expire_all()
    request = db.get(HiringRequest, world.request.id)
    assert request.status == "published" and request.job_id == body["job"]["id"]


def test_a_new_draft_version_updates_the_same_job_and_bumps_version_only_for_requirements(api, db, world):
    draft, body = _published(api, db, world)
    job = db.query(Job).one()
    application = Application(company_id=world.company.id, job_id=job.id, job_version=1, alias="A1")
    db.add(application)
    db.commit()

    def republish():
        assert _post(api, world, draft, "submit").status_code == 200
        assert _post(api, world, draft, "approve", MANAGER).status_code == 200
        response = _post(api, world, draft, "publish")
        assert response.status_code == 200, response.text
        return response.json()

    wording = api.patch(_url(world, f"/job-drafts/{draft.id}"), headers=HR, json={"lines": [
        {"id": "l1", "text": {"en": "We build great APIs"}}]})
    assert wording.json()["status"] == "draft"
    out = republish()
    db.expire_all()
    assert out["job"]["id"] == job.id and db.query(Job).count() == 1
    assert db.get(Job, job.id).version == 1 and db.get(Job, job.id).description.startswith("We build great APIs")

    api.patch(_url(world, f"/job-drafts/{draft.id}"), headers=HR, json={"lines": [
        {"id": "l2", "text": {"en": "You have 5 years of Python experience"}}]})
    # the line's source says 3 years, but HR edits by hand: the guard only lints, so confirm the new wording
    api.post(_url(world, f"/job-drafts/{draft.id}/lines/l2/confirm"), headers=HR)
    out = republish()
    db.expire_all()
    assert db.get(Job, job.id).version == 2 and out["job"]["version"] == 2
    assert db.get(Application, application.id).job_version == 1
    assert {r.text for r in db.query(JobRequirement).filter_by(job_id=job.id, active=True)} == {
        "You have 5 years of Python experience"}


def test_publish_and_approve_are_company_scoped(api, db, world):
    other = make_draft(db, world.other.id, [])
    assert _post(api, world, other, "approve", MANAGER).status_code == 404
    assert _post(api, world, other, "publish").status_code == 404


# --- channels ------------------------------------------------------------------------------------------------------

CHANNEL_TOKENS = ["linkedin", "facebook", "itviec", "topcv", "university_email", "university_post"]


def test_channels_before_publish_are_409(api, db, world):
    draft = _draft(db, world)
    assert _post(api, world, draft, "channels/generate").status_code == 409
    assert api.get(_url(world, f"/job-drafts/{draft.id}/channels"), headers=HR).status_code == 409
    assert db.query(JobChannelLink).count() == 0


def test_channels_generate_each_piece_with_its_tracked_link(api, db, world):
    draft, body = _published(api, db, world)
    response = _post(api, world, draft, "channels/generate")
    assert response.status_code == 200, response.text
    pieces = response.json()["channels"]
    assert [p["channel"] for p in pieces] == CHANNEL_TOKENS
    slug = body["job"]["slug"]
    for piece in pieces:
        link = db.query(JobChannelLink).filter_by(job_id=body["job"]["id"], channel=piece["channel"]).one()
        url = f"http://localhost:3000/jobs/{slug}?src={link.token}"
        assert url in piece["body"] and "{link}" not in piece["body"] and piece["link"]["url"] == url
        assert piece["body"].startswith("[Demo AI]")
    assert {p["channel"]: p["language"] for p in pieces}["facebook"] == "vi"
    assert "Xay dung API" in pieces[1]["body"]

    again = _post(api, world, draft, "channels/generate").json()["channels"]
    assert db.query(ChannelContent).count() == 6 and db.query(JobChannelLink).count() == 6
    assert [p["link"]["token"] for p in again] == [p["link"]["token"] for p in pieces]
    read = api.get(_url(world, f"/job-drafts/{draft.id}/channels"), headers=HR)
    assert read.status_code == 200 and read.json()["channels"] == again
    assert api.get(_url(world, f"/job-drafts/{draft.id}/channels"), headers=MANAGER).status_code == 403
    assert _post(api, world, draft, "channels/generate", MANAGER).status_code == 403


def test_public_url_comes_from_the_environment(api, db, world, monkeypatch):
    monkeypatch.setenv("SPEAKCV_PUBLIC_URL", "https://speak.hire.test/")
    draft, _ = _published(api, db, world)
    pieces = _post(api, world, draft, "channels/generate").json()["channels"]
    assert all(p["body"].count("https://speak.hire.test/jobs/") == 1 for p in pieces)


def test_a_number_the_lines_do_not_contain_is_replaced_by_a_template(api, db, world):
    draft, _ = _published(api, db, world)
    fake.enqueue("channel_content", json.dumps({"body": "Salary 50 million VND! 12 days leave. {link}"}))
    pieces = _post(api, world, draft, "channels/generate").json()["channels"]
    linkedin = pieces[0]
    assert "50" not in linkedin["body"] and "Backend Developer" in linkedin["body"]
    assert "12 days of annual leave" in linkedin["body"] and "/jobs/" in linkedin["body"]
    assert pieces[1]["body"].startswith("[Demo AI]")  # the others kept the AI text


def test_ai_text_with_only_known_numbers_is_kept_and_an_unknown_link_is_not(api, db, world):
    draft, _ = _published(api, db, world)
    fake.enqueue("channel_content", json.dumps({"body": "Join us: 3 years of Python, 12 days leave."}))
    fake.enqueue("channel_content", json.dumps({"body": "Apply at https://evil.test/x {link}"}))
    pieces = _post(api, world, draft, "channels/generate").json()["channels"]
    assert pieces[0]["body"].startswith("Join us: 3 years of Python") and "/jobs/" in pieces[0]["body"]
    assert "evil.test" not in pieces[1]["body"]


def test_itviec_template_has_sections_and_benefits_only_from_benefit_lines(db, world):
    lines = _lines(world)
    types = {world.role.id: "role", world.python.id: "requirement", world.leave.id: "fact"}
    text = channels.template(channels.BY_TOKEN["itviec"], "Backend Developer", lines, "en", types)
    assert text.index("Job title: Backend Developer") < text.index("Description:") < text.index("Requirements:") \
        < text.index("Benefits:")
    assert "- You get 12 days of annual leave" in text.split("Benefits:")[1]
    assert "Python" not in text.split("Benefits:")[1]
    bare = channels.template(channels.BY_TOKEN["topcv"], "Backend Developer", lines[:2], "en", types)
    assert "Benefits:" not in bare


def test_an_ai_failure_keeps_the_saved_content_and_is_503(api, db, world):
    draft, _ = _published(api, db, world)
    first = _post(api, world, draft, "channels/generate").json()["channels"]

    def boom(*_):
        raise RuntimeError("down")

    fake.register("channel_content", boom)
    response = _post(api, world, draft, "channels/generate")
    assert response.status_code == 503
    db.expire_all()
    assert [r.body for r in db.query(ChannelContent).order_by(ChannelContent.id)] == [p["body"] for p in first]


def test_channels_need_the_draft_to_be_published_again_after_an_edit(api, db, world):
    draft, _ = _published(api, db, world)
    _edit_patch(api, world, draft)
    assert _post(api, world, draft, "channels/generate").status_code == 409


def test_facts_within_unit():
    lines = [line("l1", [1], en="12 days leave", vi="12 ngay", ko="12")]
    assert channels.facts_within("12 days {link}", lines)
    assert not channels.facts_within("13 days {link}", lines)
    assert not channels.facts_within("see https://x.test", lines)


# --- the system never posts ---------------------------------------------------------------------------------------

def test_no_outbound_http_library_is_imported_in_bridges():
    banned = {"requests", "httpx", "urllib", "urllib3", "aiohttp", "http", "smtplib", "socket", "ftplib", "websockets"}
    for path in (Path(__file__).resolve().parents[1] / "app" / "bridges").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not {n.split(".")[0] for n in names} & banned, f"{path.name} imports {names}"
