"""Who may read and approve a draft, what a line may claim, and what an approval covers (the Block 4 final review)."""
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.ai import gateway
from app.ai.providers import fake
from app.brain import audience as aud
from app.brain import fake_demo, vectors
from app.bridges import brief, jd_studio, lint, publishing
from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, AuditLog, CandidateBrief, CompanyMember, HiringRequest, InterviewScorecard, Job, JobDraft,
    JobRequirement, Notification, RequirementResult, VoiceSession, VoiceTurn,
)
from app.main import create_app
from tests.helpers import auth_header, make_user
from tests.helpers_jd import ai_line, assistant_json, generate_json, line, make_draft, make_world

HR = auth_header("hr@acme.test")
MANAGER = auth_header("mgr@acme.test")
SALES_MANAGER = auth_header("mgr2@acme.test")
SECOND_MANAGER = auth_header("mgr3@acme.test")
EMPLOYEE = auth_header("emp@acme.test")
QUOTE_SECRET = "I would accept the confidential pay cut"
QUOTE_OPEN = "I built APIs for four teams"


@pytest.fixture(autouse=True)
def _demo():
    fake_demo.install()


@pytest.fixture
def world(db):
    made = make_world(db)
    second = make_user(db, "mgr3@acme.test")
    employee = make_user(db, "emp@acme.test")
    db.add_all([
        CompanyMember(company_id=made.company.id, user_id=second.id, role="manager", department_id=made.eng.id),
        CompanyMember(company_id=made.company.id, user_id=employee.id, role="employee"),
    ])
    db.commit()
    made.second_manager = second
    return made


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
    ]


def _draft(db, world, status="draft", lines=None, request_id="request"):
    request = world.request.id if request_id == "request" else request_id
    return make_draft(db, world.company.id, lines or _lines(world), request, status=status)


def _read(api, world, draft, headers=HR):
    return api.get(_url(world, f"/job-drafts/{draft.id}"), headers=headers)


def _act(api, world, draft_id, action, headers=HR, version=None):
    body = {"version": version} if version is not None else None
    return api.post(_url(world, f"/job-drafts/{draft_id}/{action}"), headers=headers, json=body)


def _stored(db, draft_id):
    db.rollback()
    db.expire_all()
    return db.get(JobDraft, draft_id)


def _in_other_session(work):
    session = SessionLocal()
    try:
        work(session)
        session.commit()
    finally:
        session.close()


def _assistant_returns(world, *extra, keep=True):
    kept = [ai_line("l1", [world.role.id], en="We build the APIs of our hiring platform", vi="Xay dung API", ko="API"),
            ai_line("l2", [world.python.id], en="You have 3 years of Python experience", vi="3 nam Python", ko="Python 3",
                    is_requirement=True, must_have=True)] if keep else []
    fake.enqueue("jd_assistant", assistant_json([*kept, *extra]))


# --- C-1: code decides what a line may claim ------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"en": "Salary 40 million VND per month", "vi": "Luong 40 trieu", "ko": "월급 40"},
    {"en": "Free housing and a company car", "vi": "Nha o", "ko": "주택"},
    {"en": "Competitive salary, thirteen months", "vi": "Luong", "ko": "연봉"},
    {"en": "A master's degree is mandatory", "vi": "Bang thac si", "ko": "석사", "is_requirement": True, "must_have": True},
])
def test_a_new_line_citing_any_node_is_only_proposed(db, world, bad):
    hours = world.builder.node("We work 40 hours per week", "", type="fact")
    draft = _draft(db, world)
    _assistant_returns(world, ai_line("l9", [hours.id], **bad))

    result = jd_studio.revise(db, draft, "improve it", world.hr.id)

    assert [item["id"] for item in result.draft.lines] == ["l1", "l2"]
    assert len(result.needs_confirmation) == 1 and result.needs_confirmation[0]["en"] == bad["en"]


def test_a_changed_source_or_requirement_flag_is_only_proposed_and_the_line_stays(db, world):
    draft = _draft(db, world)
    fake.enqueue("jd_assistant", assistant_json([
        ai_line("l1", [world.python.id], en="We build the APIs of our hiring platform", vi="Xay dung API", ko="API"),
        ai_line("l2", [world.python.id], en="You have 3 years of Python experience", vi="3 nam Python", ko="Python 3",
                is_requirement=False),
    ]))

    result = jd_studio.revise(db, draft, "improve it", world.hr.id)

    assert result.draft.lines[0]["source_node_ids"] == [world.role.id]
    assert result.draft.lines[1]["is_requirement"] is True and result.draft.lines[1]["must_have"] is True
    assert len(result.needs_confirmation) == 2


def test_only_a_restyle_applies_directly(db, world):
    draft = _draft(db, world)
    fake.enqueue("jd_assistant", assistant_json([
        ai_line("l1", [world.role.id], en="Build the APIs of our platform", vi="Xay API", ko="API"),
        ai_line("l2", [world.python.id], en="Bring 3 years of Python", vi="3 nam Python", ko="Python 3",
                is_requirement=True, must_have=True),
    ]))

    result = jd_studio.revise(db, draft, "shorter", world.hr.id)

    assert result.needs_confirmation == []
    assert result.draft.lines[0]["text"]["en"] == "Build the APIs of our platform"


@pytest.mark.parametrize("words", [
    {"en": "We build APIs, with free housing", "vi": "Xay API", "ko": "API"},
    {"en": "We build APIs", "vi": "Xây API, có nhà ở miễn phí", "ko": "API"},
    {"en": "We build APIs", "vi": "Xây API", "ko": "API 연봉 협상 가능"},
    {"en": "We build APIs, great pay", "vi": "Xây API", "ko": "API"},
    {"en": "We build APIs", "vi": "Xây API, thưởng tháng 13", "ko": "API"},
    {"en": "We build APIs", "vi": "Xây API", "ko": "API 스톡옵션 지급"},
])
def test_a_restyle_that_adds_a_salary_or_benefit_term_is_only_proposed(db, world, words):
    draft = _draft(db, world)
    fake.enqueue("jd_assistant", assistant_json([ai_line("l1", [world.role.id], **words)]))

    result = jd_studio.revise(db, draft, "friendlier", world.hr.id)

    assert result.draft.lines[0]["text"]["en"] == "We build the APIs of our hiring platform"
    assert len(result.needs_confirmation) == 1


def test_a_term_passes_when_a_cited_node_carries_it_in_any_language():
    texts = {1: "Mức lương được xem xét mỗi năm", 2: "연차 15일과 건강 보험"}
    salary = line("a", [1], en="Salary is reviewed every year", vi="Xem xét lương", ko="연봉 검토")
    insurance = line("b", [2], en="Health insurance", vi="Bảo hiểm", ko="건강 보험")
    wrong_node = line("c", [2], en="Salary is reviewed", vi="Lương", ko="연봉")
    result = jd_studio.validate_lines([salary, insurance, wrong_node], {1, 2}, texts)
    assert [item["id"] for item in result.valid] == ["a", "b"]
    assert [item["line_id"] for item in result.rejected] == ["c"]


@pytest.mark.parametrize("source, en, supported", [
    ("We work 40 hours per week", "Salary 40 million VND per month", False),
    ("We work 40 hours per week", "40 days of work", False),
    ("We work 40 hours per week", "A week of 40 hours", True),
    ("We work 40 hours per week", "We work 40 hours", True),
    ("We work 40 hours per week", "주 40시간 근무", True),
    ("Pay is 5 triệu đồng", "Pay is 5,000,000 VND", True),
    ("Pay is 5 triệu đồng", "Pay is 5,000,000 USD", False),
    ("Pay is 5 triệu đồng", "Pay is 5M VND", True),
    ("Pay is 5 triệu đồng", "Pay is 5", True),
    ("연봉 5천만원", "Pay is 50,000,000 won", True),
    ("Leave is 12 days", "Leave is 12 weeks", False),
    ("Leave is 12 days", "Leave is 12일", True),
    ("Needs three years of Python", "3 years of Python", True),
    ("Apply by 2026-12-01", "Apply by December 1, 2026", True),
    ("Apply by 2026-12-01", "Apply by 2026-12-02", False),
    ("Python and Web3", "Knows Python3 and Web3", True),
])
def test_a_number_is_compared_with_its_unit(source, en, supported):
    item = line("a", [1], en=en, vi="x", ko="y")
    assert bool(lint.unsupported_claims(item, {1: source})) is not supported


def test_generate_applies_the_term_and_unit_checks(db, world):
    hours = world.builder.node("We work 40 hours per week", "", type="fact")
    fake.enqueue("jd_generate", generate_json([
        ai_line("l1", [world.role.id], en="We build the APIs of our hiring platform", vi="API", ko="API"),
        ai_line("l2", [world.role.id], en="Free housing", vi="Nha o", ko="주택"),
        ai_line("l3", [hours.id], en="Salary 40 million VND", vi="Luong", ko="연봉"),
    ]))
    draft = jd_studio.generate(db, world.request, world.hr.id)
    assert [item["id"] for item in draft.lines] == ["l1"]
    assert {item["line_id"] for item in draft.rejected_lines} == {"l2", "l3"}


def test_the_demo_assistant_returns_the_bad_line_and_code_stops_it(db, world):
    draft = _draft(db, world)
    raw = json.loads(fake_demo._jd_assistant("", [{"role": "user", "content": (
        f"<draft>\n{json.dumps([jd_studio._flat(item) for item in draft.lines])}\n</draft>\n"
        "<request>\nadd a salary\n</request>")}], None))
    assert raw["proposals"] == []
    assert any("salary" in item["en"].lower() and item["source_node_ids"] for item in raw["lines"])


def test_confirming_a_proposal_for_an_existing_line_replaces_it(db, world):
    draft = _draft(db, world)
    fake.enqueue("jd_assistant", assistant_json([
        ai_line("l1", [world.role.id], en="We build APIs with 9 engineers", vi="9", ko="9"),
        ai_line("l2", [world.python.id], en="You have 3 years of Python experience", vi="3 nam Python", ko="Python 3",
                is_requirement=True, must_have=True),
    ]))
    result = jd_studio.revise(db, draft, "add the size", world.hr.id)
    assert result.draft.lines[0]["text"]["en"] == "We build the APIs of our hiring platform"

    confirmed = jd_studio.confirm_line(db, draft, result.needs_confirmation[0]["id"], world.hr.id)

    assert [item["id"] for item in confirmed.lines] == ["l1", "l2"]
    assert confirmed.lines[0]["text"]["en"] == "We build APIs with 9 engineers"
    assert confirmed.lines[0]["hr_confirmed"]["user_id"] == world.hr.id


def test_a_proposed_requirement_stays_a_requirement_when_confirmed(db, world):
    draft = _draft(db, world)
    _assistant_returns(world, ai_line("l9", [world.role.id], en="A master's degree is mandatory", vi="Thac si", ko="석사",
                                      is_requirement=True, must_have=True))
    result = jd_studio.revise(db, draft, "add it", world.hr.id)
    confirmed = jd_studio.confirm_line(db, draft, result.needs_confirmation[0]["id"], world.hr.id)
    added = [item for item in confirmed.lines if item["hr_confirmed"]][0]
    assert (added["is_requirement"], added["must_have"]) == (True, True)


# --- I-1, I-2: the assigned manager reads and approves ---------------------------------------------------------------

def test_a_second_manager_of_the_department_gets_404_on_the_draft_and_on_approve(api, db, world):
    draft = _draft(db, world, status="manager_review")
    assert _read(api, world, draft, SECOND_MANAGER).status_code == 404
    assert _act(api, world, draft.id, "approve", SECOND_MANAGER, version=draft.version).status_code == 404
    assert _read(api, world, draft, MANAGER).status_code == 200
    assert _stored(db, draft.id).status == "manager_review"


def test_the_assigned_manager_of_another_department_approves_and_the_department_cannot(api, db, world):
    created = api.post(_url(world, "/hiring-requests"), headers=HR,
                       json={"title": "Sales lead", "manager_user_id": world.manager.id, "department_id": world.sales.id})
    assert created.status_code == 201, created.text
    draft = _draft(db, world, status="manager_review", request_id=created.json()["id"])

    assert _act(api, world, draft.id, "approve", SALES_MANAGER, version=draft.version).status_code == 404
    assert _act(api, world, draft.id, "approve", MANAGER, version=draft.version).status_code == 200


def test_a_request_with_no_department_can_be_approved_by_its_manager(api, db, world):
    created = api.post(_url(world, "/hiring-requests"), headers=HR,
                       json={"title": "Roaming lead", "manager_user_id": world.manager.id})
    assert created.status_code == 201
    draft = _draft(db, world, status="manager_review", request_id=created.json()["id"])

    assert _read(api, world, draft, MANAGER).status_code == 200
    assert _act(api, world, draft.id, "approve", MANAGER, version=draft.version).status_code == 200


def test_a_draft_with_no_request_stays_with_the_departments_managers(api, db, world):
    draft = _draft(db, world, status="manager_review", request_id=None)
    assert _read(api, world, draft, SECOND_MANAGER).status_code == 200
    assert _read(api, world, draft, SALES_MANAGER).status_code == 404
    assert _act(api, world, draft.id, "approve", SECOND_MANAGER, version=draft.version).status_code == 200


def test_hr_edits_a_request_and_the_new_manager_takes_over(api, db, world):
    draft = _draft(db, world, status="manager_review")
    path = _url(world, f"/hiring-requests/{world.request.id}")
    assert api.patch(path, headers=MANAGER, json={"title": "Nope"}).status_code == 403
    assert api.patch(path, headers=HR, json={"manager_user_id": 987654}).status_code == 422
    assert api.patch(path, headers=HR, json={"department_id": 987654}).status_code == 404

    changed = api.patch(path, headers=HR, json={"title": "Staff Developer", "manager_user_id": world.second_manager.id,
                                                "department_id": None})
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["title"], body["manager_user_id"], body["department_id"]) == (
        "Staff Developer", world.second_manager.id, None)
    assert _read(api, world, draft, MANAGER).status_code == 404
    assert _read(api, world, draft, SECOND_MANAGER).status_code == 200
    assert db.query(AuditLog).filter_by(action="hiring_request_updated", target_id=world.request.id).count() == 1


def test_a_manager_cannot_be_changed_during_a_running_intake(api, db, world):
    session = VoiceSession(company_id=world.company.id, purpose="intake", owner_user_id=world.manager.id,
                           language="en", status="in_progress")
    db.add(session)
    db.commit()
    request = db.get(HiringRequest, world.request.id)
    request.intake_session_id, request.status = session.id, "intake_in_progress"
    db.commit()
    path = _url(world, f"/hiring-requests/{world.request.id}")
    assert api.patch(path, headers=HR, json={"manager_user_id": world.second_manager.id}).status_code == 409
    assert api.patch(path, headers=HR, json={"title": "Renamed"}).status_code == 200


def test_cancel_is_hr_only_and_stops_the_request(api, db, world):
    draft = _draft(db, world, status="manager_review")
    approved = _draft(db, world, status="approved")
    path = _url(world, f"/hiring-requests/{world.request.id}")
    assert api.post(f"{path}/cancel", headers=MANAGER).status_code == 403

    response = api.post(f"{path}/cancel", headers=HR)
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert db.query(AuditLog).filter_by(action="hiring_request_cancelled", target_id=world.request.id).count() == 1

    assert api.post(f"{path}/cancel", headers=HR).status_code == 409
    assert api.patch(path, headers=HR, json={"title": "Back"}).status_code == 409
    assert api.post(f"{path}/intake/start", headers=MANAGER, json={}).status_code == 409
    assert api.post(f"{path}/drafts", headers=HR, json={}).status_code == 409
    assert _act(api, world, draft.id, "approve", MANAGER, version=draft.version).status_code == 409
    assert _act(api, world, approved.id, "publish", HR, version=approved.version).status_code == 409
    fresh = _draft(db, world)
    assert _act(api, world, fresh.id, "submit", HR).status_code == 409


def test_a_published_request_cannot_be_cancelled(api, db, world):
    request = db.get(HiringRequest, world.request.id)
    request.status = "published"
    db.commit()
    assert api.post(_url(world, f"/hiring-requests/{world.request.id}/cancel"), headers=HR).status_code == 409


# --- I-3: lint keeps no title ----------------------------------------------------------------------------------------

def _near_confidential_fact(db, world, text):
    result = gateway.embed([text], "query", "t", world.company.id)
    node = world.builder.node("CANARY-LINT-SALES-FACT", "", visibility="confidential", department_id=world.sales.id,
                              fact_kind="number", fact_value="99", fact_unit="days")
    node.embedding = vectors.encode(np.asarray(result.vectors[0], dtype="<f4"))
    node.embedding_model, node.embedding_dim = result.model, result.dimension
    db.commit()
    return node


def test_a_conflict_stores_no_title_and_each_reader_gets_what_they_may_read(api, db, world):
    text = "You get 15 days of something"
    node = _near_confidential_fact(db, world, text)
    draft = _draft(db, world, status="manager_review", lines=[line("l1", [world.role.id], en=text, vi="v", ko="k")])
    fake.register("lint_conflict_check", lambda *_: json.dumps({"same_topic": True}))

    lint.run(db, draft)

    stored = _stored(db, draft.id).lint
    conflict = next(item for item in stored if item["check"] == "conflict")
    assert conflict["node_id"] == node.id and "CANARY" not in json.dumps(stored)

    as_manager = _read(api, world, draft, MANAGER)
    assert "CANARY" not in as_manager.text
    assert next(i for i in as_manager.json()["lint"] if i["check"] == "conflict")["node_title"] is None

    as_hr = _read(api, world, draft, HR).json()
    assert next(i for i in as_hr["lint"] if i["check"] == "conflict")["node_title"] == "CANARY-LINT-SALES-FACT"


# --- I-4: what a manager's read holds --------------------------------------------------------------------------------

def test_a_manager_gets_404_until_the_first_submit_and_then_no_hr_material(api, db, world):
    draft = _draft(db, world)
    jd_studio.revise(db, draft, "add a salary, the budget is tight", world.hr.id)
    assert _read(api, world, draft, MANAGER).status_code == 404
    requests = api.get(_url(world, "/hiring-requests"), headers=MANAGER).json()
    assert requests[0]["latest_draft_id"] is None
    assert api.get(_url(world, "/hiring-requests"), headers=HR).json()[0]["latest_draft_id"] == draft.id

    assert _act(api, world, draft.id, "submit", HR).status_code == 200
    response = _read(api, world, draft, MANAGER)
    assert response.status_code == 200
    body = response.json()
    assert not {"messages", "proposals", "rejected"} & set(body)
    assert "budget" not in response.text
    assert api.get(_url(world, "/hiring-requests"), headers=MANAGER).json()[0]["latest_draft_id"] == draft.id
    assert {"messages", "proposals", "rejected"} <= set(_read(api, world, draft, HR).json())


def test_a_draft_edited_after_its_first_submit_stays_readable(api, db, world):
    draft = _draft(db, world)
    assert _act(api, world, draft.id, "submit", HR).status_code == 200
    jd_studio.edit_lines(db, _stored(db, draft.id), [{"id": "l1", "text": {"en": "We build APIs"}}], world.hr.id)
    assert _stored(db, draft.id).status == "draft"
    assert _read(api, world, draft, MANAGER).status_code == 200


# --- I-5: writes after an AI call -----------------------------------------------------------------------------------

def _during_assistant(work, world):
    def respond(*_):
        _in_other_session(work)
        return assistant_json([ai_line("l1", [world.role.id], en="Unread text from the assistant", vi="v", ko="k")])
    fake.register("jd_assistant", respond)


def test_an_assistant_call_refuses_when_the_version_moved(api, db, world):
    draft = _draft(db, world)
    draft_id = draft.id

    def edit(session):
        row = session.get(JobDraft, draft_id)
        row.version += 1

    _during_assistant(edit, world)
    response = api.post(_url(world, f"/job-drafts/{draft_id}/assistant"), headers=HR, json={"message": "shorter"})
    assert response.status_code == 409, response.text
    row = _stored(db, draft_id)
    assert row.version == 2 and row.lines[0]["text"]["en"] == "We build the APIs of our hiring platform"


def test_an_approval_during_an_assistant_call_is_not_overwritten(api, db, world):
    draft = _draft(db, world)
    draft_id = draft.id

    def approve(session):
        row = session.get(JobDraft, draft_id)
        row.status = "approved"

    _during_assistant(approve, world)
    response = api.post(_url(world, f"/job-drafts/{draft_id}/assistant"), headers=HR, json={"message": "shorter"})
    assert response.status_code == 409, response.text
    row = _stored(db, draft_id)
    assert row.status == "approved" and row.lines[0]["text"]["en"] == "We build the APIs of our hiring platform"


@pytest.mark.parametrize("call", ["edit", "confirm", "submit"])
def test_a_write_after_lint_refuses_when_the_version_moved(api, db, world, monkeypatch, call):
    draft = _draft(db, world, lines=[*_lines(world), line("l3", [], en="Unsourced", vi="v", ko="k")])
    draft_id = draft.id
    real, fired = lint.evaluate, []

    def hook(*args, **kwargs):
        issues = real(*args, **kwargs)
        if not fired:
            fired.append(True)
            _in_other_session(lambda s: setattr(s.get(JobDraft, draft_id), "version", 7))
        return issues

    monkeypatch.setattr(lint, "evaluate", hook)
    if call == "edit":
        response = api.patch(_url(world, f"/job-drafts/{draft_id}"), headers=HR,
                             json={"lines": [{"id": "l1", "text": {"en": "Other"}}]})
    elif call == "confirm":
        response = _act(api, world, draft_id, "lines/l3/confirm")
    else:
        response = _act(api, world, draft_id, "submit")
    assert response.status_code == 409, response.text
    row = _stored(db, draft_id)
    assert row.version == 7 and row.status == "draft"
    assert row.lines[0]["text"]["en"] == "We build the APIs of our hiring platform"
    assert row.lines[2]["hr_confirmed"] is None


def test_lint_of_an_old_version_does_not_replace_the_newer_lint(db, world, monkeypatch):
    draft = _draft(db, world)
    draft_id = draft.id
    newer = [{"check": "must_have_count", "severity": "warning", "line_id": None, "message": "newer", "node_id": None}]
    real = lint.evaluate

    def hook(*args, **kwargs):
        issues = real(*args, **kwargs)

        def work(session):
            row = session.get(JobDraft, draft_id)
            row.version, row.lint = 2, newer
        _in_other_session(work)
        return issues

    monkeypatch.setattr(lint, "evaluate", hook)
    lint.run(db, draft)
    assert _stored(db, draft_id).lint == newer


def test_an_acknowledgement_does_not_write_back_old_lines(db, world):
    draft = _draft(db, world)
    draft.lint = [{"check": "unchecked", "severity": "block", "line_id": "l1", "message": "x", "node_id": None}]
    db.commit()
    assert draft.lines[0]["text"]["en"] == "We build the APIs of our hiring platform"  # the copy this session holds
    new_lines = [line("l1", [world.role.id], en="Newer text", vi="v", ko="k")]
    draft_id = draft.id

    def work(session):
        session.get(JobDraft, draft_id).lines = new_lines
    _in_other_session(work)

    lint.acknowledge_unchecked(db, draft, world.hr.id)
    row = _stored(db, draft_id)
    assert row.lines[0]["text"]["en"] == "Newer text" and row.lines[0]["unchecked_ack"]


# --- I-6: approval names what was read ------------------------------------------------------------------------------

def test_approve_needs_the_version_the_page_shows(api, db, world):
    draft = _draft(db, world, status="manager_review")
    assert _act(api, world, draft.id, "approve", MANAGER).status_code == 422
    assert _act(api, world, draft.id, "approve", MANAGER, version=draft.version + 1).status_code == 409
    assert _stored(db, draft.id).status == "manager_review"
    assert _act(api, world, draft.id, "approve", MANAGER, version=draft.version).status_code == 200


def test_publish_needs_the_version_the_page_shows(api, db, world):
    draft = _draft(db, world, status="approved")
    assert _act(api, world, draft.id, "publish", HR).status_code == 422
    assert _act(api, world, draft.id, "publish", HR, version=draft.version + 1).status_code == 409
    assert _stored(db, draft.id).status == "approved"
    assert db.query(Job).filter_by(company_id=world.company.id).count() == 0
    lines = _stored(db, draft.id)
    response = _act(api, world, draft.id, "publish", HR, version=lines.version)
    assert response.status_code == 200, response.text


# --- I-7: lint checks every path ------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["Salary 100 million VND", "We build APIs for 7 teams", "Free housing"])
def test_a_manual_edit_with_an_unsupported_claim_blocks_until_hr_confirms(api, db, world, text):
    draft = _draft(db, world)
    patched = api.patch(_url(world, f"/job-drafts/{draft.id}"), headers=HR,
                        json={"lines": [{"id": "l1", "text": {"en": text}}]})
    assert patched.status_code == 200
    body = patched.json()
    assert body["blocks_publish"] is True
    assert [(i["check"], i["line_id"]) for i in body["lint"] if i["severity"] == "block"] == [("no_source", "l1")]
    assert _act(api, world, draft.id, "submit").status_code == 409

    confirmed = _act(api, world, draft.id, "lines/l1/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["blocks_publish"] is False
    assert confirmed.json()["lines"][0]["hr_confirmed"]["user_id"] == world.hr.id
    assert _act(api, world, draft.id, "submit").status_code == 200


# --- I-8: what a change of text voids --------------------------------------------------------------------------------

def test_a_text_change_clears_a_confirmation_and_a_dismissal(db, world):
    draft = _draft(db, world, lines=[
        line("l1", [], en="Salary 20", vi="v", ko="k", hr_confirmed={"user_id": world.hr.id, "at": "x"}),
        line("l2", [world.leave.id], en="12 days of leave", vi="v", ko="k", conflict_dismissed=[world.leave.id]),
    ])
    edited = jd_studio.edit_lines(db, draft, [{"id": "l1", "text": {"en": "Salary 90"}},
                                              {"id": "l2", "text": {"en": "30 days of leave"}}], world.hr.id)
    assert edited.lines[0]["hr_confirmed"] is None
    assert edited.lines[1]["conflict_dismissed"] == []
    assert any(i["check"] == "no_source" and i["line_id"] == "l1" for i in edited.lint)


def test_saving_the_same_text_keeps_a_confirmation_and_a_dismissal(db, world):
    confirmation = {"user_id": world.hr.id, "at": "x"}
    draft = _draft(db, world, lines=[
        line("l1", [], en="Salary 20", vi="v", ko="k", hr_confirmed=confirmation, conflict_dismissed=[world.leave.id]),
    ])
    edited = jd_studio.edit_lines(db, draft, [{"id": "l1", "text": {"en": "Salary 20"}}], world.hr.id)
    assert edited.lines[0]["hr_confirmed"] == confirmation
    assert edited.lines[0]["conflict_dismissed"] == [world.leave.id]


def test_a_restyle_by_the_assistant_clears_a_dismissal(db, world):
    draft = _draft(db, world, lines=[line("l1", [world.leave.id], en="12 days of annual leave", vi="v", ko="k",
                                          conflict_dismissed=[world.leave.id])])
    fake.enqueue("jd_assistant", assistant_json([
        ai_line("l1", [world.leave.id], en="You get 12 days of annual leave", vi="v", ko="k"),
    ]))
    result = jd_studio.revise(db, draft, "friendlier", world.hr.id)
    assert result.draft.lines[0]["conflict_dismissed"] == []


# --- manager feedback ------------------------------------------------------------------------------------------------

def test_the_approver_sends_a_draft_back_with_a_comment(api, db, world):
    draft = _draft(db, world, status="manager_review")
    path = _url(world, f"/job-drafts/{draft.id}/request-changes")
    comment = {"comment": "  The first line undersells the team.  "}

    assert api.post(path, headers=HR, json=comment).status_code == 403
    assert api.post(path, headers=SECOND_MANAGER, json=comment).status_code == 404
    assert api.post(path, headers=MANAGER, json={"comment": "   "}).status_code == 422

    response = api.post(path, headers=MANAGER, json=comment)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft"
    feedback = _read(api, world, draft, HR).json()["manager_feedback"]
    assert [item["comment"] for item in feedback] == ["The first line undersells the team."]
    assert feedback[0]["by"] == world.manager.id and feedback[0]["created_at"]
    assert _read(api, world, draft, MANAGER).status_code == 200
    logged = db.query(AuditLog).filter_by(action="job_draft.changes_requested", target_id=draft.id).one()
    assert logged.actor_user_id == world.manager.id

    assert api.post(path, headers=MANAGER, json=comment).status_code == 409
    assert _act(api, world, draft.id, "submit").status_code == 200
    assert _stored(db, draft.id).status == "manager_review"


def test_a_comment_never_reaches_the_assistant_history(api, db, world):
    draft = _draft(db, world, status="manager_review")
    assert api.post(_url(world, f"/job-drafts/{draft.id}/request-changes"), headers=MANAGER,
                    json={"comment": "CANARY-COMMENT"}).status_code == 200
    db.expire_all()
    assert not jd_studio._history(db, db.get(JobDraft, draft.id))


def test_changes_can_only_be_requested_in_manager_review(api, db, world):
    for status in ("approved", "published"):
        draft = _draft(db, world, status=status)
        response = api.post(_url(world, f"/job-drafts/{draft.id}/request-changes"), headers=MANAGER,
                            json={"comment": "No"})
        assert response.status_code == 409, status


# --- C-3, I-1: interviews ----------------------------------------------------------------------------------------------

def _job_for_request(db, world, request=None, department_id=None, confidential=True):
    job = Job(company_id=world.company.id, title="Backend", slug="backend-x", status="published", version=1,
              interview_languages=["en"], department_id=department_id or world.sales.id)
    db.add(job)
    db.commit()
    if request is not None:
        request.job_id = job.id
    open_req = JobRequirement(company_id=world.company.id, job_id=job.id, text="Builds APIs", must_have=True, position=0)
    secret = JobRequirement(company_id=world.company.id, job_id=job.id, text="CANARY-REQ accepts a pay cut", must_have=True,
                            position=1, visibility="confidential" if confidential else "public")
    db.add_all([open_req, secret])
    db.commit()
    return job, open_req, secret


def _application(db, world, job, open_req, secret):
    user = make_user(db, f"candidate{job.id}@example.test")
    user.full_name = "Candidate Name"
    application = Application(company_id=world.company.id, job_id=job.id, job_version=1, alias="#A1", stage="ready_for_hr",
                              cv_status="meets", candidate_user_id=user.id, hr_decision="approved",
                              cv_text_raw="raw", cv_text_blind="blind")
    db.add(application)
    db.commit()
    session = VoiceSession(company_id=world.company.id, purpose="screening", application_id=application.id,
                           owner_user_id=user.id, language="en", status="completed")
    db.add(session)
    db.commit()
    turn = VoiceTurn(session_id=session.id, position=1, question_text="q", question_source="must_have",
                     transcript=f"{QUOTE_OPEN}. {QUOTE_SECRET}", transcript_status="done", audio_seconds=10)
    db.add(turn)
    db.commit()
    db.add_all([
        RequirementResult(application_id=application.id, requirement_id=open_req.id, source="interview",
                          status="evidence", quote=QUOTE_OPEN, voice_turn_id=turn.id),
        RequirementResult(application_id=application.id, requirement_id=secret.id, source="interview",
                          status="evidence", quote=QUOTE_SECRET, voice_turn_id=turn.id),
    ])
    db.commit()
    return application


def _send_brief(api, world, application):
    path = _url(world, f"/applications/{application.id}/brief")
    created = api.post(path, headers=HR, json={"language": "en"})
    assert created.status_code == 200, created.text
    assert api.patch(path, headers=HR, json={}).status_code == 200
    sent = api.post(f"{path}/send", headers=HR)
    assert sent.status_code == 200, sent.text
    return created.json()


def _world_with_interview(api, db, world):
    request = db.get(HiringRequest, world.request.id)
    job, open_req, secret = _job_for_request(db, world, request)
    application = _application(db, world, job, open_req, secret)
    _send_brief(api, world, application)
    return application, job, open_req, secret


def test_any_member_reads_only_the_requirements_of_their_layer_on_a_job(api, db, world):
    job, _open, _secret = _job_for_request(db, world)
    path = _url(world, f"/jobs/{job.id}")
    for headers, seen in ((EMPLOYEE, False), (MANAGER, False), (SALES_MANAGER, True), (HR, True)):
        response = api.get(path, headers=headers)
        assert response.status_code == 200
        assert ("CANARY-REQ" in response.text) is seen, headers


def test_a_manager_interview_leaves_out_requirements_above_their_layer(api, db, world):
    application, _job, open_req, secret = _world_with_interview(api, db, world)

    response = api.get(_url(world, f"/my-interviews/{application.id}"), headers=MANAGER)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body["requirements"]] == [open_req.id]
    assert "CANARY-REQ" not in response.text
    assert QUOTE_SECRET not in response.text
    # HR keeps the whole brief.
    full = api.get(_url(world, f"/applications/{application.id}/brief"), headers=HR).text
    assert "CANARY-REQ" in full and QUOTE_SECRET in full


def test_the_scorecard_covers_what_the_manager_may_read(api, db, world):
    application, _job, open_req, secret = _world_with_interview(api, db, world)
    path = _url(world, f"/applications/{application.id}/scorecard")
    body = {"recommendation": "hire"}

    both = [{"requirement_id": open_req.id, "score": 4}, {"requirement_id": secret.id, "score": 4}]
    assert api.post(path, headers=MANAGER, json={**body, "scores": both}).status_code == 422
    response = api.post(path, headers=MANAGER, json={**body, "scores": both[:1]})
    assert response.status_code == 200, response.text


def test_a_manager_who_may_read_nothing_still_gives_a_recommendation(api, db, world):
    application, _job, open_req, _secret = _world_with_interview(api, db, world)
    row = db.get(JobRequirement, open_req.id)
    row.visibility = "confidential"
    db.commit()
    path = _url(world, f"/applications/{application.id}/scorecard")
    assert api.post(path, headers=MANAGER, json={"recommendation": "no_hire", "scores": []}).status_code == 200


def test_an_earlier_applicant_is_scored_on_their_own_requirements(api, db, world):
    application, job, open_req, secret = _world_with_interview(api, db, world)
    db.get(JobRequirement, open_req.id).active = False
    newer = JobRequirement(company_id=world.company.id, job_id=job.id, text="Added later", must_have=True, position=2)
    db.add(newer)
    db.commit()

    detail = api.get(_url(world, f"/my-interviews/{application.id}"), headers=MANAGER).json()
    assert [item["id"] for item in detail["requirements"]] == [open_req.id]
    response = api.post(_url(world, f"/applications/{application.id}/scorecard"), headers=MANAGER,
                        json={"recommendation": "hire", "scores": [{"requirement_id": open_req.id, "score": 3}]})
    assert response.status_code == 200, response.text


def test_interviews_of_a_job_from_a_request_go_to_its_assigned_manager(api, db, world):
    application, *_ = _world_with_interview(api, db, world)
    assert api.get(_url(world, f"/my-interviews/{application.id}"), headers=MANAGER).status_code == 200
    # The job sits in Sales, and Sales' manager was not assigned.
    assert api.get(_url(world, f"/my-interviews/{application.id}"), headers=SALES_MANAGER).status_code == 404
    assert api.get(_url(world, "/my-interviews"), headers=SALES_MANAGER).json() == []
    assert [item["application_id"] for item in api.get(_url(world, "/my-interviews"), headers=MANAGER).json()] == [application.id]
    assert {row.user_id for row in db.query(Notification).filter_by(company_id=world.company.id)} == {world.manager.id}


def test_a_second_manager_of_the_department_cannot_open_the_interview(api, db, world):
    request = db.get(HiringRequest, world.request.id)
    job, open_req, secret = _job_for_request(db, world, request, department_id=world.eng.id)
    application = _application(db, world, job, open_req, secret)
    _send_brief(api, world, application)
    assert api.get(_url(world, f"/my-interviews/{application.id}"), headers=SECOND_MANAGER).status_code == 404
    assert db.query(AuditLog).filter_by(action="identity_revealed", actor_user_id=world.second_manager.id).count() == 0


def test_a_job_with_no_request_keeps_its_departments_managers(api, db, world):
    job, open_req, secret = _job_for_request(db, world, department_id=world.eng.id)
    application = _application(db, world, job, open_req, secret)
    _send_brief(api, world, application)
    assert api.get(_url(world, f"/my-interviews/{application.id}"), headers=SECOND_MANAGER).status_code == 200
    assert api.get(_url(world, f"/my-interviews/{application.id}"), headers=SALES_MANAGER).status_code == 404


def test_a_job_from_a_request_with_no_department_reaches_its_manager(api, db, world):
    request = db.get(HiringRequest, world.request.id)
    request.department_id = None
    db.commit()
    job, open_req, secret = _job_for_request(db, world, request)
    db.get(Job, job.id).department_id = None
    db.commit()
    application = _application(db, world, job, open_req, secret)
    _send_brief(api, world, application)
    assert api.get(_url(world, f"/my-interviews/{application.id}"), headers=MANAGER).status_code == 200


# --- I-11, M-3 ---------------------------------------------------------------------------------------------------------

def _during_brief(work):
    def respond(*_):
        _in_other_session(work)
        return json.dumps({"strengths": [], "to_clarify": [], "questions": []})
    fake.register("candidate_brief", respond)


def test_a_brief_sent_during_a_regenerate_stays_as_it_was_sent(api, db, world):
    application, *_ = _world_with_interview(api, db, world)
    row = db.query(CandidateBrief).filter_by(application_id=application.id).one()
    row.status, row.reviewed_by, row.sent_at = "draft", world.hr.id, None
    db.commit()
    content, row_id = dict(row.content), row.id

    def send(session):
        session.get(CandidateBrief, row_id).status = "sent"

    _during_brief(send)
    response = api.post(_url(world, f"/applications/{application.id}/brief"), headers=HR, json={"language": "en"})
    assert response.status_code == 409, response.text
    db.rollback()
    db.expire_all()
    stored = db.get(CandidateBrief, row_id)
    assert (stored.status, stored.reviewed_by) == ("sent", world.hr.id) and stored.content == content


def test_an_application_anonymized_during_a_regenerate_gets_no_brief(api, db, world):
    from datetime import datetime, timezone

    request = db.get(HiringRequest, world.request.id)
    job, open_req, secret = _job_for_request(db, world, request)
    application = _application(db, world, job, open_req, secret)
    application_id = application.id

    def anonymize(session):
        session.get(Application, application_id).anonymized_at = datetime.now(timezone.utc)

    _during_brief(anonymize)
    response = api.post(_url(world, f"/applications/{application_id}/brief"), headers=HR, json={"language": "en"})
    assert response.status_code == 409, response.text
    assert db.query(CandidateBrief).filter_by(application_id=application_id).count() == 0


def test_a_regenerate_that_loses_the_first_insert_updates_the_winner(api, db, world, monkeypatch):
    request = db.get(HiringRequest, world.request.id)
    job, open_req, secret = _job_for_request(db, world, request)
    application = _application(db, world, job, open_req, secret)
    application_id, company_id = application.id, world.company.id

    def other_generate(session):
        session.add(CandidateBrief(company_id=company_id, application_id=application_id, language="en",
                                   content={"strengths": []}, status="draft"))

    _during_brief(other_generate)
    real, calls = brief._lock_brief, []

    def not_seen_once(session, application_arg):
        calls.append(1)
        return None if len(calls) == 1 else real(session, application_arg)

    monkeypatch.setattr(brief, "_lock_brief", not_seen_once)
    response = api.post(_url(world, f"/applications/{application_id}/brief"), headers=HR, json={"language": "en"})
    assert response.status_code == 200, response.text
    assert db.query(CandidateBrief).filter_by(application_id=application_id).count() == 1


def test_send_and_edit_read_the_row_as_it_is_now(db, world, api):
    application, *_ = _world_with_interview(api, db, world)
    row = db.query(CandidateBrief).filter_by(application_id=application.id).one()
    row.status, row.reviewed_by, row.sent_at = "draft", world.hr.id, None
    db.commit()
    row_id = row.id
    assert row.reviewed_by == world.hr.id  # the copy this session holds

    # A regenerate commits in another session: review is gone, and this session's copy still says reviewed.
    def regenerate(session):
        session.get(CandidateBrief, row_id).reviewed_by = None
    _in_other_session(regenerate)

    with pytest.raises(brief.BriefError) as refused:
        brief.send(db, application, row, world.hr.id)
    assert refused.value.status_code == 409
    db.rollback()

    def sent(session):
        session.get(CandidateBrief, row_id).status = "sent"
    _in_other_session(sent)
    db.get(CandidateBrief, row_id)
    with pytest.raises(brief.BriefError):
        brief.edit(db, application, row, world.hr.id)


def test_the_tables_have_their_unique_keys(db):
    engine = db.get_bind()
    columns = {tuple(item["column_names"]) for item in inspect(engine).get_unique_constraints("interview_scorecards")}
    assert ("application_id", "manager_user_id") in columns
    briefs = {tuple(item["column_names"]) for item in inspect(engine).get_unique_constraints("candidate_briefs")}
    assert ("application_id",) in briefs


def test_a_scorecard_that_loses_the_first_insert_updates_the_winner(api, db, world, monkeypatch):
    application, _job, open_req, secret = _world_with_interview(api, db, world)
    path = _url(world, f"/applications/{application.id}/scorecard")
    scores = [{"requirement_id": open_req.id, "score": 4}]
    assert api.post(path, headers=MANAGER, json={"recommendation": "hire", "scores": scores}).status_code == 200

    real, calls = brief._find_scorecard, []

    def not_seen_once(*args, **kwargs):
        calls.append(1)
        return None if len(calls) == 1 else real(*args, **kwargs)

    monkeypatch.setattr(brief, "_find_scorecard", not_seen_once)
    response = api.post(path, headers=MANAGER, json={"recommendation": "no_hire", "scores": scores, "notes": "second"})

    assert response.status_code == 200, response.text
    db.rollback()
    db.expire_all()
    row = db.query(InterviewScorecard).filter_by(application_id=application.id).one()
    assert (row.recommendation, row.notes) == ("no_hire", "second")
    assert len(calls) == 2


# --- publishing helpers ----------------------------------------------------------------------------------------------

def test_manages_follows_the_request_then_the_department(db, world):
    with_request = _draft(db, world)
    without = _draft(db, world, request_id=None)
    member = db.query(CompanyMember).filter_by(user_id=world.second_manager.id).one()
    assert publishing.manages(db, with_request, member) is False
    assert publishing.manages(db, without, member) is True
    assert aud.for_member(db, member).department_ids  # a department manager, whose subtree holds the role
