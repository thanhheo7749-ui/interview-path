"""Races around an approval, a brief and a scorecard, on real sessions. See test_mysql_brain_races for the method."""
import json
import os
import threading

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs TEST_MYSQL_URL; run `make test-mysql`.", allow_module_level=True)

from fastapi.testclient import TestClient

from app.ai.providers import fake
from app.brain import fake_demo
from app.bridges import brief, lint
from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, CandidateBrief, CompanyMember, InterviewScorecard, Job, JobDraft, JobRequirement,
)
from app.main import app
from tests.helpers import auth_header
from tests.helpers import make_user  # noqa: E402
from tests.helpers_jd import ai_line, assistant_json, line, make_draft, make_world

HR = auth_header("hr@acme.test")
MANAGER = auth_header("mgr@acme.test")
TEXT = "We build the APIs of our hiring platform"
EMPTY_BRIEF = json.dumps({"strengths": [], "to_clarify": [], "questions": []})


@pytest.fixture(autouse=True)
def _demo():
    fake_demo.install()


@pytest.fixture
def world(db):
    return make_world(db)


def _url(world, tail):
    return f"/api/companies/{world.company.id}{tail}"


def _draft(db, world, status="draft"):
    return make_draft(db, world.company.id, [line("l1", [world.role.id], en=TEXT, vi="API", ko="API")], world.request.id,
                      status=status).id


def in_other_session(work):
    session = SessionLocal()
    try:
        result = work(session)
        session.commit()
        return result
    finally:
        session.close()


def stored(draft_id):
    return in_other_session(lambda s: (lambda row: (row.status, row.version, row.lines[0]["text"]["en"]))(s.get(JobDraft, draft_id)))


def _during_assistant(work, world):
    def respond(*_):
        in_other_session(work)
        return assistant_json([ai_line("l1", [world.role.id], en="Text the manager never read", vi="API", ko="API")])
    fake.register("jd_assistant", respond)


def _ask(client, world, draft_id):
    return client.post(_url(world, f"/job-drafts/{draft_id}/assistant"), headers=HR, json={"message": "shorter"})


def test_a_submit_and_approval_during_an_assistant_call_keep_the_text_that_was_approved(client, db, world):
    draft_id = _draft(db, world)

    def approve(session):
        session.get(JobDraft, draft_id).status = "approved"

    _during_assistant(approve, world)
    response = _ask(client, world, draft_id)
    assert response.status_code == 409, response.text
    assert stored(draft_id) == ("approved", 1, TEXT)


def test_an_edit_during_an_assistant_call_is_not_overwritten(client, db, world):
    draft_id = _draft(db, world)

    def edit(session):
        row = session.get(JobDraft, draft_id)
        row.lines, row.version = [line("l1", [world_role_id], en="Edited by HR", vi="API", ko="API")], 2

    world_role_id = world.role.id
    _during_assistant(edit, world)
    assert _ask(client, world, draft_id).status_code == 409
    assert stored(draft_id) == ("draft", 2, "Edited by HR")


def test_a_submit_during_its_lint_of_an_edited_draft_refuses(client, db, world, monkeypatch):
    draft_id = _draft(db, world)
    real, fired = lint.evaluate, []

    def hook(*args, **kwargs):
        issues = real(*args, **kwargs)
        if not fired:
            fired.append(True)
            in_other_session(lambda s: setattr(s.get(JobDraft, draft_id), "version", 2))
        return issues

    monkeypatch.setattr(lint, "evaluate", hook)
    assert client.post(_url(world, f"/job-drafts/{draft_id}/submit"), headers=HR).status_code == 409
    assert stored(draft_id)[:2] == ("draft", 2)


def test_an_approval_of_a_version_that_moved_refuses(client, db, world):
    draft_id = _draft(db, world, status="manager_review")
    in_other_session(lambda s: setattr(s.get(JobDraft, draft_id), "version", 2))
    response = client.post(_url(world, f"/job-drafts/{draft_id}/approve"), headers=MANAGER, json={"version": 1})
    assert response.status_code == 409
    assert stored(draft_id)[:2] == ("manager_review", 2)


def _application(db, world):
    job = Job(company_id=world.company.id, title="Backend", slug="backend-x", status="published", version=1,
              interview_languages=["en"], department_id=world.eng.id)
    db.add(job)
    db.commit()
    db.add(JobRequirement(company_id=world.company.id, job_id=job.id, text="Builds APIs", must_have=True, position=0))
    user = make_user(db, "candidate@example.test")
    application = Application(company_id=world.company.id, job_id=job.id, job_version=1, alias="#A1", stage="ready_for_hr",
                              cv_status="meets", candidate_user_id=user.id, hr_decision="approved",
                              cv_text_raw="raw", cv_text_blind="blind")
    db.add(application)
    db.commit()
    return application.id, job.id


def _with_evidence(db, world, application_id):
    from app.database.sql_models import CvClaim
    db.add(CvClaim(application_id=application_id, text="Team lead", quote="Led a team", status="explained"))
    db.commit()


def _generate(client, world, application_id):
    return client.post(_url(world, f"/applications/{application_id}/brief"), headers=HR, json={"language": "en"})


def test_a_brief_sent_during_a_regenerate_stays_as_it_was_sent(client, db, world):
    application_id, _ = _application(db, world)
    _with_evidence(db, world, application_id)
    row = CandidateBrief(company_id=world.company.id, application_id=application_id, language="en",
                         content={"strengths": [], "note": "as sent"}, status="draft", reviewed_by=world.hr.id)
    db.add(row)
    db.commit()
    row_id = row.id

    def respond(*_):
        in_other_session(lambda s: setattr(s.get(CandidateBrief, row_id), "status", "sent"))
        return EMPTY_BRIEF

    fake.register("candidate_brief", respond)
    assert _generate(client, world, application_id).status_code == 409
    seen = in_other_session(lambda s: (lambda r: (r.status, r.reviewed_by, r.content.get("note")))(s.get(CandidateBrief, row_id)))
    assert seen == ("sent", world.hr.id, "as sent")


def test_two_first_generates_leave_one_brief(db, world):
    application_id, _ = _application(db, world)
    _with_evidence(db, world, application_id)
    barrier = threading.Barrier(2, timeout=20)

    def respond(*_):
        barrier.wait()
        return EMPTY_BRIEF

    fake.register("candidate_brief", respond)
    results = []

    def run():
        with TestClient(app) as client:
            results.append(_generate(client, world_ref, application_id).status_code)

    world_ref = world
    threads = [threading.Thread(target=run, daemon=True) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert results == [200, 200]
    assert in_other_session(lambda s: s.query(CandidateBrief).filter_by(application_id=application_id).count()) == 1


def test_a_double_submit_of_a_scorecard_leaves_one_row(db, world, monkeypatch):
    application_id, job_id = _application(db, world)
    requirement_id = db.query(JobRequirement).filter_by(job_id=job_id).one().id
    db.add(CandidateBrief(company_id=world.company.id, application_id=application_id, language="en", content={},
                          status="sent", reviewed_by=world.hr.id))
    db.commit()
    barrier = threading.Barrier(2, timeout=20)
    real = brief._find_scorecard

    def both_find_nothing(session, application, manager_user_id, lock=False):
        found = real(session, application, manager_user_id, lock)
        if not lock:
            barrier.wait()
        return found

    monkeypatch.setattr(brief, "_find_scorecard", both_find_nothing)
    results = []
    path = _url(world, f"/applications/{application_id}/scorecard")
    body = {"recommendation": "hire", "scores": [{"requirement_id": requirement_id, "score": 4}]}

    def run():
        with TestClient(app) as client:
            results.append(client.post(path, headers=MANAGER, json=body).status_code)

    threads = [threading.Thread(target=run, daemon=True) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert results == [200, 200]
    assert in_other_session(lambda s: s.query(InterviewScorecard).filter_by(application_id=application_id).count()) == 1


def test_a_second_manager_is_kept_out_on_the_migrated_schema(client, db, world):
    second = make_user(db, "mgr3@acme.test")
    db.add(CompanyMember(company_id=world.company.id, user_id=second.id, role="manager", department_id=world.eng.id))
    db.commit()
    draft_id = _draft(db, world, status="manager_review")
    assert client.get(_url(world, f"/job-drafts/{draft_id}"), headers=auth_header("mgr3@acme.test")).status_code == 404
    assert client.get(_url(world, f"/job-drafts/{draft_id}"), headers=MANAGER).status_code == 200
