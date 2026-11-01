"""Defects SQLite cannot show: column lengths, REPEATABLE READ, foreign keys, and migrated column types.

The pipeline writes in its own session. Under REPEATABLE READ a session that is mid-transaction will not see that,
so these tests end their transaction (db.commit()) before reading another session's work.
"""
import json
import os
import threading
from datetime import timedelta

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
    Application, AssistantQuestion, AuditLog, Company, CompanyMember, Consent, Job, JobChannelLink, KbConflict, KbDocument,
    KbIngestionJob, KbNode, Notification, User, VoiceSession, VoiceTurn,
)
from app.database.database import SessionLocal  # noqa: E402
from app.hiring import analysis, consents, notify, recordings, retention, voice  # noqa: E402
from tests.helpers import auth_header, make_user  # noqa: E402

TEXT = "# Leave\n\nEmployees receive 12 days of annual leave each year."
QUOTE = "12 days of annual leave"
USER_COLUMNS = {
    "kb_documents": "uploaded_by", "kb_nodes": "approved_by", "kb_conflicts": "resolved_by",
    "assistant_questions": "user_id", "jobs": "created_by", "applications": "candidate_user_id",
    "voice_sessions": "owner_user_id", "consents": "user_id", "audit_log": "actor_user_id",
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


def hiring_world(db, company, email="candidate@example.test", **columns):
    user = make_user(db, email)
    job = db.query(Job).filter_by(company_id=company.id).first()
    if job is None:
        job = Job(company_id=company.id, title="Backend", slug="acme-backend", description="d", status="published",
                  interview_languages=["en"])
        db.add(job)
        db.flush()
    fields = dict(company_id=company.id, job_id=job.id, candidate_user_id=user.id, alias=f"#M{user.id}",
                  stage="ready_for_hr", cv_status="not_met")
    application = Application(**{**fields, **columns})
    db.add(application)
    db.commit()
    return user, job, application


def running_session(db, company, user, application):
    session = voice.create_session(db, company_id=company.id, purpose="screening", owner_user_id=user.id, language="en",
                                   plan=[{"text": "A question", "source": "role"}], application_id=application.id)
    application.stage = "session_in_progress"
    db.commit()
    return session


def test_migrated_hiring_columns_hold_what_the_fixes_write():
    inspector = inspect(engine)
    sessions = {column["name"]: column for column in inspector.get_columns("voice_sessions")}
    assert sessions["active_seconds"]["nullable"] is False and sessions["active_seconds"]["default"].strip("'") == "0"
    assert sessions["last_activity_at"]["nullable"] is True
    notifications = {column["name"]: column for column in inspector.get_columns("notifications")}
    assert notifications["application_id"]["nullable"] is True
    assert {column["name"] for column in inspector.get_columns("consents")} >= {"language"}
    constraints = inspector.get_unique_constraints("job_channel_links")
    assert ["job_id", "channel"] in [item["column_names"] for item in constraints]


def test_admin_delete_needs_anonymizing_first_and_then_keeps_the_rows(client, db, company):
    make_user(db, "root@example.test", role="admin")
    headers = auth_header("root@example.test")
    hr = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    db.commit()
    user, job, application = hiring_world(db, company, hr_decision="approved", hr_decided_by=hr.id)
    user_id, application_id = user.id, application.id
    session = VoiceSession(company_id=company.id, purpose="screening", application_id=application_id, owner_user_id=user_id,
                           language="en", status="completed")
    consent = consents.record(db, user_id, company.id, application_id, "cv_processing", consents.VERSION)
    linked = notify.enqueue(db, company.id, user_id, "decision", "en", "Update", "Body", application_id=application_id)
    db.add(session)
    db.add(AuditLog(company_id=company.id, actor_user_id=user_id, action="application_withdrawn", target_type="application",
                    target_id=application_id))
    db.commit()
    consent_id, session_id, linked_id = consent.id, session.id, linked.id

    refused = client.delete(f"/api/admin/users/{user_id}", headers=headers)
    assert refused.status_code == 409 and "anonymize" in refused.json()["detail"].lower()
    db.commit()
    db.expire_all()
    assert db.get(User, user_id) is not None

    db.expire_all()
    retention.anonymize_application(db, db.get(Application, application_id), trigger=retention.TRIGGER_RETENTION)
    # A row the anonymizing has no link to must not stop the delete: notifications.user_id cannot be NULL.
    notify.enqueue(db, company.id, user_id, "reminder", "en", "Hello", "Body")
    db.commit()

    done = client.delete(f"/api/admin/users/{user_id}", headers=headers)
    assert done.status_code == 200, done.text
    db.commit()
    db.expire_all()
    assert db.get(User, user_id) is None
    kept = db.get(Application, application_id)
    assert kept is not None and kept.candidate_user_id is None and kept.hr_decision == "approved"
    assert db.get(VoiceSession, session_id).owner_user_id is None
    assert db.get(Consent, consent_id).user_id is None
    assert db.get(Notification, linked_id) is None
    assert db.query(Notification).filter_by(user_id=user_id).count() == 0


def test_admin_delete_of_hr_staff_clears_their_links_and_keeps_the_rows(client, db, company):
    make_user(db, "root@example.test", role="admin")
    leaver = make_user(db, "leaver@example.test")
    stays = make_user(db, "stays@example.test")
    db.add_all([CompanyMember(company_id=company.id, user_id=leaver.id, role="hr"),
                CompanyMember(company_id=company.id, user_id=stays.id, role="hr")])
    db.commit()
    _, job, application = hiring_world(db, company, hr_decision="approved", hr_decided_by=leaver.id,
                                       cv_status_corrected_by=leaver.id)
    job.created_by = leaver.id
    db.add(AuditLog(company_id=company.id, actor_user_id=leaver.id, action="hr_decision", target_type="application",
                    target_id=application.id))
    db.commit()
    leaver_id, job_id, application_id = leaver.id, job.id, application.id

    response = client.delete(f"/api/admin/users/{leaver_id}", headers=auth_header("root@example.test"))
    assert response.status_code == 200, response.text
    db.commit()
    db.expire_all()
    kept = db.get(Application, application_id)
    assert kept.hr_decided_by is None and kept.cv_status_corrected_by is None and kept.hr_decision == "approved"
    assert db.get(Job, job_id).created_by is None
    assert db.query(AuditLog).filter_by(action="hr_decision", target_id=application_id).one().actor_user_id is None


def test_a_session_mid_transaction_counts_no_second_twice(db, company):
    """Under REPEATABLE READ the second reader holds an old snapshot, and must not add the same gap again."""
    user, _, application = hiring_world(db, company, stage="invited")
    session = running_session(db, company, user, application)
    session.active_seconds = 100
    session.last_activity_at = voice._now().replace(microsecond=0) - timedelta(seconds=60)  # MySQL would round it
    db.commit()
    session_id = session.id

    late = SessionLocal()
    early = SessionLocal()
    try:
        late_row = late.get(VoiceSession, session_id)
        assert late_row.active_seconds == 100  # this transaction's snapshot is now taken
        voice.current_state(early, early.get(VoiceSession, session_id))
        voice.current_state(late, late_row)
    finally:
        late.close()
        early.close()
    db.commit()
    db.expire_all()
    # 60 seconds, plus at most a few for the test itself: not 120.
    assert 160 <= db.get(VoiceSession, session_id).active_seconds <= 170


def test_a_deletion_during_transcription_is_seen_through_an_old_snapshot(db, company, tmp_path, monkeypatch):
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    user, _, application = hiring_world(db, company, stage="invited")
    session = running_session(db, company, user, application)
    session_id, application_id = session.id, application.id
    db.commit()

    monkeypatch.setattr(voice, "_transcribe", lambda audio, mime, language, company: _delete_and_transcribe(application_id))
    uploading = SessionLocal()
    try:
        with pytest.raises(voice.SessionGone):
            voice.submit_answer(uploading, uploading.get(VoiceSession, session_id), 1, b"an answer", "audio/webm")
    finally:
        uploading.close()
    db.commit()
    db.expire_all()
    turn = db.query(VoiceTurn).filter_by(session_id=session_id, position=1).one()
    assert turn.transcript is None and turn.audio_path is None
    assert list(tmp_path.rglob("*.webm")) == []


def test_a_deletion_waits_for_an_answer_being_stored_and_then_erases_it(db, company, tmp_path, monkeypatch):
    """Row locks for real: the deletion arrives while the audio is being written, waits, and takes the audio with it."""
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    user, _, application = hiring_world(db, company, stage="invited")
    session = running_session(db, company, user, application)
    session_id, application_id = session.id, application.id
    db.commit()
    real_save = recordings.save_turn_audio
    finished = threading.Event()

    def delete_like_the_route():
        other = SessionLocal()
        try:
            row = other.query(Application).filter_by(id=application_id).populate_existing().with_for_update().first()
            retention.anonymize_application(other, row, trigger=retention.TRIGGER_CANDIDATE)
        finally:
            other.close()
            finished.set()

    def save_while_a_deletion_arrives(*args):
        path = real_save(*args)
        threading.Thread(target=delete_like_the_route, daemon=True).start()
        assert finished.wait(0.5) is False  # the upload holds the lock, so the deletion cannot have finished
        return path

    monkeypatch.setattr(voice.recordings, "save_turn_audio", save_while_a_deletion_arrives)
    uploading = SessionLocal()
    try:
        voice.submit_answer(uploading, uploading.get(VoiceSession, session_id), 1, b"an answer", "audio/webm")
    finally:
        uploading.close()
    assert finished.wait(30)
    db.commit()
    db.expire_all()
    assert db.get(Application, application_id).anonymized_at is not None
    assert db.query(VoiceTurn).filter_by(session_id=session_id, position=1).one().transcript is None
    assert list(tmp_path.rglob("*.webm")) == []


def _delete_and_transcribe(application_id):
    other = SessionLocal()
    try:
        retention.anonymize_application(other, other.get(Application, application_id))
    finally:
        other.close()
    return None


def test_the_daily_sweep_and_startup_recovery_run_on_mysql(db, company, monkeypatch):
    calls = []
    monkeypatch.setattr(voice, "schedule_analysis", calls.append)
    user, _, silent = hiring_world(db, company, stage="invited")
    session = running_session(db, company, user, silent)
    session.last_activity_at = voice._now() - timedelta(hours=25)
    db.commit()
    silent_id, session_id = silent.id, session.id

    assert voice.sweep_abandoned(db) == 1
    db.commit()
    db.expire_all()
    assert db.get(VoiceSession, session_id).status == voice.ABANDONED
    assert db.get(Application, silent_id).stage == "ready_for_hr"
    assert calls == []

    _, _, stuck = hiring_world(db, company, "stuck@example.test", stage="analyzing", analysis_status="running")
    stuck_id = stuck.id
    db.commit()
    assert analysis.requeue_interrupted() == [stuck_id]
    db.commit()
    db.expire_all()
    assert db.get(Application, stuck_id).stage == "session_completed"


def test_a_second_channel_with_the_same_name_is_refused_on_mysql(client, db, company):
    hr = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    db.commit()
    _, job, _ = hiring_world(db, company)
    job_id, company_id = job.id, company.id
    url = f"/api/companies/{company_id}/jobs/{job_id}/channels"
    first = client.post(url, json={"channels": ["linkedin"]}, headers=auth_header("hr@example.test"))
    second = client.post(url, json={"channels": ["linkedin"]}, headers=auth_header("hr@example.test"))
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()[0]["token"] == second.json()[0]["token"]
    db.commit()
    assert db.query(JobChannelLink).filter_by(job_id=job_id).count() == 1
