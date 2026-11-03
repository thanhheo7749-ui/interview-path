"""Test-only seed for the insights spec, run from SpeakCV/src/backend with PYTHONPATH=. by start-backend.sh.

`jobs` makes two published jobs in the "insights" sample company, before `simulate-hiring --seed 42` runs.
`real` then adds real applications: a few to the first job (so it has both kinds) and a third job with only real
rows and no cost. It prints the ids as JSON to the path given. Everything here is invented sample data.
"""
import json
import sys

from app.database.database import SessionLocal
from app.database.models_bridges import JobDraft
from app.database.sql_models import Application, Company, Job, JobRequirement

SLUGS = {"both": "insights-both", "simulated": "insights-simulated", "real": "insights-real"}


def make_job(db, company, slug, title):
    job = Job(company_id=company.id, title=title, slug=slug, status="published", version=1,
              description="Sample job for tests", interview_languages=["en"])
    db.add(job)
    db.flush()
    for position, (text, must) in enumerate([("Python services in production", True), ("Container deployment", True),
                                              ("Mentoring juniors", False)]):
        db.add(JobRequirement(company_id=company.id, job_id=job.id, text=text, must_have=must, position=position))
    db.flush()
    return job


def real_applications(db, company, job, spec):
    for channel, approved, count in spec:
        for i in range(count):
            db.add(Application(company_id=company.id, job_id=job.id, job_version=1, alias=f"#R{job.id}{channel[0]}{i}",
                               stage="ready_for_hr", cv_status="meets", source_channel=channel,
                               hr_decision="approved" if i < approved else None))


def main(step, out_path):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == "insights").one()
        if step == "jobs":
            make_job(db, company, SLUGS["both"], "Insights Both Engineer")
            make_job(db, company, SLUGS["simulated"], "Insights Simulated Engineer")
        else:
            both = db.query(Job).filter(Job.slug == SLUGS["both"]).one()
            real_applications(db, company, both, [("linkedin", 1, 2)])
            only_real = make_job(db, company, SLUGS["real"], "Insights Real Engineer")
            real_applications(db, company, only_real, [("linkedin", 1, 3), ("referral", 0, 2)])
            draft = JobDraft(company_id=company.id, job_id=both.id)
            db.add(draft)
        db.commit()
        if step == "real":
            ids = {key: db.query(Job.id).filter(Job.slug == slug).scalar() for key, slug in SLUGS.items()}
            ids["company_id"] = company.id
            ids["draft_id"] = draft.id
            with open(out_path, "w", encoding="utf-8") as handle:
                json.dump(ids, handle)
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
