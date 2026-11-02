import asyncio
import importlib
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, String, Text, select

from app.core import storage
from app.database import models_hiring
from app.database.database import Base
from app.database.sql_models import (
    Application, AuditLog, Company, CompanyMember, Consent, CultureNote, CvClaim, Job, JobRequirement, KbNode,
    Notification, RejectionFeedback, RequirementResult, ScreeningCache, VoiceSession, VoiceTurn,
)
from app.hiring import notify, retention
from tests.helpers import auth_header, make_user

CANARY = "CANARYSECRET"
CANDIDATE = "candidate@example.test"
OTHER = "other@example.test"
HR = "hr@example.test"
RETENTION_DAYS = 30


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def days_ago(days):
    return utcnow() - timedelta(days=days)


@pytest.fixture(autouse=True)
def recordings(tmp_path, monkeypatch):
    """Task 5 owns app.hiring.recordings. This stands in for it, with the same signatures, until that module exists."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path / "recordings"))
    try:
        return importlib.import_module("app.hiring.recordings")
    except ImportError:
        pass

    root = tmp_path / "recordings"

    def save_turn_audio(company_id, owner_key, position, data, suffix):
        path = root / str(company_id) / str(owner_key) / f"{position}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(root))

    def delete(path):
        (root / path).unlink(missing_ok=True)

    stand_in = types.ModuleType("app.hiring.recordings")
    stand_in.save_turn_audio = save_turn_audio
    stand_in.read = lambda path: (root / path).read_bytes()
    stand_in.delete = delete
    monkeypatch.setitem(sys.modules, "app.hiring.recordings", stand_in)
    return stand_in


def audio_file(tmp_path, path) -> Path:
    return tmp_path / "recordings" / path


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme", default_locale="en", retention_days=RETENTION_DAYS)
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend Developer", slug="acme-backend", description="d", status="published",
              interview_languages=["en"])
    db.add(job)
    db.commit()
    requirement = JobRequirement(company_id=company.id, job_id=job.id, text="FastAPI", must_have=True, position=0)
    node = KbNode(company_id=company.id, type="value", title="Candor", body="b", language="en", visibility="public",
                  status="published")
    db.add_all([requirement, node])
    db.commit()
    hr = make_user(db, HR)
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    db.commit()
    return SimpleNamespace(
        company_id=company.id, job_id=job.id, requirement_id=requirement.id, node_id=node.id, hr_id=hr.id,
        candidate_id=make_user(db, CANDIDATE).id, other_id=make_user(db, OTHER).id,
    )


_aliases = iter(range(1, 100000))


def bare_application(db, world, **columns):
    fields = dict(
        company_id=world.company_id, job_id=world.job_id, alias=f"#A{next(_aliases)}",
        candidate_user_id=world.candidate_id, stage="ready_for_hr", created_at=days_ago(1),
    )
    application = Application(**{**fields, **columns})
    db.add(application)
    db.commit()
    return application


def full_application(db, world, **columns):
    """An application holding personal content in every place the model has one, on disk as well."""
    from app.hiring import recordings

    user_id = columns.get("candidate_user_id", world.candidate_id)
    blind_hash = columns.pop("cv_blind_hash", f"hash-{CANARY}")
    cv_path = storage.save_bytes(world.company_id, "cv", ".pdf", f"{CANARY} cv".encode())
    application = bare_application(
        db, world, cv_file_path=cv_path, cv_suffix=".pdf", cv_text_raw=f"{CANARY} raw", cv_text_blind=f"{CANARY} blind",
        cv_blind_hash=blind_hash, cv_status="not_met", interview_band="many", source_channel="linkedin",
        cv_status_reason=[{"requirement_id": world.requirement_id, "text": f"{CANARY} reason", "status": "not_found"}],
        cv_status_corrected_by=world.hr_id, cv_status_correction_reason=f"{CANARY} correction",
        processing_error=f"{CANARY} error", ai_suggestion=f"{CANARY} suggestion", withdraw_reason=f"{CANARY} withdraw",
        final_outcome="hired", is_simulated=True, analysis_status="done", **columns,
    )
    session = VoiceSession(company_id=world.company_id, purpose="screening", application_id=application.id,
                           owner_user_id=user_id, language="en", status="completed",
                           plan=[{"text": f"{CANARY} planned question"}])
    db.add(session)
    db.commit()
    audio_path = recordings.save_turn_audio(world.company_id, application.id, 0, f"{CANARY} audio".encode(), ".webm")
    turn = VoiceTurn(session_id=session.id, position=0, question_text=f"{CANARY} question", question_source="claim",
                     source_ref=f"{CANARY} ref", audio_path=audio_path, audio_seconds=12, transcript=f"{CANARY} transcript",
                     transcript_status="done")
    db.add(turn)
    db.commit()
    db.add_all([
        RequirementResult(application_id=application.id, requirement_id=world.requirement_id, source="cv", status="met",
                          quote=f"{CANARY} cv quote"),
        RequirementResult(application_id=application.id, requirement_id=world.requirement_id, source="interview",
                          status="evidence", quote=f"{CANARY} interview quote", voice_turn_id=turn.id),
        CvClaim(application_id=application.id, text=f"{CANARY} claim", quote=f"{CANARY} claim quote", status="explained",
                evidence_quote=f"{CANARY} evidence", voice_turn_id=turn.id),
        CultureNote(application_id=application.id, value_node_id=world.node_id, note=f"{CANARY} note",
                    quote=f"{CANARY} culture quote", voice_turn_id=turn.id),
        Consent(user_id=user_id, company_id=world.company_id, application_id=application.id, purpose="cv_processing",
                text_version="v1"),
        Notification(company_id=world.company_id, user_id=user_id, kind="invited", language="en",
                     subject="Your next step for Backend Developer", body=f"{CANARY} Backend Developer", status="pending"),
        ScreeningCache(blind_hash=blind_hash, job_id=world.job_id, job_version=1, prompt_version="p", model="m",
                       result={"claims": [{"text": f"{CANARY} cached"}]}),
        AuditLog(company_id=world.company_id, actor_user_id=user_id, action="application_withdrawn",
                 target_type="application", target_id=application.id),
    ])
    db.commit()
    return SimpleNamespace(application=application, id=application.id, cv_path=cv_path, audio_path=audio_path, turn=turn)


def fresh(db, application_id):
    db.rollback()
    db.expire_all()
    return db.get(Application, application_id)


def database_dump(db) -> str:
    db.rollback()
    rows = []
    for table in Base.metadata.sorted_tables:
        rows += [repr(tuple(row)) for row in db.execute(select(table)).all()]
    return "\n".join(rows)


def decided(world, days, decision="approved"):
    return {"hr_decision": decision, "hr_decided_at": days_ago(days), "hr_decided_by": world.hr_id}


# 1. Decided applications


def test_decided_after_the_retention_period_is_anonymized(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    assert retention.run(db) == 1
    assert fresh(db, item.id).anonymized_at is not None


def test_decided_within_the_retention_period_is_untouched(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS - 1))
    assert retention.run(db) == 0
    application = fresh(db, item.id)
    assert application.anonymized_at is None
    assert application.cv_text_raw == f"{CANARY} raw"
    assert storage.read_bytes(item.cv_path)


def test_each_company_uses_its_own_retention_days(db, world):
    other = Company(slug="long", name="Long", retention_days=RETENTION_DAYS * 10)
    db.add(other)
    db.commit()
    job = Job(company_id=other.id, title="Long", slug="long-job", description="d", status="published", interview_languages=[])
    db.add(job)
    db.commit()
    kept = bare_application(db, world, company_id=other.id, job_id=job.id, hr_decision="rejected",
                            hr_decided_at=days_ago(RETENTION_DAYS + 1))
    assert retention.run(db) == 0
    assert fresh(db, kept.id).anonymized_at is None


def test_an_old_application_decided_recently_is_untouched(db, world):
    item = bare_application(db, world, created_at=days_ago(400), **decided(world, 1))
    assert retention.run(db) == 0
    assert fresh(db, item.id).anonymized_at is None


# 2. Undecided applications


def test_undecided_is_anonymized_180_days_after_submission(db, world):
    item = bare_application(db, world, created_at=days_ago(181))
    assert retention.run(db) == 1
    assert fresh(db, item.id).anonymized_at is not None


def test_undecided_is_not_anonymized_at_179_days(db, world):
    item = bare_application(db, world, created_at=days_ago(179))
    assert retention.run(db) == 0
    assert fresh(db, item.id).anonymized_at is None


def test_an_extension_keeps_a_due_application_for_block_5(db, world, monkeypatch):
    item = bare_application(db, world, created_at=days_ago(181))
    monkeypatch.setattr(retention, "has_extension", lambda _db, application: application.id == item.id)
    assert retention.run(db) == 0
    assert fresh(db, item.id).anonymized_at is None


def test_has_extension_is_false_for_now(db, world):
    assert retention.has_extension(db, bare_application(db, world)) is False


# 3. What goes


def test_anonymizing_deletes_the_cv_file_and_the_audio_files(db, world, tmp_path):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    assert audio_file(tmp_path, item.audio_path).exists()
    retention.run(db)
    with pytest.raises(FileNotFoundError):
        storage.read_bytes(item.cv_path)
    assert not audio_file(tmp_path, item.audio_path).exists()


def test_audio_from_every_session_of_the_application_is_deleted(db, world, tmp_path):
    from app.hiring import recordings

    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    restarted = VoiceSession(company_id=world.company_id, purpose="screening", application_id=item.id,
                             owner_user_id=world.candidate_id, language="en")
    db.add(restarted)
    db.commit()
    second = recordings.save_turn_audio(world.company_id, item.id, 5, b"second session", ".webm")
    db.add(VoiceTurn(session_id=restarted.id, position=5, question_text="q", question_source="role", audio_path=second))
    db.commit()
    retention.run(db)
    assert not audio_file(tmp_path, second).exists()
    assert db.query(VoiceSession).filter_by(id=restarted.id).one().owner_user_id is None


def test_anonymizing_clears_every_personal_column(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    retention.run(db)
    application = fresh(db, item.id)
    for column in ("cv_text_raw", "cv_text_blind", "cv_blind_hash", "cv_file_path", "cv_status_reason",
                   "cv_status_correction_reason", "candidate_user_id", "withdraw_reason", "ai_suggestion", "processing_error"):
        assert getattr(application, column) is None, column
    assert all(row.quote is None for row in db.query(RequirementResult).filter_by(application_id=item.id))
    claim = db.query(CvClaim).filter_by(application_id=item.id).one()
    assert (claim.text, claim.quote, claim.evidence_quote) == ("", "", None)
    note = db.query(CultureNote).filter_by(application_id=item.id).one()
    assert (note.note, note.quote) == ("", "")
    turn = db.query(VoiceTurn).filter_by(id=item.turn.id).one()
    assert (turn.transcript, turn.question_text, turn.audio_path, turn.source_ref) == (None, "", None, None)
    session = db.query(VoiceSession).filter_by(application_id=item.id).one()
    assert (session.owner_user_id, session.plan) == (None, None)
    assert db.query(Consent).filter_by(application_id=item.id).one().user_id is None


def test_no_copy_of_the_personal_content_is_left_anywhere_in_the_database(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    assert CANARY in database_dump(db)
    retention.run(db)
    assert CANARY not in database_dump(db)
    assert fresh(db, item.id).anonymized_at is not None


def test_no_row_of_the_application_still_links_to_the_user(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    retention.run(db)
    db.rollback()
    uid = world.candidate_id
    assert db.query(Application).filter_by(candidate_user_id=uid).count() == 0
    assert db.query(VoiceSession).filter_by(owner_user_id=uid).count() == 0
    assert db.query(Consent).filter_by(user_id=uid).count() == 0
    assert db.query(Notification).filter_by(user_id=uid).count() == 0
    assert db.query(AuditLog).filter_by(actor_user_id=uid).count() == 0
    assert db.query(AuditLog).filter_by(target_type="application", target_id=item.id, action="application_withdrawn").count() == 1


def test_a_pending_notification_can_never_be_sent_blank(db, world, monkeypatch):
    full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    retention.run(db)
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid")
    sent = []
    monkeypatch.setattr(notify.smtplib, "SMTP", lambda *a, **k: sent.append(a))
    assert notify.send_pending(db) == 0
    assert sent == []


def test_notifications_of_another_live_application_at_the_company_survive(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    second_job = Job(company_id=world.company_id, title="Data Analyst", slug="acme-data", description="d",
                     status="published", interview_languages=[])
    db.add(second_job)
    db.commit()
    bare_application(db, world, job_id=second_job.id)
    db.add(Notification(company_id=world.company_id, user_id=world.candidate_id, kind="invited", language="en",
                        subject="Your next step for Data Analyst", body="We have read your CV for Data Analyst."))
    db.commit()
    retention.run(db)
    db.rollback()
    left = db.query(Notification).filter_by(user_id=world.candidate_id).all()
    assert [row.subject for row in left] == ["Your next step for Data Analyst"]
    assert fresh(db, item.id).anonymized_at is not None


def test_another_candidates_rows_are_untouched(db, world):
    full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    other = full_application(db, world, candidate_user_id=world.other_id, cv_blind_hash="other-hash")
    retention.run(db)
    application = fresh(db, other.id)
    assert application.cv_text_raw == f"{CANARY} raw"
    assert application.candidate_user_id == world.other_id
    assert db.query(Notification).filter_by(user_id=world.other_id).count() == 1
    assert db.query(Consent).filter_by(application_id=other.id).one().user_id == world.other_id
    assert db.query(VoiceTurn).filter_by(id=other.turn.id).one().transcript == f"{CANARY} transcript"
    assert storage.read_bytes(other.cv_path)


def test_hr_members_actions_stay_attributed(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    db.add(AuditLog(company_id=world.company_id, actor_user_id=world.hr_id, action="application_decided",
                    target_type="application", target_id=item.id))
    db.commit()
    retention.run(db)
    db.rollback()
    assert db.query(AuditLog).filter_by(action="application_decided").one().actor_user_id == world.hr_id
    assert fresh(db, item.id).hr_decided_by == world.hr_id


def test_a_candidate_who_is_also_a_member_keeps_their_hr_actions(db, world):
    db.add(CompanyMember(company_id=world.company_id, user_id=world.candidate_id, role="employee"))
    db.commit()
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    db.add(AuditLog(company_id=world.company_id, actor_user_id=world.candidate_id, action="job_published",
                    target_type="job", target_id=world.job_id))
    db.commit()
    retention.run(db)
    db.rollback()
    assert db.query(AuditLog).filter_by(action="job_published").one().actor_user_id == world.candidate_id
    assert db.query(AuditLog).filter_by(target_type="application", target_id=item.id,
                                        actor_user_id=world.candidate_id).count() == 0


def test_anonymizing_clears_the_rejection_draft_and_keeps_its_status(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1, decision="rejected"))
    db.add(RejectionFeedback(company_id=world.company_id, application_id=item.id, language="vi", status="sent",
                             draft=f"{CANARY} draft quoting an answer"))
    db.commit()
    retention.run(db)
    db.expire_all()
    row = db.query(RejectionFeedback).filter_by(application_id=item.id).one()
    assert (row.draft, row.status, row.language) == ("", "sent", "vi")


# 4. What stays


def test_anonymizing_keeps_what_block_5_metrics_need(db, world):
    created = days_ago(RETENTION_DAYS + 5).replace(microsecond=0)
    item = full_application(db, world, created_at=created, **decided(world, RETENTION_DAYS + 1, decision="rejected"))
    alias = item.application.alias
    retention.run(db)
    application = fresh(db, item.id)
    assert application.cv_status == "not_met"
    assert application.interview_band == "many"
    assert application.hr_decision == "rejected"
    assert application.hr_decided_by == world.hr_id
    assert application.stage == "ready_for_hr"
    assert application.source_channel == "linkedin"
    assert application.final_outcome == "hired"
    assert application.is_simulated is True
    assert application.job_id == world.job_id
    assert application.alias == alias
    assert application.created_at.replace(tzinfo=None) == created
    assert sorted(row.status for row in db.query(RequirementResult).filter_by(application_id=item.id)) == ["evidence", "met"]
    assert db.query(CvClaim).filter_by(application_id=item.id).one().status == "explained"
    turn = db.query(VoiceTurn).filter_by(id=item.turn.id).one()
    assert (turn.transcript_status, turn.audio_seconds, turn.question_source) == ("done", 12, "claim")
    assert db.query(VoiceSession).filter_by(application_id=item.id).one().status == "completed"
    consent = db.query(Consent).filter_by(application_id=item.id).one()
    assert (consent.purpose, consent.text_version) == ("cv_processing", "v1")


@pytest.mark.parametrize("stage", ["submitted", "cv_processing"])
def test_a_cv_job_still_running_gives_way_and_cannot_write_the_text_back(db, world, stage):
    from app.hiring import cv_processing

    item = bare_application(db, world, stage=stage)
    retention.anonymize_application(db, item)
    application = fresh(db, item.id)
    assert application.stage == "cv_failed"
    with pytest.raises(cv_processing._NoLongerProcessing):
        cv_processing._locked_processing(db, item.id)
    db.rollback()


# 5. The screening cache


def test_cache_rows_are_deleted_when_no_other_application_uses_the_hash(db, world):
    full_application(db, world, cv_blind_hash="only-mine", **decided(world, RETENTION_DAYS + 1))
    assert db.query(ScreeningCache).filter_by(blind_hash="only-mine").count() == 1
    retention.run(db)
    db.rollback()
    assert db.query(ScreeningCache).filter_by(blind_hash="only-mine").count() == 0


def test_cache_rows_are_kept_while_another_application_uses_the_hash_and_go_with_the_last(db, world):
    first = full_application(db, world, cv_blind_hash="shared", **decided(world, RETENTION_DAYS + 1))
    second = bare_application(db, world, candidate_user_id=world.other_id, cv_blind_hash="shared")
    retention.run(db)
    db.rollback()
    assert fresh(db, first.id).anonymized_at is not None
    assert db.query(ScreeningCache).filter_by(blind_hash="shared").count() == 1
    retention.anonymize_application(db, fresh(db, second.id))
    db.rollback()
    assert db.query(ScreeningCache).filter_by(blind_hash="shared").count() == 0


def test_an_anonymized_application_no_longer_keeps_a_cache_row_alive(db, world):
    first = full_application(db, world, cv_blind_hash="twice", **decided(world, RETENTION_DAYS + 1))
    second = bare_application(db, world, candidate_user_id=world.other_id, cv_blind_hash="twice", **decided(world, RETENTION_DAYS + 1))
    assert retention.run(db) == 2
    db.rollback()
    assert db.query(ScreeningCache).filter_by(blind_hash="twice").count() == 0
    assert fresh(db, first.id).anonymized_at and fresh(db, second.id).anonymized_at


def test_the_run_removes_a_cache_row_no_application_uses(db, world):
    """A CV job that finished its AI call after the candidate deleted the application leaves such a row behind."""
    db.add(ScreeningCache(blind_hash="orphan", job_id=world.job_id, job_version=1, prompt_version="p", model="m",
                          result={"claims": [{"text": CANARY}]}))
    db.commit()
    retention.run(db)
    db.rollback()
    assert db.query(ScreeningCache).filter_by(blind_hash="orphan").count() == 0


# 6. Idempotent


def test_a_second_run_skips_anonymized_rows(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    assert retention.run(db) == 1
    stamp = fresh(db, item.id).anonymized_at
    audit_rows = db.query(AuditLog).filter_by(action="application_anonymized").count()
    assert retention.run(db) == 0
    assert fresh(db, item.id).anonymized_at == stamp
    assert db.query(AuditLog).filter_by(action="application_anonymized").count() == audit_rows == 1


def test_anonymize_application_twice_does_nothing_new(db, world):
    item = full_application(db, world)
    retention.anonymize_application(db, item.application)
    retention.anonymize_application(db, fresh(db, item.id))
    assert db.query(AuditLog).filter_by(action="application_anonymized").count() == 1


def test_a_row_decided_in_another_session_after_the_list_was_read_is_rechecked(db, world, monkeypatch):
    item = bare_application(db, world, created_at=days_ago(181))
    real = retention._due_ids

    def decided_meanwhile(session, company_id, retention_days, now):
        ids = real(session, company_id, retention_days, now)
        session.query(Application).filter_by(id=item.id).update({"hr_decided_at": days_ago(1)}, synchronize_session=False)
        session.commit()
        return ids

    monkeypatch.setattr(retention, "_due_ids", decided_meanwhile)
    assert retention.run(db) == 0
    assert fresh(db, item.id).anonymized_at is None


# 7. The candidate deleting


def test_candidate_delete_has_the_same_effect_at_once(client, db, world, tmp_path):
    item = full_application(db, world)  # recent and undecided: retention would not touch it
    db.rollback()
    response = client.delete(f"/api/me/applications/{item.id}", headers=auth_header(CANDIDATE))
    assert response.status_code == 204
    application = fresh(db, item.id)
    assert application.anonymized_at is not None
    assert application.candidate_user_id is None
    assert CANARY not in database_dump(db)
    with pytest.raises(FileNotFoundError):
        storage.read_bytes(item.cv_path)
    assert not audio_file(tmp_path, item.audio_path).exists()
    db.rollback()
    assert client.get("/api/me/applications", headers=auth_header(CANDIDATE)).json() == []


def test_deleting_another_users_application_gets_404_and_changes_nothing(client, db, world):
    item = full_application(db, world)
    db.rollback()
    response = client.delete(f"/api/me/applications/{item.id}", headers=auth_header(OTHER))
    assert response.status_code == 404
    application = fresh(db, item.id)
    assert application.anonymized_at is None
    assert application.cv_text_raw == f"{CANARY} raw"


def test_delete_needs_a_login_and_a_deleted_application_is_then_gone(client, db, world):
    item = full_application(db, world)
    db.rollback()
    assert client.delete(f"/api/me/applications/{item.id}").status_code == 401
    assert client.delete(f"/api/me/applications/{item.id}", headers=auth_header(CANDIDATE)).status_code == 204
    assert client.delete(f"/api/me/applications/{item.id}", headers=auth_header(CANDIDATE)).status_code == 404


def test_a_file_that_cannot_be_deleted_leaves_the_candidate_able_to_retry(app, db, world, monkeypatch):
    item = full_application(db, world)
    db.rollback()

    def refuse(_path):
        raise PermissionError(CANARY)

    monkeypatch.setattr(storage, "delete", refuse)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.delete(f"/api/me/applications/{item.id}", headers=auth_header(CANDIDATE))
    assert response.status_code == 503
    assert CANARY not in response.text
    application = fresh(db, item.id)
    assert application.anonymized_at is None
    assert application.candidate_user_id == world.candidate_id
    assert application.cv_file_path == item.cv_path


# 8. HR audio


def test_hr_audio_after_anonymizing_gets_404_with_no_stack_trace(app, db, world):
    """The real route answers: test_hiring_board shows it serving this same audio through recordings.read first."""
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    position = item.turn.position
    url = f"/api/companies/{world.company_id}/applications/{item.id}/turns/{position}/audio"
    retention.run(db)
    db.rollback()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(url, headers=auth_header(HR))
    assert response.status_code == 404
    assert "Traceback" not in response.text
    assert CANARY not in response.text
    assert "recordings" not in response.text


# 9. The audit row


def test_an_audit_row_is_written_with_no_personal_content(db, world):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    retention.run(db)
    db.rollback()
    row = db.query(AuditLog).filter_by(action="application_anonymized").one()
    assert (row.company_id, row.target_type, row.target_id) == (world.company_id, "application", item.id)
    assert row.actor_user_id is None
    assert row.payload == {"trigger": "retention"}


def test_the_candidates_delete_is_not_attributed_to_them(client, db, world):
    item = full_application(db, world)
    db.rollback()
    client.delete(f"/api/me/applications/{item.id}", headers=auth_header(CANDIDATE))
    db.rollback()
    row = db.query(AuditLog).filter_by(action="application_anonymized").one()
    assert row.actor_user_id is None
    assert row.payload == {"trigger": "candidate_request"}
    text = json.dumps(row.payload)
    assert CANDIDATE not in text and CANARY not in text


# 10. Failures do not stop the run


def test_a_missing_file_does_not_stop_the_run(db, world, tmp_path):
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    storage.delete(item.cv_path)
    audio_file(tmp_path, item.audio_path).unlink()
    assert retention.run(db) == 1
    application = fresh(db, item.id)
    assert application.anonymized_at is not None
    assert application.cv_file_path is None


def test_one_failing_application_does_not_stop_the_others_and_is_retried(db, world, monkeypatch, caplog):
    stuck = full_application(db, world, cv_blind_hash="a", **decided(world, RETENTION_DAYS + 2))
    done = full_application(db, world, cv_blind_hash="b", candidate_user_id=world.other_id, **decided(world, RETENTION_DAYS + 1))
    real = storage.delete

    def refuse(path):
        if path == stuck.cv_path:
            raise PermissionError(CANARY)
        real(path)

    monkeypatch.setattr(storage, "delete", refuse)
    assert retention.run(db) == 1
    assert CANARY not in caplog.text
    application = fresh(db, stuck.id)
    assert application.anonymized_at is None
    assert application.cv_file_path == stuck.cv_path  # still known, so tomorrow's run can delete it
    assert application.cv_text_raw == f"{CANARY} raw"
    assert fresh(db, done.id).anonymized_at is not None

    monkeypatch.setattr(storage, "delete", real)
    assert retention.run(db) == 1
    assert fresh(db, stuck.id).anonymized_at is not None


def test_retention_makes_no_ai_call(db, world, monkeypatch):
    from app.ai import gateway

    def boom(*_args, **_kwargs):
        raise AssertionError("Retention must not call AI")

    for name in ("generate_structured", "generate_text", "embed", "transcribe", "synthesize"):
        monkeypatch.setattr(gateway, name, boom, raising=False)
    item = full_application(db, world, **decided(world, RETENTION_DAYS + 1))
    assert retention.run(db) == 1
    assert fresh(db, item.id).anonymized_at is not None


def test_a_run_with_no_audio_needs_no_recordings_module(db, world, monkeypatch):
    monkeypatch.setitem(sys.modules, "app.hiring.recordings", None)
    item = bare_application(db, world, created_at=days_ago(181))
    assert retention.run(db) == 1
    assert fresh(db, item.id).anonymized_at is not None


# Every column is classified


SCREENED_TYPES = (String, Text, JSON)


def hiring_tables():
    return [getattr(models_hiring, name).__table__ for name in models_hiring.__all__]


def holds_content_or_a_user(column) -> bool:
    links_to_user = any(key.target_fullname == "users.id" for key in column.foreign_keys)
    return isinstance(column.type, SCREENED_TYPES) or links_to_user


def classified(table_name):
    if table_name in retention.DELETED_ROWS:
        return None
    return {*retention.ERASED.get(table_name, ()), *retention.KEPT.get(table_name, ())}


@pytest.mark.parametrize("table", hiring_tables(), ids=lambda table: table.name)
def test_every_text_column_and_user_link_is_classified_for_retention(table):
    """A new column fails here until someone decides whether deleting an application clears it."""
    known = classified(table.name)
    if known is None:
        return
    missing = sorted(column.name for column in table.columns if holds_content_or_a_user(column) and column.name not in known)
    assert missing == [], (
        f"{table.name}: add {missing} to retention.ERASED (personal, cleared) or retention.KEPT (with the reason it is safe)"
    )


def test_the_classification_names_only_real_columns_and_no_column_twice():
    tables = {table.name: table for table in Base.metadata.sorted_tables}  # includes the bridges tables
    for name, columns in (*retention.ERASED.items(), *retention.KEPT.items()):
        assert set(columns) <= set(tables[name].columns.keys()), name
    for name in retention.ERASED:
        assert not set(retention.ERASED[name]) & set(retention.KEPT.get(name, ())), name
    assert set(retention.DELETED_ROWS) <= set(tables)


def test_every_table_pointing_at_an_application_is_classified():
    linked = [
        table.name for table in Base.metadata.sorted_tables
        if any(key.target_fullname == "applications.id" for column in table.columns for key in column.foreign_keys)
    ]
    assert sorted(linked) == sorted(set(linked) & {*retention.ERASED, *retention.DELETED_ROWS})


# Reminders


def invited(db, world, **columns):
    return bare_application(db, world, **{"stage": "invited", "created_at": days_ago(4), **columns})


def test_reminder_is_queued_three_days_after_the_invitation(db, world):
    item = invited(db, world)
    assert retention.send_reminders(db) == 1
    db.rollback()
    row = db.query(Notification).filter_by(user_id=world.candidate_id, kind="reminder").one()
    assert "Backend Developer" in row.subject + row.body
    assert row.status == "pending"
    assert db.query(AuditLog).filter_by(action="reminder_queued", target_id=item.id).count() == 1


def test_reminder_goes_once_per_application(db, world):
    invited(db, world)
    assert retention.send_reminders(db) == 1
    assert retention.send_reminders(db) == 0
    db.rollback()
    assert db.query(Notification).filter_by(kind="reminder").count() == 1


def test_no_reminder_before_three_days(db, world):
    invited(db, world, created_at=days_ago(2))
    assert retention.send_reminders(db) == 0


def test_the_three_days_count_from_the_invitation_not_the_submission(db, world):
    item = invited(db, world, created_at=days_ago(20))  # re-uploaded yesterday, so invited yesterday
    db.add(AuditLog(company_id=world.company_id, action="cv_assessed", target_type="application", target_id=item.id,
                    created_at=days_ago(1)))
    db.commit()
    assert retention.send_reminders(db) == 0


def test_no_reminder_once_a_session_exists(db, world):
    item = invited(db, world)
    db.add(VoiceSession(company_id=world.company_id, purpose="screening", application_id=item.id,
                        owner_user_id=world.candidate_id, language="en"))
    db.commit()
    assert retention.send_reminders(db) == 0


@pytest.mark.parametrize("columns", [
    {"stage": "withdrawn"}, {"stage": "ready_for_hr"}, {"candidate_user_id": None},
])
def test_no_reminder_for_an_application_no_longer_waiting(db, world, columns):
    invited(db, world, **columns)
    assert retention.send_reminders(db) == 0


# The daily task and the command


def test_the_daily_task_does_not_start_under_test(app):
    assert retention.start_daily_task(app) is None


def test_the_daily_task_runs_at_start_then_sleeps_a_day_and_survives_a_failure(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    passes, sleeps = [], []

    def daily_pass():
        passes.append(1)
        raise RuntimeError("database is down")

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(retention, "_daily_pass", daily_pass)
    monkeypatch.setattr(retention.asyncio, "sleep", sleep)

    async def scenario():
        task = retention.start_daily_task(SimpleNamespace())
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert len(passes) == 2
    assert sleeps == [24 * 60 * 60, 24 * 60 * 60]


def test_a_failed_step_of_the_daily_pass_does_not_stop_the_next(monkeypatch):
    steps = []
    monkeypatch.setattr(retention, "run", lambda _db: (_ for _ in ()).throw(RuntimeError("no")))
    monkeypatch.setattr(retention, "send_reminders", lambda _db: steps.append("reminders"))
    monkeypatch.setattr(notify, "send_pending", lambda _db: steps.append("send"))
    retention._daily_pass()
    assert steps == ["reminders", "send"]


def test_the_cli_runs_retention(db, world, capsys):
    from app import cli

    item = bare_application(db, world, created_at=days_ago(181))
    assert cli.main(["retention"]) == 0
    assert "1" in capsys.readouterr().out
    assert fresh(db, item.id).anonymized_at is not None
