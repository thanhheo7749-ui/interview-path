"""An HR edit to a draft plan and a consent withdrawal take the plan row first, so neither can deadlock on the items."""
import os
import threading

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs TEST_MYSQL_URL; run `make test-mysql`.", allow_module_level=True)

from app.database.database import SessionLocal
from app.database.sql_models import Application, Company, Consent, Job, OnboardingItem, OnboardingPlan
from app.hiring import consents
from app.posthire import onboarding
from tests.helpers import make_user


def test_a_withdrawal_waits_for_an_edit_in_flight_on_the_same_plan():
    db, other = SessionLocal(), SessionLocal()
    try:
        company = Company(slug="acme", name="Acme")
        db.add(company)
        db.commit()
        job = Job(company_id=company.id, title="Backend", slug="backend", status="published", version=1,
                  interview_languages=["en"])
        user = make_user(db, "hire@example.test")
        db.add(job)
        db.commit()
        application = Application(company_id=company.id, job_id=job.id, alias="#A1", stage="ready_for_hr",
                                  candidate_user_id=user.id, final_outcome="hired")
        db.add(application)
        db.commit()
        plan = OnboardingPlan(company_id=company.id, application_id=application.id, status="draft",
                              used_interview_data=True, employee_user_id=user.id)
        consent = Consent(user_id=user.id, company_id=company.id, application_id=application.id,
                          purpose="onboarding_use", text_version=consents.VERSION)
        db.add_all([plan, consent])
        db.commit()
        team = OnboardingItem(plan_id=plan.id, phase=30, title="team", from_interview=False)
        gap = OnboardingItem(plan_id=plan.id, phase=60, title="gap", from_interview=True)
        db.add_all([team, gap])
        db.commit()
        plan_id, team_id, consent_id, user_id = plan.id, team.id, consent.id, user.id

        # The edit removes the kept item and holds the plan row until it commits.
        onboarding.update_plan(db, db.get(OnboardingPlan, plan_id), [{"id": team_id, "remove": True}], [], user_id)
        errors = []

        def withdraw():
            try:
                consents.withdraw(other, consent_id, user_id)
                other.commit()
            except Exception as exc:  # a deadlock or lock timeout shows up here
                errors.append(exc)

        thread = threading.Thread(target=withdraw)
        thread.start()
        thread.join(1.5)
        assert thread.is_alive(), "the withdrawal ran while the edit held the plan"
        db.commit()
        thread.join(10)
        assert not thread.is_alive() and not errors, errors
        db.expire_all()
        assert db.query(OnboardingItem).filter_by(plan_id=plan_id).count() == 0
    finally:
        db.close()
        other.close()
