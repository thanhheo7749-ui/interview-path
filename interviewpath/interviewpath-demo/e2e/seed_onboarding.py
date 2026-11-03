"""Test-only seed for the onboarding spec, run from SpeakCV/src/backend with PYTHONPATH=. by start-backend.sh.

Writes real rows into the "onboarding" company: a department, a published job in it, a manager of that department with a
known password, and one candidate (#O1) with a known password whose interview is finished and whose brief was sent. HR
approves the candidate and records "hired" in the spec. Everything here is invented sample data. Prints the ids as JSON
to the path given.
"""
import json
import sys
from datetime import datetime, timezone

from app.auth.security import get_password_hash
from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, CandidateBrief, Company, CompanyMember, Department, Job, JobRequirement, User,
)

# Test-only passwords for sample users, also written in e2e/onboarding.spec.js.
PASSWORD = "e2e-onboarding-pass-123"


def make_user(db, email, name):
    user = User(email=email, full_name=name, hashed_password=get_password_hash(PASSWORD), must_change_password=False)
    db.add(user)
    db.flush()
    return user


def main(out_path):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == "onboarding").one()
        department = Department(company_id=company.id, name="Onboarding Platform")
        db.add(department)
        db.flush()
        job = Job(company_id=company.id, title="Onboarding Backend Developer", slug="onboarding-backend-developer",
                  status="published", version=1, description="Run services in production.",
                  interview_languages=["en"], department_id=department.id)
        db.add(job)
        db.flush()
        db.add(JobRequirement(company_id=company.id, job_id=job.id, text="Run services in production", must_have=True,
                              position=0))
        manager = make_user(db, "manager@onboarding.e2e.test", "Onboarding Manager")
        db.add(CompanyMember(company_id=company.id, user_id=manager.id, role="manager", department_id=department.id))
        hire = make_user(db, "hire@onboarding.e2e.test", "Onboarding Hire")
        application = Application(company_id=company.id, job_id=job.id, job_version=1, alias="#O1", stage="ready_for_hr",
                                  cv_status="meets", interview_band="many", cv_text_blind="[NAME]\nSample CV text.",
                                  candidate_user_id=hire.id)
        db.add(application)
        db.flush()
        db.add(CandidateBrief(company_id=company.id, application_id=application.id, language="en", status="sent",
                              sent_at=datetime.now(timezone.utc)))
        db.commit()
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump({"job_id": job.id, "company_id": company.id, "department_id": department.id,
                       "application_id": application.id}, handle)
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1])
