"""Test-only seed for the feedback spec, run from SpeakCV/src/backend with PYTHONPATH=. by start-backend.sh.

Writes real rows into the "feedback" sample company: a job with four undecided candidates who have no interview (so a
rejection gets the standard message and no AI call), a skill for the learning catalogue, and one candidate with an interview (so the AI writes
the draft), and a person in the talent pool who was rejected from an earlier job. Everything here is invented sample data. Prints the ids as JSON to the path given.
"""
import json
import sys
from datetime import datetime, timezone

from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, Company, Job, JobRequirement, KbNode, RequirementResult, User, VoiceSession, VoiceTurn,
)
from app.hiring import consents
from app.posthire import talent_pool

CV = "[NAME]\nBuilt FastAPI services and ran Docker in production for three years."


def make_job(db, company, slug, title):
    job = Job(company_id=company.id, title=title, slug=slug, status="published", version=1,
              description="Run FastAPI services with Docker in production.", interview_languages=["en"])
    db.add(job)
    db.flush()
    for position, text in enumerate(["FastAPI experience", "Docker in production"]):
        db.add(JobRequirement(company_id=company.id, job_id=job.id, text=text, must_have=True, position=position))
    db.flush()
    return job


def make_application(db, company, job, alias, number, **extra):
    user = User(email=f"sample-feedback-{number}@example.test", full_name=f"Sample Person {alias[1:]}",
                hashed_password="!", must_change_password=False)
    db.add(user)
    db.flush()
    row = Application(company_id=company.id, job_id=job.id, job_version=1, alias=alias, stage="ready_for_hr",
                      cv_status="not_met", interview_band="few", cv_text_blind=CV, candidate_user_id=user.id, **extra)
    db.add(row)
    db.flush()
    return row, user


def main(out_path):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == "feedback").one()
        skill = KbNode(company_id=company.id, type="skill", title="Docker deployment", language="en",
                       visibility="public", status="published")
        db.add(skill)
        board_job = make_job(db, company, "feedback-board-engineer", "Feedback Board Engineer")
        for number, alias in enumerate(["#F1", "#F2", "#F3", "#F4"], start=1):
            make_application(db, company, board_job, alias, number)
        # One candidate who was interviewed: a verified quote for one requirement and a gap on the other, so the AI drafts.
        talked, user = make_application(db, company, board_job, "#F5", 5)
        quote = "I built a FastAPI service used by three teams"
        session = VoiceSession(company_id=company.id, purpose="screening", application_id=talked.id,
                               owner_user_id=user.id, language="en", status="completed")
        db.add(session)
        db.flush()
        turn = VoiceTurn(session_id=session.id, position=1, question_text="Tell me about a service you ran.",
                         question_source="must_have", transcript=f"{quote}.", transcript_status="done")
        db.add(turn)
        db.flush()
        reqs = db.query(JobRequirement).filter(JobRequirement.job_id == board_job.id).order_by(JobRequirement.position).all()
        db.add_all([
            RequirementResult(application_id=talked.id, requirement_id=reqs[0].id, source="interview", status="evidence",
                              quote=quote, voice_turn_id=turn.id),
            RequirementResult(application_id=talked.id, requirement_id=reqs[1].id, source="interview", status="none"),
        ])
        past_job = make_job(db, company, "feedback-past-engineer", "Feedback Past Engineer")
        past, person = make_application(db, company, past_job, "#P1", 9, hr_decision="rejected",
                                        hr_decided_at=datetime.now(timezone.utc))
        talent_job = make_job(db, company, "feedback-talent-engineer", "Feedback Talent Engineer")
        db.commit()
        talent_pool.give_consent(db, past, person, consents.VERSION, "en")
        talent_pool.opt_in(db, past, person)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump({"board_job": board_job.id, "talent_job": talent_job.id, "skill": skill.title}, handle)
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1])
