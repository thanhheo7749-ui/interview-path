"""Shared builders for the analysis, decision and board tests."""
from app.database.sql_models import (
    Application, Company, CompanyMember, CvClaim, Job, JobRequirement, KbNode, VoiceSession, VoiceTurn,
)
from tests.helpers import auth_header, make_user

CONFIDENTIAL = "CANARY-CONFIDENTIAL-REQ-7741"
CANDIDATE_NAME = "Nguyen Canary Candidate"
CANDIDATE_EMAIL = "canary.candidate@example.test"
CV_RAW = "CANARY-RAW-CV-TEXT with identity"
CV_BLIND = "[NAME]\nBuilt a FastAPI service used by 3 teams.\nUsed Docker in production."


def make_world(db):
    company = Company(slug="acme", name="Acme")
    other = Company(slug="other", name="Other")
    db.add_all([company, other])
    db.commit()
    job = Job(company_id=company.id, title="Backend", slug="backend", status="published", version=1,
              interview_languages=["en"])
    other_job = Job(company_id=other.id, title="Foreign", slug="foreign", status="published", version=1,
                    interview_languages=["en"])
    db.add_all([job, other_job])
    db.commit()
    requirements = [
        JobRequirement(company_id=company.id, job_id=job.id, text="FastAPI experience", must_have=True, position=0),
        JobRequirement(company_id=company.id, job_id=job.id, text="Docker in production", must_have=True, position=1),
        JobRequirement(company_id=company.id, job_id=job.id, text="Kubernetes", must_have=False, position=2),
        JobRequirement(company_id=company.id, job_id=job.id, text=CONFIDENTIAL, must_have=True, position=3,
                       visibility="confidential"),
    ]
    db.add_all(requirements)
    value = KbNode(company_id=company.id, type="value", title="Ownership", body="We own our results.",
                   language="en", visibility="public", status="published")
    private_value = KbNode(company_id=company.id, type="value", title="Secret value", body="x",
                           language="en", visibility="confidential", status="published")
    db.add_all([value, private_value])
    people = {}
    for who, member_company in (("hr", company), ("emp", company), ("hr2", other)):
        user = make_user(db, f"{who}@example.test")
        db.add(CompanyMember(company_id=member_company.id, user_id=user.id,
                             role="employee" if who == "emp" else "hr"))
        people[who] = {"headers": auth_header(user.email), "id": user.id}
    db.commit()
    return {"company": company, "other": other, "job": job, "other_job": other_job, "requirements": requirements,
            "value": value, "private_value": private_value, "people": people}


def make_application(db, job, alias="#A1", stage="ready_for_hr", cv_status="meets", band=None, **extra):
    first = alias == "#A1" and job.title == "Backend"
    candidate = make_user(db, CANDIDATE_EMAIL if first else f"cand{alias[2:]}-{job.id}@example.test")
    candidate.full_name = CANDIDATE_NAME if first else f"Person {alias[2:]}"
    row = Application(
        company_id=job.company_id, job_id=job.id, job_version=job.version, alias=alias, stage=stage,
        cv_status=cv_status, interview_band=band, cv_text_raw=CV_RAW, cv_text_blind=CV_BLIND,
        candidate_user_id=candidate.id, **extra,
    )
    db.add(row)
    db.commit()
    return row


def make_session(db, application, turns, restart_count=0, status="completed"):
    """turns: list of (position, question, transcript, audio_path)."""
    session = VoiceSession(company_id=application.company_id, purpose="screening", application_id=application.id,
                           owner_user_id=application.candidate_user_id, language="en", status=status,
                           restart_count=restart_count)
    db.add(session)
    db.commit()
    rows = []
    for position, question, transcript, audio_path in turns:
        turn = VoiceTurn(session_id=session.id, position=position, question_text=question,
                         question_source="must_have", transcript=transcript, transcript_status="done",
                         audio_path=audio_path)
        db.add(turn)
        rows.append(turn)
    db.commit()
    return session, rows


def add_claims(db, application, items):
    rows = [CvClaim(application_id=application.id, text=text, quote=text) for text in items]
    db.add_all(rows)
    db.commit()
    return rows
