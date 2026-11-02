"""Hiring requests and Manager Intake. HR opens a request and names the manager; only that manager answers the intake.
Every lookup filters on company_id. The voice turns of an intake use the generic /api/voice routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.bridges import intake
from app.database.database import get_db
from app.database.sql_models import CompanyMember, Department, HiringRequest, JobDraft, VoiceSession
from app.hiring import audit, voice
from app.routers.screening import StateOut, state_out
from app.schemas.bridges import HiringRequestIn, IntakeStartIn

router = APIRouter()

BASE = "/api/companies/{company_id}"
INTAKE_OPEN_STATUSES = ("open", "intake_in_progress", intake.EMPTY_STATUS)


def _latest_drafts(db: Session, company_id: int, request_ids: list[int]) -> dict[int, tuple[int, str]]:
    """Request id -> (id, status) of its newest draft, in one query."""
    if not request_ids:
        return {}
    rows = (db.query(JobDraft.hiring_request_id, JobDraft.id, JobDraft.status)
            .filter(JobDraft.company_id == company_id, JobDraft.hiring_request_id.in_(request_ids))
            .order_by(JobDraft.id).all())
    return {request_id: (draft_id, status) for request_id, draft_id, status in rows}  # the last row of each wins


def _out(row: HiringRequest, drafts: dict[int, tuple[int, str]] | None = None) -> dict:
    draft_id, draft_status = (drafts or {}).get(row.id, (None, None))
    return {
        "latest_draft_id": draft_id, "latest_draft_status": draft_status,
        "id": row.id, "title": row.title, "department_id": row.department_id, "manager_user_id": row.manager_user_id,
        "status": row.status, "intake_session_id": row.intake_session_id, "intake_document_id": row.intake_document_id,
        "job_id": row.job_id, "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _get(db: Session, company_id: int, req_id: int, lock: bool = False) -> HiringRequest:
    query = db.query(HiringRequest).filter(HiringRequest.id == req_id, HiringRequest.company_id == company_id)
    if lock:
        query = query.populate_existing().with_for_update()
    row = query.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Hiring request not found")
    return row


@router.post(BASE + "/hiring-requests", status_code=201)
def create_request(company_id: int, body: HiringRequestIn, member: CompanyMember = Depends(require_member("hr")),
                   db: Session = Depends(get_db)):
    if body.department_id is not None and not db.query(Department.id).filter(
        Department.id == body.department_id, Department.company_id == company_id
    ).first():
        raise HTTPException(status_code=404, detail="Department not found")
    manager = db.query(CompanyMember).filter(
        CompanyMember.company_id == company_id, CompanyMember.user_id == body.manager_user_id,
        CompanyMember.role == "manager",
    ).first()
    if manager is None:
        raise HTTPException(status_code=422, detail="The manager must be a manager of this company")
    row = HiringRequest(company_id=company_id, department_id=body.department_id, title=body.title,
                        manager_user_id=body.manager_user_id, status="open", created_by=member.user_id)
    db.add(row)
    db.flush()
    audit.record(db, company_id, member.user_id, "hiring_request_created", "hiring_request", row.id)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get(BASE + "/hiring-requests")
def list_requests(company_id: int, member: CompanyMember = Depends(require_member("hr", "manager")),
                  db: Session = Depends(get_db)):
    query = db.query(HiringRequest).filter(HiringRequest.company_id == company_id)
    if member.role == "manager":
        query = query.filter(HiringRequest.manager_user_id == member.user_id)
    rows = query.order_by(HiringRequest.id.desc()).all()
    drafts = _latest_drafts(db, company_id, [row.id for row in rows])
    return [_out(row, drafts) for row in rows]


@router.get(BASE + "/hiring-requests/{req_id}")
def read_request(company_id: int, req_id: int, member: CompanyMember = Depends(require_member("hr", "manager")),
                 db: Session = Depends(get_db)):
    row = _get(db, company_id, req_id)
    if member.role == "manager" and row.manager_user_id != member.user_id:
        raise HTTPException(status_code=404, detail="Hiring request not found")
    return _out(row, _latest_drafts(db, company_id, [row.id]))


def _running_session(db: Session, row: HiringRequest) -> VoiceSession | None:
    if row.intake_session_id is None:
        return None
    return db.query(VoiceSession).filter(
        VoiceSession.id == row.intake_session_id, VoiceSession.status.in_(voice.ACTIVE_STATUSES)
    ).first()


def _resume(db: Session, row: HiringRequest) -> StateOut | None:
    """The state of the session still running, or None if there is none or the clock has just finished it."""
    session = _running_session(db, row)
    if session is None:
        return None
    session_id = session.id
    state = voice.current_state(db, session)
    return None if state.status in voice.TERMINAL_STATUSES else state_out(session_id, state)


def _check_can_start(db: Session, row: HiringRequest) -> None:
    # A wholly silent intake is also "completed", and leaves no document: that one may be started again.
    finished = row.status != intake.EMPTY_STATUS and row.intake_session_id is not None and db.query(VoiceSession.id).filter(
        VoiceSession.id == row.intake_session_id, VoiceSession.status == voice.COMPLETED
    ).first()
    if row.status not in INTAKE_OPEN_STATUSES or finished:
        raise HTTPException(status_code=409, detail="The intake of this request is already done")


@router.post(BASE + "/hiring-requests/{req_id}/intake/start", response_model=StateOut)
def start_intake(company_id: int, req_id: int, body: IntakeStartIn | None = None,
                 member: CompanyMember = Depends(require_member("manager")), db: Session = Depends(get_db)):
    language = body.language if body is not None else "ko"
    user_id = member.user_id
    row = _get(db, company_id, req_id)
    if row.manager_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the manager assigned to this request can do its intake")
    resumed = _resume(db, row)
    if resumed is not None:
        return resumed
    _check_can_start(db, row)

    plan = intake.build_plan(db, row, language)

    # Planning took a while with no lock held, so another request may have started the session. The rollback ends this
    # request's snapshot and the lock comes first in the new transaction, so the reads below see what that request committed.
    db.rollback()
    row = _get(db, company_id, req_id, lock=True)
    if _running_session(db, row) is not None:  # lost the race: the winner's session is the one to resume
        resumed = _resume(db, row)
        if resumed is not None:
            return resumed
        row = _get(db, company_id, req_id, lock=True)
    _check_can_start(db, row)
    session = voice.create_session(db, company_id=company_id, purpose=intake.PURPOSE, owner_user_id=user_id,
                                   language=language, plan=plan)
    row.intake_session_id = session.id
    row.status = "intake_in_progress"
    audit.record(db, company_id, user_id, "intake_started", "hiring_request", row.id,
                 payload={"language": language, "questions": len(plan)})
    db.commit()
    session_id = session.id
    return state_out(session_id, voice.current_state(db, session))
