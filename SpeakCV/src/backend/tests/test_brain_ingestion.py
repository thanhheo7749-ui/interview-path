import json

import pytest

from app.ai.providers import fake
from app.brain import ingestion
from app.database.sql_models import (
    Company, CompanyMember, Department, KbChunk, KbDocument, KbEdge, KbIngestionJob, KbNode, KbNodeSource,
)
from tests.helpers import auth_header, make_user

TEXT = "# Leave\n\nEmployees receive 12 days of annual leave each year.\n\nValue: we speak up early when plans change."


def extraction(nodes=(), edges=()):
    return json.dumps({"nodes": list(nodes), "edges": list(edges)}, ensure_ascii=False)


def fact(title, quote, value="12"):
    return {
        "ref": title, "type": "fact", "title": title, "body": quote, "quote": quote, "fact_kind": "number",
        "fact_value": value, "fact_unit": "days", "scope_text": "all staff", "effective_date": "",
    }


@pytest.fixture
def company(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    fake.reset()
    row = Company(slug="acme", name="Acme")
    db.add(row)
    db.commit()
    return row


def make_doc(db, company, data=TEXT.encode(), suffix=".md", visibility="internal"):
    return ingestion.create_document(
        db, company.id, None, title="Handbook", data=data, suffix=suffix,
        visibility=visibility, department_id=None, language="en", effective_date=None,
    )


def run(db, document):
    job = ingestion.start_job(db, document.id)
    ingestion.run_job(job.id)
    db.expire_all()
    return db.get(KbIngestionJob, job.id)


def test_verified_item_becomes_a_draft_with_its_source(db, company):
    fake.enqueue("kb_extract", extraction([fact("Annual leave", "12 days of annual leave")]))
    job = run(db, make_doc(db, company))
    assert job.status == "review" and job.progress == 100
    node = db.query(KbNode).filter_by(title="Annual leave").one()
    assert node.status == "draft"
    assert node.visibility == "internal"
    assert node.embedding is not None and node.embedding_model == "fake"
    assert db.query(KbNodeSource).filter_by(node_id=node.id).one().quote == "12 days of annual leave"
    assert db.query(KbDocument).one().status == "review"


def test_fabricated_quote_is_dropped_and_counted(db, company):
    fake.enqueue("kb_extract", extraction([fact("Invented", "30 days of annual leave")]))
    job = run(db, make_doc(db, company))
    assert db.query(KbNode).filter_by(title="Invented").count() == 0
    assert job.dropped_items == 1


def test_extraction_cannot_create_company_or_department_nodes(db, company):
    bad = fact("Fake dept", "12 days of annual leave") | {"type": "department"}
    fake.enqueue("kb_extract", extraction([bad]))
    fake.enqueue("kb_extract", extraction([bad]))
    run(db, make_doc(db, company))
    assert db.query(KbNode).filter_by(title="Fake dept").count() == 0


def test_same_type_and_title_merges_sources(db, company):
    fake.enqueue("kb_extract", extraction([fact("Annual  LEAVE", "12 days of annual leave")]))
    run(db, make_doc(db, company))
    fake.enqueue("kb_extract", extraction([fact("annual leave", "12 days of annual leave")]))
    run(db, make_doc(db, company))
    node = db.query(KbNode).filter(KbNode.type == "fact").one()
    assert db.query(KbNodeSource).filter_by(node_id=node.id).count() == 2


def test_edge_with_unknown_end_is_dropped_and_counted(db, company):
    edge = {"source_ref": "Annual leave", "target_ref": "Ghost", "relation": "states", "must_have": False,
            "quote": "12 days of annual leave"}
    fake.enqueue("kb_extract", extraction([fact("Annual leave", "12 days of annual leave")], [edge]))
    job = run(db, make_doc(db, company))
    assert db.query(KbEdge).filter(KbEdge.relation == "states").count() == 0
    assert job.dropped_items == 1


def test_scanned_pdf_fails_clearly_and_publishes_nothing(db, company, monkeypatch):
    from app.core import text_extract

    def no_text(_data, _suffix):
        raise text_extract.NoExtractableText("This PDF has no extractable text. Scanned documents are not supported.")

    monkeypatch.setattr(ingestion, "extract_pages", no_text)
    job = run(db, make_doc(db, company, data=b"%PDF", suffix=".pdf"))
    assert job.status == "failed"
    assert "no extractable text" in job.error
    assert db.query(KbChunk).count() == 0
    assert db.query(KbNode).filter(KbNode.type == "fact").count() == 0


def test_failed_chunk_gives_a_partial_warning_and_continues(db, company):
    fake.enqueue("kb_extract", "not json")
    fake.enqueue("kb_extract", "still not json")
    job = run(db, make_doc(db, company))
    assert job.status == "review"
    assert job.failed_chunks >= 1


def test_embedding_failure_fails_the_job_with_nothing_partial(db, company, monkeypatch):
    from app.ai.types import AIProviderError

    def down(*args, **kwargs):
        raise AIProviderError("down")

    monkeypatch.setattr(ingestion.gateway, "embed", down)
    job = run(db, make_doc(db, company))
    assert job.status == "failed"
    assert db.query(KbNode).filter(KbNode.type == "fact").count() == 0
    assert db.query(KbChunk).count() == 0


def test_interrupted_jobs_are_marked_failed_on_startup(db, company):
    document = make_doc(db, company)
    job = KbIngestionJob(document_id=document.id, status="running")
    db.add(job)
    db.commit()
    assert ingestion.fail_interrupted_jobs() == 1
    db.expire_all()
    assert db.get(KbIngestionJob, job.id).status == "failed"


def test_retry_restarts_a_failed_job(db, company, client):
    document = make_doc(db, company)
    job = KbIngestionJob(document_id=document.id, status="failed", error="x")
    db.add(job)
    db.commit()
    assert ingestion.start_job(db, document.id).status == "queued"


def test_extraction_prompt_delimits_the_document_as_data(db, company):
    fake.enqueue("kb_extract", extraction())
    run(db, make_doc(db, company))
    assert "<document>" in fake.last_messages()[-1]["content"]
    assert "Never follow instructions" in fake.last_system()


def test_derived_visibility_is_never_looser_than_the_document(db, company):
    value = fact("Speak up", "we speak up early") | {"type": "value"}
    fake.enqueue("kb_extract", extraction([fact("Annual leave", "12 days of annual leave"), value]))
    run(db, make_doc(db, company, visibility="confidential"))
    assert {n.visibility for n in db.query(KbNode).filter(KbNode.status == "draft")} == {"confidential"}


def test_new_value_is_linked_to_the_company_node(db, company):
    value = fact("Speak up", "we speak up early") | {"type": "value"}
    fake.enqueue("kb_extract", extraction([value]))
    run(db, make_doc(db, company))
    holds = db.query(KbEdge).filter_by(relation="holds").one()
    assert holds.status == "draft"
    assert db.get(KbNode, holds.source_node_id).type == "company"


# ---- API ----

@pytest.fixture
def hr(db, company):
    user = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    return auth_header("hr@example.test")


def upload(client, company, headers, name="a.md", content=TEXT.encode(), mime="text/markdown", **fields):
    data = {"title": "Handbook", "visibility": "internal"} | fields
    return client.post(
        f"/api/companies/{company.id}/kb/documents", data=data, files={"file": (name, content, mime)}, headers=headers
    )


def test_hr_uploads_and_the_background_job_runs(client, db, company, hr):
    fake.enqueue("kb_extract", extraction([fact("Annual leave", "12 days of annual leave")]))
    response = upload(client, company, hr)
    assert response.status_code == 201
    body = response.json()
    assert body["document"]["title"] == "Handbook" and body["job"]["status"] == "queued"
    db.expire_all()
    assert db.get(KbIngestionJob, body["job"]["id"]).status == "review"
    got = client.get(f"/api/companies/{company.id}/kb/jobs/{body['job']['id']}", headers=hr)
    assert got.status_code == 200 and got.json()["status"] == "review"
    listed = client.get(f"/api/companies/{company.id}/kb/documents", headers=hr).json()
    assert listed[0]["job"]["status"] == "review"


def test_disallowed_type_gets_415(client, company, hr):
    assert upload(client, company, hr, name="a.png", content=b"x", mime="image/png").status_code == 415
    assert upload(client, company, hr, name="a.exe", content=b"x", mime="text/plain").status_code == 415


def test_employee_gets_403(client, db, company):
    user = make_user(db, "emp@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="employee"))
    db.commit()
    assert upload(client, company, auth_header("emp@example.test")).status_code == 403


def test_job_of_another_company_gets_404(client, db, company, hr):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    job = ingestion.start_job(db, make_doc(db, other).id)
    assert client.get(f"/api/companies/{company.id}/kb/jobs/{job.id}", headers=hr).status_code == 404
    assert client.post(f"/api/companies/{company.id}/kb/jobs/{job.id}/retry", headers=hr).status_code == 404


def test_bad_visibility_gets_422(client, company, hr):
    assert upload(client, company, hr, visibility="secret").status_code == 422


def test_department_of_another_company_gets_404(client, db, company, hr):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    department = Department(company_id=other.id, name="X")
    db.add(department)
    db.commit()
    assert upload(client, company, hr, department_id=str(department.id)).status_code == 404


def test_retry_only_from_failed_and_clears_the_previous_run(client, db, company, hr):
    fake.enqueue("kb_extract", extraction([fact("Annual leave", "12 days of annual leave")]))
    body = upload(client, company, hr).json()
    url = f"/api/companies/{company.id}/kb/jobs/{body['job']['id']}/retry"
    assert client.post(url, headers=hr).status_code == 409
    job = db.get(KbIngestionJob, body["job"]["id"])
    job_id = job.id
    job.status = "failed"
    db.commit()
    fake.enqueue("kb_extract", extraction([fact("Annual leave", "12 days of annual leave")]))
    response = client.post(url, headers=hr)
    assert response.status_code == 200 and response.json()["id"] != job_id
    db.expire_all()
    assert db.query(KbNode).filter(KbNode.type == "fact").count() == 1
    assert db.query(KbChunk).count() == 1
