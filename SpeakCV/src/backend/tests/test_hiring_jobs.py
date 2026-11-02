import pytest
from fastapi.testclient import TestClient

from app.database.sql_models import (
    Application, Company, CompanyMember, Department, Job, JobChannelLink, JobRequirement, KbEdge, KbNode,
    RequirementResult,
)
from app.hiring import jobs
from app.main import create_app
from tests.helpers import auth_header, make_user

CANARY = "CANARY-CONFIDENTIAL-REQ-5521"
INTERNAL_CANARY = "CANARY-INTERNAL-REQ-8830"


@pytest.fixture
def api():
    return TestClient(create_app())


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme", is_sample=True)
    other = Company(slug="other", name="Other")
    db.add_all([company, other])
    db.commit()
    dept = Department(company_id=company.id, name="Engineering")
    foreign_dept = Department(company_id=other.id, name="Foreign")
    db.add_all([dept, foreign_dept])
    db.commit()

    def node(company_id, type, title, body="", visibility="public", department_id=None):
        row = KbNode(company_id=company_id, department_id=department_id, type=type, title=title, body=body,
                     language="en", visibility=visibility, status="published")
        db.add(row)
        db.commit()
        return row

    role = node(company.id, "role", "Backend Developer", "Builds services.", "public", dept.id)
    python = node(company.id, "skill", "Python", "Python for 3 years.")
    secret = node(company.id, "requirement", "Secret", CANARY, "confidential")
    foreign_role = node(other.id, "role", "Foreign role")
    for target, must in ((python, True), (secret, False)):
        db.add(KbEdge(company_id=company.id, source_node_id=role.id, target_node_id=target.id,
                      relation="requires", must_have=must, status="published"))
    db.commit()

    people = {}
    for who, member_role, company_id in (("hr", "hr", company.id), ("emp", "employee", company.id),
                                         ("hr2", "hr", other.id)):
        user = make_user(db, f"{who}@example.test")
        db.add(CompanyMember(company_id=company_id, user_id=user.id, role=member_role))
        people[who] = auth_header(user.email)
    db.commit()
    return {"company": company, "other": other, "dept": dept, "foreign_dept": foreign_dept, "role": role,
            "foreign_role": foreign_role, "people": people}


def url(world, tail=""):
    return f"/api/companies/{world['company'].id}/jobs{tail}"


def make_job(api, world, **extra):
    body = {"title": "Backend Developer", "description": "Build things.", "interview_languages": ["en"],
            "requirements": [
                {"text": "Python 3 years", "must_have": True, "visibility": "public"},
                {"text": CANARY, "must_have": False, "visibility": "confidential"},
                {"text": INTERNAL_CANARY, "must_have": False, "visibility": "internal"},
            ], **extra}
    response = api.post(url(world), json=body, headers=world["people"]["hr"])
    assert response.status_code == 201, response.text
    return response.json()


def test_create_draft_and_cross_company_ids(api, world):
    job = make_job(api, world, department_id=world["dept"].id, role_node_id=world["role"].id)
    assert job["status"] == "draft" and job["slug"] is None and job["version"] == 1
    assert len(job["requirements"]) == 3
    hr = world["people"]["hr"]
    base = {"title": "T", "interview_languages": ["en"]}
    assert api.post(url(world), json={**base, "department_id": world["foreign_dept"].id}, headers=hr).status_code == 404
    assert api.post(url(world), json={**base, "role_node_id": world["foreign_role"].id}, headers=hr).status_code == 404
    bad_node = {"requirements": [{"text": "x", "node_id": world["foreign_role"].id}]}
    assert api.post(url(world), json={**base, **bad_node}, headers=hr).status_code == 404


@pytest.mark.parametrize("languages", [[], ["fr"], ["en", "de"]])
def test_languages_are_validated(api, world, languages):
    response = api.post(url(world), json={"title": "T", "interview_languages": languages},
                        headers=world["people"]["hr"])
    assert response.status_code == 422


def test_only_hr_writes_but_any_member_reads(api, world):
    job = make_job(api, world)
    emp = world["people"]["emp"]
    assert api.post(url(world), json={"title": "T", "interview_languages": ["en"]}, headers=emp).status_code == 403
    assert api.get(url(world), headers=emp).status_code == 200
    assert api.get(url(world, f"/{job['id']}"), headers=emp).status_code == 200
    assert api.get(url(world, "/role-options"), headers=emp).status_code == 403
    assert api.get(url(world, "/prefill?role_node_id=1"), headers=emp).status_code == 403
    assert api.patch(url(world, f"/{job['id']}"), json={"title": "x"}, headers=emp).status_code == 403


def test_role_options_and_prefill(api, world):
    hr = world["people"]["hr"]
    options = api.get(url(world, "/role-options"), headers=hr).json()
    assert [(o["id"], o["title"], o["department_id"], o["department_name"]) for o in options] == [
        (world["role"].id, "Backend Developer", world["dept"].id, "Engineering")]
    prefill = api.get(url(world, f"/prefill?role_node_id={world['role'].id}"), headers=hr).json()
    assert prefill["title"] == "Backend Developer" and prefill["description"] == "Builds services."
    by_text = {r["text"]: r for r in prefill["requirements"]}
    assert by_text["Python for 3 years."]["must_have"] is True
    assert by_text["Python for 3 years."]["visibility"] == "public"
    assert by_text[CANARY]["visibility"] == "confidential" and by_text[CANARY]["must_have"] is False
    assert api.get(url(world, f"/prefill?role_node_id={world['foreign_role'].id}"), headers=hr).status_code == 404


def test_publish_needs_requirement_and_description(api, world):
    hr = world["people"]["hr"]
    empty = api.post(url(world), json={"title": "T", "description": "d", "interview_languages": ["en"]},
                     headers=hr).json()
    assert api.post(url(world, f"/{empty['id']}/publish"), headers=hr).status_code == 422
    nodesc = api.post(url(world), json={"title": "T", "interview_languages": ["en"],
                                        "requirements": [{"text": "x"}]}, headers=hr).json()
    assert api.post(url(world, f"/{nodesc['id']}/publish"), headers=hr).status_code == 422


def test_publish_sets_slug_unique_and_date(api, world):
    hr = world["people"]["hr"]
    first, second = make_job(api, world), make_job(api, world)
    a = api.post(url(world, f"/{first['id']}/publish"), headers=hr).json()
    b = api.post(url(world, f"/{second['id']}/publish"), headers=hr).json()
    assert a["status"] == "published" and a["published_at"]
    assert a["slug"].startswith("acme-backend-developer-") and a["slug"] != b["slug"]
    assert api.post(url(world, f"/{first['id']}/publish"), headers=hr).status_code == 409


def test_channels(api, world, db):
    hr = world["people"]["hr"]
    job = make_job(api, world)
    path = url(world, f"/{job['id']}/channels")
    links = api.post(path, json={"channels": ["linkedin", "company_site"]}, headers=hr).json()
    assert {link["channel"] for link in links} == {"linkedin", "company_site"}
    assert all(len(link["token"]) >= 16 and link["token"].replace("-", "").replace("_", "").isalnum() for link in links)
    again = api.post(path, json={"channels": ["linkedin"]}, headers=hr).json()
    assert again[0]["token"] == next(link["token"] for link in links if link["channel"] == "linkedin")
    assert db.query(JobChannelLink).filter_by(job_id=job["id"]).count() == 2
    assert api.post(path, json={"channels": []}, headers=hr).status_code == 422
    assert api.post(path, json={"channels": ["Bad Channel!"]}, headers=hr).status_code == 422


def test_requirement_edit_versions(api, world, db):
    hr = world["people"]["hr"]
    job = make_job(api, world)
    path = url(world, f"/{job['id']}")
    ids = {r["text"]: r["id"] for r in job["requirements"]}
    application = Application(company_id=world["company"].id, job_id=job["id"], job_version=1, alias="A1")
    db.add(application)
    db.commit()
    db.add(RequirementResult(application_id=application.id, requirement_id=ids["Python 3 years"],
                             source="cv", status="met"))
    db.commit()

    title_only = api.patch(path, json={"title": "New title", "description": "New desc"}, headers=hr).json()
    assert title_only["version"] == 1 and title_only["title"] == "New title"

    same = [{"text": r["text"], "must_have": r["must_have"], "visibility": r["visibility"]}
            for r in job["requirements"]]
    assert api.patch(path, json={"requirements": same}, headers=hr).json()["version"] == 1

    changed = [{**same[0], "text": "Python 5 years"}, *same[1:]]
    result = api.patch(path, json={"requirements": changed}, headers=hr).json()
    assert result["version"] == 2
    assert result["requirements"][0]["text"] == "Python 5 years"
    old = db.get(JobRequirement, ids["Python 3 years"])
    db.refresh(old)
    assert old.active is False
    assert db.query(JobRequirement).filter_by(job_id=job["id"]).count() == 4
    assert len(jobs.active_requirements(db, job["id"])) == 3
    kept = db.query(RequirementResult).filter_by(application_id=application.id).one()
    assert kept.requirement_id == old.id
    db.refresh(application)
    assert application.job_version == 1

    removed = api.patch(path, json={"requirements": changed[:1]}, headers=hr).json()
    assert removed["version"] == 3 and len(removed["requirements"]) == 1


def test_public_page_shows_only_public_requirements(api, world):
    hr = world["people"]["hr"]
    job = make_job(api, world)
    published = api.post(url(world, f"/{job['id']}/publish"), headers=hr).json()
    response = api.get(f"/api/public/jobs/{published['slug']}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Backend Developer" and data["company_name"] == "Acme" and data["is_sample"] is True
    assert data["interview_languages"] == ["en"] and data["status"] == "published" and data["can_apply"] is True
    assert [r["text"] for r in data["requirements"]] == ["Python 3 years"]
    assert CANARY not in response.text and INTERNAL_CANARY not in response.text
    assert "created_by" not in data and "company_id" not in data
    assert data["company_slug"] == "acme"


def test_public_page_draft_and_closed(api, world, db):
    hr = world["people"]["hr"]
    assert api.get("/api/public/jobs/nope").status_code == 404
    draft = make_job(api, world)
    db.get(Job, draft["id"]).slug = "forced-draft-slug"
    db.commit()
    assert api.get("/api/public/jobs/forced-draft-slug").status_code == 404

    job = make_job(api, world)
    published = api.post(url(world, f"/{job['id']}/publish"), headers=hr).json()
    closed = api.post(url(world, f"/{job['id']}/close"), headers=hr).json()
    assert closed["status"] == "closed"
    data = api.get(f"/api/public/jobs/{published['slug']}").json()
    assert data["status"] == "closed" and data["can_apply"] is False
    assert api.post(url(world, f"/{draft['id']}/close"), headers=hr).status_code == 409


def test_src_counts_clicks_and_unknown_is_ignored(api, world, db):
    hr = world["people"]["hr"]
    job = make_job(api, world)
    slug = api.post(url(world, f"/{job['id']}/publish"), headers=hr).json()["slug"]
    links = api.post(url(world, f"/{job['id']}/channels"), json={"channels": ["linkedin", "referral"]},
                     headers=hr).json()
    token = next(link["token"] for link in links if link["channel"] == "linkedin")
    assert api.get(f"/api/public/jobs/{slug}?src={token}").status_code == 200
    assert api.get(f"/api/public/jobs/{slug}?src={token}").status_code == 200
    assert api.get(f"/api/public/jobs/{slug}?src=unknown-token-value").status_code == 200
    assert db.query(JobChannelLink).filter_by(token=token).one().click_count == 2
    assert db.query(JobChannelLink).filter(JobChannelLink.token != token).one().click_count == 0
    columns = {c.name for c in JobChannelLink.__table__.columns}
    assert not {"ip", "ip_address", "user_agent", "user_id"} & columns


def test_other_company_job_is_404(api, world):
    other_job = api.post(f"/api/companies/{world['other'].id}/jobs",
                         json={"title": "T", "interview_languages": ["en"]}, headers=world["people"]["hr2"]).json()
    hr = world["people"]["hr"]
    jid = other_job["id"]
    assert api.get(url(world, f"/{jid}"), headers=hr).status_code == 404
    assert api.patch(url(world, f"/{jid}"), json={"title": "x"}, headers=hr).status_code == 404
    assert api.post(url(world, f"/{jid}/publish"), headers=hr).status_code == 404
    assert api.post(url(world, f"/{jid}/close"), headers=hr).status_code == 404
    assert api.post(url(world, f"/{jid}/channels"), json={"channels": ["linkedin"]}, headers=hr).status_code == 404
    assert all(j["id"] != jid for j in api.get(url(world), headers=hr).json())


def test_seed_creates_one_published_backend_job_per_sample_company(db, tmp_path, monkeypatch):
    from app.brain import seed

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    seed.seed_samples(auto_approve=True)
    seed.seed_samples(auto_approve=True)
    db.expire_all()
    rows = db.query(Job).all()
    assert len(rows) == 2
    for job in rows:
        assert job.title == "Backend Developer" and job.status == "published" and job.slug
        assert job.interview_languages == ["vi", "en", "ko"] and job.description
        requirements = jobs.active_requirements(db, job.id)
        assert any(r.must_have for r in requirements)
        assert not any("salary" in r.text.lower() for r in requirements)
        channels = {c.channel for c in db.query(JobChannelLink).filter_by(job_id=job.id)}
        assert channels == {"company_site", "linkedin", "referral"}


def test_patching_the_description_runs_the_discrimination_guard(api, world):
    job = make_job(api, world)
    hr = world["people"]["hr"]
    path = url(world, f"/{job['id']}")
    blocked = api.patch(path, json={"description": "Chi tuyen nam duoi 30 tuoi."}, headers=hr)
    assert blocked.status_code == 422 and "age" in blocked.text
    assert api.get(path, headers=hr).json()["description"] == "Build things."
    assert api.patch(path, json={"description": "Build better things."}, headers=hr).status_code == 200


def test_a_description_the_check_cannot_look_at_is_saved_with_a_warning(api, world):
    from app.ai.providers import fake

    def down(*_):
        raise RuntimeError("down")

    fake.register("discrimination_check", down)
    job = make_job(api, world)
    response = api.patch(url(world, f"/{job['id']}"), json={"description": "A friendly team."},
                         headers=world["people"]["hr"])
    assert response.status_code == 200 and response.json()["warnings"]


def test_a_job_made_from_a_draft_refuses_description_edits(api, db, world):
    from app.database.sql_models import JobDraft

    job = make_job(api, world)
    path = url(world, f"/{job['id']}")
    hr = world["people"]["hr"]
    draft = JobDraft(company_id=world["company"].id, job_id=job["id"], version=1, lines=[], requirement_lines=[],
                     lint=[], failed_languages=[], status="published")
    db.add(draft)
    db.commit()
    refused = api.patch(path, json={"description": "Something else."}, headers=hr)
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "description_in_jd_studio" and refused.json()["detail"]["draft_id"] == draft.id
    assert api.patch(path, json={"title": "New title"}, headers=hr).status_code == 200
    same = api.patch(path, json={"description": "Build things."}, headers=hr)
    assert same.status_code == 200  # the unchanged text is not an edit
