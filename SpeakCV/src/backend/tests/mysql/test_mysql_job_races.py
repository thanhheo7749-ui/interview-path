"""F5: three races around a job and its AI check, on two real sessions. See test_mysql_brain_races for the method."""
import os
import threading

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs TEST_MYSQL_URL; run `make test-mysql`.", allow_module_level=True)

from fastapi.testclient import TestClient

from app.bridges import publishing
from app.database.database import SessionLocal
from app.database.sql_models import Company, CompanyMember, Job, JobDraft, JobRequirement
from app.hiring import jobs
from app.main import app
from tests.helpers import auth_header, make_user
from tests.helpers_jd import line, make_draft

BLOCKED_FOR = 1.0


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    user = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    return company.id, auth_header("hr@example.test")


def in_other_session(work):
    session = SessionLocal()
    try:
        return work(session)
    finally:
        session.close()


def during_the_check(monkeypatch, work):
    """Runs work once, in its own session and to its commit, while the request is in its AI check."""
    real, fired = jobs.check_requirements, []

    def hook(*args, **kwargs):
        result = real(*args, **kwargs)
        if not fired:
            fired.append(True)
            in_other_session(work)
        return result

    monkeypatch.setattr(jobs, "check_requirements", hook)


def published_job(db, company_id):
    job = Job(company_id=company_id, title="Backend", description="d", status="published", version=1, slug="acme-backend",
              interview_languages=["en"])
    db.add(job)
    db.commit()
    return job.id


def test_a_job_closed_during_the_check_cannot_be_edited(client, db, world, monkeypatch):
    company_id, headers = world
    job_id = published_job(db, company_id)

    def close(session):
        session.get(Job, job_id).status = "closed"
        session.commit()

    during_the_check(monkeypatch, close)
    response = client.patch(f"/api/companies/{company_id}/jobs/{job_id}", headers=headers,
                            json={"title": "Changed", "requirements": [{"text": "Knows Python"}]})
    assert response.status_code == 409, response.text
    check = in_other_session(lambda s: (s.get(Job, job_id).title, s.query(JobRequirement).filter_by(job_id=job_id).count()))
    assert check == ("Backend", 0)


LINES = [line("l1", [], en="We build APIs"), line("l2", [], en="Knows Python", is_requirement=True, must_have=True)]


def approved_draft(db, company_id):
    return make_draft(db, company_id, LINES, status="approved").id


@pytest.fixture
def no_lint(monkeypatch):
    monkeypatch.setattr(publishing, "_check_clean", lambda *_: None)


def publish_url(company_id, draft_id):
    return f"/api/companies/{company_id}/job-drafts/{draft_id}/publish"


def test_a_draft_edited_during_the_check_is_not_published_from_old_lines(client, db, world, monkeypatch, no_lint):
    company_id, headers = world
    draft_id = approved_draft(db, company_id)

    def edit(session):
        draft = session.get(JobDraft, draft_id)
        draft.version += 1
        session.commit()

    during_the_check(monkeypatch, edit)
    response = client.post(publish_url(company_id, draft_id), headers=headers)
    assert response.status_code == 409, response.text
    assert in_other_session(lambda s: (s.query(Job).filter_by(company_id=company_id).count(),
                                       s.get(JobDraft, draft_id).status)) == (0, "approved")


def post_in_thread(url, headers, results):
    def run():
        with TestClient(app) as other_client:
            results.append(other_client.post(url, headers=headers).status_code)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_a_second_publish_finishing_during_the_check_is_reused(client, db, world, monkeypatch, no_lint):
    company_id, headers = world
    draft_id = approved_draft(db, company_id)
    url = publish_url(company_id, draft_id)
    real, threads, results = jobs.check_requirements, [], []

    def hook(*args, **kwargs):
        result = real(*args, **kwargs)
        if not threads:
            threads.append(post_in_thread(url, headers, results))
            threads[0].join(30)
            assert results == [200]
        return result

    monkeypatch.setattr(jobs, "check_requirements", hook)
    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.text
    check = in_other_session(lambda s: (s.query(Job).filter_by(company_id=company_id).count(),
                                        s.query(JobRequirement).filter_by(active=True).count(), s.get(JobDraft, draft_id).job_id))
    assert check[:2] == (1, 1) and check[2] == response.json()["job"]["id"]


def test_a_second_publish_waits_for_the_first_and_reuses_its_job(client, db, world, monkeypatch, no_lint):
    company_id, headers = world
    draft_id = approved_draft(db, company_id)
    url = publish_url(company_id, draft_id)
    real, threads, results = publishing._new_job, [], []

    def hook(*args, **kwargs):
        job = real(*args, **kwargs)
        if not threads:
            threads.append(post_in_thread(url, headers, results))
            threads[0].join(BLOCKED_FOR)
            assert threads[0].is_alive(), f"the second publish did not wait for the lock: {results}"
        return job

    monkeypatch.setattr(publishing, "_new_job", hook)
    response = client.post(url, headers=headers)
    threads[0].join(30)
    assert response.status_code == 200, response.text
    assert results == [200]
    assert in_other_session(lambda s: (s.query(Job).filter_by(company_id=company_id).count(),
                                       s.query(JobRequirement).filter_by(active=True).count())) == (1, 1)
