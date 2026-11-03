"""Onboarding 30-60-90 routes, the hire's consent, and probation results.

HR creates a plan. HR and the manager of the job's department edit and approve it; another department's manager gets a
404. The hire reaches it only after approval, as an employee. Every lookup filters on company_id. Routes that call the
AI are plain def, so they run in the threadpool.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.auth.dependencies import get_authenticated_user, require_member
from app.brain import audience as aud
from app.database.database import get_db
from app.database.sql_models import (
    Application, CompanyMember, Consent, Job, KbNode, LearningResource, OnboardingItem, OnboardingPlan, ProbationOutcome, User,
)
from app.hiring import audit, consents
from app.posthire import onboarding
from app.routers.interviews import job_scope

router = APIRouter()

BASE = "/api/companies/{company_id}"
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=onboarding.MAX_TITLE_CHARS)]


class ItemEdit(BaseModel):
    id: int
    title: Title | None = None
    phase: int | None = None
    remove: bool = False


class ItemAdd(BaseModel):
    phase: int
    title: Title
    source_node_id: int | None = None
    learning_resource_id: int | None = None


class PlanPatch(BaseModel):
    items: list[ItemEdit] = Field(default_factory=list, max_length=100)
    add: list[ItemAdd] = Field(default_factory=list, max_length=100)


class ProbationIn(BaseModel):
    result: str


class ConsentIn(BaseModel):
    version: str = Field(max_length=30)
    language: str | None = Field(default=None, max_length=10)


def _translate(error: onboarding.OnboardingError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


# --- lookups --------------------------------------------------------------------------------------------------------

def _may_manage(db: Session, member: CompanyMember, job: Job | None) -> bool:
    """HR for any job. A manager by the same rule as their interviews (see interviews.job_scope)."""
    if member.role == "hr":
        return True
    if job is None:
        return False
    return db.query(Job.id).filter(Job.id == job.id, Job.company_id == member.company_id, job_scope(db, member)).first() is not None


def _application(db: Session, company_id: int, application_id: int) -> Application:
    application = db.query(Application).filter(
        Application.id == application_id, Application.company_id == company_id,
        Application.is_simulated.is_(False)).first()
    if application is None:
        raise _not_found("Application")
    return application


def _managed_plan(db: Session, member: CompanyMember, plan_id: int) -> OnboardingPlan:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id,
                                           OnboardingPlan.company_id == member.company_id).first()
    application = db.get(Application, plan.application_id) if plan else None
    job = db.get(Job, application.job_id) if application else None
    if plan is None or application is None or application.is_simulated or not _may_manage(db, member, job):
        raise _not_found("Plan")
    return plan


# --- output ---------------------------------------------------------------------------------------------------------

def _items_out(db: Session, plan: OnboardingPlan, progress: bool = False) -> list[dict]:
    rows = (db.query(OnboardingItem).filter(OnboardingItem.plan_id == plan.id)
            .order_by(OnboardingItem.phase, OnboardingItem.id).all())
    node_ids = {row.source_node_id for row in rows if row.source_node_id}
    titles = {}
    if node_ids:  # a node that left the employee audience since approval shows no title
        titles = dict(db.query(KbNode.id, KbNode.title).filter(KbNode.id.in_(node_ids),
                                                              aud.node_filter(onboarding.employee_audience(plan.company_id))))
    resource_ids = {row.learning_resource_id for row in rows if row.learning_resource_id}
    resources = {}
    if resource_ids:
        resources = {r.id: r for r in db.query(LearningResource).filter(
            LearningResource.id.in_(resource_ids), LearningResource.company_id == plan.company_id)}
    out = []
    for row in rows:
        resource = resources.get(row.learning_resource_id)
        out.append({
            "id": row.id, "phase": row.phase, "title": row.title,
            "source_node_id": row.source_node_id, "source_title": titles.get(row.source_node_id),
            "learning_resource": {"id": resource.id, "title": resource.title, "url": resource.url,
                                  "provider": resource.provider} if resource else None,
            **({"done_at": row.done_at.isoformat() if row.done_at else None} if progress else {}),
        })
    return out


def _plan_out(db: Session, plan: OnboardingPlan) -> dict:
    """For HR and managers: never the hire's ticks, which are the hire's own."""
    application = db.get(Application, plan.application_id)
    job = db.get(Job, application.job_id)
    probation = db.query(ProbationOutcome.result).filter_by(application_id=application.id).scalar()
    return {"id": plan.id, "application_id": plan.application_id, "alias": application.alias, "job_title": job.title,
            "probation_result": probation, "status": plan.status,
            "used_interview_data": plan.used_interview_data, "employee_user_id": plan.employee_user_id,
            "approved_by": plan.approved_by, "items": _items_out(db, plan)}


def _checklist_out(db: Session, plan: OnboardingPlan) -> dict:
    """For the hire: no approval or consent details."""
    return {"id": plan.id, "status": plan.status, "items": _items_out(db, plan, progress=True)}


# --- HR and managers ------------------------------------------------------------------------------------------------

@router.post(BASE + "/applications/{app_id}/onboarding")
def create_onboarding(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                      db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    try:
        plan = onboarding.create_plan(db, application, member.user_id)
    except onboarding.OnboardingError as error:
        db.rollback()
        raise _translate(error) from error
    db.commit()
    return _plan_out(db, plan)


@router.get(BASE + "/onboarding/{plan_id}")
def read_onboarding(company_id: int, plan_id: int, member: CompanyMember = Depends(require_member("hr", "manager")),
                    db: Session = Depends(get_db)):
    return _plan_out(db, _managed_plan(db, member, plan_id))


@router.patch(BASE + "/onboarding/{plan_id}")
def edit_onboarding(company_id: int, plan_id: int, body: PlanPatch,
                    member: CompanyMember = Depends(require_member("hr", "manager")), db: Session = Depends(get_db)):
    plan = _managed_plan(db, member, plan_id)
    try:
        onboarding.update_plan(db, plan, [e.model_dump(exclude_unset=True) for e in body.items],
                               [a.model_dump() for a in body.add], member.user_id)
    except onboarding.OnboardingError as error:
        db.rollback()
        raise _translate(error) from error
    db.commit()
    return _plan_out(db, plan)


@router.post(BASE + "/onboarding/{plan_id}/approve")
def approve_onboarding(company_id: int, plan_id: int,
                       member: CompanyMember = Depends(require_member("hr", "manager")), db: Session = Depends(get_db)):
    plan = _managed_plan(db, member, plan_id)
    try:
        onboarding.approve(db, plan, member.user_id)
    except onboarding.OnboardingError as error:
        db.rollback()
        raise _translate(error) from error
    db.commit()
    return _plan_out(db, plan)


@router.post(BASE + "/applications/{app_id}/probation")
def record_probation(company_id: int, app_id: int, body: ProbationIn,
                     member: CompanyMember = Depends(require_member("hr", "manager")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    if not _may_manage(db, member, db.get(Job, application.job_id)):
        raise HTTPException(status_code=403, detail="You do not have access to this resource")
    try:
        row: ProbationOutcome = onboarding.record_probation(db, application, body.result, member.user_id)
    except onboarding.OnboardingError as error:
        db.rollback()
        raise _translate(error) from error
    db.commit()
    return {"application_id": application.id, "result": row.result, "recorded_by": row.recorded_by,
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None}


# --- the hire --------------------------------------------------------------------------------------------------------

@router.get(BASE + "/my-onboarding")
def my_onboarding(company_id: int, member: CompanyMember = Depends(require_member()), db: Session = Depends(get_db)):
    plans = (db.query(OnboardingPlan)
             .filter(OnboardingPlan.company_id == member.company_id, OnboardingPlan.employee_user_id == member.user_id,
                     OnboardingPlan.status.in_(("active", "done")))
             .order_by(OnboardingPlan.id).all())
    return [_checklist_out(db, plan) for plan in plans]


@router.post(BASE + "/onboarding/items/{item_id}/done")
def tick_item(company_id: int, item_id: int, member: CompanyMember = Depends(require_member()),
              db: Session = Depends(get_db)):
    item = db.get(OnboardingItem, item_id)
    plan = db.get(OnboardingPlan, item.plan_id) if item else None
    if (item is None or plan.company_id != member.company_id or item.owner_user_id != member.user_id
            or plan.status not in ("active", "done")):
        raise _not_found("Item")
    onboarding.mark_done(db, item, plan)
    db.commit()
    return {"id": item.id, "phase": item.phase, "title": item.title, "done_at": item.done_at.isoformat()}


# --- the candidate's consent ------------------------------------------------------------------------------------------

def _hired_application(db: Session, user: User, application_id: int) -> Application:
    application = db.query(Application).filter(
        Application.id == application_id, Application.candidate_user_id == user.id,
        Application.is_simulated.is_(False)).first()
    if application is None:
        raise _not_found("Application")
    if application.final_outcome != "hired" or application.anonymized_at is not None:
        raise HTTPException(status_code=409, detail="This application is not open for onboarding consent")
    return application


def _consent_out(db: Session, application: Application, language: str) -> dict:
    current = consents.current_text(onboarding.PURPOSE, language)
    active = db.query(Consent).filter(
        Consent.user_id == application.candidate_user_id, Consent.application_id == application.id,
        Consent.purpose == onboarding.PURPOSE, Consent.withdrawn_at.is_(None)).first()
    return {"purpose": onboarding.PURPOSE, "version": current.version, "text": current.text,
            "language": current.language, "granted": active is not None, "consent_id": active.id if active else None}


@router.get("/api/applications/{application_id}/onboarding-consent")
def read_onboarding_consent(application_id: int, language: str = Query("en", max_length=10),
                            user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    return _consent_out(db, _hired_application(db, user, application_id), language)


@router.post("/api/applications/{application_id}/onboarding-consent")
def grant_onboarding_consent(application_id: int, body: ConsentIn, user: User = Depends(get_authenticated_user),
                             db: Session = Depends(get_db)):
    application = _hired_application(db, user, application_id)
    if body.version != consents.VERSION:
        raise HTTPException(status_code=409, detail={
            "message": "The consent text has changed. Please read it again.", "current_version": consents.VERSION})
    language = body.language or "en"
    if not _consent_out(db, application, language)["granted"]:
        consents.record(db, user.id, application.company_id, application.id, onboarding.PURPOSE, consents.VERSION,
                        body.language)
        audit.record(db, application.company_id, user.id, "onboarding_consent.granted", "application", application.id)
        db.commit()
    return _consent_out(db, application, language)
