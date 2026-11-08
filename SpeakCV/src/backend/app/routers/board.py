"""HR board routes. HR only; every lookup filters on company_id. Routes that run AI are plain `def`."""
import io
import os
import zipfile
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.database.database import get_db
from app.database.sql_models import Application, Company, CompanyMember, Job, User, VoiceSession, VoiceTurn
from app.hiring import analysis, applications, audit, board, consents, cv_processing, decisions, identity, notify
from app.hiring.state import CONSENT_WITHDRAWN, TRANSCRIPTION_FAILED, InvalidTransition, advance
from app.posthire import feedback

router = APIRouter()

BASE = "/api/companies/{company_id}"
MAX_BULK = 200
AUDIO_TYPES = {".webm": "audio/webm", ".mp4": "audio/mp4", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
               ".wav": "audio/wav"}


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=2000)


class CvStatusIn(BaseModel):
    cv_status: Literal["meets", "not_met"]
    reason: str = Field(max_length=2000)

    @field_validator("reason")
    @classmethod
    def _needs_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A reason is required")
        return value


class BulkIn(BaseModel):
    application_ids: list[int] = Field(min_length=1, max_length=MAX_BULK)
    reason: str | None = Field(default=None, max_length=2000)


def _application(db: Session, company_id: int, application_id: int, lock: bool = False) -> Application:
    query = db.query(Application).filter(Application.id == application_id, Application.company_id == company_id,
                                         Application.is_simulated.is_(False))
    if lock:  # a locking read returns the latest committed row, not this request's earlier snapshot
        query = query.populate_existing().with_for_update()
    application = query.first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _live_application(db: Session, company_id: int, application_id: int) -> Application:
    """Once deleted, nothing of it is served, whatever a row still holds."""
    application = _application(db, company_id, application_id)
    if application.anonymized_at is not None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _translate(error: decisions.DecisionError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.get(BASE + "/jobs/{job_id}/board")
def get_board(company_id: int, job_id: int, member: CompanyMember = Depends(require_member("hr")),
              db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": {"id": job.id, "title": job.title}, **board.job_board(db, company_id, job_id)}


@router.get(BASE + "/applications/{app_id}")
def get_application(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                    db: Session = Depends(get_db)):
    return board.detail(db, _live_application(db, company_id, app_id), viewer_id=member.user_id)


@router.post(BASE + "/applications/{app_id}/decision")
def post_decision(company_id: int, app_id: int, body: DecisionIn, background: BackgroundTasks,
                  member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id, lock=True)
    try:
        decisions.decide(db, application, body.decision, member.user_id, body.reason)
    except decisions.DecisionError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    background.add_task(notify.deliver_pending)  # the candidate hears now, not at the next daily run
    if body.decision == "rejected":
        background.add_task(feedback.create_draft_for, application.id)
    return {"id": application.id, "hr_decision": application.hr_decision}


@router.post(BASE + "/applications/{app_id}/cv-status")
def post_cv_status(company_id: int, app_id: int, body: CvStatusIn,
                   member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id, lock=True)
    try:
        decisions.correct_cv_status(db, application, body.cv_status, member.user_id, body.reason)
    except decisions.DecisionError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return {"id": application.id, "cv_status": application.cv_status}


@router.post(BASE + "/applications/{app_id}/reveal")
def post_reveal(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    try:
        identity = decisions.reveal(db, application, member.user_id)
    except decisions.DecisionError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return identity


@router.post(BASE + "/applications/{app_id}/restart")
def post_restart(company_id: int, app_id: int, background: BackgroundTasks,
                 member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id, lock=True)
    try:
        decisions.grant_restart(db, application, member.user_id)
    except decisions.DecisionError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    background.add_task(notify.deliver_pending)
    return {"id": application.id, "stage": application.stage}


@router.post(BASE + "/applications/{app_id}/fast-track")
def post_fast_track(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                    db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id, lock=True)
    try:
        decisions.fast_track(db, application, member.user_id)
    except decisions.DecisionError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return {"id": application.id, "stage": application.stage}


@router.post(BASE + "/applications/{app_id}/invite-anyway")
def post_invite_anyway(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                       db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id, lock=True)
    try:
        decisions.invite_without_cv(db, application, member.user_id)
    except decisions.DecisionError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return {"id": application.id, "stage": application.stage}


@router.post(BASE + "/applications/{app_id}/transcription/retry", status_code=202)
def post_retry_transcription(company_id: int, app_id: int, background: BackgroundTasks,
                             member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    """Claims the retry here, under the lock, so the card moves at once and a second click cannot pay for STT twice."""
    application = _application(db, company_id, app_id, lock=True)
    if (application.anonymized_at is not None or application.stage != "ready_for_hr"
            or application.analysis_status != TRANSCRIPTION_FAILED):
        db.rollback()
        raise HTTPException(status_code=409, detail="Only a failed transcription can be retried")
    application.analysis_status = "running"
    audit.record(db, company_id, member.user_id, "transcription_retried", "application", application.id)
    db.commit()
    background.add_task(analysis.retry_transcription, application.id)
    return {"id": application.id, "analysis_status": "running"}


@router.post(BASE + "/applications/{app_id}/analysis/retry", status_code=202)
def post_retry_analysis(company_id: int, app_id: int, background: BackgroundTasks,
                        member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    if application.anonymized_at is not None or application.stage != "ready_for_hr" or application.analysis_status != "failed":
        raise HTTPException(status_code=409, detail="Only a failed analysis can be retried")
    audit.record(db, company_id, member.user_id, "analysis_retried", "application", application.id)
    db.commit()
    background.add_task(analysis.run, application.id)
    return {"id": application.id, "analysis_status": "failed"}


@router.post(BASE + "/jobs/{job_id}/decisions/bulk")
def post_bulk_reject(company_id: int, job_id: int, body: BulkIn, background: BackgroundTasks,
                     member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    if db.query(Job.id).filter(Job.id == job_id, Job.company_id == company_id).first() is None:
        raise HTTPException(status_code=404, detail="Job not found")
    ids = list(dict.fromkeys(body.application_ids))
    rows = (
        db.query(Application)
        .filter(Application.id.in_(ids), Application.company_id == company_id, Application.job_id == job_id,
                Application.is_simulated.is_(False))
        .populate_existing().with_for_update().all()
    )
    if len(rows) != len(ids):
        db.rollback()
        raise HTTPException(status_code=404, detail="Application not found")
    if any(application.analysis_status == CONSENT_WITHDRAWN for application in rows):
        db.rollback()
        raise HTTPException(status_code=409, detail="A candidate who withdrew consent to recording is decided one at a time")
    if any(application.analysis_status == TRANSCRIPTION_FAILED for application in rows):
        db.rollback()
        raise HTTPException(status_code=409, detail="A candidate whose audio could not be transcribed cannot be rejected in bulk")
    try:
        for application in rows:
            decisions.decide(db, application, "rejected", member.user_id, body.reason)
    except decisions.DecisionError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    background.add_task(notify.deliver_pending)
    for application_id in ids:
        background.add_task(feedback.create_draft_for, application_id)
    return {"rejected": len(rows)}


@router.get(BASE + "/applications/{app_id}/turns/{position}/audio")
def get_audio(company_id: int, app_id: int, position: int, member: CompanyMember = Depends(require_member("hr")),
              db: Session = Depends(get_db)):
    from app.hiring import recordings  # Task 5 owns this module

    application = _application(db, company_id, app_id)
    if application.anonymized_at is not None:
        raise HTTPException(status_code=404, detail="Recording not found")
    turn = (
        db.query(VoiceTurn)
        .join(VoiceSession, VoiceSession.id == VoiceTurn.session_id)
        .filter(VoiceSession.application_id == application.id, VoiceSession.company_id == company_id,
                VoiceTurn.position == position, VoiceTurn.audio_path.isnot(None))
        .order_by(VoiceSession.id.desc()).first()
    )
    if turn is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    try:
        data = recordings.read(turn.audio_path)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=404, detail="Recording not found") from None
    audit.record(db, company_id, member.user_id, "audio_played", "voice_turn", turn.id,
                 payload={"application_id": application.id, "position": position})
    db.commit()
    media_type = AUDIO_TYPES.get(os.path.splitext(turn.audio_path)[1].lower(), "application/octet-stream")
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "private, no-store"})


class ContactUpdateIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)


@router.post(BASE + "/jobs/{job_id}/import-cvs", status_code=201)
def post_import_cvs(
    company_id: int,
    job_id: int,
    background: BackgroundTasks,
    source_channel: str = Form("direct", max_length=32),
    files: list[UploadFile] = File(...),
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "published":
        raise HTTPException(status_code=409, detail="Only a published job can import CVs")

    entries: list[tuple[str, bytes, str]] = []
    for up in files:
        raw = up.file.read()
        ext = os.path.splitext(up.filename or "")[1].lower()
        if ext == ".zip":
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    inner_ext = os.path.splitext(info.filename)[1].lower()
                    if inner_ext in (".pdf", ".docx"):
                        base = os.path.splitext(os.path.basename(info.filename))[0]
                        entries.append((base, zf.read(info.filename), inner_ext))
        elif ext in (".pdf", ".docx"):
            base = os.path.splitext(os.path.basename(up.filename or "cv"))[0]
            entries.append((base, raw, ext))
        else:
            raise HTTPException(status_code=415, detail="Only PDF, DOCX, and ZIP files are accepted")

    imported_ids: list[int] = []
    duplicate_ids: list[int] = []
    missing_contact_ids: list[int] = []

    for base_name, file_bytes, suffix in entries:
        status, app_row, _token = applications.import_cv_file(
            db, job, file_bytes, suffix, source_channel, fallback_name=base_name.replace("_", " ").replace("-", " ")
        )
        if status == "imported" and app_row is not None:
            imported_ids.append(app_row.id)
            background.add_task(cv_processing.run, app_row.id)
        elif status == "duplicate" and app_row is not None:
            duplicate_ids.append(app_row.id)
        elif status == "missing_contact" and app_row is not None:
            missing_contact_ids.append(app_row.id)

    audit.record(
        db, company_id, member.user_id, "cv_bulk_imported", "job", job.id,
        payload={"channel": source_channel, "imported": len(imported_ids), "duplicates": len(duplicate_ids),
                 "missing_contact": len(missing_contact_ids)},
    )
    db.commit()
    return {
        "imported": len(imported_ids),
        "duplicates": len(duplicate_ids),
        "missing_contact": len(missing_contact_ids),
        "imported_ids": imported_ids,
        "duplicate_ids": duplicate_ids,
        "missing_contact_ids": missing_contact_ids,
    }


@router.post(BASE + "/applications/{app_id}/contact")
def post_update_contact(
    company_id: int,
    app_id: int,
    body: ContactUpdateIn,
    background: BackgroundTasks,
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    application = _application(db, company_id, app_id, lock=True)
    clean_email = body.email.strip().lower()
    if "@" not in clean_email:
        raise HTTPException(status_code=422, detail="Invalid email address")
    user = applications.resolve_or_create_candidate_user(db, clean_email, body.name or application.candidate_name)
    application.candidate_user_id = user.id
    application.candidate_email = clean_email
    if body.name:
        application.candidate_name = body.name.strip()[:255]
    if body.phone:
        application.candidate_phone = body.phone.strip()[:64]
    contact = identity.extract_contact_info(
        "", fallback_name=application.candidate_name, fallback_email=clean_email, fallback_phone=application.candidate_phone
    )
    application.contact_hash = contact.contact_hash
    consents.record(db, user.id, company_id, application.id, "cv_processing", consents.VERSION)
    should_process = application.stage in ("missing_contact", "cv_failed")
    db.commit()
    if should_process:
        background.add_task(cv_processing.run, application.id)
    return {"id": application.id, "candidate_email": application.candidate_email, "stage": application.stage}


class ResetCredentialsIn(BaseModel):
    password: str | None = Field(default=None, max_length=128)
    send_email: bool = True


@router.get(BASE + "/candidate-accounts")
def get_candidate_accounts(
    company_id: int,
    job_id: int | None = None,
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Application, Job, User)
        .join(Job, Job.id == Application.job_id)
        .outerjoin(User, User.id == Application.candidate_user_id)
        .filter(
            Application.company_id == company_id,
            Application.is_simulated.is_(False),
            Application.anonymized_at.is_(None),
        )
    )
    if job_id is not None:
        query = query.filter(Application.job_id == job_id)
    items = []
    for app_row, job_row, user_row in query.order_by(Application.id.desc()).all():
        email = app_row.candidate_email or (user_row.email if user_row else None)
        name = app_row.candidate_name or (user_row.full_name if user_row else None)
        raw_token = applications.deterministic_claim_token(app_row) if app_row.candidate_user_id else None
        items.append({
            "application_id": app_row.id,
            "alias": app_row.alias,
            "user_id": app_row.candidate_user_id,
            "account_created": bool(app_row.candidate_user_id),
            "candidate_name": name,
            "candidate_email": email,
            "candidate_phone": app_row.candidate_phone,
            "source_channel": app_row.source_channel,
            "job_id": job_row.id,
            "job_title": job_row.title,
            "job_slug": job_row.slug,
            "stage": app_row.stage,
            "cv_status": app_row.cv_status,
            "hr_decision": app_row.hr_decision,
            "final_outcome": app_row.final_outcome,
            "default_password": applications.default_candidate_password(email) if email else None,
            "claim_token": raw_token,
            "invited_at": app_row.invited_at.isoformat() if app_row.invited_at else None,
            "created_at": app_row.created_at.isoformat() if app_row.created_at else None,
        })
    return {"items": items}


@router.post(BASE + "/candidate-accounts/{app_id}/reset-credentials")
def post_reset_candidate_credentials(
    company_id: int,
    app_id: int,
    body: ResetCredentialsIn,
    background: BackgroundTasks,
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    from app.auth import security

    application = _live_application(db, company_id, app_id)
    email = application.candidate_email
    if not email:
        raise HTTPException(status_code=409, detail="This application has no candidate email yet")
    user = applications.resolve_or_create_candidate_user(db, email, application.candidate_name)
    application.candidate_user_id = user.id
    new_password = (body.password or "").strip() or applications.default_candidate_password(email)
    user.hashed_password = security.get_password_hash(new_password)
    raw_token = applications.issue_claim_token(application)
    job = db.get(Job, application.job_id)
    if body.send_email and job is not None:
        claim_url = f"http://localhost:3001/claim/{raw_token}"
        login_url = "http://localhost:3001/login"
        notify.enqueue(
            db,
            company_id,
            user.id,
            "invited",
            "vi",
            f"Thông tin tài khoản & Link phỏng vấn AI — {job.title}",
            (
                f"Xin chào {application.candidate_name or email},\n\n"
                f"Hệ thống đã khởi tạo tài khoản ứng viên của bạn cho vị trí {job.title}:\n"
                f"• Cổng đăng nhập: {login_url}\n"
                f"• Email đăng nhập: {email}\n"
                f"• Mật khẩu: {new_password}\n\n"
                f"Hoặc bấm trực tiếp vào đường dẫn Magic Link (1-Click vào thẳng phòng phỏng vấn AI không cần mật khẩu):\n"
                f"{claim_url}"
            ),
            application_id=application.id,
        )
    audit.record(db, company_id, member.user_id, "candidate_credentials_reset", "application", application.id)
    db.commit()
    if body.send_email:
        background.add_task(notify.deliver_pending)
    return {
        "application_id": application.id,
        "user_id": user.id,
        "candidate_email": email,
        "password": new_password,
        "claim_token": raw_token,
    }


@router.get(BASE + "/applications/{app_id}/cv-file")
def get_cv_file(
    company_id: int,
    app_id: int,
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    from app.core import storage

    application = _live_application(db, company_id, app_id)
    if not application.cv_file_path:
        raise HTTPException(status_code=404, detail="CV file not found")
    try:
        data = storage.read_bytes(application.cv_file_path)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=404, detail="CV file not found") from None
    ext = (application.cv_suffix or os.path.splitext(application.cv_file_path)[1] or ".docx").lower()
    media_type = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    safe_name = (application.candidate_name or application.alias or f"cv-{app_id}").replace(" ", "_")
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="CV_{safe_name}{ext}"'},
    )


@router.post(BASE + "/applications/{app_id}/invite-from-hold")
def post_invite_from_hold(
    company_id: int,
    app_id: int,
    background: BackgroundTasks,
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    application = _application(db, company_id, app_id, lock=True)
    try:
        advance(application, "invited")
    except InvalidTransition as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Application is not in cv_hold stage") from exc
    application.invited_at = datetime.now(timezone.utc)
    if application.candidate_user_id is not None:
        company = db.get(Company, company_id)
        job = db.get(Job, application.job_id)
        lang = company.default_locale if company and company.default_locale in cv_processing.INVITATION else "en"
        subject, body_text = cv_processing.INVITATION[lang]
        notify.enqueue(
            db, company_id, application.candidate_user_id, "invited", lang,
            subject.format(title=job.title), body_text.format(title=job.title), application_id=application.id
        )
    audit.record(db, company_id, member.user_id, "invited_from_hold", "application", application.id)
    db.commit()
    background.add_task(notify.deliver_pending)
    return {"id": application.id, "stage": application.stage}
