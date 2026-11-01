"""Candidate routes. Every lookup filters on the signed-in user. No response schema here holds the CV label or text."""
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_authenticated_user
from app.brain import audience, retriever
from app.core import storage
from app.core.rate_limit import limiter, user_key
from app.core.uploads import CV_UPLOAD_TYPES, read_upload
from app.database.database import get_db
from app.database.sql_models import Application, Company, Job, RequirementResult, User
from app.hiring import applications, audit, consents, cv_processing, jobs
from app.hiring.state import InvalidTransition, advance

router = APIRouter()

CV_SUFFIXES = {".pdf", ".docx"}
CV_UPLOAD_LIMIT = "10/hour"  # each upload can cost AI calls
FRIENDLY_STATUS = {
    "submitted": "reading_cv",
    "cv_processing": "reading_cv",
    "cv_failed": "cv_unreadable",
    "invited": "invited",
    "session_in_progress": "interview_in_progress",
    "session_completed": "with_hr",
    "analyzing": "with_hr",
    "declined_recording": "with_hr",
    "ready_for_hr": "with_hr",
    "withdrawn": "withdrawn",
}
FIT_WORDS = {"met": "matches", "partial": "partly", "not_found": "not_seen"}
FIT_NOT_READY = {"submitted", "cv_processing", "cv_failed"}
STYLE_TYPES = ("value", "behavior")
NOT_FOUND = "Application not found"


class ApplicationOut(BaseModel):
    id: int
    alias: str
    status: str
    job_title: str
    company_name: str
    is_sample: bool
    created_at: str | None
    withdraw_reason: str | None
    processing_error: str | None  # holds only the fixed messages written by cv_processing


class FitItem(BaseModel):
    requirement_id: int
    text: str
    fit: str


class StyleItem(BaseModel):
    type: str
    title: str
    body: str


class FitOut(BaseModel):
    requirements: list[FitItem]
    team_style: list[StyleItem]


class WithdrawIn(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ConsentOut(BaseModel):
    purpose: str
    version: str
    text: str


def _out(db: Session, application: Application, **overrides) -> ApplicationOut:
    job = db.get(Job, application.job_id)
    company = db.get(Company, application.company_id)
    fields = {
        "id": application.id,
        "alias": application.alias,
        "status": FRIENDLY_STATUS[application.stage],
        "job_title": job.title,
        "company_name": company.name,
        "is_sample": bool(company.is_sample),
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "withdraw_reason": application.withdraw_reason,
        "processing_error": application.processing_error,
    }
    return ApplicationOut(**{**fields, **overrides})


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail=NOT_FOUND)


def _owned(db: Session, user: User, application_id: int, lock: bool = False) -> Application:
    query = db.query(Application).filter(Application.id == application_id, Application.candidate_user_id == user.id)
    if lock:  # a locking read returns the latest committed row, not this request's earlier snapshot
        query = query.populate_existing().with_for_update()
    application = query.first()
    if application is None:
        raise _not_found()
    return application


def _suffix(file: UploadFile) -> str:
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in CV_SUFFIXES:
        raise HTTPException(status_code=415, detail="Only PDF and DOCX files are accepted")
    return suffix


def _ensure_fits(data: bytes, suffix: str) -> None:
    try:
        applications.ensure_cv_fits(data, suffix)
    except applications.CvTooLong as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _apply(db: Session, user: User, slug: str, data: bytes, suffix: str, src: str | None, consent_version: str) -> ApplicationOut:
    job = db.query(Job).filter(Job.slug == slug, Job.status != "draft").first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    _ensure_fits(data, suffix)
    try:
        application = applications.create_application(db, user, job, data, suffix, src, consent_version)
    except applications.JobNotOpen as exc:
        raise HTTPException(status_code=409, detail="This job is closed") from exc
    except applications.AlreadyApplied as exc:
        raise HTTPException(status_code=409, detail={
            "message": "You have already applied to this job.", "reapply_after": exc.reapply_after.isoformat(),
        }) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=503, detail="Please try again.") from exc
    return _out(db, application)


@router.post("/api/public/jobs/{slug}/apply", response_model=ApplicationOut, status_code=201)
@limiter.limit(CV_UPLOAD_LIMIT, key_func=user_key)
async def apply_to_job(
    request: Request,
    slug: str,
    background_tasks: BackgroundTasks,
    consent_version: str = Form(..., max_length=30),
    src: str | None = Form(None, max_length=64),
    file: UploadFile = File(...),
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    if consent_version != consents.VERSION:
        raise HTTPException(status_code=409, detail={
            "message": "The consent text has changed. Please read it again.", "current_version": consents.VERSION,
        })
    suffix = _suffix(file)
    data = await read_upload(file, CV_UPLOAD_TYPES)
    created = await run_in_threadpool(_apply, db, user, slug, data, suffix, src, consent_version)
    background_tasks.add_task(cv_processing.run, created.id)
    return created


@router.get("/api/me/applications", response_model=list[ApplicationOut])
def my_applications(user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    rows = db.query(Application).filter(Application.candidate_user_id == user.id).order_by(Application.id.desc()).all()
    return [_out(db, row) for row in rows]


@router.get("/api/applications/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    return _out(db, _owned(db, user, application_id))


def _team_style(db: Session, job: Job) -> list[StyleItem]:
    candidate = audience.candidate(job.company_id)
    profile = retriever.role_profile(db, candidate, job.role_node_id) if job.role_node_id is not None else None
    if profile is not None:
        items = (*profile.values, *profile.behaviors)
    else:
        nodes, _ = retriever.visible_graph(db, candidate)
        items = [node for node in nodes if node.type in STYLE_TYPES]
    return [StyleItem(type=item.type, title=item.title, body=item.body) for item in items]


@router.get("/api/applications/{application_id}/fit", response_model=FitOut)
def get_fit(application_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    application = _owned(db, user, application_id)
    if application.stage in FIT_NOT_READY:
        raise HTTPException(status_code=409, detail="Your CV has not been read yet")
    statuses = {
        row.requirement_id: row.status
        for row in db.query(RequirementResult).filter_by(application_id=application.id, source="cv")
    }
    requirements = [
        FitItem(requirement_id=row.id, text=row.text, fit=FIT_WORDS.get(statuses.get(row.id), "not_seen"))
        for row in jobs.active_requirements(db, application.job_id)
        if row.visibility == "public"
    ]
    return FitOut(requirements=requirements, team_style=_team_style(db, db.get(Job, application.job_id)))


@router.post("/api/applications/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw(
    application_id: int,
    body: WithdrawIn | None = None,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    application = _owned(db, user, application_id, lock=True)
    try:
        advance(application, "withdrawn")
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail="This application cannot be withdrawn now") from exc
    application.withdraw_reason = ((body.reason or "").strip() or None) if body else None
    audit.record(db, application.company_id, user.id, "application_withdrawn", "application", application.id)
    db.commit()
    return _out(db, application)


def _check_can_reupload(db: Session, user: User, application_id: int) -> None:
    if _owned(db, user, application_id).stage != "cv_failed":
        raise HTTPException(status_code=409, detail="This application is not waiting for a new CV")


def _replace_cv(db: Session, user: User, application_id: int, data: bytes, suffix: str) -> ApplicationOut:
    _ensure_fits(data, suffix)
    application = _owned(db, user, application_id, lock=True)
    if application.stage != "cv_failed":
        raise HTTPException(status_code=409, detail="This application is not waiting for a new CV")
    old_path = application.cv_file_path
    new_path = storage.save_bytes(application.company_id, "cv", suffix, data)
    application.cv_file_path = new_path
    application.cv_suffix = suffix
    application.processing_error = None
    try:
        db.commit()
    except Exception:
        storage.delete(new_path)
        raise
    if old_path:
        storage.delete(old_path)
    return _out(db, application, status=FRIENDLY_STATUS["cv_processing"])


@router.post("/api/applications/{application_id}/reupload", response_model=ApplicationOut)
@limiter.limit(CV_UPLOAD_LIMIT, key_func=user_key)
async def reupload(
    request: Request,
    application_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    await run_in_threadpool(_check_can_reupload, db, user, application_id)
    suffix = _suffix(file)
    data = await read_upload(file, CV_UPLOAD_TYPES)
    updated = await run_in_threadpool(_replace_cv, db, user, application_id, data, suffix)
    background_tasks.add_task(cv_processing.run, application_id)
    return updated


@router.post("/api/applications/{application_id}/decline-recording", response_model=ApplicationOut)
def decline_recording(application_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    application = _owned(db, user, application_id, lock=True)
    try:
        advance(application, "declined_recording")
        advance(application, "ready_for_hr")
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail="Recording cannot be declined now") from exc
    audit.record(db, application.company_id, user.id, "recording_declined", "application", application.id)
    db.commit()
    return _out(db, application)


@router.get("/api/consents/{purpose}", response_model=ConsentOut)
def consent_text(
    purpose: str,
    language: str = Query("en", max_length=10),
    company_id: int | None = None,
    _: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    if purpose not in consents.PURPOSES:
        raise HTTPException(status_code=404, detail="Consent text not found")
    retention_days = consents.DEFAULT_RETENTION_DAYS
    if company_id is not None:
        company = db.get(Company, company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Consent text not found")
        retention_days = company.retention_days
    current = consents.current_text(purpose, language, retention_days=retention_days)
    return ConsentOut(purpose=purpose, version=current.version, text=current.text)
