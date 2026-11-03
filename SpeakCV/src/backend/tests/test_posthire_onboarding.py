"""Onboarding 30-60-90: a consented plan, a checklist for the hire, Copilot access and probation results."""
import json
import re
from types import SimpleNamespace

import pytest

from app.ai.providers import fake
from app.ai.types import AIProviderError
from app.brain import fake_demo
from app.database.sql_models import (
    Application, AuditLog, Company, CompanyMember, Consent, Job, JobRequirement, KbNode, LearningResource,
    OnboardingItem, OnboardingPlan, ProbationOutcome, RequirementResult,
)
from app.hiring import consents, retention
from tests.helpers import auth_header, make_user
from tests.helpers_jd import CANARY, POLICY_CANARY, make_world

HR = auth_header("hr@acme.test")
ENG_MANAGER = auth_header("mgr@acme.test")
SALES_MANAGER = auth_header("mgr2@acme.test")
GAP_TEXT = "Docker in production"
CONFIDENTIAL_GAP = "CANARY-CONFIDENTIAL-GAP-6612"
CV_CANARY = "CANARY-RAW-CV-TEXT-9931"
QUOTE_CANARY = "CANARY-INTERVIEW-QUOTE-4417"


def build(db, hired=True, consent=True, gaps=True):
    world = make_world(db)
    job = Job(company_id=world.company.id, title="Backend Developer", slug="backend", status="published", version=1,
              interview_languages=["en"], department_id=world.eng.id, role_node_id=world.role.id)
    db.add(job)
    db.commit()
    open_gap = JobRequirement(company_id=world.company.id, job_id=job.id, text=GAP_TEXT, must_have=True, position=0)
    secret_gap = JobRequirement(company_id=world.company.id, job_id=job.id, text=CONFIDENTIAL_GAP, must_have=True,
                                position=1, visibility="confidential")
    db.add_all([open_gap, secret_gap])
    candidate = make_user(db, "hire@example.test")
    application = Application(
        company_id=world.company.id, job_id=job.id, job_version=1, alias="#A1", stage="ready_for_hr",
        candidate_user_id=candidate.id, cv_text_raw=CV_CANARY, cv_text_blind=CV_CANARY, cv_status="meets",
        hr_decision="approved", final_outcome="hired" if hired else "not_hired",
    )
    db.add(application)
    db.commit()
    if gaps:
        db.add_all([
            RequirementResult(application_id=application.id, requirement_id=open_gap.id, source="interview",
                              status="none", quote=QUOTE_CANARY),
            RequirementResult(application_id=application.id, requirement_id=secret_gap.id, source="interview",
                              status="none", quote=QUOTE_CANARY),
        ])
    if consent:
        db.add(Consent(user_id=candidate.id, company_id=world.company.id, application_id=application.id,
                       purpose="onboarding_use", text_version=consents.VERSION))
    other_employee = make_user(db, "emp2@example.test")
    db.add(CompanyMember(company_id=world.company.id, user_id=other_employee.id, role="employee",
                         department_id=world.eng.id))
    db.commit()
    resource = LearningResource(company_id=world.company.id, skill_node_id=world.docker.id, title="Docker basics",
                                url="https://learn.example.test/docker", provider="Example", language="en")
    db.add(resource)
    db.commit()
    return SimpleNamespace(
        w=world, job=job, application=application, candidate=candidate, hire=auth_header(candidate.email),
        other_employee=auth_header(other_employee.email), resource=resource, open_gap=open_gap,
    )


def company_url(s, tail):
    return f"/api/companies/{s.w.company.id}{tail}"


def create_url(s):
    return company_url(s, f"/applications/{s.application.id}/onboarding")


def create(client, s, headers=HR):
    return client.post(create_url(s), headers=headers)


def prompt_of(captured):
    return captured["messages"][-1]["content"]


def capturing(captured, items=None):
    """A responder that records the prompt and answers one item per phase from the first context node, unless
    `items` supplies a function building the answer from the context's node and resource ids."""
    def answer(system, messages, schema):
        captured["system"], captured["messages"] = system, messages
        content = messages[-1]["content"]
        nodes = [int(i) for i in re.findall(r"^\[n(\d+)\]", content, re.MULTILINE)]
        resources = [int(i) for i in re.findall(r"^\[r(\d+)\]", content, re.MULTILINE)]
        built = items(nodes, resources) if items else [
            {"phase": phase, "title": f"[Demo AI] step {phase}", "source_node_id": nodes[0], "learning_resource_id": 0}
            for phase in (30, 60, 90)
        ]
        return json.dumps({"items": built})
    fake.register("onboarding_plan", answer)
    return captured


@pytest.fixture(autouse=True)
def demo_ai():
    fake_demo.install()


@pytest.fixture
def s(db):
    return build(db)


# --- 1. only a hire gets a plan --------------------------------------------------------------------------------------

def test_only_a_hired_application_gets_a_plan(client, db):
    s = build(db, hired=False)
    response = create(client, s)
    assert response.status_code == 409
    assert db.query(OnboardingPlan).count() == 0


@pytest.mark.parametrize("outcome", [None, "offer_declined"])
def test_other_outcomes_get_no_plan(client, db, s, outcome):
    s.application.final_outcome = outcome
    db.commit()
    assert create(client, s).status_code == 409


def test_a_simulated_or_foreign_application_is_not_found(client, db, s):
    s.application.is_simulated = True
    db.commit()
    assert create(client, s).status_code == 404
    s.application.is_simulated = False
    s.application.company_id = s.w.other.id
    db.commit()
    assert create(client, s).status_code == 404


def test_only_hr_creates_a_plan(client, s):
    assert create(client, s, ENG_MANAGER).status_code == 403
    assert create(client, s, s.hire).status_code == 403


def test_a_plan_is_built_across_three_phases(client, db, s):
    response = create(client, s)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "draft" and body["application_id"] == s.application.id
    assert [item["phase"] for item in body["items"]] == [30, 60, 90]
    assert all(item["title"].startswith("[Demo AI]") for item in body["items"])
    assert all("done_at" not in item for item in body["items"])
    assert db.query(OnboardingPlan).filter_by(application_id=s.application.id).count() == 1


def test_a_draft_plan_is_rebuilt_in_the_same_row_and_an_approved_one_is_kept(client, db, s):
    first = create(client, s).json()
    second = create(client, s).json()
    assert second["id"] == first["id"]
    db.expire_all()
    assert db.query(OnboardingPlan).count() == 1
    assert db.query(OnboardingItem).count() == 3
    client.post(company_url(s, f"/onboarding/{first['id']}/approve"), headers=HR)
    assert create(client, s).status_code == 409


# --- 2. consent ------------------------------------------------------------------------------------------------------

def test_a_granted_consent_lets_the_gaps_into_the_plan(client, db, s):
    seen = capturing({})
    body = create(client, s).json()
    assert body["used_interview_data"] is True
    assert GAP_TEXT in prompt_of(seen)


@pytest.mark.parametrize("how", ["absent", "withdrawn"])
def test_without_consent_only_the_team_graph_is_used(client, db, how):
    s = build(db, consent=how == "withdrawn")
    if how == "withdrawn":
        consents.withdraw(db, db.query(Consent).filter_by(purpose="onboarding_use").one().id, s.candidate.id)
        db.commit()
    seen = capturing({})
    body = create(client, s).json()
    assert body["used_interview_data"] is False
    assert GAP_TEXT not in prompt_of(seen)
    assert body["items"]


def test_a_consent_for_another_purpose_does_not_count(client, db):
    s = build(db, consent=False)
    db.add(Consent(user_id=s.candidate.id, company_id=s.w.company.id, application_id=s.application.id,
                   purpose="recording_screening", text_version=consents.VERSION))
    db.commit()
    seen = capturing({})
    assert create(client, s).json()["used_interview_data"] is False
    assert GAP_TEXT not in prompt_of(seen)


def test_a_consent_for_another_application_does_not_count(client, db):
    s = build(db, consent=False)
    db.add(Consent(user_id=s.candidate.id, company_id=s.w.company.id, application_id=None,
                   purpose="onboarding_use", text_version=consents.VERSION))
    db.commit()
    assert create(client, s).json()["used_interview_data"] is False


def test_the_candidate_grants_consent_after_being_hired(client, db):
    s = build(db, consent=False)
    url = f"/api/applications/{s.application.id}/onboarding-consent"
    shown = client.get(url, headers=s.hire)
    assert shown.status_code == 200
    assert shown.json()["granted"] is False and shown.json()["version"] == consents.VERSION
    assert shown.json()["text"]
    assert client.post(url, headers=s.hire, json={"version": "1999-01-01"}).status_code == 409
    granted = client.post(url, headers=s.hire, json={"version": consents.VERSION, "language": "en"})
    assert granted.status_code == 200
    assert granted.json()["granted"] is True
    again = client.post(url, headers=s.hire, json={"version": consents.VERSION})
    assert again.json()["consent_id"] == granted.json()["consent_id"]
    assert db.query(Consent).filter_by(purpose="onboarding_use").count() == 1
    assert create(client, s).json()["used_interview_data"] is True


def test_only_the_owner_of_a_hired_application_can_consent(client, db):
    s = build(db, consent=False)
    url = f"/api/applications/{s.application.id}/onboarding-consent"
    body = {"version": consents.VERSION}
    assert client.post(url, headers=s.other_employee, json=body).status_code == 404
    assert client.post(url, headers=HR, json=body).status_code == 404
    s.application.final_outcome = "not_hired"
    db.commit()
    assert client.post(url, headers=s.hire, json=body).status_code == 409


def test_consent_withdrawal_works_through_the_existing_route_and_the_next_plan_ignores_the_gaps(client, db, s):
    consent = db.query(Consent).filter_by(purpose="onboarding_use").one()
    assert client.post(f"/api/me/consents/{consent.id}/withdraw", headers=s.hire).status_code in (200, 204)
    assert create(client, s).json()["used_interview_data"] is False


def test_the_consent_text_exists_in_english_and_vietnamese():
    assert "onboarding_use" in consents.PURPOSES
    assert consents.current_text("onboarding_use", "en").text
    assert consents.current_text("onboarding_use", "vi").text != consents.current_text("onboarding_use", "en").text


# --- 3. evidence gone ------------------------------------------------------------------------------------------------

def test_after_retention_the_plan_uses_only_the_team_graph_with_no_error(client, db, s):
    retention.anonymize_application(db, s.application)
    seen = capturing({})
    response = create(client, s)
    assert response.status_code == 200, response.text
    assert response.json()["used_interview_data"] is False
    assert GAP_TEXT not in prompt_of(seen)
    assert response.json()["items"]


def test_missing_results_alone_mean_the_team_graph_only(client, db, s):
    db.query(RequirementResult).delete()
    db.commit()
    body = create(client, s).json()
    assert body["used_interview_data"] is False


def test_a_consent_withdrawn_during_the_ai_call_discards_the_plan(client, db, s):
    consent_id = db.query(Consent).filter_by(purpose="onboarding_use").one().id

    def withdraw_meanwhile(_system, messages, _schema):
        from app.database.database import SessionLocal
        other = SessionLocal()
        consents.withdraw(other, consent_id, s.candidate.id)
        other.commit()
        other.close()
        node = int(re.search(r"^\[n(\d+)\]", messages[-1]["content"], re.MULTILINE).group(1))
        return json.dumps({"items": [{"phase": 30, "title": "x", "source_node_id": node, "learning_resource_id": 0}]})

    fake.register("onboarding_plan", withdraw_meanwhile)
    assert create(client, s).status_code == 409
    db.expire_all()
    assert db.query(OnboardingPlan).count() == 0


# --- 4. references are checked by code -------------------------------------------------------------------------------

def test_every_item_points_at_a_real_employee_node_or_a_catalogue_resource(client, db, s):
    capturing({}, lambda nodes, resources: [
        {"phase": 30, "title": "Read the remote policy", "source_node_id": s.w.internal.id, "learning_resource_id": 0},
        {"phase": 60, "title": "Docker course", "source_node_id": 0, "learning_resource_id": s.resource.id},
        {"phase": 90, "title": "Own an API", "source_node_id": s.w.python.id, "learning_resource_id": 0},
    ])
    body = create(client, s).json()
    assert [item["phase"] for item in body["items"]] == [30, 60, 90]
    assert body["items"][0]["source_node_id"] == s.w.internal.id
    assert body["items"][1]["learning_resource"] == {
        "id": s.resource.id, "title": "Docker basics", "url": "https://learn.example.test/docker",
        "provider": "Example"}
    for item in body["items"]:
        assert item["source_node_id"] or item["learning_resource"]


def test_items_citing_unknown_or_confidential_ids_are_dropped_by_code(client, db, s):
    foreign_node = KbNode(company_id=s.w.other.id, type="policy", title="Foreign", body="x", language="en",
                          visibility="public", status="published")
    draft_node = KbNode(company_id=s.w.company.id, type="policy", title="Draft", body="x", language="en",
                        visibility="public", status="draft")
    db.add_all([foreign_node, draft_node])
    db.commit()
    hidden_skill = s.w.builder.node("Secret skill", "x", type="skill", visibility="confidential",
                                    department_id=s.w.eng.id)
    foreign_resource = LearningResource(company_id=s.w.other.id, skill_node_id=foreign_node.id, title="Foreign",
                                        url="https://x.test", provider="", language="en")
    hidden_resource = LearningResource(company_id=s.w.company.id, skill_node_id=hidden_skill.id, title="Hidden",
                                       url="https://y.test", provider="", language="en")
    db.add_all([foreign_resource, hidden_resource])
    db.commit()

    def bad(nodes, resources):
        good = {"phase": 30, "title": "Keep me", "source_node_id": nodes[0], "learning_resource_id": 0}
        return [
            good,
            {"phase": 60, "title": "confidential node", "source_node_id": s.w.note.id, "learning_resource_id": 0},
            {"phase": 60, "title": "unknown node", "source_node_id": 999999, "learning_resource_id": 0},
            {"phase": 60, "title": "foreign node", "source_node_id": foreign_node.id, "learning_resource_id": 0},
            {"phase": 60, "title": "draft node", "source_node_id": draft_node.id, "learning_resource_id": 0},
            {"phase": 90, "title": "unknown course", "source_node_id": 0, "learning_resource_id": 999999},
            {"phase": 90, "title": "foreign course", "source_node_id": 0, "learning_resource_id": foreign_resource.id},
            {"phase": 90, "title": "hidden course", "source_node_id": 0, "learning_resource_id": hidden_resource.id},
            {"phase": 90, "title": "no reference", "source_node_id": 0, "learning_resource_id": 0},
            {"phase": 45, "title": "bad phase", "source_node_id": nodes[0], "learning_resource_id": 0},
            {"phase": 90, "title": "   ", "source_node_id": nodes[0], "learning_resource_id": 0},
        ]

    capturing({}, bad)
    body = create(client, s).json()
    assert [item["title"] for item in body["items"]] == ["Keep me"]
    assert db.query(OnboardingItem).count() == 1


def test_a_plan_with_nothing_usable_is_refused_and_saves_nothing(client, db, s):
    capturing({}, lambda nodes, resources: [
        {"phase": 30, "title": "x", "source_node_id": 999999, "learning_resource_id": 0}])
    response = create(client, s)
    assert response.status_code == 422
    assert db.query(OnboardingPlan).count() == 0


def test_with_no_team_knowledge_the_ai_is_not_asked(client, db, s):
    db.query(KbNode).update({"status": "draft"})
    db.commit()
    seen = capturing({})
    assert create(client, s).status_code == 422
    assert "messages" not in seen
    assert db.query(OnboardingPlan).count() == 0


# --- 5. nothing confidential reaches the prompt ----------------------------------------------------------------------

def test_the_prompt_holds_no_confidential_text(client, db, s):
    seen = capturing({})
    assert create(client, s).status_code == 200
    prompt = prompt_of(seen) + seen["system"]
    for canary in (CANARY, CONFIDENTIAL_GAP, CV_CANARY, QUOTE_CANARY, "Pay note", s.candidate.email):
        assert canary not in prompt
    assert POLICY_CANARY in prompt  # internal text is for employees, so it may be there
    assert "skill" in seen["system"].lower()


# --- 6. AI failure ---------------------------------------------------------------------------------------------------

def test_an_ai_failure_gives_503_with_no_partial_plan_and_hr_can_retry(client, db, s):
    def down(_system, _messages, _schema):
        raise AIProviderError("down")
    fake.register("onboarding_plan", down)
    response = create(client, s)
    assert response.status_code == 503
    db.expire_all()
    assert db.query(OnboardingPlan).count() == 0
    assert db.query(OnboardingItem).count() == 0
    fake_demo.install()
    retry = create(client, s)
    assert retry.status_code == 200
    assert db.query(OnboardingPlan).count() == 1


# --- 7. edit and approve ---------------------------------------------------------------------------------------------

def test_manager_and_hr_edit_the_draft(client, db, s):
    plan = create(client, s).json()
    url = company_url(s, f"/onboarding/{plan['id']}")
    first = plan["items"][0]
    response = client.patch(url, headers=ENG_MANAGER, json={"items": [
        {"id": first["id"], "title": "Shadow a senior engineer"},
        {"id": plan["items"][1]["id"], "remove": True},
    ], "add": [{"phase": 90, "title": "Lead a review", "source_node_id": s.w.python.id}]})
    assert response.status_code == 200, response.text
    titles = {item["title"] for item in response.json()["items"]}
    assert "Shadow a senior engineer" in titles and "Lead a review" in titles
    assert len(response.json()["items"]) == 3
    assert client.patch(url, headers=HR, json={"items": [{"id": first["id"], "phase": 60}]}).status_code == 200


def test_edits_are_checked_like_generated_items(client, s):
    plan = create(client, s).json()
    url = company_url(s, f"/onboarding/{plan['id']}")
    for added in ({"phase": 30, "title": "x", "source_node_id": s.w.note.id},
                  {"phase": 30, "title": "x"},
                  {"phase": 45, "title": "x", "source_node_id": s.w.python.id},
                  {"phase": 30, "title": "x", "learning_resource_id": 999999}):
        assert client.patch(url, headers=HR, json={"add": [added]}).status_code == 422
    assert client.patch(url, headers=HR, json={"items": [{"id": 999999, "title": "x"}]}).status_code == 404
    assert client.patch(url, headers=HR, json={"items": [{"id": plan["items"][0]["id"], "phase": 45}]}).status_code == 422


def test_an_employee_cannot_edit_or_read_a_draft_plan(client, s):
    plan = create(client, s).json()
    url = company_url(s, f"/onboarding/{plan['id']}")
    assert client.patch(url, headers=s.other_employee, json={"add": []}).status_code == 403
    assert client.get(url, headers=s.other_employee).status_code == 403
    assert client.post(url + "/approve", headers=s.other_employee).status_code == 403


def test_a_manager_of_another_department_cannot_reach_the_plan(client, s):
    plan = create(client, s).json()
    url = company_url(s, f"/onboarding/{plan['id']}")
    assert client.get(url, headers=SALES_MANAGER).status_code == 404
    assert client.patch(url, headers=SALES_MANAGER, json={}).status_code == 404
    assert client.post(url + "/approve", headers=SALES_MANAGER).status_code == 404
    assert client.get(url, headers=ENG_MANAGER).status_code == 200


def test_approving_activates_the_plan_and_makes_the_hire_an_employee(client, db, s):
    plan = create(client, s).json()
    response = client.post(company_url(s, f"/onboarding/{plan['id']}/approve"), headers=ENG_MANAGER)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"
    db.expire_all()
    stored = db.get(OnboardingPlan, plan["id"])
    assert stored.status == "active" and stored.approved_by == s.w.manager.id
    assert stored.employee_user_id == s.candidate.id
    member = db.query(CompanyMember).filter_by(company_id=s.w.company.id, user_id=s.candidate.id).one()
    assert (member.role, member.department_id) == ("employee", s.w.eng.id)
    assert {row.owner_user_id for row in db.query(OnboardingItem).filter_by(plan_id=plan["id"])} == {s.candidate.id}
    assert db.query(AuditLog).filter_by(action="onboarding.approved").count() == 1


def test_approving_twice_or_after_editing_is_refused_and_creates_no_second_membership(client, db, s):
    plan = create(client, s).json()
    url = company_url(s, f"/onboarding/{plan['id']}")
    assert client.post(url + "/approve", headers=HR).status_code == 200
    assert client.post(url + "/approve", headers=HR).status_code == 409
    assert client.patch(url, headers=HR, json={"items": [{"id": plan["items"][0]["id"], "title": "x"}]}).status_code == 409
    assert db.query(CompanyMember).filter_by(user_id=s.candidate.id).count() == 1


@pytest.mark.parametrize("role", ["hr", "manager", "employee"])
def test_an_existing_membership_is_kept_and_not_duplicated(client, db, s, role):
    db.add(CompanyMember(company_id=s.w.company.id, user_id=s.candidate.id, role=role,
                         department_id=s.w.sales.id if role != "hr" else None))
    db.commit()
    plan = create(client, s).json()
    assert client.post(company_url(s, f"/onboarding/{plan['id']}/approve"), headers=HR).status_code == 200
    db.expire_all()
    rows = db.query(CompanyMember).filter_by(company_id=s.w.company.id, user_id=s.candidate.id).all()
    assert len(rows) == 1 and rows[0].role == role


def test_a_hire_whose_account_is_gone_cannot_be_approved(client, db, s):
    retention.anonymize_application(db, s.application)
    plan = create(client, s).json()
    response = client.post(company_url(s, f"/onboarding/{plan['id']}/approve"), headers=HR)
    assert response.status_code == 409
    db.expire_all()
    assert db.get(OnboardingPlan, plan["id"]).status == "draft"


# --- 8. the hire's checklist -----------------------------------------------------------------------------------------

def approved(client, s):
    plan = create(client, s).json()
    assert client.post(company_url(s, f"/onboarding/{plan['id']}/approve"), headers=HR).status_code == 200
    return plan


def test_the_hire_sees_the_checklist_and_marks_items_done(client, db, s):
    plan = approved(client, s)
    mine = client.get(company_url(s, "/my-onboarding"), headers=s.hire)
    assert mine.status_code == 200, mine.text
    plans = mine.json()
    assert len(plans) == 1 and plans[0]["id"] == plan["id"] and plans[0]["status"] == "active"
    assert [item["phase"] for item in plans[0]["items"]] == [30, 60, 90]
    assert "approved_by" not in plans[0] and "used_interview_data" not in plans[0]
    item_id = plans[0]["items"][0]["id"]
    done = client.post(company_url(s, f"/onboarding/items/{item_id}/done"), headers=s.hire)
    assert done.status_code == 200 and done.json()["done_at"]
    first_time = done.json()["done_at"]
    again = client.post(company_url(s, f"/onboarding/items/{item_id}/done"), headers=s.hire)
    assert again.json()["done_at"] == first_time
    refreshed = client.get(company_url(s, "/my-onboarding"), headers=s.hire).json()[0]
    assert [bool(item["done_at"]) for item in refreshed["items"]] == [True, False, False]


def test_ticks_stay_private_to_the_hire(client, db, s):
    plan = approved(client, s)
    for item in client.get(company_url(s, "/my-onboarding"), headers=s.hire).json()[0]["items"]:
        assert client.post(company_url(s, f"/onboarding/items/{item['id']}/done"), headers=s.hire).status_code == 200
    mine = client.get(company_url(s, "/my-onboarding"), headers=s.hire).json()[0]
    assert all(item["done_at"] for item in mine["items"]) and mine["status"] == "active"
    for headers in (HR, ENG_MANAGER):
        shown = client.get(company_url(s, f"/onboarding/{plan['id']}"), headers=headers)
        assert shown.status_code == 200 and "done_at" not in shown.text
        assert shown.json()["status"] == "active"
    assert db.get(OnboardingPlan, plan["id"]).status == "active"


def test_the_hire_can_ask_the_policy_copilot(client, s):
    approved(client, s)
    response = client.post(company_url(s, "/copilot/ask"), headers=s.hire, json={"question": "How much annual leave?"})
    assert response.status_code == 200, response.text
    assert CANARY not in response.text  # the employee layer, so no confidential text


def test_another_employee_gets_404_for_items_that_are_not_theirs(client, db, s):
    approved(client, s)
    item_id = db.query(OnboardingItem).first().id
    assert client.post(company_url(s, f"/onboarding/items/{item_id}/done"), headers=s.other_employee).status_code == 404
    assert client.post(company_url(s, "/onboarding/items/999999/done"), headers=s.hire).status_code == 404
    db.expire_all()
    assert db.get(OnboardingItem, item_id).done_at is None
    assert client.get(company_url(s, "/my-onboarding"), headers=s.other_employee).json() == []


def test_hr_and_managers_cannot_tick_an_employees_items(client, db, s):
    approved(client, s)
    item_id = db.query(OnboardingItem).first().id
    for headers in (HR, ENG_MANAGER):
        assert client.post(company_url(s, f"/onboarding/items/{item_id}/done"), headers=headers).status_code == 404


def test_an_item_whose_node_left_the_employee_audience_shows_no_title(client, db, s):
    capturing({}, lambda nodes, resources: [
        {"phase": 30, "title": "Read it", "source_node_id": s.w.internal.id, "learning_resource_id": 0}])
    plan = create(client, s).json()
    client.post(company_url(s, f"/onboarding/{plan['id']}/approve"), headers=HR)
    s.w.internal.visibility = "confidential"
    s.w.internal.department_id = s.w.sales.id
    db.commit()
    item = client.get(company_url(s, "/my-onboarding"), headers=s.hire).json()[0]["items"][0]
    assert item["source_title"] is None


# --- 9. probation ----------------------------------------------------------------------------------------------------

def probation_url(s):
    return company_url(s, f"/applications/{s.application.id}/probation")


def test_the_departments_manager_records_probation_and_it_stays_one_row(client, db, s):
    first = client.post(probation_url(s), headers=ENG_MANAGER, json={"result": "extended"})
    assert first.status_code == 200, first.text
    assert first.json()["result"] == "extended"
    second = client.post(probation_url(s), headers=ENG_MANAGER, json={"result": "passed"})
    assert second.status_code == 200
    db.expire_all()
    rows = db.query(ProbationOutcome).filter_by(application_id=s.application.id).all()
    assert len(rows) == 1 and rows[0].result == "passed" and rows[0].recorded_by == s.w.manager.id
    assert rows[0].company_id == s.w.company.id and rows[0].recorded_at is not None
    assert db.query(AuditLog).filter_by(action="probation.recorded").count() == 2


def test_probation_results_are_limited(client, db, s):
    assert client.post(probation_url(s), headers=ENG_MANAGER, json={"result": "promoted"}).status_code == 422
    assert client.post(probation_url(s), headers=ENG_MANAGER, json={}).status_code == 422
    assert db.query(ProbationOutcome).count() == 0


def test_another_departments_manager_gets_403(client, db, s):
    assert client.post(probation_url(s), headers=SALES_MANAGER, json={"result": "passed"}).status_code == 403
    assert db.query(ProbationOutcome).count() == 0


def test_employees_and_outsiders_cannot_record_probation(client, db, s):
    assert client.post(probation_url(s), headers=s.other_employee, json={"result": "passed"}).status_code == 403
    assert client.post(probation_url(s), headers=auth_header("hr@other.test"), json={"result": "passed"}).status_code == 403


def test_probation_needs_a_hire_and_a_real_application(client, db, s):
    s.application.final_outcome = "not_hired"
    db.commit()
    assert client.post(probation_url(s), headers=ENG_MANAGER, json={"result": "passed"}).status_code == 409
    s.application.final_outcome = "hired"
    s.application.is_simulated = True
    db.commit()
    assert client.post(probation_url(s), headers=ENG_MANAGER, json={"result": "passed"}).status_code == 404


def test_hr_may_record_probation_too(client, s):
    assert client.post(probation_url(s), headers=HR, json={"result": "failed"}).status_code == 200


def test_the_result_is_what_reality_check_reads(client, db, s):
    client.post(probation_url(s), headers=ENG_MANAGER, json={"result": "passed"})
    row = db.query(ProbationOutcome).one()
    assert (row.application_id, row.result) == (s.application.id, "passed")


# --- 10. no attrition prediction, no monitoring -----------------------------------------------------------------------

FORBIDDEN = ("attrition", "churn", "risk", "predict", "likelihood", "flight", "score", "sentiment", "activity",
             "login", "keystroke", "monitor", "track", "engagement", "last_seen", "duration", "clicks")


def test_the_models_hold_no_attrition_or_monitoring_fields():
    for model in (OnboardingPlan, OnboardingItem, ProbationOutcome):
        for column in model.__table__.columns:
            assert not any(word in column.name for word in FORBIDDEN), (model.__tablename__, column.name)
    assert {c.name for c in OnboardingItem.__table__.columns} == {
        "id", "plan_id", "phase", "title", "source_node_id", "learning_resource_id", "owner_user_id", "done_at"}
    assert {c.name for c in OnboardingPlan.__table__.columns} == {
        "id", "company_id", "application_id", "employee_user_id", "used_interview_data", "status", "approved_by"}


def test_tracking_stores_only_done_at(client, db, s):
    approved(client, s)
    item = db.query(OnboardingItem).first()
    before = {c.name: getattr(item, c.name) for c in OnboardingItem.__table__.columns if c.name != "done_at"}
    client.get(company_url(s, "/my-onboarding"), headers=s.hire)
    client.post(company_url(s, f"/onboarding/items/{item.id}/done"), headers=s.hire)
    db.expire_all()
    after = db.get(OnboardingItem, item.id)
    assert {c.name: getattr(after, c.name) for c in OnboardingItem.__table__.columns if c.name != "done_at"} == before
    assert after.done_at is not None
    assert db.query(AuditLog).filter(AuditLog.action.like("onboarding.item%")).count() == 0


def test_no_route_predicts_or_monitors(app):
    from tests.helpers import iter_routes, route_path
    paths = [route_path(route) for route in iter_routes(app) if "onboarding" in route_path(route)]
    assert paths
    assert not any(word in path for path in paths for word in ("attrition", "risk", "monitor", "activity", "track"))


# --- 11. nothing before approval -------------------------------------------------------------------------------------

def test_the_hire_cannot_see_the_plan_before_approval(client, db, s):
    plan = create(client, s).json()
    # Not a member yet: the company routes refuse.
    assert client.get(company_url(s, "/my-onboarding"), headers=s.hire).status_code == 403
    assert client.get(company_url(s, f"/onboarding/{plan['id']}"), headers=s.hire).status_code == 403
    # Already an employee for another reason: the draft is still not theirs to see.
    db.add(CompanyMember(company_id=s.w.company.id, user_id=s.candidate.id, role="employee"))
    db.commit()
    assert client.get(company_url(s, "/my-onboarding"), headers=s.hire).json() == []
    item_id = plan["items"][0]["id"]
    assert client.post(company_url(s, f"/onboarding/items/{item_id}/done"), headers=s.hire).status_code == 404
    db.expire_all()
    assert db.get(OnboardingItem, item_id).done_at is None


def test_hr_reads_the_plan(client, s):
    plan = create(client, s).json()
    read = client.get(company_url(s, f"/onboarding/{plan['id']}"), headers=HR)
    assert read.status_code == 200 and read.json()["id"] == plan["id"]
    assert read.json()["used_interview_data"] is True
    assert client.get(company_url(s, "/onboarding/999999"), headers=HR).status_code == 404
    assert client.get(company_url(s, f"/onboarding/{plan['id']}"), headers=auth_header("hr@other.test")).status_code == 403


# --- 11. what the pages need ------------------------------------------------------------------------------------------

def test_the_plan_names_the_alias_the_job_and_the_probation_result(client, s):
    plan = create(client, s).json()
    assert (plan["alias"], plan["job_title"], plan["probation_result"]) == ("#A1", "Backend Developer", None)
    client.post(probation_url(s), headers=ENG_MANAGER, json={"result": "extended"})
    shown = client.get(company_url(s, f"/onboarding/{plan['id']}"), headers=ENG_MANAGER).json()
    assert shown["probation_result"] == "extended"


def test_the_board_and_the_managers_list_point_at_the_plan(client, db, s):
    from app.database.sql_models import CandidateBrief

    board_url = company_url(s, f"/applications/{s.application.id}")
    assert client.get(board_url, headers=HR).json()["onboarding_plan_id"] is None
    plan = create(client, s).json()
    assert client.get(board_url, headers=HR).json()["onboarding_plan_id"] == plan["id"]
    db.add(CandidateBrief(company_id=s.w.company.id, application_id=s.application.id, language="en", status="sent"))
    db.commit()
    listed = client.get(company_url(s, "/my-interviews"), headers=ENG_MANAGER).json()
    assert [row["onboarding_plan_id"] for row in listed] == [plan["id"]]


def test_the_consent_text_says_which_language_it_is_in(client, db):
    s = build(db, consent=False)
    url = f"/api/applications/{s.application.id}/onboarding-consent"
    assert client.get(url + "?language=ko", headers=s.hire).json()["language"] == "en"
    assert client.get(url + "?language=vi", headers=s.hire).json()["language"] == "vi"


def test_a_manager_opens_a_plan_only_by_the_request_rule(client, db):
    from app.database.sql_models import CandidateBrief

    s = build(db)
    s.w.request.job_id = s.job.id
    s.w.request.manager_user_id = s.w.other_manager.id  # the request is assigned to the sales manager
    db.add(CandidateBrief(company_id=s.w.company.id, application_id=s.application.id, language="en", status="sent"))
    db.commit()
    plan = create(client, s).json()
    url = company_url(s, f"/onboarding/{plan['id']}")
    probation = company_url(s, f"/applications/{s.application.id}/probation")
    # The department manager is not assigned: no link, no plan, no probation.
    assert client.get(company_url(s, "/my-interviews"), headers=ENG_MANAGER).json() == []
    assert client.get(url, headers=ENG_MANAGER).status_code == 404
    assert client.post(probation, headers=ENG_MANAGER, json={"result": "failed"}).status_code in (403, 404)
    # The assigned manager gets the link, and it opens.
    listed = client.get(company_url(s, "/my-interviews"), headers=SALES_MANAGER).json()
    assert [row["onboarding_plan_id"] for row in listed] == [plan["id"]]
    assert client.get(url, headers=SALES_MANAGER).status_code == 200
    assert client.post(probation, headers=SALES_MANAGER, json={"result": "passed"}).status_code == 200
