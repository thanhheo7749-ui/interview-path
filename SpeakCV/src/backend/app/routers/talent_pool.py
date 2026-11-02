"""The talent pool. Candidate routes filter on the signed-in user, and HR routes on company_id. No response holds a name or a CV."""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_authenticated_user, require_member
from app.core.rate_limit import limiter, user_key
from app.database.database import get_db
from app.database.sql_models import Application, Company, Job, TalentPoolEntry, User
from app.hiring import applications, consents, cv_processing
from app.posthire import talent_pool

router = APIRouter()
company_router = APIRouter(prefix="/api/companies/{company_id}", dependencies=[Depends(require_member("hr"))])

MATCHES_LIMIT = "60/hour"  # each view can cost an AI call per match
MAX_TOP_K = 50
NOT_FOUND = "Not found"


class OptInIn(BaseModel):
    consent_version: str = Field(max_length=30)
    consent_language: str | None = Field(default=None, max_length=10)


class EntryOut(BaseModel):
    id: int
    application_id: int
    consent_id: int
    status: str
    expires_at: datetime
    job_title: str
    company_name: str


class LeftOut(BaseModel):
    id: int
    status: str


class RequirementMatchOut(BaseModel):
    requirement_id: int
    text: str
    must_have: bool
    status: str
    quote: str


class TalentMatchOut(BaseModel):
    entry_id: int
    alias: str
    similarity: float
    strength: str
    must_haves_met: int
    must_haves_total: int
    requirements: list[RequirementMatchOut]


class InviteIn(BaseModel):
    job_id: int


class InvitedOut(BaseModel):
    id: int
    alias: str
    job_id: int
    stage: str
    source_channel: str


def _entry_out(db: Session, entry: TalentPoolEntry) -> EntryOut:
    application = db.get(Application, entry.source_application_id)
    return EntryOut(id=entry.id, application_id=entry.source_application_id, consent_id=entry.consent_id,
                    status=entry.status, expires_at=entry.expires_at, job_title=db.get(Job, application.job_id).title,
                    company_name=db.get(Company, entry.company_id).name)


def _consent_needed() -> HTTPException:
    return HTTPException(status_code=422, detail={
        "message": "Please read and accept the current text first.", "current_version": consents.VERSION,
    })


@router.post("/api/applications/{application_id}/talent-pool", response_model=EntryOut)
def join_pool(application_id: int, body: OptInIn, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id, Application.candidate_user_id == user.id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        talent_pool.give_consent(db, application, user, body.consent_version, body.consent_language)
        entry = talent_pool.opt_in(db, application, user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Application not found") from exc
    except talent_pool.NotEligible as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except talent_pool.ConsentRequired as exc:
        raise _consent_needed() from exc
    return _entry_out(db, entry)


@router.get("/api/me/talent-pool", response_model=list[EntryOut])
def my_entries(user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    rows = (
        db.query(TalentPoolEntry).filter(TalentPoolEntry.candidate_user_id == user.id)
        .order_by(TalentPoolEntry.id.desc()).all()
    )
    return [_entry_out(db, row) for row in rows]


@router.post("/api/talent-pool/{entry_id}/leave", response_model=LeftOut)
def leave_pool(entry_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    try:
        return LeftOut(id=entry_id, status=talent_pool.leave(db, entry_id, user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc


@company_router.get("/jobs/{job_id}/talent-matches", response_model=list[TalentMatchOut])
@limiter.limit(MATCHES_LIMIT, key_func=user_key)
def talent_matches(
    request: Request,
    company_id: int,
    job_id: int,
    top_k: int = Query(10, ge=1, le=MAX_TOP_K),
    db: Session = Depends(get_db),
):
    try:
        return talent_pool.matches(db, company_id, job_id, top_k=top_k)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@company_router.post("/talent-pool/{entry_id}/invite", response_model=InvitedOut, status_code=201)
def invite_from_pool(
    company_id: int,
    entry_id: int,
    body: InviteIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    entry = db.query(TalentPoolEntry).filter(TalentPoolEntry.id == entry_id, TalentPoolEntry.company_id == company_id).first()
    job = db.query(Job).filter(Job.id == body.job_id, Job.company_id == company_id).first()
    if entry is None or job is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    try:
        application = talent_pool.invite(db, entry, job, user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except talent_pool.EntryEnded as exc:
        raise HTTPException(status_code=409, detail="This person is no longer in the talent pool") from exc
    except applications.JobNotOpen as exc:
        raise HTTPException(status_code=409, detail="This job is closed") from exc
    except applications.AlreadyApplied as exc:
        raise HTTPException(status_code=409, detail="This person has already applied to this job") from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=503, detail="Please try again.") from exc
    if application.cv_text_blind:
        background_tasks.add_task(cv_processing.run_from_blind_text, application.id, application.cv_text_blind)
    return InvitedOut(id=application.id, alias=application.alias, job_id=application.job_id, stage=application.stage,
                      source_channel=application.source_channel)
