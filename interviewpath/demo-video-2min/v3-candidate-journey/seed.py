"""
Deterministic seed for the candidate-journey demo. Runs inside speakcv_backend
(docker exec). Makes NO real AI-vendor calls: the reasoning/bulk slots are
already "fake" in this dev stack (app/hiring/fake_demo.py's keyword-matching
responders), so calling the real app.hiring.analysis.run() pipeline here is
exactly what the product itself does in dev/demo mode -- just fed an
authored interview transcript instead of a live microphone recording, since
this recording environment has no virtual mic device wired into Chrome.

Prepares, every run, fresh and idempotent:
1. A HiringRequest for the Korean manager's voice-intake screen (status
   stays "open" -- we only show the real mic-check UI, we don't complete it).
2. A "Hidden Gem" candidate application for job 4 (Backend Developer,
   daehan-precision): real CV upload via the real public apply endpoint,
   then advanced through the real stage machine with a real VoiceSession +
   VoiceTurns (authored Q&A), then the real analysis pipeline computes real
   per-requirement evidence from that transcript.
"""
import sys
import time

from app.database.database import SessionLocal
from app.database.sql_models import Company, CompanyMember, Job, User
from app.database.models_bridges import HiringRequest
from app.database.models_hiring import Application, CvClaim, VoiceSession, VoiceTurn
from app.hiring.state import advance
from app.hiring.analysis import run as run_analysis
from app.hiring import fake_demo as hiring_fake_demo
from app.auth.security import get_password_hash

# This script runs as its own process (docker exec), so the module-level
# fake-provider responder registry (app.ai.providers.fake) starts empty here
# even though the live uvicorn process already installed it at its own
# startup (app/main.py). Without this, generate_structured() falls back to
# schema defaults -- every requirement silently comes back "none".
hiring_fake_demo.install()

COMPANY_SLUG = "daehan-precision"
JOB_SLUG = "daehan-precision-backend-developer-007dff"
HIDDEN_GEM_NAME = "Pham Thi Lan"
INTAKE_TITLE = "Production Line Engineer (Korea HQ Line) [DEMO]"
KNOWN_PASSWORD = "DemoPass123!"
# The candidate the storyboard itself applies as, live, through the real browser
# form -- clearing any prior take's row keeps that scene idempotent too.
LIVE_APPLICANT_NAME = "Tran Thi B"

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
    db.commit()
    print(f"reset: passwords for hr + manager -> known value")


def reset_intake_request(db, company_id, manager_user_id):
    db.query(HiringRequest).filter(
        HiringRequest.company_id == company_id, HiringRequest.title == INTAKE_TITLE
    ).delete(synchronize_session=False)
    db.commit()
    req = HiringRequest(
        company_id=company_id, department_id=None, title=INTAKE_TITLE,
        manager_user_id=manager_user_id, status="open",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    print(f"seed: hiring_request id={req.id} title={INTAKE_TITLE!r} status=open")
    return req.id


def reset_hidden_gem_application(db, company_id, job_id):
    old = db.query(Application).filter(
        Application.company_id == company_id, Application.job_id == job_id,
        Application.candidate_name == HIDDEN_GEM_NAME,
    ).all()
    # DB-level ON DELETE CASCADE handles voice_sessions -> voice_turns and the
    # application's own requirement_results in the right order; a manual
    # pre-delete of voice_sessions hits the (non-cascading) requirement_results
    # -> voice_turns FK first and fails.
    for app_row in old:
        db.delete(app_row)
    db.commit()
    if old:
        print(f"reset: cleared {len(old)} prior hidden-gem application(s)")


def reset_live_applicant(db, company_id, job_id):
    old = db.query(Application).filter(
        Application.company_id == company_id, Application.job_id == job_id,
        Application.candidate_name == LIVE_APPLICANT_NAME,
    ).all()
    for app_row in old:
        db.delete(app_row)
    db.commit()
    if old:
        print(f"reset: cleared {len(old)} prior live-applicant application(s)")


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
            "candidate_email": "candidate.hiddengem.demo@example.com",
            "candidate_name": HIDDEN_GEM_NAME,
            "src": "aidemo-candidate-demo",
        }
        resp = httpx.post(
            f"http://localhost:8000/api/public/jobs/{job_slug}/apply", files=files, data=data, timeout=30
        )
    resp.raise_for_status()
    body = resp.json()
    app_id = body["id"]
    print(f"seed: applied -> application id={app_id} status={body['status']}")

    # The real CV-screening (fake provider) runs in a background task right
    # after this response; poll (fresh session each time -- MySQL
    # REPEATABLE READ would otherwise keep showing the pre-task snapshot)
    # until it reaches a terminal pre-interview stage, so cv_status is the
    # real computed one, not a guess.
    db.close()
    app_row = None
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

    # The CV's own claims are all frontend/React specifics (it's a mismatched
    # resume -- that's the point of a Hidden Gem); the screening interview
    # legitimately never addresses them, since the questions are about the
    # backend role instead. The fake provider's claim heuristic has no way to
    # mark an irrelevant claim "not applicable", only "not_explained", which
    # would otherwise drag interview_band down regardless of how strong the
    # requirement evidence is. Drop them so the band reflects just that.
    db.query(CvClaim).filter(CvClaim.application_id == app_id).delete(synchronize_session=False)
    db.commit()

    for position, question, transcript in TURNS:
        db.add(VoiceTurn(
            session_id=session.id, position=position, question_text=question,
            question_source="requirement", transcript=transcript,
            transcript_status="transcribed",
        ))
    db.commit()
    print(f"seed: voice_session id={session.id} with {len(TURNS)} turn(s)")

    db.close()  # run_analysis() uses its own session/connection + commits there
    run_analysis(app_id)

    fresh = SessionLocal()
    app_row = fresh.query(Application).filter(Application.id == app_id).first()
    print(
        f"seed: analysis done -> stage={app_row.stage!r} "
        f"analysis_status={app_row.analysis_status!r} band={app_row.interview_band!r}"
    )
    if app_row.stage != "ready_for_hr":
        print(f"ERROR: expected stage=ready_for_hr, got {app_row.stage!r}", file=sys.stderr)
        fresh.close()
        sys.exit(1)
    fresh.close()
    return app_id


def main():
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == COMPANY_SLUG).first()
        if company is None:
            print(f"ERROR: company {COMPANY_SLUG!r} not found", file=sys.stderr)
            sys.exit(1)
        job = db.query(Job).filter(Job.slug == JOB_SLUG).first()
        if job is None:
            print(f"ERROR: job {JOB_SLUG!r} not found", file=sys.stderr)
            sys.exit(1)
        manager = db.query(User).filter(User.email == "manager@daehan-precision.sample").first()
        if manager is None:
            print("ERROR: manager@daehan-precision.sample not found", file=sys.stderr)
            sys.exit(1)

        reset_passwords(db)
        reset_intake_request(db, company.id, manager.id)
        reset_hidden_gem_application(db, company.id, job.id)
        reset_live_applicant(db, company.id, job.id)
        app_id = create_hidden_gem_application(db, company, job)
        print(f"DONE application_id={app_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
