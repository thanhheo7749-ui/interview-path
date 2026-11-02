"""Test-only seed for the board spec. Writes real rows into the "board" sample company, through the app's models.

Run from SpeakCV/src/backend with PYTHONPATH=. by start-backend.sh when E2E_SEED_BOARD=1. Everything here is
sample data: invented aliases and people, no real CV. Safe to run twice: it stops if the job already exists.
Prints the ids the spec needs as JSON to the path given as the first argument.
"""
import io
import json
import sys
import wave

from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, Company, CultureNote, CvClaim, Department, Job, JobRequirement, KbNode, RequirementResult, User,
    VoiceSession, VoiceTurn,
)
from app.hiring import recordings

SLUG = "board-sample-platform-engineer"
# A second job that only the full-loop spec reads, so the board spec's corrections and rejections never touch it.
GEM_SLUG = "board-sample-hidden-gem-engineer"
# A third job, in a department, that only the brief spec reads: its candidate is approved and briefed there.
BRIEF_SLUG = "board-sample-brief-engineer"
# A fourth job that only the states spec reads: its candidates move to other lanes and cells during the spec.
STATES_SLUG = "board-sample-states-engineer"


def silent_wav() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()


def main(out_path: str) -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == "board").one()
        job = db.query(Job).filter(Job.slug == SLUG).first()
        if job is None:
            job = seed(db, company)
        ids = {a.alias: a.id for a in db.query(Application).filter(Application.job_id == job.id)}
        gem = db.query(Job).filter(Job.slug == GEM_SLUG).first() or seed_gem(db, company)
        gem_ids = {a.alias: a.id for a in db.query(Application).filter(Application.job_id == gem.id)}
        brief = db.query(Job).filter(Job.slug == BRIEF_SLUG).first() or seed_brief(db, company)
        brief_ids = {a.alias: a.id for a in db.query(Application).filter(Application.job_id == brief.id)}
        states = db.query(Job).filter(Job.slug == STATES_SLUG).first() or seed_states(db, company)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump({"job_id": job.id, "company_id": company.id, "applications": ids,
                       "gem_job_id": gem.id, "gem_applications": gem_ids,
                       "brief_job_id": brief.id, "brief_department_id": brief.department_id,
                       "brief_applications": brief_ids, "states_job_id": states.id}, handle)
    finally:
        db.close()


def seed_states(db, company):
    """One candidate whose answer has audio and no transcript, and one whose CV could not be processed."""
    job = Job(company_id=company.id, title="Sample States Engineer", slug=STATES_SLUG, status="published", version=1,
              description="Sample job for tests", interview_languages=["en"])
    db.add(job)
    db.flush()
    db.add(JobRequirement(company_id=company.id, job_id=job.id, text="Sample public must-have", must_have=True, position=0))
    people = {}
    for alias in ("T1", "C1"):
        people[alias] = User(email=f"sample-states-{alias.lower()}@example.test", full_name=f"Sample Person {alias}",
                             hashed_password="!", must_change_password=False)
    db.add_all(people.values())
    db.flush()
    untranscribed = Application(company_id=company.id, job_id=job.id, job_version=1, alias="#T1", stage="ready_for_hr",
                                cv_status="meets", analysis_status="transcription_failed",
                                cv_text_blind="[NAME]\nSample CV text.", candidate_user_id=people["T1"].id)
    unreadable = Application(company_id=company.id, job_id=job.id, job_version=1, alias="#C1", stage="cv_failed",
                             processing_error="We could not process your CV right now. Please try again.",
                             candidate_user_id=people["C1"].id)
    db.add_all([untranscribed, unreadable])
    db.flush()
    session = VoiceSession(company_id=company.id, purpose="screening", application_id=untranscribed.id,
                           owner_user_id=people["T1"].id, language="en", status="completed")
    db.add(session)
    db.flush()
    path = recordings.save_turn_audio(company.id, f"sample-{untranscribed.id}", 1, silent_wav(), ".wav")
    db.add(VoiceTurn(session_id=session.id, position=1, question_text="Tell me about a service you ran.",
                     question_source="must_have", transcript_status="failed", stt_failures=2, audio_path=path))
    db.commit()
    return job


def seed_gem(db, company):
    """One candidate whose CV does not meet the must-have but whose interview does: a Hidden Gem only HR sees."""
    job = Job(company_id=company.id, title="Sample Gem Engineer", slug=GEM_SLUG, status="published", version=1,
              description="Sample job for tests", interview_languages=["en"])
    db.add(job)
    db.flush()
    req = JobRequirement(company_id=company.id, job_id=job.id, text="Sample must-have the CV lacks", must_have=True, position=0)
    user = User(email="sample-gem-1@example.test", full_name="Sample Person H1", hashed_password="!",
                must_change_password=False)
    db.add_all([req, user])
    db.flush()
    row = Application(company_id=company.id, job_id=job.id, job_version=1, alias="#H1", stage="ready_for_hr",
                      cv_status="not_met", interview_band="many", cv_text_blind="[NAME]\nSample CV text.",
                      candidate_user_id=user.id)
    session = VoiceSession(company_id=company.id, purpose="screening", owner_user_id=user.id, language="en",
                           status="completed")
    db.add_all([row, session])
    db.flush()
    session.application_id = row.id
    turn = VoiceTurn(session_id=session.id, position=1, question_text="Tell me about a time you learned fast.",
                     question_source="must_have", transcript="I taught myself the whole stack in a month.",
                     transcript_status="transcribed")
    db.add(turn)
    db.flush()
    db.add_all([
        RequirementResult(application_id=row.id, requirement_id=req.id, source="cv", status="not_found"),
        RequirementResult(application_id=row.id, requirement_id=req.id, source="interview", status="evidence",
                          quote="I taught myself the whole stack in a month.", voice_turn_id=turn.id),
    ])
    db.commit()
    return job


def seed_brief(db, company):
    """One candidate with a two-answer interview. The first answer is 133 seconds long, so a quote from the second
    sits at 02:13 of the recording. Both answers have audio. HR approves the candidate in the spec."""
    department = Department(company_id=company.id, name="Brief Sample Department")
    db.add(department)
    db.flush()
    job = Job(company_id=company.id, title="Sample Brief Engineer", slug=BRIEF_SLUG, status="published", version=1,
              description="Sample job for tests", interview_languages=["en"], department_id=department.id)
    db.add(job)
    db.flush()
    reqs = [
        JobRequirement(company_id=company.id, job_id=job.id, text="Run services in production", must_have=True, position=0),
        JobRequirement(company_id=company.id, job_id=job.id, text="Lead incident reviews", must_have=False, position=1),
    ]
    user = User(email="sample-brief-1@example.test", full_name="Sample Person B1", hashed_password="!",
                must_change_password=False)
    db.add_all(reqs + [user])
    db.flush()
    row = Application(company_id=company.id, job_id=job.id, job_version=1, alias="#B1", stage="ready_for_hr",
                      cv_status="meets", interview_band="many", cv_text_blind="[NAME]\nSample CV text.",
                      candidate_user_id=user.id)
    db.add(row)
    db.flush()
    session = VoiceSession(company_id=company.id, purpose="screening", application_id=row.id,
                           owner_user_id=user.id, language="ko", status="completed")
    db.add(session)
    db.flush()
    made = []
    for position, question, transcript, seconds in [
        (1, "서비스 운영 경험을 말씀해 주세요.", "저는 결제 서비스를 2년 동안 운영했습니다.", 133.0),
        (2, "장애 회고는 어떻게 이끌었나요?", "장애 회고를 매달 직접 진행했습니다.", 45.0),
    ]:
        path = recordings.save_turn_audio(company.id, f"sample-{row.id}", position, silent_wav(), ".wav")
        turn = VoiceTurn(session_id=session.id, position=position, question_text=question, question_source="must_have",
                         transcript=transcript, transcript_status="transcribed", audio_path=path,
                         audio_seconds=seconds)
        db.add(turn)
        made.append(turn)
    db.flush()
    db.add_all([
        RequirementResult(application_id=row.id, requirement_id=reqs[0].id, source="interview", status="evidence",
                          quote="저는 결제 서비스를 2년 동안 운영했습니다.", voice_turn_id=made[0].id),
        RequirementResult(application_id=row.id, requirement_id=reqs[1].id, source="interview", status="partial",
                          quote="장애 회고를 매달 직접 진행했습니다.", voice_turn_id=made[1].id),
    ])
    db.commit()
    return job


def seed(db, company):
    job = Job(company_id=company.id, title="Sample Platform Engineer", slug=SLUG, status="published", version=1,
              description="Sample job for tests", interview_languages=["en"])
    db.add(job)
    db.flush()
    reqs = [
        JobRequirement(company_id=company.id, job_id=job.id, text="Python services in production", must_have=True, position=0),
        JobRequirement(company_id=company.id, job_id=job.id, text="Container deployment", must_have=True, position=1),
        JobRequirement(company_id=company.id, job_id=job.id, text="Mentoring juniors", must_have=False, position=2),
        JobRequirement(company_id=company.id, job_id=job.id, text="Sample confidential requirement", must_have=True,
                       position=3, visibility="confidential"),
    ]
    value = KbNode(company_id=company.id, type="value", title="Ownership", body="We own our results.",
                   language="en", visibility="public", status="published")
    db.add_all(reqs + [value])
    db.flush()

    counter = {"n": 0}

    def application(alias, stage="ready_for_hr", cv="meets", band=None, **extra):
        counter["n"] += 1
        user = User(email=f"sample-board-{counter['n']}@example.test", full_name=f"Sample Person {alias[1:]}",
                    hashed_password="!", must_change_password=False)
        db.add(user)
        db.flush()
        row = Application(company_id=company.id, job_id=job.id, job_version=1, alias=alias, stage=stage,
                          cv_status=cv, interview_band=band, cv_text_blind="[NAME]\nSample CV text.",
                          candidate_user_id=user.id, **extra)
        db.add(row)
        db.flush()
        return row

    def interview(row, turns):
        session = VoiceSession(company_id=company.id, purpose="screening", application_id=row.id,
                               owner_user_id=row.candidate_user_id, language="en", status="completed")
        db.add(session)
        db.flush()
        made = []
        for position, question, transcript, audio in turns:
            path = recordings.save_turn_audio(company.id, f"sample-{row.id}", position, silent_wav(), ".wav") if audio else None
            turn = VoiceTurn(session_id=session.id, position=position, question_text=question,
                             question_source="must_have", transcript=transcript, transcript_status="transcribed",
                             audio_path=path)
            db.add(turn)
            made.append(turn)
        db.flush()
        return made

    # Full detail: the candidate the spec opens.
    p1 = application("#P1", band="many", ai_suggestion="Strong Python evidence in answer 1; worth a call.")
    t1, t2, _t3 = interview(p1, [
        (1, "Tell me about a Python service you ran.", "I ran a billing service for two years.", True),
        (2, "How did you deploy it?", "We shipped it in containers with a rolling update.", True),
        (3, "Describe a team you helped grow.", "I paired with two juniors every week.", False),
    ])
    db.add_all([
        RequirementResult(application_id=p1.id, requirement_id=reqs[0].id, source="cv", status="evidence", quote="Python billing service"),
        RequirementResult(application_id=p1.id, requirement_id=reqs[0].id, source="interview", status="evidence",
                          quote="I ran a billing service for two years.", voice_turn_id=t1.id),
        RequirementResult(application_id=p1.id, requirement_id=reqs[1].id, source="cv", status="partial", quote="Docker mentioned"),
        RequirementResult(application_id=p1.id, requirement_id=reqs[1].id, source="interview", status="evidence",
                          quote="We shipped it in containers with a rolling update.", voice_turn_id=t2.id),
        RequirementResult(application_id=p1.id, requirement_id=reqs[3].id, source="interview", status="none"),
        CvClaim(application_id=p1.id, text="Led a team of five", quote="Led a team of five", status="explained",
                evidence_quote="I paired with two juniors every week.", voice_turn_id=t1.id),
        CvClaim(application_id=p1.id, text="Cut costs by 30 percent", quote="Cut costs by 30 percent", status="not_explained"),
        CultureNote(application_id=p1.id, value_node_id=value.id, note="Took ownership of an outage.",
                    quote="I ran a billing service for two years.", voice_turn_id=t1.id),
    ])

    p2 = application("#P2", band="many")
    interview(p2, [(1, "Tell me about a Python service you ran.", "Sample answer.", False)])
    p3 = application("#P3", band="many")
    interview(p3, [(1, "Tell me about a Python service you ran.", "Sample answer.", False)])
    application("#S1", band="few")
    g1 = application("#G1", cv="not_met", band="many")
    interview(g1, [(1, "Tell me about a Python service you ran.", "Self-taught, but I run three services.", False)])
    g2 = application("#G2", cv="not_met", band="many")
    interview(g2, [(1, "Tell me about a Python service you ran.", "Sample answer.", False)])
    application("#N1", cv="not_met", band="few")

    application("#L1", stage="invited", cv="meets")
    application("#L2", stage="invited", cv="meets")
    application("#R1", stage="declined_recording", cv="meets")
    application("#W1", stage="withdrawn", cv="meets")
    application("#F1", stage="ready_for_hr", cv="meets", analysis_status="failed")
    application("#Z1", stage="analyzing", cv="meets")
    db.commit()
    return job


if __name__ == "__main__":
    main(sys.argv[1])
