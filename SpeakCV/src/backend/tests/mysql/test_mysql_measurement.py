"""The Block 5 tables on a real MySQL: foreign key rules SQLite does not enforce, and the simulator's delete order."""
import os
from datetime import datetime

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs TEST_MYSQL_URL; run `make test-mysql`.", allow_module_level=True)

from alembic import command
from sqlalchemy import inspect

from app.database.database import SessionLocal, engine
from app.database.migrate import alembic_config
from app.database.sql_models import (
    Application, ChannelCost, Company, Consent, Job, JobRequirement, KbNode, LearningResource, OnboardingItem,
    OnboardingPlan, ProbationOutcome, RequirementResult, TalentPoolEntry, User,
)
from app.insights import simulator
from tests.helpers import make_user


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def world(db):
    company = Company(slug="sample", name="Sample", is_sample=True)
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend", slug="backend", status="published", version=1,
              interview_languages=["en"])
    db.add(job)
    db.commit()
    db.add_all([JobRequirement(company_id=company.id, job_id=job.id, text=text, must_have=True, position=position)
                for position, text in enumerate(("Python", "Team leading"))])
    db.commit()
    return company, job


def test_foreign_keys_follow_the_rules_the_later_tasks_rely_on():
    inspector = inspect(engine)
    for table, column, rule in (
        ("rejection_feedbacks", "approved_by", "SET NULL"), ("learning_resources", "created_by", "SET NULL"),
        ("onboarding_plans", "employee_user_id", "SET NULL"), ("onboarding_plans", "approved_by", "SET NULL"),
        ("onboarding_items", "owner_user_id", "SET NULL"), ("onboarding_items", "source_node_id", "SET NULL"),
        ("onboarding_items", "learning_resource_id", "SET NULL"), ("probation_outcomes", "recorded_by", "SET NULL"),
        ("talent_pool_entries", "candidate_user_id", "CASCADE"), ("talent_pool_entries", "consent_id", "CASCADE"),
        ("learning_resources", "skill_node_id", "CASCADE"),
    ):
        keys = [key for key in inspector.get_foreign_keys(table) if key["constrained_columns"] == [column]]
        assert [key["options"].get("ondelete") for key in keys] == [rule], f"{table}.{column}"


def test_deleting_a_candidate_deletes_the_retained_cv(db, world):
    company, job = world
    user = make_user(db, "candidate@example.test")
    application = Application(company_id=company.id, job_id=job.id, alias="#A1", stage="ready_for_hr")
    db.add(application)
    db.commit()
    consent = Consent(user_id=user.id, company_id=company.id, application_id=application.id, purpose="talent_pool",
                      text_version="1")
    db.add(consent)
    db.commit()
    db.add(TalentPoolEntry(company_id=company.id, candidate_user_id=user.id, source_application_id=application.id,
                           consent_id=consent.id, expires_at=datetime(2030, 1, 1), retained_cv_text="blind"))
    db.commit()
    db.query(User).filter_by(id=user.id).delete()
    db.commit()
    assert db.query(TalentPoolEntry).count() == 0


def test_deleting_a_draft_node_does_not_block_and_clears_what_points_at_it(db, world):
    company, job = world
    application = Application(company_id=company.id, job_id=job.id, alias="#A1", stage="ready_for_hr")
    node = KbNode(company_id=company.id, type="skill", title="Docker", body="", language="en", visibility="public",
                  status="draft")
    db.add_all([application, node])
    db.commit()
    resource = LearningResource(company_id=company.id, skill_node_id=node.id, title="Course", url="https://example.test")
    plan = OnboardingPlan(company_id=company.id, application_id=application.id)
    db.add_all([resource, plan])
    db.commit()
    item = OnboardingItem(plan_id=plan.id, phase=30, title="Learn Docker", source_node_id=node.id,
                          learning_resource_id=resource.id)
    db.add(item)
    db.commit()
    item_id = item.id
    db.query(KbNode).filter_by(id=node.id).delete()
    db.commit()
    db.expire_all()
    assert db.query(LearningResource).count() == 0
    kept = db.get(OnboardingItem, item_id)
    assert (kept.source_node_id, kept.learning_resource_id) == (None, None)


def test_simulating_twice_replaces_rows_under_real_foreign_keys_and_keeps_real_ones(db, world):
    company, job = world
    real = Application(company_id=company.id, job_id=job.id, alias="#A1", stage="ready_for_hr", final_outcome="hired")
    db.add(real)
    db.commit()
    db.add(ProbationOutcome(company_id=company.id, application_id=real.id, result="passed"))
    db.commit()
    real_id = real.id

    simulator.simulate(db, company, seed=42, count=60)
    summary = simulator.simulate(db, company, seed=42, count=60)

    assert summary.replaced == 60 and summary.requirement_results > 0
    assert db.query(Application).filter_by(company_id=company.id, is_simulated=True).count() == 60
    assert db.query(RequirementResult).count() == summary.requirement_results
    assert db.query(ChannelCost).count() == summary.channel_costs
    assert db.query(ProbationOutcome).filter_by(application_id=real_id).count() == 1


def test_the_migration_downgrades_and_upgrades_again():
    config = alembic_config()
    command.downgrade(config, "0007_bridges")
    assert "channel_costs" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert "channel_costs" in inspect(engine).get_table_names()
