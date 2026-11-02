"""HR board routes. HR only; every lookup filters on company_id. Routes that run AI are plain `def`."""
import os
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.database.database import get_db
from app.database.sql_models import Application, CompanyMember, Job, VoiceSession, VoiceTurn
from app.hiring import analysis, audit, board, decisions, notify
from app.hiring.state import CONSENT_WITHDRAWN, TRANSCRIPTION_FAILED
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
