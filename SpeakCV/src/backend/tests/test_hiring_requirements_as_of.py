"""An application reads the requirements it was assessed on, whatever the job has become since."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.ai.providers import fake
from app.brain import audience
from app.bridges import brief
from app.database.database import engine
from app.ai.config import get_config
from app.database.sql_models import (
    Application, CompanyMember, Department, Job, JobRequirement, RequirementResult, ScreeningCache,
)
from app.hiring import analysis, board, fairness, jobs, planner, screening
from app.main import create_app
from tests.helpers import auth_header, make_user
from tests.helpers_board import CANDIDATE_EMAIL, CONFIDENTIAL, make_application, make_session, make_world

CANDIDATE = auth_header(CANDIDATE_EMAIL)
EDITED = "FastAPI experience."
OMITTED = [("en", "does not mention"), ("vi", "chưa nhắc đến"), ("ko", "언급이 없습니다")]


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def api():
    return TestClient(create_app())


def _job_url(world, tail=""):
    return f"/api/companies/{world['company'].id}/jobs/{world['job'].id}{tail}"


def _hr(world):
    return world["people"]["hr"]["headers"]


def _fresh(db, application_id):
    db.rollback()
    db.expire_all()
    return db.get(Application, application_id)


def _assessed(db, world, statuses=("met", "met", "not_found", "met"), stage="invited"):
    application = make_application(db, world["job"], stage=stage, cv_status="meets")
    for requirement, status in zip(world["requirements"], statuses):
        db.add(RequirementResult(application_id=application.id, requirement_id=requirement.id, source="cv", status=status,
                                 quote="Built a FastAPI service" if status == "met" else None))
    db.commit()
    return application


def _edit(api, world, *added):
    """HR fixes a typo in the first requirement. The job's rows change, as they do on the real route."""
    rows = [
        {"text": EDITED, "must_have": True},
        {"text": "Docker in production", "must_have": True},
        {"text": "Kubernetes", "must_have": False},
        {"text": CONFIDENTIAL, "must_have": True, "visibility": "confidential"},
        *added,
    ]
    response = api.patch(_job_url(world), json={"requirements": rows}, headers=_hr(world))
    assert response.status_code == 200, response.text


def _fit(api, application):
    response = api.get(f"/api/applications/{application.id}/fit", headers=CANDIDATE)
    assert response.status_code == 200, response.text
    return response.json()["requirements"]


def _detail(api, world, application):
    response = api.get(f"/api/companies/{world['company'].id}/applications/{application.id}", headers=_hr(world))
    assert response.status_code == 200, response.text
    return response.json()["requirements"]


# I-1


def test_a_typo_edit_changes_nothing_on_the_fit_page_of_an_earlier_applicant(db, world, api):
    application = _assessed(db, world)
    before = _fit(api, application)
    _edit(api, world)
    after = _fit(api, application)
    assert after == before
    assert after[0]["text"] == "FastAPI experience" and after[0]["fit"] == "matches"


def test_a_typo_edit_changes_nothing_on_the_hr_detail_of_an_earlier_applicant(db, world, api):
    application = _assessed(db, world, stage="ready_for_hr")
    before = _detail(api, world, application)
    _edit(api, world)
    after = _detail(api, world, application)
    assert after == before
    assert after[0]["text"] == "FastAPI experience" and after[0]["cv"]["status"] == "met"


def test_a_typo_edit_does_not_make_the_planner_ask_about_what_the_cv_shows(db, world, api):
    application = _assessed(db, world)
    _edit(api, world)
    selected = planner._select(db, application, world["job"], planner.TEMPLATES["en"])
    assert not [item for item in selected if item.source == "requirement"]


def test_a_later_applicant_sees_the_new_text(db, world, api):
    earlier = _assessed(db, world)
    _edit(api, world)
    later = make_application(db, world["job"], "#A2", stage="invited", cv_status=None)
    assert EDITED in [row["text"] for row in _later_fit(api, later)]
    texts = [row.text for row in jobs.requirements_for(db, later)]
    assert EDITED in texts and "FastAPI experience" not in texts
    assert "FastAPI experience" in [row.text for row in jobs.requirements_for(db, earlier)]


def _later_fit(api, later):
    email = f"cand{later.alias[2:]}-{later.job_id}@example.test"
    response = api.get(f"/api/applications/{later.id}/fit", headers=auth_header(email))
    assert response.status_code == 200, response.text
    return response.json()["requirements"]


def test_a_requirement_added_later_is_not_part_of_an_earlier_application(db, world, api):
    application = _assessed(db, world)
    _edit(api, world, {"text": "Rust", "must_have": True})
    assert "Rust" not in [row["text"] for row in _fit(api, application)]
    assert "Rust" not in [row.text for row in jobs.requirements_for(db, application)]


def test_the_helper_reads_rows_named_by_interview_results_too(db, world):
    application = make_application(db, world["job"], stage="ready_for_hr")
    only = world["requirements"][1]
    db.add(RequirementResult(application_id=application.id, requirement_id=only.id, source="interview", status="evidence"))
    db.commit()
    assert [row.id for row in jobs.requirements_for(db, application)] == [only.id]


def test_analysis_and_its_band_use_the_list_the_label_used(db, world, api):
    application = _assessed(db, world, stage="session_completed")
    make_session(db, application, [(1, "Q", "I built a FastAPI service for three years and Docker in production", None)])
    old_first, old_second = world["requirements"][0].id, world["requirements"][1].id
    _edit(api, world)

    prompts = []

    def answer(_system, messages, _schema):
        prompts.append(messages[-1]["content"])
        return json.dumps({
            "requirements": [
                {"requirement_id": old_first, "status": "evidence", "quote": "built a FastAPI service", "position": 1},
                {"requirement_id": old_second, "status": "evidence", "quote": "Docker in production", "position": 1},
            ],
            "claims": [], "culture_notes": [], "suggestion": "Fine.",
        })

    fake.register("session_analysis", answer)
    analysis.run(application.id)

    row = _fresh(db, application.id)
    assert row.analysis_status == "done" and row.interview_band == "many"
    assert f"id={old_first}: FastAPI experience" in prompts[0] and EDITED not in prompts[0]
    interview = {r.requirement_id for r in db.query(RequirementResult).filter_by(application_id=application.id, source="interview")}
    assert interview == {old_first, old_second}
    assert board.detail(db, row)["requirements"][0]["interview"]["status"] == "evidence"


def test_requirement_results_keep_their_shape():
    """Block 5's Reality Check reads these rows."""
    assert {column.name for column in RequirementResult.__table__.columns} == {
        "id", "application_id", "requirement_id", "source", "status", "quote", "voice_turn_id",
    }


def test_the_brief_keeps_the_evidence_of_an_earlier_applicant(db, world, api):
    application = _assessed(db, world, stage="ready_for_hr")
    _edit(api, world)
    labels = [item["label"] for item in brief.collect_evidence(db, application) if item["kind"] == "requirement"]
    assert "FastAPI experience" in labels and EDITED not in labels


def test_the_fairness_check_still_compares_the_results_of_the_version_this_application_was_assessed_on(db, world, api):
    """It reads no requirement list: its cache key carries application.job_version, which a later edit does not move."""
    application = _assessed(db, world)
    assert application.job_version == 1
    common = {"job_id": world["job"].id, "job_version": 1, "prompt_version": screening.PROMPT_VERSION,
              "model": get_config().slot("bulk").model, "result": {"requirements": [], "claims": []}}
    db.add_all([ScreeningCache(blind_hash="a", **common), ScreeningCache(blind_hash="b", **common)])
    db.commit()
    _edit(api, world)
    row = _fresh(db, application.id)
    assert db.get(Job, row.job_id).version == 2 and row.job_version == 1
    assert fairness._same_result(db, row, "a", "b") is True


# I-9


def _member(db, world, email, role, department_id=None):
    user = make_user(db, email)
    db.add(CompanyMember(company_id=world["company"].id, user_id=user.id, role=role, department_id=department_id))
    db.commit()
    return auth_header(email)


@pytest.fixture
def layered(db, world):
    """A job in Engineering, with one requirement in each layer."""
    engineering = Department(company_id=world["company"].id, name="Engineering")
    sales = Department(company_id=world["company"].id, name="Sales")
    db.add_all([engineering, sales])
    db.commit()
    world["job"].department_id = engineering.id
    db.add(JobRequirement(company_id=world["company"].id, job_id=world["job"].id, text="INTERNAL-ROW", must_have=False,
                          position=4, visibility="internal"))
    db.commit()
    return {"engineering": engineering.id, "sales": sales.id}


def _texts(api, world, headers):
    response = api.get(_job_url(world), headers=headers)
    assert response.status_code == 200, response.text
    return {row["text"] for row in response.json()["requirements"]}


def test_an_employee_reads_no_confidential_requirement_of_a_job(world, api, layered):
    texts = _texts(api, world, world["people"]["emp"]["headers"])
    assert CONFIDENTIAL not in texts and {"FastAPI experience", "INTERNAL-ROW"} <= texts


def test_a_manager_reads_confidential_requirements_only_for_their_own_department(db, world, api, layered):
    inside = _member(db, world, "inside@example.test", "manager", layered["engineering"])
    outside = _member(db, world, "outside@example.test", "manager", layered["sales"])
    assert CONFIDENTIAL in _texts(api, world, inside)
    assert CONFIDENTIAL not in _texts(api, world, outside)
    assert "INTERNAL-ROW" in _texts(api, world, outside)


def test_a_manager_reads_no_confidential_requirement_of_a_job_with_no_department(db, world, api):
    assert CONFIDENTIAL not in _texts(api, world, _member(db, world, "nodept@example.test", "manager"))


def test_hr_still_reads_every_layer(world, api, layered):
    assert {CONFIDENTIAL, "INTERNAL-ROW"} <= _texts(api, world, _hr(world))


def test_the_layer_filter_runs_in_sql(db, world, layered):
    member = db.query(CompanyMember).filter_by(company_id=world["company"].id, role="employee").one()
    viewer = audience.for_member(db, member)
    statements = []

    def remember(_connection, _cursor, statement, *_rest):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", remember)
    try:
        rows = jobs.visible_requirements(db, world["job"].id, viewer)
    finally:
        event.remove(engine, "before_cursor_execute", remember)
    assert CONFIDENTIAL not in [row.text for row in rows]
    assert any("job_requirements.visibility IN" in statement for statement in statements)


# M-5


@pytest.mark.parametrize("language,omitted", OMITTED)
def test_a_partial_must_have_asks_for_more_detail_and_does_not_say_the_cv_omits_it(db, world, language, omitted):
    application = _assessed(db, world, statuses=("partial", "met", "not_found", "met"))
    selected = planner._select(db, application, world["job"], planner.TEMPLATES[language])
    question = next(item for item in selected if item.source == "requirement")
    assert omitted not in question.text and omitted not in question.why
    assert "FastAPI experience" in question.text


@pytest.mark.parametrize("language,omitted", OMITTED)
def test_a_missing_must_have_still_says_the_cv_does_not_mention_it(db, world, language, omitted):
    application = _assessed(db, world, statuses=("not_found", "met", "not_found", "met"))
    selected = planner._select(db, application, world["job"], planner.TEMPLATES[language])
    question = next(item for item in selected if item.source == "requirement")
    assert omitted in question.text and omitted in question.why


@pytest.mark.parametrize("language,omitted", OMITTED)
def test_a_cv_never_read_is_not_said_to_omit_anything(db, world, language, omitted):
    application = make_application(db, world["job"], stage="invited", cv_status=None)
    selected = planner._select(db, application, world["job"], planner.TEMPLATES[language])
    questions = [item for item in selected if item.source == "requirement"]
    assert questions and not [item for item in questions if omitted in item.text or omitted in item.why]


# M-10


def _make_job(api, world, requirements):
    response = api.post(f"/api/companies/{world['company'].id}/jobs", headers=_hr(world), json={
        "title": "T", "description": "d", "interview_languages": ["en"], "requirements": requirements,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _publish(api, world, job):
    response = api.post(f"/api/companies/{world['company'].id}/jobs/{job['id']}/publish", headers=_hr(world))
    assert response.status_code == 200, response.text
    return response.json()


def test_spec_a_job_with_public_requirements_but_no_public_must_have_can_reach_priority(db, world):
    """Given a job whose public requirements are all nice-to-haves and whose must-have is confidential,
    when a candidate gives evidence for the public ones, then the band is many and the card reaches Priority."""
    public = [r for r in world["requirements"] if r.visibility == "public"]
    for requirement in public:
        requirement.must_have = False
    db.commit()
    application = make_application(db, world["job"], stage="session_completed", cv_status="meets")
    make_session(db, application, [(1, "Q", "I built a FastAPI service and used Docker in production and Kubernetes", None)])
    quotes = ["built a FastAPI service", "Docker in production", "Kubernetes"]
    fake.enqueue("session_analysis", json.dumps({
        "requirements": [{"requirement_id": r.id, "status": "evidence", "quote": q, "position": 1} for r, q in zip(public, quotes)],
        "claims": [], "culture_notes": [], "suggestion": "Fine.",
    }))
    analysis.run(application.id)
    row = _fresh(db, application.id)
    assert row.interview_band == "many" and board.cell_for(row) == "priority"
    assert CONFIDENTIAL not in fake.last_messages()[-1]["content"]


def test_spec_public_must_haves_alone_decide_the_band_when_they_exist(db, world):
    """Given a public must-have and a public nice-to-have, evidence for the nice-to-have only leaves the band at few."""
    application = make_application(db, world["job"], stage="session_completed", cv_status="meets")
    make_session(db, application, [(1, "Q", "I use Kubernetes every day", None)])
    kubernetes = world["requirements"][2]
    fake.enqueue("session_analysis", json.dumps({
        "requirements": [{"requirement_id": kubernetes.id, "status": "evidence", "quote": "Kubernetes", "position": 1}],
        "claims": [], "culture_notes": [], "suggestion": "Fine.",
    }))
    analysis.run(application.id)
    assert _fresh(db, application.id).interview_band == "few"
    written = {r.requirement_id for r in db.query(RequirementResult).filter_by(application_id=application.id, source="interview")}
    assert kubernetes.id not in written


def test_spec_with_no_public_requirement_the_band_is_few_and_publishing_warns(db, world, api):
    """Given a job whose requirements are all confidential, publishing warns HR, and nobody gets past few on that job."""
    job = _make_job(api, world, [{"text": "Secret", "must_have": True, "visibility": "confidential"}])
    published = _publish(api, world, job)
    assert published["status"] == "published"
    assert len(published["warnings"]) == 1 and "public" in published["warnings"][0]

    application = make_application(db, db.get(Job, job["id"]), stage="session_completed", cv_status="meets")
    make_session(db, application, [(1, "Q", "I built everything", None)])
    fake.enqueue("session_analysis", json.dumps({"requirements": [], "claims": [], "culture_notes": [], "suggestion": "x"}))
    analysis.run(application.id)
    assert _fresh(db, application.id).interview_band == "few"


def test_publishing_a_job_with_a_public_requirement_does_not_warn(world, api):
    job = _make_job(api, world, [{"text": "Python", "must_have": False}])
    assert _publish(api, world, job)["warnings"] == []
