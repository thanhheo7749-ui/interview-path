"""Briefs, the manager's interviews, scorecards and hiring outcomes.

HR routes need the hr role. Manager routes need the manager role and only see sent briefs for applications of a job from
a request assigned to them, or of a job with no request in their department subtree; anything else is a 404. A manager
reads and scores only the requirements of their layer. Every lookup filters on company_id.
Routes that run AI are plain `def`.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.brain import audience
from app.bridges import brief
from app.database.database import get_db
from app.database.sql_models import (
    Application, CandidateBrief, CompanyMember, HiringRequest, InterviewScorecard, Job, JobRequirement, OnboardingPlan, User,
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
    """Sent briefs on live, approved applications this manager reads: of a job from a request assigned to them, or of a
    job with no request in their department subtree."""
    departments = audience.for_member(db, member).department_ids
    from_request = exists().where(HiringRequest.job_id == Job.id, HiringRequest.company_id == member.company_id)
    assigned = from_request.where(HiringRequest.manager_user_id == member.user_id)
    return (
        db.query(Application, Job, CandidateBrief)
        .join(Job, Job.id == Application.job_id)
        .join(CandidateBrief, CandidateBrief.application_id == Application.id)
        .filter(Application.company_id == member.company_id, Job.company_id == member.company_id,
                CandidateBrief.company_id == member.company_id, CandidateBrief.status == "sent",
                Application.hr_decision == "approved", Application.anonymized_at.is_(None),
                or_(assigned, and_(~from_request, Job.department_id.in_(departments))))
    )


def _managed(db: Session, member: CompanyMember, application_id: int):
    found = _managed_query(db, member).filter(Application.id == application_id).first()
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
    """Every manager's submitted scorecard, newest first. Advice to HR: reading them changes nothing."""
    application = _live_application(db, company_id, app_id)
    rows = (
        db.query(InterviewScorecard)
        .filter(InterviewScorecard.application_id == application.id,
                InterviewScorecard.company_id == company_id, InterviewScorecard.submitted_at.isnot(None))
        .order_by(InterviewScorecard.submitted_at.desc(), InterviewScorecard.id.desc()).all()
    )
    texts = {r.id: r.text for r in db.query(JobRequirement).filter(
        JobRequirement.job_id == application.job_id, JobRequirement.company_id == company_id)}
    manager_ids = {r.manager_user_id for r in rows if r.manager_user_id is not None}
    names = {}
    if manager_ids:
        for user in db.query(User).filter(User.id.in_(manager_ids)):
            names[user.id] = user.full_name or user.email
    cards = []
    for row in rows:
        card = _scorecard(row)
        card["requirement_scores"] = [
            {**score, "text": texts.get(score.get("requirement_id"), "")} for score in (row.requirement_scores or [])
        ]
        card["manager_name"] = names.get(row.manager_user_id, "")  # "" once the manager's account is deleted
        cards.append(card)
    return {"scorecards": cards}


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
    rows = _managed_query(db, member).order_by(CandidateBrief.sent_at.desc(), Application.id.desc()).all()
    scored = {
        application_id for (application_id,) in db.query(InterviewScorecard.application_id).filter(
            InterviewScorecard.company_id == company_id, InterviewScorecard.manager_user_id == member.user_id).all()
    }
    plans = dict(db.query(OnboardingPlan.application_id, OnboardingPlan.id).filter(
        OnboardingPlan.company_id == company_id, OnboardingPlan.application_id.in_([a.id for a, _, _ in rows])))
    return [
        {"application_id": application.id, "alias": application.alias, "job_id": job.id, "job_title": job.title,
         "language": row.language, "sent_at": brief.utc_iso(row.sent_at),
         "scored": application.id in scored, "onboarding_plan_id": plans.get(application.id)}
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
    reader = audience.for_member(db, member)
    body = {
        "application_id": application.id, "alias": application.alias, "job": {"id": job.id, "title": job.title},
        "candidate": identity, "brief": brief.for_reader(db, application, row, reader),
        "requirements": [{"id": r.id, "text": r.text} for r in brief.readable_requirements(db, application, reader)],
        "scorecard": _scorecard(_own_scorecard(db, member, application.id)),
    }
    db.commit()
    return body


@router.post(BASE + "/applications/{app_id}/scorecard")
def post_scorecard(company_id: int, app_id: int, body: ScorecardIn,
                   member: CompanyMember = Depends(require_member("manager")), db: Session = Depends(get_db)):
    application, _job, _row = _managed(db, member, app_id)
    required = {r.id for r in brief.readable_requirements(db, application, audience.for_member(db, member))}
    try:
        card = brief.submit_scorecard(db, application, member.user_id, required,
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
