import json

import pytest

from app.ai.providers import fake
from app.ai.types import AIError
from app.brain import contradiction, ingestion, vectors
from app.brain.contradiction import normalise_fact_value
from app.database.sql_models import Company, CompanyMember, KbConflict, KbIngestionJob, KbNode
from tests.helpers import auth_header, make_user


@pytest.mark.parametrize("kind,raw,expected", [
    ("number", "1,000", "1000"), ("number", "12", "12"), ("number", "12.0", "12"),
    ("number", "12 ngày", "12"), ("number", "abc", None), ("number", "12,5", "12.5"),
    ("date", "2026-01-31", "2026-01-31"), ("date", "31/01/2026", "2026-01-31"), ("date", "2026년 1월 31일", "2026-01-31"),
    ("boolean", "yes", "true"), ("boolean", "có", "true"), ("boolean", "예", "true"),
    ("boolean", "no", "false"), ("boolean", "không", "false"), ("boolean", "아니요", "false"),
    ("boolean", "maybe", None), ("date", "soon", None),
])
def test_normalise_fact_value(kind, raw, expected):
    assert normalise_fact_value(kind, raw) == expected


def conflict_answer(same_topic=True, same_scope=True):
    return json.dumps({"same_topic": same_topic, "same_scope": same_scope})


@pytest.fixture
def company(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    fake.reset()
    row = Company(slug="acme", name="Acme")
    db.add(row)
    db.commit()
    return row


def vec(*values):
    return vectors.encode(list(values) + [0.0] * (4 - len(values)))


def node(db, company, value="12", kind="number", status="published", embedding=None, model="fake", title="Leave"):
    row = KbNode(
        company_id=company.id, type="fact", title=title, body=f"{title} {value}", language="en", visibility="internal",
        status=status, fact_kind=kind, fact_value=value, fact_unit="days", scope_text="all staff",
        embedding=embedding if embedding is not None else vec(1, 0), embedding_model=model, embedding_dim=4,
    )
    db.add(row)
    db.commit()
    return row


def conflicts(db):
    db.expire_all()
    return db.query(KbConflict).all()


def test_differing_values_open_one_conflict(db, company):
    old, new = node(db, company, "12"), node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", conflict_answer())
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 1
    row = db.query(KbConflict).one()
    assert (row.status, row.node_a_id, row.node_b_id, row.company_id) == ("open", old.id, new.id, company.id)


def test_check_is_given_the_facts_as_delimited_data(db, company):
    node(db, company, "12")
    new = node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", conflict_answer())
    contradiction.check_new_facts(db, company.id, [new.id])
    prompt = fake.last_messages()[-1]["content"]
    assert prompt.count("<fact>") == 2 and "15" in prompt
    assert "data" in fake.last_system().lower()


def test_equal_normalised_values_make_no_ai_call(db, company):
    node(db, company, "12")
    new = node(db, company, "12.0", status="draft")
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert fake.last_messages() == []
    assert conflicts(db) == []


def test_different_scope_opens_nothing(db, company):
    node(db, company, "12")
    new = node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", conflict_answer(same_scope=False))
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert conflicts(db) == []


def test_different_topic_opens_nothing(db, company):
    node(db, company, "12")
    new = node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", conflict_answer(same_topic=False))
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0


def test_different_fact_kind_is_never_compared(db, company):
    node(db, company, "12", kind="number")
    new = node(db, company, "2026-01-31", kind="date", status="draft")
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert fake.last_messages() == []


def test_low_cosine_is_never_compared(db, company):
    node(db, company, "12", embedding=vec(1, 0))
    new = node(db, company, "15", status="draft", embedding=vec(0, 1))
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert fake.last_messages() == []


def test_different_embedding_models_are_never_compared(db, company):
    node(db, company, "12", model="other")
    new = node(db, company, "15", status="draft")
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert fake.last_messages() == []


def test_other_company_facts_are_never_compared(db, company):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    node(db, other, "12")
    new = node(db, company, "15", status="draft")
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert fake.last_messages() == []


def test_existing_pair_is_not_opened_twice_in_either_order(db, company):
    old, new = node(db, company, "12"), node(db, company, "15", status="draft")
    db.add(KbConflict(company_id=company.id, node_a_id=new.id, node_b_id=old.id, status="dismissed"))
    db.commit()
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert fake.last_messages() == []
    assert len(conflicts(db)) == 1


def test_two_new_facts_make_one_conflict(db, company):
    first, second = node(db, company, "12", status="draft"), node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", conflict_answer())
    assert contradiction.check_new_facts(db, company.id, [first.id, second.id]) == 1


def test_rejected_and_superseded_facts_are_ignored(db, company):
    node(db, company, "12", status="rejected")
    node(db, company, "13", status="superseded")
    new = node(db, company, "15", status="draft")
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 0
    assert fake.last_messages() == []


def test_unparseable_value_still_goes_to_the_ai_check(db, company):
    node(db, company, "twelve")
    new = node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", conflict_answer())
    assert contradiction.check_new_facts(db, company.id, [new.id]) == 1


def make_open(db, company, a_status="published", b_status="draft"):
    a, b = node(db, company, "12", status=a_status), node(db, company, "15", status=b_status)
    row = KbConflict(company_id=company.id, node_a_id=a.id, node_b_id=b.id, status="open")
    db.add(row)
    db.commit()
    return a, b, row


def test_resolve_a_supersedes_b_and_bumps_kb_version(db, company):
    a, b, row = make_open(db, company)
    user = make_user(db, "hr@acme.test")
    before = db.get(Company, company.id).kb_version
    contradiction.resolve(db, row, "a", user.id)
    db.expire_all()
    row = db.get(KbConflict, row.id)
    assert (row.status, row.resolution, row.resolved_by) == ("resolved", "a", user.id)
    assert row.resolved_at is not None
    assert db.get(KbNode, b.id).status == "superseded" and db.get(KbNode, a.id).status == "published"
    assert db.get(Company, company.id).kb_version > before


def test_resolve_b_supersedes_a(db, company):
    a, b, row = make_open(db, company)
    user = make_user(db, "hr@acme.test")
    contradiction.resolve(db, row, "b", user.id)
    db.expire_all()
    assert db.get(KbNode, a.id).status == "superseded" and db.get(KbNode, b.id).status == "draft"


def test_resolve_different_scope_leaves_nodes_alone(db, company):
    a, b, row = make_open(db, company)
    user = make_user(db, "hr@acme.test")
    contradiction.resolve(db, row, "different_scope", user.id)
    db.expire_all()
    row = db.get(KbConflict, row.id)
    assert (row.status, row.resolution) == ("dismissed", "different_scope")
    assert db.get(KbNode, a.id).status == "published" and db.get(KbNode, b.id).status == "draft"


def test_rejecting_a_node_dismisses_its_open_conflicts(db, company):
    a, b, open_row = make_open(db, company)
    c = node(db, company, "20")
    other = KbConflict(company_id=company.id, node_a_id=a.id, node_b_id=c.id, status="open")
    db.add(other)
    db.commit()
    contradiction.on_node_rejected(db, b.id)
    db.commit()
    db.expire_all()
    row = db.get(KbConflict, open_row.id)
    assert (row.status, row.resolution) == ("dismissed", "node_rejected")
    assert db.get(KbConflict, other.id).status == "open"


def test_ai_error_propagates_from_the_check_and_leaves_no_conflict(db, company):
    node(db, company, "12")
    new = node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", "not json")
    fake.enqueue("kb_conflict_check", "still not json")
    with pytest.raises(AIError):
        contradiction.check_new_facts(db, company.id, [new.id])
    assert conflicts(db) == []


def test_ingestion_wrapper_turns_ai_error_into_a_failure_count(db, company):
    node(db, company, "12")
    new = node(db, company, "15", status="draft")
    fake.enqueue("kb_conflict_check", "not json")
    fake.enqueue("kb_conflict_check", "still not json")
    assert ingestion._check_contradictions(db, company.id, [new.id]) == 1
    assert conflicts(db) == []


# API

@pytest.fixture
def hr(db, company):
    user = make_user(db, "hr@acme.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    return auth_header("hr@acme.test")


def test_list_open_conflicts(db, company, client, hr):
    make_open(db, company)
    body = client.get(f"/api/companies/{company.id}/kb/conflicts", headers=hr).json()
    assert len(body) == 1 and body[0]["node_a"]["fact_value"] == "12" and body[0]["node_b"]["fact_value"] == "15"


def test_resolve_route_and_closed_conflict_is_409(db, company, client, hr):
    _, _, row = make_open(db, company)
    url = f"/api/companies/{company.id}/kb/conflicts/{row.id}/resolve"
    assert client.post(url, json={"action": "bogus"}, headers=hr).status_code == 422
    assert client.post(url, json={"action": "a"}, headers=hr).status_code == 200
    assert client.post(url, json={"action": "b"}, headers=hr).status_code == 409


def test_other_company_conflict_is_404(db, company, client, hr):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    _, _, row = make_open(db, other)
    url = f"/api/companies/{company.id}/kb/conflicts/{row.id}/resolve"
    assert client.post(url, json={"action": "a"}, headers=hr).status_code == 404


def test_non_hr_member_is_forbidden(db, company, client):
    user = make_user(db, "emp@acme.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="employee"))
    db.commit()
    assert client.get(f"/api/companies/{company.id}/kb/conflicts", headers=auth_header("emp@acme.test")).status_code == 403


# ingestion end to end

def extraction(value, quote, type_="fact"):
    item = {"ref": "Annual leave", "type": type_, "title": "Annual leave", "body": quote, "quote": quote,
            "fact_kind": "number", "fact_value": value, "fact_unit": "days", "scope_text": "all staff", "effective_date": ""}
    return json.dumps({"nodes": [item], "edges": []})


def upload(db, company, text):
    document = ingestion.create_document(
        db, company.id, None, title="Handbook", data=text.encode(), suffix=".md",
        visibility="internal", department_id=None, language="en", effective_date=None,
    )
    job = ingestion.start_job(db, document.id)
    ingestion.run_job(job.id)
    db.expire_all()
    return db.get(KbIngestionJob, job.id)


def test_second_document_with_a_differing_fact_opens_a_conflict(db, company):
    fake.enqueue("kb_extract", extraction("12", "12 days of annual leave"))
    upload(db, company, "# Leave\n\nEmployees receive 12 days of annual leave.")
    db.query(KbNode).filter_by(title="Annual leave").update({"status": "published"})
    db.commit()
    # a different node type keeps the same title from merging into the first node
    fake.enqueue("kb_extract", extraction("15", "15 days of annual leave", "policy"))
    fake.enqueue("kb_conflict_check", conflict_answer())
    job = upload(db, company, "# Leave\n\nStaff receive 15 days of annual leave.")
    assert job.status == "review" and job.failed_chunks == 0
    assert db.query(KbConflict).filter_by(status="open").count() == 1


def test_ai_error_during_ingestion_counts_a_failed_chunk(db, company):
    fake.enqueue("kb_extract", extraction("12", "12 days of annual leave"))
    upload(db, company, "# Leave\n\nEmployees receive 12 days of annual leave.")
    db.query(KbNode).filter_by(title="Annual leave").update({"status": "published"})
    db.commit()
    fake.enqueue("kb_extract", extraction("15", "15 days of annual leave", "policy"))
    fake.enqueue("kb_conflict_check", "not json")
    fake.enqueue("kb_conflict_check", "not json")
    job = upload(db, company, "# Leave\n\nStaff receive 15 days of annual leave.")
    assert job.status == "review" and job.failed_chunks == 1
    assert conflicts(db) == []
