"""Candidate routes for the recorded interview. Every lookup filters on the signed-in user; no response holds a label."""
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.types import AIError
from app.auth.dependencies import get_authenticated_user
from app.core.rate_limit import VOICE_ANSWER_LIMIT, VOICE_QUESTION_AUDIO_LIMIT, VOICE_START_LIMIT, limiter, user_key
from app.core.uploads import CHUNK_SIZE
from app.database.database import get_db
from app.database.sql_models import Application, Company, CompanyMember, Job, User, VoiceSession, VoiceTurn
from app.hiring import audit, consents, planner, voice
from app.hiring.state import advance

router = APIRouter()
logger = logging.getLogger(__name__)

PURPOSE = "screening"
CONSENT_PURPOSE = "recording_screening"
NOT_FOUND = "Not found"
START_CLAIM_SECONDS = 120  # planning calls AI: one start pays for it, and a claim left by a crash expires
TOO_LONG = "This recording is longer than 3 minutes. Please record a shorter answer."


class StartIn(BaseModel):
    consent_version: str = Field(max_length=30)
    language: str = Field(max_length=10)


class StateOut(BaseModel):
    session_id: int
    status: str
    position: int | None
    question_text: str | None
    question_source: str | None
    why: str | None
    total: int
    time_left_seconds: int
    is_followup: bool
    notice: str | None


def state_out(session_id: int, state: voice.SessionState) -> StateOut:
    return StateOut(session_id=session_id, **asdict(state))


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail=NOT_FOUND)


def _owned_application(db: Session, user_id: int, application_id: int, lock: bool = False) -> Application:
    query = db.query(Application).filter(Application.id == application_id, Application.candidate_user_id == user_id)
    if lock:
        query = query.populate_existing().with_for_update()
    application = query.first()
    if application is None:
        raise _not_found()
    return application


def _owned_session(db: Session, user_id: int, session_id: int, purpose: str | None = None) -> VoiceSession:
    """A session belongs to its owner, whatever its purpose. The /api/screening aliases pass the purpose they serve."""
    query = db.query(VoiceSession).filter(VoiceSession.id == session_id, VoiceSession.owner_user_id == user_id)
    if purpose is not None:
        query = query.filter(VoiceSession.purpose == purpose)
    session = query.first()
    if session is None:
        raise _not_found()
    if session.purpose == "intake" and db.query(CompanyMember.id).filter(
        CompanyMember.company_id == session.company_id, CompanyMember.user_id == user_id,
        CompanyMember.role == "manager",
    ).first() is None:
        raise _not_found()  # a manager who was removed, or changed role, no longer answers for the company
    return session


def _active_session(db: Session, application_id: int) -> VoiceSession | None:
    return (
        db.query(VoiceSession)
        .filter(VoiceSession.application_id == application_id, VoiceSession.status.in_(voice.ACTIVE_STATUSES))
        .order_by(VoiceSession.id.desc())
        .first()
    )


def _current_state(db: Session, session: VoiceSession) -> voice.SessionState:
    try:
        return voice.current_state(db, session)
    except voice.SessionGone as exc:
        raise _not_found() from exc


def _resume(db: Session, session: VoiceSession) -> StateOut | None:
    """The state of a session still running, or None if the clock has just finished it."""
    session_id = session.id
    state = _current_state(db, session)
    return None if state.status in voice.TERMINAL_STATUSES else state_out(session_id, state)


def _check_can_start(application: Application) -> None:
    if application.stage != "invited":
        raise HTTPException(status_code=409, detail="This interview cannot be started now")


def _release_start_claim(db: Session, application_id: int, claim: datetime) -> None:
    """Clear this request's claim. Only its own: one that expired and was taken over stays."""
    try:
        db.rollback()
        db.query(Application).filter(Application.id == application_id, Application.start_claimed_at == claim).update(
            {Application.start_claimed_at: None}, synchronize_session=False)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Could not clear the start claim of application %s: %s", application_id, type(exc).__name__)


def _claim_start(db: Session, user_id: int, application_id: int):
    """Claim the right to plan (which calls AI) under the lock. Returns (claim, None), or (None, state) if a session is
    already running. A second start while one is planning gets 409 instead of paying again."""
    db.rollback()
    application = _owned_application(db, user_id, application_id, lock=True)
    active = _active_session(db, application_id)
    if active is not None and (resumed := _resume(db, active)) is not None:
        return None, resumed
    _check_can_start(application)
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    started = application.start_claimed_at
    if started is not None:
        started = started.astimezone(timezone.utc).replace(tzinfo=None) if started.tzinfo else started
        if (now - started).total_seconds() < START_CLAIM_SECONDS:
            db.rollback()
            raise HTTPException(status_code=409, detail="Your interview is being prepared. Please wait a moment.")
    application.start_claimed_at = now
    db.commit()
    return now, None


@router.post("/api/screening/{application_id}/start", response_model=StateOut)
@limiter.limit(VOICE_START_LIMIT, key_func=user_key)
def start(request: Request, application_id: int, body: StartIn, user: User = Depends(get_authenticated_user),
          db: Session = Depends(get_db)):
    user_id = user.id
    application = _owned_application(db, user_id, application_id)
    active = _active_session(db, application_id)
    if active is not None and (resumed := _resume(db, active)) is not None:
        return resumed
    if body.consent_version != consents.VERSION:
        raise HTTPException(status_code=409, detail={
            "message": "The consent text has changed. Please read it again.", "current_version": consents.VERSION,
        })
    _check_can_start(application)
    job = db.get(Job, application.job_id)
    allowed = job.interview_languages or [db.get(Company, application.company_id).default_locale]
    if body.language not in allowed:
        raise HTTPException(status_code=422, detail="This language is not offered for this job")

    claim, resumed = _claim_start(db, user_id, application_id)
    if resumed is not None:
        return resumed
    try:
        return _plan_and_start(db, user_id, application_id, application, body)
    finally:
        _release_start_claim(db, application_id, claim)


def _plan_and_start(db: Session, user_id: int, application_id: int, application: Application, body: StartIn) -> StateOut:
    plan = planner.build_plan(db, application, body.language)

    # Planning took a while with no lock held, so another request may have started this session. The rollback ends this
    # request's snapshot and the lock comes first in the new transaction, so the reads below see what that request committed.
    db.rollback()
    application = _owned_application(db, user_id, application_id, lock=True)
    active = _active_session(db, application_id)
    if active is not None and (resumed := _resume(db, active)) is not None:
        return resumed
    _check_can_start(application)
    consents.record(db, user_id, application.company_id, application_id, CONSENT_PURPOSE, body.consent_version,
                    language=body.language)
    session = voice.create_session(
        db, company_id=application.company_id, purpose=PURPOSE, owner_user_id=user_id, language=body.language,
        plan=plan, application_id=application_id,
    )
    # HR's single restart is counted on the session, so the new session must carry the count forward.
    session.restart_count = (
        db.query(func.max(VoiceSession.restart_count)).filter(VoiceSession.application_id == application_id).scalar() or 0
    )
    advance(application, "session_in_progress")
    audit.record(db, application.company_id, user_id, "voice_session_started", "voice_session", session.id,
                 payload={"language": body.language, "questions": len(plan)})
    db.commit()
    session_id = session.id
    return state_out(session_id, _current_state(db, session))


def _get_state(db: Session, user_id: int, session_id: int, purpose: str | None) -> StateOut:
    return state_out(session_id, _current_state(db, _owned_session(db, user_id, session_id, purpose)))


@router.get("/api/voice/{session_id}/state", response_model=StateOut)
def get_voice_state(session_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    return _get_state(db, user.id, session_id, None)


@router.get("/api/screening/{session_id}/state", response_model=StateOut)
def get_state(session_id: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    return _get_state(db, user.id, session_id, PURPOSE)


async def _read_audio(file: UploadFile) -> tuple[bytes, str]:
    """Like read_upload, with this route's own types and limit. Stops reading as soon as the limit is passed."""
    mime_type = (file.content_type or "").split(";")[0].strip().lower()
    if mime_type not in voice.ALLOWED_AUDIO:
        raise HTTPException(status_code=415, detail="This audio type is not accepted")
    limit = voice.max_audio_bytes(mime_type)  # what 200 seconds can weigh in this type, never over the file limit
    chunks, total = [], 0
    while chunk := await file.read(CHUNK_SIZE):
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=TOO_LONG)
        chunks.append(chunk)
    if not total:
        raise HTTPException(status_code=422, detail="This recording is empty")
    return b"".join(chunks), mime_type


def _submit(db: Session, user_id: int, session_id: int, position: int, audio: bytes, mime_type: str,
            purpose: str | None) -> StateOut:
    session = _owned_session(db, user_id, session_id, purpose)
    # Only a candidate's recording rests on the consent they gave; a manager is a member of the company.
    if session.purpose == PURPOSE and not consents.has_active(
        db, user_id, CONSENT_PURPOSE, application_id=session.application_id
    ):
        raise HTTPException(status_code=409, detail="Your recording consent has been withdrawn")
    try:
        return state_out(session_id, voice.submit_answer(db, session, position, audio, mime_type))
    except voice.PositionNotCurrent as exc:
        raise HTTPException(status_code=409, detail="This is not the current question") from exc
    except voice.TranscriptionInFlight as exc:
        raise HTTPException(
            status_code=409, detail="Your recording of this answer is still being processed. Please wait a moment.",
        ) from exc
    except voice.AudioTooLong as exc:
        raise HTTPException(status_code=413, detail=TOO_LONG) from exc
    except voice.SessionGone as exc:
        raise _not_found() from exc


async def _answer(db: Session, user_id: int, session_id: int, position: int, file: UploadFile, purpose: str | None):
    await run_in_threadpool(_owned_session, db, user_id, session_id, purpose)
    audio, mime_type = await _read_audio(file)
    return await run_in_threadpool(_submit, db, user_id, session_id, position, audio, mime_type, purpose)


# Declares only the file: a transcript or history sent by the client has nowhere to go.
@router.post("/api/voice/{session_id}/turns/{position}/answer", response_model=StateOut)
@limiter.limit(VOICE_ANSWER_LIMIT, key_func=user_key)
async def submit_voice_answer(
    request: Request,
    session_id: int,
    position: int,
    file: UploadFile = File(...),
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return await _answer(db, user.id, session_id, position, file, None)


@router.post("/api/screening/{session_id}/turns/{position}/answer", response_model=StateOut)
@limiter.limit(VOICE_ANSWER_LIMIT, key_func=user_key)
async def submit_answer(
    request: Request,
    session_id: int,
    position: int,
    file: UploadFile = File(...),
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return await _answer(db, user.id, session_id, position, file, PURPOSE)


def _question_audio(db: Session, user_id: int, session_id: int, position: int, purpose: str | None):
    session = _owned_session(db, user_id, session_id, purpose)
    session_id = session.id
    try:
        audio, mime_type = voice.question_audio(db, session_id, position)
    except (voice.NoSuchTurn, voice.SessionGone) as exc:
        raise _not_found() from exc
    except voice.SessionEnded as exc:
        raise HTTPException(status_code=409, detail="This interview has ended") from exc
    except AIError:
        return Response(status_code=204)
    return Response(content=audio, media_type=mime_type, headers={"Cache-Control": "no-store"})


@router.get("/api/voice/{session_id}/turns/{position}/question-audio")
@limiter.limit(VOICE_QUESTION_AUDIO_LIMIT, key_func=user_key)
def voice_question_audio(request: Request, session_id: int, position: int, user: User = Depends(get_authenticated_user),
                         db: Session = Depends(get_db)):
    return _question_audio(db, user.id, session_id, position, None)


@router.get("/api/screening/{session_id}/turns/{position}/question-audio")
@limiter.limit(VOICE_QUESTION_AUDIO_LIMIT, key_func=user_key)
def question_audio(request: Request, session_id: int, position: int, user: User = Depends(get_authenticated_user),
                   db: Session = Depends(get_db)):
    return _question_audio(db, user.id, session_id, position, PURPOSE)
