"""Candidate routes for the recorded interview. Every lookup filters on the signed-in user; no response holds a label."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.types import AIError
from app.auth.dependencies import get_authenticated_user
from app.core.uploads import CHUNK_SIZE
from app.database.database import get_db
from app.database.sql_models import Application, Company, Job, User, VoiceSession, VoiceTurn
from app.hiring import audit, consents, planner, voice
from app.hiring.state import advance

router = APIRouter()

PURPOSE = "screening"
CONSENT_PURPOSE = "recording_screening"
CV_CONSENT_PURPOSE = "cv_processing"
NOT_FOUND = "Not found"


class StartIn(BaseModel):
    consent_version: str = Field(max_length=30)
    language: str = Field(max_length=10)
    consent_language: str | None = Field(default=None, max_length=10)  # the language the consent route said it returned


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


def _check_can_start(db: Session, application: Application) -> None:
    if consents.was_withdrawn(db, application.id, CV_CONSENT_PURPOSE):  # planning runs AI over the CV
        raise HTTPException(status_code=409, detail={
            "code": consents.CV_CONSENT_WITHDRAWN, "message": "You withdrew consent to CV processing for this application.",
        })
    if application.stage != "invited":
        raise HTTPException(status_code=409, detail="This interview cannot be started now")


@router.post("/api/screening/{application_id}/start", response_model=StateOut)
def start(application_id: int, body: StartIn, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    user_id = user.id
    application = _owned_application(db, user_id, application_id)
    active = _active_session(db, application_id)
    if active is not None and (resumed := _resume(db, active)) is not None:
        return resumed
    if body.consent_version != consents.VERSION:
        raise HTTPException(status_code=409, detail={
            "message": "The consent text has changed. Please read it again.", "current_version": consents.VERSION,
        })
    _check_can_start(db, application)
    job = db.get(Job, application.job_id)
    allowed = job.interview_languages or [db.get(Company, application.company_id).default_locale]
    if body.language not in allowed:
        raise HTTPException(status_code=422, detail="This language is not offered for this job")

    plan = planner.build_plan(db, application, body.language)

    # Planning took a while with no lock held, so another request may have started this session. The rollback ends this
    # request's snapshot and the lock comes first in the new transaction, so the reads below see what that request committed.
    db.rollback()
    application = _owned_application(db, user_id, application_id, lock=True)
    active = _active_session(db, application_id)
    if active is not None and (resumed := _resume(db, active)) is not None:
        return resumed
    _check_can_start(db, application)
    consents.record(db, user_id, application.company_id, application_id, CONSENT_PURPOSE, body.consent_version,
                    language=body.consent_language)
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
    chunks, total = [], 0
    while chunk := await file.read(CHUNK_SIZE):
        total += len(chunk)
        if total > voice.MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="This recording is too large")
        chunks.append(chunk)
    if not total:
        raise HTTPException(status_code=422, detail="This recording is empty")
    return b"".join(chunks), mime_type


def _recording_consent_withdrawn() -> HTTPException:
    return HTTPException(status_code=409, detail={
        "code": consents.RECORDING_CONSENT_WITHDRAWN, "message": "Your recording consent has been withdrawn",
    })


def _submit(db: Session, user_id: int, session_id: int, position: int, audio: bytes, mime_type: str,
            purpose: str | None) -> StateOut:
    session = _owned_session(db, user_id, session_id, purpose)
    # Only a candidate's recording rests on the consent they gave; a manager is a member of the company.
    if session.purpose == PURPOSE and not consents.has_active(
        db, user_id, CONSENT_PURPOSE, application_id=session.application_id
    ):
        raise _recording_consent_withdrawn()
    try:
        return state_out(session_id, voice.submit_answer(db, session, position, audio, mime_type))
    except voice.ConsentWithdrawn as exc:
        raise _recording_consent_withdrawn() from exc
    except voice.PositionNotCurrent as exc:
        raise HTTPException(status_code=409, detail="This is not the current question") from exc
    except voice.SessionGone as exc:
        raise _not_found() from exc


async def _answer(db: Session, user_id: int, session_id: int, position: int, file: UploadFile, purpose: str | None):
    await run_in_threadpool(_owned_session, db, user_id, session_id, purpose)
    audio, mime_type = await _read_audio(file)
    return await run_in_threadpool(_submit, db, user_id, session_id, position, audio, mime_type, purpose)


# Declares only the file: a transcript or history sent by the client has nowhere to go.
@router.post("/api/voice/{session_id}/turns/{position}/answer", response_model=StateOut)
async def submit_voice_answer(
    session_id: int,
    position: int,
    file: UploadFile = File(...),
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return await _answer(db, user.id, session_id, position, file, None)


@router.post("/api/screening/{session_id}/turns/{position}/answer", response_model=StateOut)
async def submit_answer(
    session_id: int,
    position: int,
    file: UploadFile = File(...),
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return await _answer(db, user.id, session_id, position, file, PURPOSE)


def _question_audio(db: Session, user_id: int, session_id: int, position: int, purpose: str | None):
    session = _owned_session(db, user_id, session_id, purpose)
    turn = db.query(VoiceTurn).filter_by(session_id=session.id, position=position).first()
    if turn is None or not turn.question_text:
        raise _not_found()
    text, language, company_id = turn.question_text, session.language, session.company_id
    db.rollback()  # hold no snapshot during a slow call
    try:
        result = gateway.synthesize(text, language, None, "session_tts", company_id)
    except AIError:
        return Response(status_code=204)
    return Response(content=result.audio, media_type=result.mime_type, headers={"Cache-Control": "no-store"})


@router.get("/api/voice/{session_id}/turns/{position}/question-audio")
def voice_question_audio(session_id: int, position: int, user: User = Depends(get_authenticated_user),
                         db: Session = Depends(get_db)):
    return _question_audio(db, user.id, session_id, position, None)


@router.get("/api/screening/{session_id}/turns/{position}/question-audio")
def question_audio(session_id: int, position: int, user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    return _question_audio(db, user.id, session_id, position, PURPOSE)
