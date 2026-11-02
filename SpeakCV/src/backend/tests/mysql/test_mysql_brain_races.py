"""Two real sessions racing on the Company Brain's row locks. Each test forces the order with a hook, so it cannot pass by
luck of timing: the second session either runs to its end inside the first one's window, or is seen to be waiting."""
import os
import threading
from types import SimpleNamespace

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs TEST_MYSQL_URL; run `make test-mysql`.", allow_module_level=True)

from fastapi.testclient import TestClient

from app.ai.providers import fake
from app.brain import contradiction, ingestion, review
from app.database.database import SessionLocal
from app.database.sql_models import (
    Company, CompanyMember, KbChunk, KbConflict, KbDocument, KbIngestionJob, KbNode, KbNodeSource,
)
from app.main import app
from tests.helpers import auth_header, make_user

BLOCKED_FOR = 1.0  # long enough to see a session waiting on a lock, well under innodb_lock_wait_timeout


def decision(**fields):
    return SimpleNamespace(**{**dict(action="edit", node_id=None, into_node_id=None, document_id=None, title=None,
                                     body=None, visibility=None, fact_value=None, fact_unit=None, scope_text=None),
                              **fields})


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    document = KbDocument(company_id=company.id, title="D", language="en", visibility="public", status="review")
    db.add(document)
    db.commit()
    chunk = KbChunk(company_id=company.id, document_id=document.id, position=0, page=1, text="x")
    db.add(chunk)
    db.commit()

    def node(value):
        row = KbNode(company_id=company.id, type="fact", title="Leave", body="b", language="en", visibility="public",
                     status="draft", fact_kind="number", fact_value=value, fact_unit="days")
        db.add(row)
        db.commit()
        db.add(KbNodeSource(node_id=row.id, chunk_id=chunk.id, quote="q"))
        db.commit()
        return row

    return SimpleNamespace(company_id=company.id, document_id=document.id, node=node)


def fresh_look(model, row_id):
    session = SessionLocal()
    try:
        return session.get(model, row_id)
    finally:
        session.close()


def in_other_session(work):
    session = SessionLocal()
    try:
        return work(session)
    finally:
        session.close()


def run_first_inside(monkeypatch, work):
    """Runs `work` in its own session, to its commit, at the moment the decision has read its sources but locked nothing."""
    real = review.documents_of_nodes
    fired = []

    def hook(*args, **kwargs):
        if not fired:
            fired.append(True)
            in_other_session(work)
        return real(*args, **kwargs)

    monkeypatch.setattr(review, "documents_of_nodes", hook)


def start_while_holding_locks(monkeypatch, work):
    """Starts `work` once the decision holds its locks, and checks that it waits for them. Returns a way to wait for it."""
    real = review.settle_edges
    fired, finished, outcome = [], threading.Event(), {}

    def run():
        try:
            outcome["result"] = in_other_session(work)
        except Exception as exc:  # noqa: BLE001 - the test reads it
            outcome["error"] = exc
        finally:
            finished.set()

    def hook(*args, **kwargs):
        if not fired:
            fired.append(True)
            threading.Thread(target=run, daemon=True).start()
            assert finished.wait(BLOCKED_FOR) is False, f"did not wait for the lock: {outcome}"
        return real(*args, **kwargs)

    monkeypatch.setattr(review, "settle_edges", hook)

    def wait():
        assert finished.wait(30)
        return outcome

    return wait


def unpublish_and_commit(company_id, document_id):
    def work(session):
        counts = review.unpublish_document(session, company_id, document_id)
        session.commit()
        return counts

    return work


def test_a_withdrawal_that_commits_first_stops_a_late_accept(db, world, monkeypatch):
    node_id = world.node("15").id
    db.commit()
    run_first_inside(monkeypatch, unpublish_and_commit(world.company_id, world.document_id))
    with pytest.raises(review.ReviewError) as refused:
        review.apply_decisions(db, world.company_id, None, [decision(action="accept", node_id=node_id)])
    assert refused.value.status_code == 409
    db.rollback()
    assert fresh_look(KbDocument, world.document_id).status == "withdrawn"
    assert fresh_look(KbNode, node_id).status == "rejected"


def test_a_withdrawal_arriving_during_an_accept_waits_and_then_undoes_it(db, world, monkeypatch):
    node_id = world.node("15").id
    db.commit()
    wait = start_while_holding_locks(monkeypatch, unpublish_and_commit(world.company_id, world.document_id))
    review.apply_decisions(db, world.company_id, None, [decision(action="accept", node_id=node_id)])
    db.commit()
    outcome = wait()
    assert "error" not in outcome and outcome["result"]["rejected_nodes"] == 1
    assert fresh_look(KbDocument, world.document_id).status == "withdrawn"
    assert fresh_look(KbNode, node_id).status == "rejected"


def test_a_stale_document_read_cannot_bring_a_withdrawn_document_back(db, world, monkeypatch):
    """The session has read the document as in review before anything else happens, as a request does."""
    node_id = world.node("15").id
    assert db.get(KbDocument, world.document_id).status == "review"
    run_first_inside(monkeypatch, unpublish_and_commit(world.company_id, world.document_id))
    with pytest.raises(review.ReviewError):
        review.apply_decisions(db, world.company_id, None, [decision(action="reject", node_id=node_id)])
    db.rollback()
    assert fresh_look(KbDocument, world.document_id).status == "withdrawn"


def conflict_of(db, world):
    a, b = world.node("15"), world.node("12")
    conflict = KbConflict(company_id=world.company_id, node_a_id=a.id, node_b_id=b.id, status="open")
    db.add(conflict)
    db.commit()
    return a.id, b.id, conflict.id


def resolve_keeping_a(conflict_id):
    def work(session):
        return contradiction.resolve(session, session.get(KbConflict, conflict_id), "a", None).status

    return work


def test_a_resolve_that_commits_first_stops_a_late_accept_of_the_loser(db, world, monkeypatch):
    a_id, b_id, conflict_id = conflict_of(db, world)
    db.commit()
    run_first_inside(monkeypatch, resolve_keeping_a(conflict_id))
    with pytest.raises(review.ReviewError) as refused:
        review.apply_decisions(db, world.company_id, None, [decision(action="accept", node_id=b_id)])
    assert refused.value.status_code == 409
    db.rollback()
    assert fresh_look(KbNode, b_id).status == "superseded"
    assert fresh_look(KbConflict, conflict_id).status == "resolved"


def test_a_resolve_arriving_during_an_accept_waits_and_then_supersedes_it(db, world, monkeypatch):
    a_id, b_id, conflict_id = conflict_of(db, world)
    db.commit()
    wait = start_while_holding_locks(monkeypatch, resolve_keeping_a(conflict_id))
    review.apply_decisions(db, world.company_id, None, [decision(action="accept", node_id=b_id)])
    db.commit()
    outcome = wait()
    assert outcome.get("result") == "resolved", outcome
    assert fresh_look(KbNode, b_id).status == "superseded"
    assert fresh_look(KbConflict, conflict_id).resolution == "a"


def test_two_accepts_of_one_documents_last_drafts_publish_it(db, world, monkeypatch):
    """The second accept's snapshot predates the first one's commit, and must not see a draft that is gone."""
    first, second = world.node("15").id, world.node("12").id
    assert db.get(KbDocument, world.document_id).status == "review"

    def accept_other(session):
        review.apply_decisions(session, world.company_id, None, [decision(action="accept", node_id=second)])
        session.commit()

    run_first_inside(monkeypatch, accept_other)
    review.apply_decisions(db, world.company_id, None, [decision(action="accept", node_id=first)])
    db.commit()
    assert fresh_look(KbDocument, world.document_id).status == "published"


@pytest.fixture
def hr(db, world):
    user = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=world.company_id, user_id=user.id, role="hr"))
    db.commit()
    return auth_header("hr@example.test")


def post_in_thread(url, headers, results):
    def run():
        with TestClient(app) as client:
            results.append(client.post(url, headers=headers).status_code)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


@pytest.mark.parametrize("route,hook_name,document_status,job_fields", [
    ("retry", "clear_document_output", "failed", {"status": "failed"}),
    ("retry-failed", "start_failed_retry", "review",
     {"status": "review", "failed_chunks": 1, "failed_chunk_ids": [1]}),
])
def test_retry_against_retry_of_one_job_runs_once(client, db, world, hr, monkeypatch, route, hook_name, document_status,
                                                  job_fields):
    job = KbIngestionJob(document_id=world.document_id, progress=100, **job_fields)
    db.add(job)
    db.get(KbDocument, world.document_id).status = document_status
    db.commit()
    job_id = job.id
    url = f"/api/companies/{world.company_id}/kb/jobs/{job_id}/{route}"
    monkeypatch.setattr(ingestion, "run_job", lambda *_: None)
    monkeypatch.setattr(ingestion, "run_failed_retry", lambda *_: None)
    real = getattr(ingestion, hook_name)
    results, threads = [], []

    def hook(*args, **kwargs):
        if not threads:
            threads.append(post_in_thread(url, hr, results))
            threads[0].join(BLOCKED_FOR)
            assert threads[0].is_alive(), f"the second retry did not wait for the lock: {results}"
        return real(*args, **kwargs)

    monkeypatch.setattr(ingestion, hook_name, hook)
    first = client.post(url, headers=hr)
    threads[0].join(30)
    assert first.status_code == 200, first.text
    assert results == [409]
    db.commit()
    jobs = db.query(KbIngestionJob).filter_by(document_id=world.document_id).count()
    assert jobs == (2 if route == "retry" else 1)


def test_retry_failed_on_an_old_job_is_refused(client, db, world, hr):
    old = KbIngestionJob(document_id=world.document_id, status="review", progress=100, failed_chunks=1, failed_chunk_ids=[1])
    db.add(old)
    db.commit()
    db.add(KbIngestionJob(document_id=world.document_id, status="review", progress=100))
    db.commit()
    url = f"/api/companies/{world.company_id}/kb/jobs/{old.id}/retry-failed"
    assert client.post(url, headers=hr).status_code == 409


def test_unpublishing_twice_on_mysql_is_refused_the_second_time(client, db, world, hr):
    fake.reset()
    base = f"/api/companies/{world.company_id}/kb/documents/{world.document_id}/unpublish"
    response = client.post(base, headers=hr)
    assert response.status_code == 200 and response.json()["document"]["status"] == "withdrawn"
    assert client.post(base, headers=hr).status_code == 409
