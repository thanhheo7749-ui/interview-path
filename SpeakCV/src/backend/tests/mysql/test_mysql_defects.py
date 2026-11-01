"""Defects SQLite cannot show: column lengths, REPEATABLE READ, foreign keys, and migrated column types.

The pipeline writes in its own session. Under REPEATABLE READ a session that is mid-transaction will not see that,
so these tests end their transaction (db.commit()) before reading another session's work.
"""
import json
import os

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs a MySQL server: run make test-mysql", allow_module_level=True)

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

from app.ai.providers import fake  # noqa: E402
from app.brain import ingestion, seed  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.migrate import alembic_config  # noqa: E402
from app.database.sql_models import (  # noqa: E402
    AssistantQuestion, Company, CompanyMember, KbConflict, KbDocument, KbIngestionJob, KbNode, User,
)
from tests.helpers import auth_header, make_user  # noqa: E402

TEXT = "# Leave\n\nEmployees receive 12 days of annual leave each year."
QUOTE = "12 days of annual leave"
USER_COLUMNS = {
    "kb_documents": "uploaded_by", "kb_nodes": "approved_by", "kb_conflicts": "resolved_by",
    "assistant_questions": "user_id",
}


def fact(title=QUOTE, value="12", **fields):
    return {
        "ref": title, "type": "fact", "title": title, "body": QUOTE, "quote": QUOTE, "fact_kind": "number",
        "fact_value": value, "fact_unit": "days", "scope_text": "all staff", "effective_date": "", **fields,
    }


@pytest.fixture
def company(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    row = Company(slug="acme", name="Acme")
    db.add(row)
    db.commit()
    return row


def upload(db, company, user_id=None, data=TEXT.encode()):
    document = ingestion.create_document(
        db, company.id, user_id, title="Handbook", data=data, suffix=".md", visibility="internal", department_id=None,
        language="en", effective_date=None,
    )
    job = ingestion.start_job(db, document.id)
    ingestion.run_job(job.id)
    db.commit()
    return document, db.get(KbIngestionJob, job.id)


def test_migrations_from_empty_match_the_models_with_type_comparison_on():
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diffs = compare_metadata(context, Base.metadata)
    assert diffs == []


def test_there_is_one_migration_head():
    assert ScriptDirectory.from_config(alembic_config()).get_heads() == ["0006_hiring"]


def test_foreign_keys_to_users_set_null_on_delete():
    inspector = inspect(engine)
    for table, column in USER_COLUMNS.items():
        keys = [k for k in inspector.get_foreign_keys(table) if k["constrained_columns"] == [column]]
        assert [k["options"].get("ondelete") for k in keys] == ["SET NULL"], table


@pytest.mark.parametrize("bad", [
    {"fact_value": "1" * 256}, {"fact_unit": "u" * 51}, {"scope_text": "s" * 501}, {"title": "t" * 501},
    {"body": "가" * 30000},
])
def test_an_over_long_field_drops_the_item_and_not_the_job(db, company, bad):
    fake.enqueue("kb_extract", json.dumps({"nodes": [fact(**{"title": "Long", **bad}), fact("Kept")], "edges": []}))
    document, job = upload(db, company)
    assert (job.status, job.error, job.dropped_items, job.failed_chunks) == ("review", None, 1, 0)
    assert db.get(KbDocument, document.id).status == "review"
    assert [row.title for row in db.query(KbNode).filter_by(type="fact")] == ["Kept"]


def test_fields_at_their_limits_are_stored(db, company):
    item = fact("t" * 500, fact_unit="u" * 50, scope_text="s" * 500, fact_value="12" + " " * 3 + "d" * 250)
    fake.enqueue("kb_extract", json.dumps({"nodes": [item], "edges": []}))
    _, job = upload(db, company)
    assert job.dropped_items == 0
    node = db.query(KbNode).filter_by(type="fact").one()
    assert (len(node.title), len(node.fact_unit), len(node.scope_text), len(node.fact_value)) == (500, 50, 500, 255)


def test_seed_samples_auto_approve_publishes_every_document(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    results = seed.seed_samples(auto_approve=True)
    db.commit()
    assert all(result["dropped_items"] == 0 for result in results)
    assert all(result["open_conflicts"] == 4 for result in results)
    statuses = [row.status for row in db.query(KbDocument)]
    assert len(statuses) == sum(result["documents_created"] for result in results) > 0
    assert set(statuses) == {"published"}
    assert db.query(KbNode).filter_by(status="draft").count() == 0


def test_admin_can_delete_a_user_who_touched_the_brain(client, db, company):
    leaver = make_user(db, "leaver@example.test")
    stays = make_user(db, "stays@example.test")
    make_user(db, "root@example.test", role="admin")
    db.add_all([
        CompanyMember(company_id=company.id, user_id=leaver.id, role="hr"),
        CompanyMember(company_id=company.id, user_id=stays.id, role="hr"),
    ])
    db.commit()
    leaver_id = leaver.id

    fake.enqueue("kb_extract", json.dumps({"nodes": [fact()], "edges": []}))
    document, _ = upload(db, company, leaver_id)
    node = db.query(KbNode).filter_by(type="fact").one()
    node.status, node.approved_by = "published", leaver_id
    other = KbNode(
        company_id=company.id, type="fact", title="Other", body="", language="en", visibility="internal", status="draft",
    )
    db.add(other)
    db.flush()
    conflict = KbConflict(
        company_id=company.id, node_a_id=node.id, node_b_id=other.id, status="dismissed", resolved_by=leaver_id,
    )
    question = AssistantQuestion(
        company_id=company.id, user_id=leaver_id, audience="hr", question="How many days?", language="en",
        answered=False, state="not_found", resolved=False,
    )
    db.add_all([conflict, question])
    db.commit()

    response = client.delete(f"/api/admin/users/{leaver_id}", headers=auth_header("root@example.test"))
    assert response.status_code == 200, response.text

    db.commit()
    db.expire_all()
    assert db.get(User, leaver_id) is None
    assert db.get(KbDocument, document.id).uploaded_by is None
    assert db.get(KbNode, node.id).approved_by is None
    assert db.get(KbConflict, conflict.id).resolved_by is None
    kept = db.get(AssistantQuestion, question.id)
    assert kept is not None and kept.user_id is None


def test_retry_failed_records_and_clears_chunk_ids_as_json(client, db, company):
    user = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    fake.enqueue("kb_extract", "not json")
    fake.enqueue("kb_extract", "still not json")
    _, job = upload(db, company, user.id)
    assert len(job.failed_chunk_ids) == 1 and job.failed_chunks == 1

    fake.enqueue("kb_extract", json.dumps({"nodes": [fact()], "edges": []}))
    url = f"/api/companies/{company.id}/kb/jobs/{job.id}/retry-failed"
    assert client.post(url, headers=auth_header("hr@example.test")).status_code == 200
    db.commit()
    db.expire_all()
    job = db.get(KbIngestionJob, job.id)
    assert job.failed_chunk_ids == [] and job.failed_chunks == 0
    assert db.query(KbNode).filter_by(type="fact").count() == 1
    assert client.post(url, headers=auth_header("hr@example.test")).status_code == 409


def test_retry_and_unpublish_take_their_row_locks_on_mysql(client, db, company):
    user = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    headers = auth_header("hr@example.test")
    fake.enqueue("kb_extract", json.dumps({"nodes": [fact()], "edges": []}))
    document, job = upload(db, company, user.id)
    base = f"/api/companies/{company.id}/kb"
    assert client.post(f"{base}/jobs/{job.id}/retry", headers=headers).status_code == 409
    response = client.post(f"{base}/documents/{document.id}/unpublish", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["document"]["status"] == "withdrawn"
    assert client.post(f"{base}/documents/{document.id}/unpublish", headers=headers).status_code == 409
