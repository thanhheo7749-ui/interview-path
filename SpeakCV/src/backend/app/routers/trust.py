"""The Trust Center for HR, and a candidate's consent withdrawal. Every HR lookup filters on company_id."""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_authenticated_user, require_member
from app.database.database import get_db
from app.database.sql_models import Application, AuditLog, Company, CompanyMember, Consent, Job, User
from app.hiring import consents, fairness, retention, withdrawal

router = APIRouter(prefix="/api/companies/{company_id}/trust", dependencies=[Depends(require_member("hr"))])
me_router = APIRouter()

PAGE_SIZE = 50
logger = logging.getLogger(__name__)


class ConsentRow(BaseModel):
    id: int
    purpose: str
    version: str
    granted_at: datetime
    withdrawn_at: datetime | None
    alias: str | None


class ConsentPage(BaseModel):
    items: list[ConsentRow]
    total: int
    page: int
    page_size: int


class AuditRow(BaseModel):
    id: int
    action: str
    actor_user_id: int | None  # staff only, so a candidate's user ID never reaches HR
    target_type: str
    target_id: int | None
    ai_provider: str | None
    ai_model: str | None
    prompt_version: str | None
    payload: dict
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditRow]
    total: int
    page: int
    page_size: int


class RetentionOut(BaseModel):
    retention_days: int
    undecided_retention_days: int
    awaiting_deletion: int
    due_now: int
    anonymized: int


class FairnessIn(BaseModel):
    application_id: int


class FairnessOut(BaseModel):
    identical_blind_text: bool
    identical_result: bool
    original_blind_text: str
    swapped_blind_text: str


class WithdrawnConsent(BaseModel):
    id: int
    purpose: str
    withdrawn_at: datetime


class MyConsent(BaseModel):
    id: int
    purpose: str
    version: str
    language: str | None
    granted_at: datetime
    withdrawn_at: datetime | None
    job_title: str | None


def _offset(page: int) -> int:
    return (page - 1) * PAGE_SIZE


@router.get("/consents", response_model=ConsentPage)
def list_consents(company_id: int, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    query = db.query(Consent).filter(Consent.company_id == company_id)
    rows = query.order_by(Consent.id.desc()).offset(_offset(page)).limit(PAGE_SIZE).all()
    application_ids = {row.application_id for row in rows if row.application_id is not None}
    aliases = dict(
        db.query(Application.id, Application.alias)
        .filter(Application.company_id == company_id, Application.id.in_(application_ids))
        .all()
    ) if application_ids else {}
    items = [
        ConsentRow(id=row.id, purpose=row.purpose, version=row.text_version, granted_at=row.granted_at,
                   withdrawn_at=row.withdrawn_at, alias=aliases.get(row.application_id))
        for row in rows
    ]
    return ConsentPage(items=items, total=query.count(), page=page, page_size=PAGE_SIZE)


@router.get("/audit", response_model=AuditPage)
def list_audit(
    company_id: int,
    action: str | None = Query(None, max_length=80),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog).filter(AuditLog.company_id == company_id)
    if action:
        query = query.filter(AuditLog.action == action)
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(_offset(page)).limit(PAGE_SIZE).all()
    staff = {user_id for (user_id,) in db.query(CompanyMember.user_id).filter(CompanyMember.company_id == company_id)}
    items = [
        AuditRow(id=row.id, action=row.action, actor_user_id=row.actor_user_id if row.actor_user_id in staff else None,
                 target_type=row.target_type, target_id=row.target_id, ai_provider=row.ai_provider, ai_model=row.ai_model,
                 prompt_version=row.prompt_version, payload=row.payload or {}, created_at=row.created_at)
        for row in rows
    ]
    return AuditPage(items=items, total=query.count(), page=page, page_size=PAGE_SIZE)


@router.get("/retention", response_model=RetentionOut)
def retention_status(company_id: int, db: Session = Depends(get_db)):
    return retention.counts(db, db.get(Company, company_id))


@router.post("/fairness-check", response_model=FairnessOut)
def fairness_check(
    company_id: int,
    body: FairnessIn,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    application = db.query(Application).filter(Application.id == body.application_id, Application.company_id == company_id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if consents.was_withdrawn(db, application.id, withdrawal.CV_PROCESSING):
        raise HTTPException(status_code=409, detail="The candidate withdrew consent to CV processing, so this check cannot run")
    try:
        result = fairness.check(db, application, actor_user_id=user.id)
    except fairness.ApplicationDeleted as exc:
        raise HTTPException(status_code=404, detail="Application not found") from exc
    except fairness.FairnessUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FairnessOut(
        identical_blind_text=result.identical_blind_text, identical_result=result.identical_result,
        original_blind_text=result.original_blind_text, swapped_blind_text=result.swapped_blind_text,
    )


@me_router.get("/api/me/consents", response_model=list[MyConsent])
def my_consents(user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Consent, Job.title)
        .outerjoin(Application, Application.id == Consent.application_id)
        .outerjoin(Job, Job.id == Application.job_id)
        .filter(Consent.user_id == user.id)
        .order_by(Consent.id.desc())
        .all()
    )
    return [
        MyConsent(id=consent.id, purpose=consent.purpose, version=consent.text_version, language=consent.language,
                  granted_at=consent.granted_at, withdrawn_at=consent.withdrawn_at, job_title=title)
        for consent, title in rows
    ]


@me_router.post("/api/me/consents/{consent_id}/withdraw", response_model=WithdrawnConsent)
def withdraw_consent(consent_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    user_id = user.id
    try:
        consent = withdrawal.withdraw(db, consent_id, user_id)
    except Exception as exc:  # a file that could not be deleted; the paths survive, so the candidate can try again
        db.rollback()
        logger.warning("Could not withdraw consent %s: %s", consent_id, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Your consent could not be withdrawn just now. Please try again.") from None
    if consent is None:
        raise HTTPException(status_code=404, detail="Consent not found")
    return WithdrawnConsent(id=consent.id, purpose=consent.purpose, withdrawn_at=consent.withdrawn_at)
