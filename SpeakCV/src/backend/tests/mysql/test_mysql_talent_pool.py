"""The talent pool on a real MySQL: locks, foreign keys, and sessions that must see what another session committed."""
import os
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs TEST_MYSQL_URL; run `make test-mysql`.", allow_module_level=True)

from app.database.database import SessionLocal
from app.database.sql_models import Application, Company, Consent, Job, JobRequirement, Notification, TalentPoolEntry, User
from app.hiring import consents, cv_processing, retention
from app.hiring import fake_demo as hiring_fake_demo
from app.posthire import talent_pool
from tests.helpers import make_user

BLIND = "[NAME]\nBuilt a FastAPI service used by 3 teams."


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def other():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def world(db):
    hiring_fake_demo.install()
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend", slug="backend", status="published", version=1, interview_languages=["en"])
    target = Job(company_id=company.id, title="Platform", slug="platform", status="published", version=1,
                 interview_languages=["en"])
    db.add_all([job, target])
    db.commit()
    db.add(JobRequirement(company_id=company.id, job_id=target.id, text="FastAPI", must_have=True, position=0))
    user = make_user(db, "candidate@example.test")
    hr = make_user(db, "hr@example.test")
    application = Application(company_id=company.id, job_id=job.id, alias="#A1", stage="ready_for_hr",
                              hr_decision="rejected", hr_decided_at=utcnow(), candidate_user_id=user.id, cv_text_blind=BLIND)
    db.add(application)
    db.commit()
    return company.id, target.id, application.id, user.id, hr.id


def join(db, application_id, user_id):
    application, user = db.get(Application, application_id), db.get(User, user_id)
    talent_pool.give_consent(db, application, user, consents.VERSION, "en")
    return talent_pool.opt_in(db, application, user)


def test_withdrawing_after_anonymizing_deletes_the_row_and_the_link(db, world):
    _, _, application_id, user_id, _ = world
    entry = join(db, application_id, user_id)
    entry_id, consent_id = entry.id, entry.consent_id
    application = db.get(Application, application_id)
    application.hr_decided_at = utcnow() - timedelta(days=4000)
    db.commit()
    assert retention.run(db) == 1
    db.expire_all()
    assert db.get(TalentPoolEntry, entry_id).retained_cv_text == BLIND
    assert db.get(Consent, consent_id).user_id == user_id

    consents.withdraw(db, consent_id, user_id)
    db.commit()
    db.expire_all()
    assert db.get(TalentPoolEntry, entry_id) is None
    assert db.get(Consent, consent_id).user_id is None


def test_expiry_on_an_anonymized_application_deletes_the_row(db, world):
    _, _, application_id, user_id, _ = world
    entry = join(db, application_id, user_id)
    entry_id = entry.id
    retention.anonymize_application(db, db.get(Application, application_id))
    assert talent_pool.expire(db, now=utcnow() + timedelta(days=400)) == 1
    db.expire_all()
    assert db.get(TalentPoolEntry, entry_id) is None


def test_invitation_runs_through_and_leaving_retracts_it(db, world):
    company_id, target_id, application_id, user_id, hr_id = world
    entry = join(db, application_id, user_id)
    entry_id = entry.id
    assert [match.entry_id for match in talent_pool.matches(db, company_id, target_id)] == [entry_id]
    invited = talent_pool.invite(db, db.get(TalentPoolEntry, entry_id), db.get(Job, target_id), hr_id)
    invited_id = invited.id
    cv_processing.run_from_blind_text(invited_id, BLIND)
    db.commit()
    db.expire_all()
    assert db.get(Application, invited_id).stage == "invited"
    assert db.query(Notification).filter_by(application_id=invited_id, kind="invited_from_pool").count() == 1

    assert talent_pool.leave(db, entry_id, db.get(User, user_id)) == "left"
    db.expire_all()
    assert db.get(Application, invited_id).anonymized_at is not None
    assert db.get(TalentPoolEntry, entry_id).retained_cv_text is None
    assert db.query(Notification).filter_by(application_id=invited_id).count() == 0


def test_an_invite_in_a_session_with_an_old_snapshot_sees_that_the_person_left(db, other, world):
    _, target_id, application_id, user_id, hr_id = world
    entry_id = join(db, application_id, user_id).id
    entry, job = other.get(TalentPoolEntry, entry_id), other.get(Job, target_id)  # `other` now holds a snapshot
    assert entry.status == "active"

    talent_pool.leave(db, entry_id, db.get(User, user_id))
    with pytest.raises(talent_pool.EntryEnded):
        talent_pool.invite(other, entry, job, hr_id)


def test_matching_in_a_session_with_an_old_snapshot_sees_that_the_person_left(db, other, world):
    company_id, target_id, application_id, user_id, _ = world
    entry_id = join(db, application_id, user_id).id
    assert other.get(TalentPoolEntry, entry_id).status == "active"

    talent_pool.leave(db, entry_id, db.get(User, user_id))
    assert talent_pool.matches(other, company_id, target_id) == []


def test_expire_in_a_session_with_an_old_snapshot_sees_a_new_entry(db, other, world):
    _, _, application_id, user_id, _ = world
    assert other.query(TalentPoolEntry).count() == 0  # `other` now holds a snapshot
    join(db, application_id, user_id)
    assert talent_pool.expire(other, now=utcnow() + timedelta(days=400)) == 1


def test_a_leave_with_an_old_snapshot_is_idempotent(db, other, world):
    _, _, application_id, user_id, _ = world
    entry_id = join(db, application_id, user_id).id
    assert other.get(TalentPoolEntry, entry_id).status == "active"
    talent_pool.leave(db, entry_id, db.get(User, user_id))
    assert talent_pool.leave(other, entry_id, other.get(User, user_id)) == "left"
    other.expire_all()
    assert other.get(TalentPoolEntry, entry_id).retained_cv_text is None
