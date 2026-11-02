"""Gaps found when the portal met the API: draft id on requests, audience-filtered sources, lint node ids."""
import json

import pytest
from fastapi.testclient import TestClient

from app.ai.providers import fake
from app.brain import fake_demo
from app.bridges import lint
from app.main import create_app
from tests.helpers import auth_header
from tests.helpers_jd import line, make_draft, make_world


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


def test_requests_carry_the_latest_draft_for_hr_and_the_assigned_manager(api, db, world):
    hr, manager = auth_header("hr@acme.test"), auth_header("mgr@acme.test")
    detail = api.get(_url(world, f"/hiring-requests/{world.request.id}"), headers=hr).json()
    assert detail["latest_draft_id"] is None and detail["latest_draft_status"] is None
    make_draft(db, world.company.id, [], world.request.id)
    newest = make_draft(db, world.company.id, [], world.request.id, status="manager_review")
    for headers in (hr, manager):
        listed = api.get(_url(world, "/hiring-requests"), headers=headers).json()
        assert [(r["latest_draft_id"], r["latest_draft_status"]) for r in listed] == [(newest.id, "manager_review")]
        detail = api.get(_url(world, f"/hiring-requests/{world.request.id}"), headers=headers).json()
        assert detail["latest_draft_id"] == newest.id and detail["latest_draft_status"] == "manager_review"
        assert detail["title"] == "Backend Developer"  # existing fields stay


def test_another_managers_request_stays_hidden(api, db, world):
    make_draft(db, world.company.id, [], world.request.id)
    other = auth_header("mgr2@acme.test")
    assert api.get(_url(world, "/hiring-requests"), headers=other).json() == []
    assert api.get(_url(world, f"/hiring-requests/{world.request.id}"), headers=other).status_code == 404


def _sources(body):
    return {item["id"]: item["sources"] for item in body["lines"]}


def test_a_manager_gets_titles_only_for_sources_their_layer_allows(api, db, world):
    secret = world.builder.node("Sales commission plan", "private", type="private_note", visibility="confidential",
                                department_id=world.sales.id)
    lines = [line("l1", [world.python.id, world.internal.id, world.note.id, secret.id]),
             line("l2", [world.role.id])]
    draft = make_draft(db, world.company.id, lines, world.request.id)
    out = api.get(_url(world, f"/job-drafts/{draft.id}"), headers=auth_header("mgr@acme.test"))
    assert out.status_code == 200
    sources = {s["node_id"]: s["title"] for s in _sources(out.json())["l1"]}
    assert sources[world.python.id] == "Python experience"
    assert sources[world.internal.id] == "Remote policy"
    assert sources[world.note.id] == "Pay note"  # confidential, but in the manager's own department
    assert sources[secret.id] is None  # above the layer: no title
    assert "Sales commission plan" not in out.text
    hr = api.get(_url(world, f"/job-drafts/{draft.id}"), headers=auth_header("hr@acme.test"))
    assert {s["node_id"]: s["title"] for s in _sources(hr.json())["l1"]}[secret.id] == "Sales commission plan"


def test_sources_never_expose_a_node_of_another_company(api, db, world):
    foreign = world.builder.node("Foreign secret title", "x", company_id=world.other.id)
    draft = make_draft(db, world.company.id, [line("l1", [foreign.id, world.python.id])], world.request.id)
    for who in ("hr@acme.test", "mgr@acme.test"):
        out = api.get(_url(world, f"/job-drafts/{draft.id}"), headers=auth_header(who))
        assert "Foreign secret title" not in out.text
        assert {s["node_id"]: s["title"] for s in _sources(out.json())["l1"]}[foreign.id] is None


def test_a_line_without_sources_has_an_empty_list(api, db, world):
    draft = make_draft(db, world.company.id, [line("l1", [])], world.request.id)
    out = api.get(_url(world, f"/job-drafts/{draft.id}"), headers=auth_header("hr@acme.test")).json()
    assert out["lines"][0]["sources"] == []


def test_conflict_issues_carry_the_node_id(db, world):
    draft = make_draft(db, world.company.id, [line("l1", [world.role.id], en="Employees get 15 days of annual leave", vi="Nghi phep", ko="Yeonca")])
    fake.enqueue("lint_conflict_check", json.dumps({"same_topic": True}))
    report = lint.run(db, draft)
    conflicts = [i for i in report.issues if i.check == "conflict"]
    assert [i.node_id for i in conflicts] == [world.leave.id]
    assert str(world.leave.id) in conflicts[0].message
    assert all(i.node_id is None for i in report.issues if i.check != "conflict")
    db.refresh(draft)
    assert [i["node_id"] for i in draft.lint if i["check"] == "conflict"] == [world.leave.id]
