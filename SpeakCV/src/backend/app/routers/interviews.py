"""Briefs, the manager's interviews, scorecards and hiring outcomes.

HR routes need the hr role. Manager routes need the manager role and only see sent briefs for applications whose job
sits in the manager's own department subtree; anything else is a 404. Every lookup filters on company_id.
Routes that run AI are plain `def`.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.brain import audience
from app.bridges import brief
from app.database.database import get_db
from app.database.sql_models import (
    Application, CandidateBrief, CompanyMember, InterviewScorecard, Job, JobRequirement, User,
)
from app.hiring import decisions
from app.schemas.bridges import BriefIn, BriefPatch, OutcomeIn, ScorecardIn

router = APIRouter()

BASE = "/api/companies/{company_id}"


def _translate(error: ValueError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


def _application(db: Session, company_id: int, application_id: int) -> Application:
    application = db.query(Application).filter(Application.id == application_id,
                                               Application.company_id == company_id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _managed_query(db: Session, member: CompanyMember):
    """Sent briefs on live, approved applications in the manager's department subtree."""
    departments = audience.for_member(db, member).department_ids
    if not departments:
        return None
    return (
        db.query(Application, Job, CandidateBrief)
        .join(Job, Job.id == Application.job_id)
        .join(CandidateBrief, CandidateBrief.application_id == Application.id)
        .filter(Application.company_id == member.company_id, Job.company_id == member.company_id,
                CandidateBrief.company_id == member.company_id, CandidateBrief.status == "sent",
                Application.hr_decision == "approved", Application.anonymized_at.is_(None),
                Job.department_id.in_(departments))
    )


def _managed(db: Session, member: CompanyMember, application_id: int):
    query = _managed_query(db, member)
    found = query.filter(Application.id == application_id).first() if query is not None else None
    if found is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    return found


def _scorecard(row: InterviewScorecard | None):
    if row is None:
        return None
    return {"requirement_scores": row.requirement_scores, "recommendation": row.recommendation, "notes": row.notes,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None}


def _own_scorecard(db: Session, member: CompanyMember, application_id: int) -> InterviewScorecard | None:
    return (
        db.query(InterviewScorecard)
        .filter(InterviewScorecard.application_id == application_id,
                InterviewScorecard.company_id == member.company_id,
                InterviewScorecard.manager_user_id == member.user_id).first()
    )


@router.post(BASE + "/applications/{app_id}/brief")
def post_brief(company_id: int, app_id: int, body: BriefIn | None = None,
               member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    try:
        row = brief.generate(db, application, member.user_id, (body or BriefIn()).language)
    except brief.BriefError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return brief.serialize(row)


def _draft(db: Session, application: Application) -> CandidateBrief:
    row = brief.get_brief(db, application)
    if row is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return row


def _live_application(db: Session, company_id: int, application_id: int) -> Application:
    """For the read-back routes: an anonymized application has nothing left to show, so it is a 404."""
    application = _application(db, company_id, application_id)
    if application.anonymized_at is not None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.get(BASE + "/applications/{app_id}/brief")
def get_brief(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
              db: Session = Depends(get_db)):
    return brief.serialize(_draft(db, _live_application(db, company_id, app_id)))


@router.get(BASE + "/applications/{app_id}/scorecard")
def get_scorecard(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                  db: Session = Depends(get_db)):
    """What the hiring manager submitted. Advice to HR: reading it changes nothing."""
    application = _live_application(db, company_id, app_id)
    row = (
        db.query(InterviewScorecard)
        .filter(InterviewScorecard.application_id == application.id,
                InterviewScorecard.company_id == company_id, InterviewScorecard.submitted_at.isnot(None))
        .order_by(InterviewScorecard.submitted_at.desc(), InterviewScorecard.id.desc()).first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    manager = db.get(User, row.manager_user_id)
    texts = {r.id: r.text for r in db.query(JobRequirement).filter(
        JobRequirement.job_id == application.job_id, JobRequirement.company_id == company_id)}
    body = _scorecard(row)
    body["requirement_scores"] = [
        {**score, "text": texts.get(score.get("requirement_id"), "")} for score in (row.requirement_scores or [])
    ]
    body["manager_name"] = (manager.full_name or manager.email) if manager is not None else ""
    return body


@router.patch(BASE + "/applications/{app_id}/brief")
def patch_brief(company_id: int, app_id: int, body: BriefPatch,
                member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    row = _draft(db, application)
    try:
        brief.edit(
            db, application, row, member.user_id,
            [(p.evidence_id, p.summary, "") for p in body.strengths] if body.strengths is not None else None,
            [(p.evidence_id, p.summary, "") for p in body.to_clarify] if body.to_clarify is not None else None,
            [(q.evidence_id, q.question, "") for q in body.questions] if body.questions is not None else None,
        )
    except brief.BriefError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return brief.serialize(row)


@router.post(BASE + "/applications/{app_id}/brief/send")
def post_send_brief(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                    db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    row = _draft(db, application)
    try:
        brief.send(db, application, row, member.user_id)
    except brief.BriefError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return brief.serialize(row)


@router.get(BASE + "/my-interviews")
def list_my_interviews(company_id: int, member: CompanyMember = Depends(require_member("manager")),
                       db: Session = Depends(get_db)):
    query = _managed_query(db, member)
    if query is None:
        return []
    rows = query.order_by(CandidateBrief.sent_at.desc(), Application.id.desc()).all()
    scored = {
        application_id for (application_id,) in db.query(InterviewScorecard.application_id).filter(
            InterviewScorecard.company_id == company_id, InterviewScorecard.manager_user_id == member.user_id).all()
    }
    return [
        {"application_id": application.id, "alias": application.alias, "job_id": job.id, "job_title": job.title,
         "language": row.language, "sent_at": row.sent_at.isoformat() if row.sent_at else None,
         "scored": application.id in scored}
        for application, job, row in rows
    ]


@router.get(BASE + "/my-interviews/{app_id}")
def get_my_interview(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("manager")),
                     db: Session = Depends(get_db)):
    application, job, row = _managed(db, member, app_id)
    try:
        identity = decisions.reveal(db, application, member.user_id)  # HR approved; the access is logged
    except decisions.DecisionError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    requirements = (
        db.query(JobRequirement)
        .filter(JobRequirement.job_id == job.id, JobRequirement.company_id == company_id,
                JobRequirement.active.is_(True))
        .order_by(JobRequirement.position, JobRequirement.id).all()
    )
    body = {
        "application_id": application.id, "alias": application.alias, "job": {"id": job.id, "title": job.title},
        "candidate": identity, "brief": brief.serialize(row),
        "requirements": [{"id": r.id, "text": r.text} for r in requirements],
        "scorecard": _scorecard(_own_scorecard(db, member, application.id)),
    }
    db.commit()
    return body


@router.post(BASE + "/applications/{app_id}/scorecard")
def post_scorecard(company_id: int, app_id: int, body: ScorecardIn,
                   member: CompanyMember = Depends(require_member("manager")), db: Session = Depends(get_db)):
    application, _job, _row = _managed(db, member, app_id)
    try:
        card = brief.submit_scorecard(db, application, member.user_id,
                                      [(s.requirement_id, s.score) for s in body.scores], body.recommendation,
                                      body.notes)
    except brief.BriefError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return _scorecard(card)


@router.post(BASE + "/applications/{app_id}/outcome")
def post_outcome(company_id: int, app_id: int, body: OutcomeIn,
                 member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    try:
        brief.record_outcome(db, application, member.user_id, body.outcome)
    except brief.BriefError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return {"id": application.id, "final_outcome": application.final_outcome}
