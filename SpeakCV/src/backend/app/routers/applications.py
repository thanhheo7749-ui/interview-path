"""Candidate routes. Every lookup filters on the signed-in user. No response schema here holds the CV label or text."""
import os
from datetime import timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import security
from app.auth.dependencies import get_authenticated_user, get_optional_user
from app.brain import audience, retriever
from app.core import storage
from app.core.rate_limit import limiter, user_key
from app.core.text_extract import NoExtractableText
from app.core.uploads import CV_UPLOAD_TYPES, read_upload
from app.database.database import get_db
from app.database.sql_models import Application, Company, Job, RequirementResult, User
from app.hiring import applications, audit, consents, cv_processing, decisions, identity, interview_window, jobs, notify
from app.hiring import retention
from app.hiring.hidden_text import CvTooLarge, extract_cv
from app.hiring.state import InvalidTransition, advance
from app.posthire import feedback as rejection_feedback

router = APIRouter()

CV_SUFFIXES = {".pdf", ".docx"}
CV_UPLOAD_LIMIT = "10/hour"  # each upload can cost AI calls
FRIENDLY_STATUS = {
    "submitted": "reading_cv",
    "missing_contact": "reading_cv",
    "cv_processing": "reading_cv",
    "cv_failed": "cv_unreadable",
    "cv_hold": "with_hr",
    "invited": "invited",
    "session_in_progress": "interview_in_progress",
    "session_completed": "with_hr",
    "analyzing": "with_hr",
    "declined_recording": "with_hr",
    "ready_for_hr": "with_hr",
    "withdrawn": "withdrawn",
}
FIT_WORDS = {"met": "matches", "partial": "partly", "not_found": "not_seen"}
NOT_ASSESSED = "not_assessed"  # HR invited this candidate although their CV could not be processed
FIT_NOT_READY = {"submitted", "cv_processing", "cv_failed"}
STYLE_TYPES = ("value", "behavior")
NOT_FOUND = "Application not found"
CV_CONSENT = "cv_processing"


class ApplicationOut(BaseModel):
    id: int
    alias: str
    status: str
    job_title: str
    job_slug: str | None = None
    company_name: str
    company_slug: str
    is_sample: bool
    interview_languages: list[str]
    created_at: str | None
    withdraw_reason: str | None
    processing_error: str | None  # holds only the fixed messages written by cv_processing
    decision: str | None = None  # approved or rejected once HR has decided; never a reason, label or band
    failure_reason: str | None = None  # a fixed code for why the CV failed; the app words it
    email_enabled: bool = False  # whether this deployment can send email at all
    contact_email: str | None = None  # the candidate's own account email, only once they are approved
    feedback: "FeedbackOut | None" = None  # only what HR approved and sent
    reapply_after: str | None = None  # once rejected: the first day the same job takes a new application
    interview_window: dict | None = None  # start/end/timezone when the job schedules interviews, else None
    final_outcome: str | None = None  # hired or not_hired once manager round concludes
    access_token: str | None = None  # returned on passwordless direct apply so candidate is signed in immediately


class LearningItem(BaseModel):
    id: int
    title: str
    url: str
    provider: str
    language: str


class FeedbackOut(BaseModel):
    application_id: int
    language: str
    message: str
    learning: list[LearningItem]
    sent_at: str | None


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
    language: str  # of the text returned, which is what the ledger records
    text: str


def _out(db: Session, application: Application, **overrides) -> ApplicationOut:
    job = db.get(Job, application.job_id)
    company = db.get(Company, application.company_id)
    fields = {
        "id": application.id,
        "alias": application.alias,
        "status": FRIENDLY_STATUS[application.stage],
        "job_title": job.title,
        "job_slug": job.slug,
        "company_name": company.name,
        "company_slug": company.slug,
        "interview_languages": list(job.interview_languages or []),
        "is_sample": bool(company.is_sample),
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "withdraw_reason": application.withdraw_reason,
        "processing_error": application.processing_error,
        "failure_reason": cv_processing.failure_reason(application.processing_error),
        "email_enabled": notify.is_configured(),
        "interview_window": interview_window.payload(job, application),
        "final_outcome": application.final_outcome,
    }
    decision = decisions.visible_to_candidate(application)
    if decision is not None:
        fields["status"] = "decided"
        fields["decision"] = decision
        if decision == "approved" and application.candidate_user_id is not None:
            owner = db.get(User, application.candidate_user_id)
            fields["contact_email"] = owner.email if owner is not None else None
        fields["feedback"] = rejection_feedback.candidate_view(db, application)
        if decision == "rejected":
            # The apply check counts from the newest application to the same job, so this does too.
            newest = application.created_at
            if application.candidate_user_id is not None:
                newest = (db.query(func.max(Application.created_at))
                          .filter(Application.candidate_user_id == application.candidate_user_id,
                                  Application.job_id == application.job_id).scalar())
            if newest is not None:
                fields["reapply_after"] = (newest + timedelta(days=consents.REAPPLY_DAYS)).replace(tzinfo=timezone.utc).isoformat()
    return ApplicationOut(**{**fields, **overrides})


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail=NOT_FOUND)


def _owned(db: Session, user: User, application_id: int, lock: bool = False) -> Application:
    return _owned_by(db, user.id, application_id, lock)


def _owned_by(db: Session, user_id: int, application_id: int, lock: bool = False) -> Application:
    query = db.query(Application).filter(Application.id == application_id, Application.candidate_user_id == user_id)
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


def _apply(db: Session, user: User | None, slug: str, data: bytes, suffix: str, src: str | None, consent_version: str,
           consent_language: str | None = None, candidate_email: str | None = None,
           candidate_name: str | None = None) -> ApplicationOut:
    job = db.query(Job).filter(Job.slug == slug, Job.status != "draft").first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    _ensure_fits(data, suffix)
    was_guest = user is None
    if user is None:
        extracted_email, extracted_name = None, None
        try:
            raw_text = extract_cv(data, suffix).text
            contact = identity.extract_contact_info(raw_text, fallback_name=candidate_name, fallback_email=candidate_email)
            extracted_email, extracted_name = contact.email, contact.name
        except (NoExtractableText, CvTooLarge):
            extracted_email = (candidate_email or "").strip().lower() or None
            extracted_name = (candidate_name or "").strip() or None
        email_to_use = (candidate_email or extracted_email or "").strip().lower()
        name_to_use = (candidate_name or extracted_name or "").strip() or None
        if not email_to_use or "@" not in email_to_use:
            raise HTTPException(status_code=422, detail="Please provide your email address to apply.")
        user = applications.resolve_or_create_candidate_user(db, email_to_use, name_to_use)
        db.commit()
    try:
        application = applications.create_application(db, user, job, data, suffix, src, consent_version, consent_language)
    except applications.JobNotOpen as exc:
        raise HTTPException(status_code=409, detail="This job is closed") from exc
    except applications.AlreadyApplied as exc:
        raise HTTPException(status_code=409, detail={
            "message": "You have already applied to this job.", "reapply_after": exc.reapply_after.isoformat(),
        }) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=503, detail="Please try again.") from exc
    if candidate_name:
        application.candidate_name = candidate_name.strip()[:255]
    if candidate_email:
        application.candidate_email = candidate_email.strip().lower()[:255]
    if candidate_name or candidate_email:
        db.commit()
    token = security.create_access_token({"sub": user.email}) if was_guest else None
    return _out(db, application, access_token=token)


@router.post("/api/public/jobs/{slug}/apply", response_model=ApplicationOut, status_code=201)
@limiter.limit(CV_UPLOAD_LIMIT, key_func=user_key)
async def apply_to_job(
    request: Request,
    slug: str,
    background_tasks: BackgroundTasks,
    consent_version: str = Form(..., max_length=30),
    src: str | None = Form(None, max_length=64),
    consent_language: str | None = Form(None, max_length=10),
    candidate_email: str | None = Form(None, max_length=255),
    candidate_name: str | None = Form(None, max_length=255),
    file: UploadFile = File(...),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if consent_version != consents.VERSION:
        raise HTTPException(status_code=409, detail={
            "message": "The consent text has changed. Please read it again.", "current_version": consents.VERSION,
        })
    suffix = _suffix(file)
    data = await read_upload(file, CV_UPLOAD_TYPES)
    created = await run_in_threadpool(
        _apply, db, user, slug, data, suffix, src, consent_version, consent_language, candidate_email, candidate_name
    )
    background_tasks.add_task(cv_processing.run, created.id)
    return created


class ClaimIn(BaseModel):
    token: str = Field(..., min_length=8, max_length=128)
    consent_version: str = Field(..., max_length=30)
    consent_language: str | None = Field(default=None, max_length=10)


@router.get("/api/public/applications/claim/{token}")
def get_claim_info(token: str, db: Session = Depends(get_db)):
    import hashlib
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    application = db.query(Application).filter(Application.claim_token_hash == token_hash, Application.anonymized_at.is_(None)).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Invalid or expired claim link")
    job = db.get(Job, application.job_id)
    company = db.get(Company, application.company_id)
    return {
        "application_id": application.id,
        "candidate_name": application.candidate_name,
        "candidate_email": application.candidate_email,
        "job_title": job.title if job else "",
        "company_name": company.name if company else "",
        "company_id": application.company_id,
        "stage": application.stage,
        "consent_version": consents.VERSION,
    }


@router.post("/api/public/applications/claim")
def claim_application(body: ClaimIn, db: Session = Depends(get_db)):
    import hashlib
    if body.consent_version != consents.VERSION:
        raise HTTPException(status_code=409, detail={
            "message": "The consent text has changed. Please read it again.", "current_version": consents.VERSION,
        })
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    application = (
        db.query(Application)
        .filter(Application.claim_token_hash == token_hash, Application.anonymized_at.is_(None))
        .populate_existing().with_for_update().first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Invalid or expired claim link")
    email = application.candidate_email
    if not email and application.candidate_user_id:
        owner = db.get(User, application.candidate_user_id)
        email = owner.email if owner else None
    if not email:
        raise HTTPException(status_code=409, detail="Application has no candidate email yet")
    user = applications.resolve_or_create_candidate_user(db, email, application.candidate_name)
    application.candidate_user_id = user.id
    consents.record(db, user.id, application.company_id, application.id, CV_CONSENT, body.consent_version,
                    language=body.consent_language)
    db.commit()
    token = security.create_access_token({"sub": user.email})
    return {
        "application_id": application.id,
        "access_token": token,
        "token_type": "bearer",
        "email": user.email,
    }


@router.get("/api/me/applications", response_model=list[ApplicationOut])
def my_applications(user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    rows = db.query(Application).filter(Application.candidate_user_id == user.id).order_by(Application.id.desc()).all()
    return [_out(db, row) for row in rows]


@router.get("/api/applications/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    return _out(db, _owned(db, user, application_id))


@router.get("/api/applications/{application_id}/feedback", response_model=FeedbackOut)
def get_feedback(application_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    view = rejection_feedback.candidate_view(db, _owned(db, user, application_id))
    if view is None:  # a draft looks exactly like no feedback at all
        raise HTTPException(status_code=404, detail="Feedback not found")
    return view


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
        FitItem(requirement_id=row.id, text=row.text, fit=FIT_WORDS.get(statuses.get(row.id), NOT_ASSESSED))
        for row in jobs.requirements_for(db, application)
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


def _cv_consent_withdrawn() -> HTTPException:
    return HTTPException(status_code=409, detail={
        "code": consents.CV_CONSENT_WITHDRAWN, "message": "You withdrew consent to CV processing for this application.",
    })


def _check_can_reupload(db: Session, user: User, application_id: int) -> None:
    application = _owned(db, user, application_id)
    if consents.was_withdrawn(db, application.id, CV_CONSENT):
        raise _cv_consent_withdrawn()
    if application.stage != "cv_failed":
        raise HTTPException(status_code=409, detail="This application is not waiting for a new CV")


def _replace_cv(db: Session, user: User, application_id: int, data: bytes, suffix: str) -> ApplicationOut:
    _ensure_fits(data, suffix)
    user_id = user.id
    # The upload took a while. The rollback ends this request's snapshot and the lock comes first in the new transaction,
    # so the read of the consent below sees a withdrawal committed in the meantime.
    db.rollback()
    application = _owned_by(db, user_id, application_id, lock=True)
    if consents.was_withdrawn(db, application_id, CV_CONSENT):
        raise _cv_consent_withdrawn()
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


@router.delete("/api/me/applications/{application_id}", status_code=204)
def delete_my_application(application_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    application = _owned(db, user, application_id, lock=True)
    if not retention.try_anonymize(db, application, trigger=retention.TRIGGER_CANDIDATE):
        raise HTTPException(status_code=503, detail="Your data could not be deleted just now. Please try again.")


@router.get("/api/public/consents/{purpose}", response_model=ConsentOut)
def public_consent_text(
    purpose: str,
    language: str = Query("en", max_length=10),
    company_id: int | None = None,
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
    return ConsentOut(purpose=purpose, version=current.version, language=current.language, text=current.text)


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
    return ConsentOut(purpose=purpose, version=current.version, language=current.language, text=current.text)


@router.get("/api/applications/{application_id}/consents/{purpose}", response_model=ConsentOut)
def application_consent_text(
    application_id: int,
    purpose: str,
    language: str = Query("en", max_length=10),
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """The text this candidate agrees to: with this company's retention period, in the language it says it is in."""
    application = _owned(db, user, application_id)
    if purpose not in consents.PURPOSES:
        raise HTTPException(status_code=404, detail="Consent text not found")
    company = db.get(Company, application.company_id)
    current = consents.current_text(purpose, language, retention_days=company.retention_days)
    return ConsentOut(purpose=purpose, version=current.version, language=current.language, text=current.text)
