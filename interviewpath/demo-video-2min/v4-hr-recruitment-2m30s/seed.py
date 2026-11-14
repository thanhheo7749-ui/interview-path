"""
Deterministic seed for the 2m30s Human Resources & Recruitment demo.
Prepares:
1. Known password (DemoPass123!) for hr@daehan-precision.sample & manager@daehan-precision.sample.
2. Clears any prior 'Senior Backend Engineer' JobDraft / HiringRequest in daehan-precision so Scene 1 (JD Studio) creates a fresh one.
3. Resets App 258 ('1 CV Dat Chuan Tu Dong Moi Phong Van') to stage 'cv_hold' with deterministic claim token 'demo-magic-link-round1' so Scene 2 can click 'Invite to AI interview anyway' and then claim it on port 3001.
4. Recreates 'Pham Thi Lan' Hidden Gem application in stage 'ready_for_hr' on Job 4 (Backend Developer) and clears any prior CompanyMember row for her so Scene 3 (Approve + Round 2 Brief), Scene 4 (Hired + Onboarding Plan), and Scene 5 (Probation Employee My Onboarding + Copilot) run cleanly.
"""
import hashlib
import sys
import time

from app.database.database import SessionLocal
from app.database.sql_models import Company, CompanyMember, Job, User
from app.database.models_bridges import HiringRequest, JobDraft, JobDraftMessage
from app.database.models_hiring import Application, CvClaim, VoiceSession, VoiceTurn
from app.hiring.state import advance
from app.hiring.analysis import run as run_analysis
from app.hiring import fake_demo as hiring_fake_demo
from app.auth.security import get_password_hash

hiring_fake_demo.install()

COMPANY_SLUG = "daehan-precision"
JOB_SLUG = "daehan-precision-backend-developer-007dff"
HIDDEN_GEM_NAME = "Pham Thi Lan"
HIDDEN_GEM_EMAIL = "candidate.hiddengem.demo@example.com"
LIVE_APPLICANT_NAME = "Tran Thi B"
KNOWN_PASSWORD = "DemoPass123!"
DEMO_MAGIC_TOKEN = "demo-magic-link-round1"

TURNS = [
    (1, "Tell me about your backend development experience.",
     "I have about three years of Java backend development experience, mostly "
     "building REST services with Spring Boot for internal systems."),
    (2, "How do you approach a new feature before you start writing code?",
     "I always write a short design document first and get it reviewed by my "
     "tech lead before I start coding, so everyone agrees on the approach."),
    (3, "Have you worked under any formal quality or change-control process?",
     "Yes, my previous company followed ISO 9001 quality management, and every "
     "release had to go through a change-control and approval workflow before "
     "it was deployed."),
    (4, "Can you communicate with a Korean headquarters team?",
     "I can write clear technical English, and I have been studying Korean for "
     "two years, so I can follow simple conversations with the Korea "
     "headquarters team."),
    (5, "Do you have experience with any specialized plant or database systems?",
     "I have not worked with that kind of specialized database and plant "
     "software before, but I pick up new tools quickly."),
]


def reset_passwords(db):
    for email in ("hr@daehan-precision.sample", "manager@daehan-precision.sample"):
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.hashed_password = get_password_hash(KNOWN_PASSWORD)
    lan = db.query(User).filter(User.email == HIDDEN_GEM_EMAIL).first()
    if lan:
        lan.hashed_password = get_password_hash("UV@Candid2026!")
    db.commit()
    print("reset: passwords for hr, manager, and hidden gem candidate")


def reset_senior_backend_draft(db, company_id):
    drafts = db.query(JobDraft).filter(
        JobDraft.company_id == company_id, JobDraft.title == "Senior Backend Engineer"
    ).all()
    draft_ids = [d.id for d in drafts]
    if draft_ids:
        db.query(JobDraftMessage).filter(JobDraftMessage.job_draft_id.in_(draft_ids)).delete(synchronize_session=False)
        db.query(JobDraft).filter(JobDraft.id.in_(draft_ids)).delete(synchronize_session=False)
    db.query(HiringRequest).filter(
        HiringRequest.company_id == company_id, HiringRequest.title == "Senior Backend Engineer"
    ).delete(synchronize_session=False)
    db.commit()
    print(f"reset: cleared {len(draft_ids)} Senior Backend Engineer draft(s) + request(s)")


def reset_cv_hold_candidate(db, company_id, job_id):
    from app.hiring import applications, consents, voice
    token_hash = hashlib.sha256(DEMO_MAGIC_TOKEN.encode("utf-8")).hexdigest()
    # Clear any collision on token_hash first
    for row in db.query(Application).filter(Application.claim_token_hash == token_hash).all():
        row.claim_token_hash = None
    db.flush()

    hold_app = db.query(Application).filter(
        Application.company_id == company_id,
        Application.job_id == job_id,
        Application.candidate_email == "tran.hoang.minh.demo@gmail.com",
    ).first()
    if hold_app:
        user = applications.resolve_or_create_candidate_user(
            db, hold_app.candidate_email, hold_app.candidate_name
        )
        hold_app.candidate_user_id = user.id
        hold_app.stage = "cv_hold"
        hold_app.cv_status = "not_met"
        hold_app.invited_at = None
        hold_app.hr_decision = "pending"
        hold_app.claim_token_hash = token_hash
        db.flush()

        old_sessions = db.query(VoiceSession).filter(VoiceSession.application_id == hold_app.id).all()
        for old_s in old_sessions:
            db.query(VoiceTurn).filter(VoiceTurn.session_id == old_s.id).delete(synchronize_session=False)
            db.delete(old_s)
        db.flush()

        consents.record(
            db, user.id, company_id, hold_app.id, "cv_processing", consents.VERSION, language="en"
        )
        consents.record(
            db, user.id, company_id, hold_app.id, "recording_screening", consents.VERSION, language="en"
        )
        plan = [
            {
                "text": "Tell us about your backend development experience building REST services with Spring Boot.",
                "source": "requirement",
                "source_ref": "req:1",
                "why": "Your CV mentions backend API development — this verifies core role requirements.",
            },
            {
                "text": "Follow-up: How did you structure your design document and ISO 9001 change-control approval before deploying?",
                "source": "claim",
                "source_ref": "claim:1",
                "why": "Follow-up on your last answer — we would like more detail on how your team reviews changes.",
            },
        ]
        voice.create_session(
            db,
            company_id=company_id,
            purpose="screening",
            owner_user_id=user.id,
            language="en",
            plan=plan,
            application_id=hold_app.id,
        )
        db.commit()
        print(f"reset: hold_app id={hold_app.id} set to stage=cv_hold with magic token {DEMO_MAGIC_TOKEN!r} + 2-question live session")


def reset_applications(db, company_id, job_id):
    lan_user = db.query(User).filter(User.email == HIDDEN_GEM_EMAIL).first()
    if lan_user:
        db.query(CompanyMember).filter(
            CompanyMember.company_id == company_id,
            CompanyMember.user_id == lan_user.id,
        ).delete(synchronize_session=False)
        db.commit()

    for name in (HIDDEN_GEM_NAME, LIVE_APPLICANT_NAME):
        old = db.query(Application).filter(
            Application.company_id == company_id, Application.job_id == job_id,
            Application.candidate_name == name,
        ).all()
        for app_row in old:
            db.delete(app_row)
        db.commit()
        if old:
            print(f"reset: cleared {len(old)} prior application(s) for {name}")


def create_hidden_gem_application(db, company, job):
    import httpx

    company_id = company.id
    job_slug = job.slug
    cv_path = "/app/_demo_cv.docx"
    with open(cv_path, "rb") as fh:
        files = {
            "file": (
                "cv.docx", fh,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {
            "consent_version": "2026-11-02",
            "consent_language": "en",
            "candidate_email": HIDDEN_GEM_EMAIL,
            "candidate_name": HIDDEN_GEM_NAME,
            "src": "aidemo-hr-recruitment-demo",
        }
        resp = httpx.post(
            f"http://localhost:8000/api/public/jobs/{job_slug}/apply", files=files, data=data, timeout=30
        )
    resp.raise_for_status()
    body = resp.json()
    app_id = body["id"]
    print(f"seed: applied -> application id={app_id} status={body['status']}")

    db.close()
    for _ in range(20):
        time.sleep(1)
        probe = SessionLocal()
        app_row = probe.query(Application).filter(Application.id == app_id).first()
        stage = app_row.stage
        cv_status = app_row.cv_status
        probe.close()
        if stage in ("invited", "cv_hold", "cv_failed"):
            break
    else:
        print(f"ERROR: CV screening did not finish in time, stuck at stage={stage!r}", file=sys.stderr)
        sys.exit(1)
    print(f"seed: CV screening done -> stage={stage!r} cv_status={cv_status!r}")

    db = SessionLocal()
    app_row = db.query(Application).filter(Application.id == app_id).first()
    if app_row.stage != "invited":
        app_row.stage = "invited"
        db.commit()

    advance(app_row, "session_in_progress")
    advance(app_row, "session_completed")
    db.commit()

    session = VoiceSession(
        company_id=company_id, purpose="screening", application_id=app_id,
        language="en", status="completed",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    db.query(CvClaim).filter(CvClaim.application_id == app_id).delete(synchronize_session=False)
    db.commit()

    for position, question, transcript in TURNS:
        db.add(VoiceTurn(
            session_id=session.id, position=position, question_text=question,
            question_source="requirement", transcript=transcript,
            transcript_status="transcribed",
        ))
    db.commit()

    db.close()
    run_analysis(app_id)

    fresh = SessionLocal()
    app_row = fresh.query(Application).filter(Application.id == app_id).first()
    print(f"seed: analysis done -> stage={app_row.stage!r} band={app_row.interview_band!r}")
    fresh.close()
    return app_id


def main():
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == COMPANY_SLUG).first()
        job = db.query(Job).filter(Job.slug == JOB_SLUG).first()
        if not company or not job:
            print("ERROR: company or job not found", file=sys.stderr)
            sys.exit(1)
        reset_passwords(db)
        reset_senior_backend_draft(db, company.id)
        reset_cv_hold_candidate(db, company.id, job.id)
        reset_applications(db, company.id, job.id)
        app_id = create_hidden_gem_application(db, company, job)
        print(f"DONE application_id={app_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
