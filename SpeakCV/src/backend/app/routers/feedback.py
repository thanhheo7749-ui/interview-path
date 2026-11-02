"""HR routes for rejection feedback and the learning catalogue. HR only; every lookup filters on company_id."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.auth.dependencies import require_member
from app.core.settings import max_upload_bytes
from app.core.uploads import read_upload
from app.database.database import get_db
from app.database.sql_models import Application, CompanyMember, KbNode, LearningResource, RejectionFeedback
from app.posthire import feedback, learning

router = APIRouter()

BASE = "/api/companies/{company_id}"
MAX_BULK = 200
CSV_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}


class DraftEditIn(BaseModel):
    draft: str = Field(max_length=feedback.MAX_DRAFT_CHARS)


class ApproveIn(BaseModel):
    application_ids: list[int] = Field(min_length=1, max_length=MAX_BULK)


class ResourcePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_node_id: int | None = None
    title: str | None = None
    url: str | None = None
    provider: str | None = None
    language: str | None = None


def _application(db: Session, company_id: int, application_id: int, lock: bool = False) -> Application:
    query = db.query(Application).filter(Application.id == application_id, Application.company_id == company_id,
                                         Application.is_simulated.is_(False))
    if lock:  # a locking read returns the latest committed row, not this request's earlier snapshot
        query = query.populate_existing().with_for_update()
    application = query.first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _translate(error: feedback.FeedbackError) -> HTTPException:
    if error.problems is None:
        return HTTPException(status_code=error.status_code, detail=error.detail)
    return HTTPException(status_code=error.status_code, detail={"message": error.detail, "problems": error.problems})


def _out(db: Session, application: Application, row: RejectionFeedback) -> dict:
    erased = application.anonymized_at is not None
    return {
        "id": row.id,
        "application_id": row.application_id,
        "language": row.language,
        "draft": row.draft,
        "status": row.status,
        "source": feedback.source_of(db, application.id),
        "approved_by": row.approved_by,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "learning": [learning.public_row(item) for item in learning.linked(db, application.company_id, row.draft)],
        "problems": [] if erased or row.status == "sent" else feedback.guard(row.draft, application),
    }


@router.post(BASE + "/applications/{app_id}/feedback/draft")
def post_draft(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
               db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    existing = db.query(RejectionFeedback.draft).filter_by(application_id=app_id).first()
    before = existing[0] if existing else None
    try:
        row = feedback.draft(db, application, member.user_id)
    except feedback.FeedbackError as error:
        db.rollback()
        raise _translate(error)
    return {**_out(db, application, row), "regenerated": row.draft != before}


@router.get(BASE + "/applications/{app_id}/feedback")
def get_feedback(company_id: int, app_id: int, member: CompanyMember = Depends(require_member("hr")),
                 db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id)
    row = db.query(RejectionFeedback).filter_by(application_id=application.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="There is no feedback draft yet")
    return _out(db, application, row)


@router.patch(BASE + "/applications/{app_id}/feedback")
def patch_feedback(company_id: int, app_id: int, body: DraftEditIn, member: CompanyMember = Depends(require_member("hr")),
                   db: Session = Depends(get_db)):
    application = _application(db, company_id, app_id, lock=True)
    try:
        row = feedback.edit(db, application, body.draft, member.user_id)
    except feedback.FeedbackError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return _out(db, application, row)


@router.post(BASE + "/feedback/approve")
def post_approve(company_id: int, body: ApproveIn, member: CompanyMember = Depends(require_member("hr")),
                 db: Session = Depends(get_db)):
    try:
        sent = feedback.approve(db, company_id, body.application_ids, member.user_id)
    except feedback.FeedbackError as error:
        db.rollback()
        raise _translate(error)
    db.commit()
    return {"sent": sent}


def _resource_out(db: Session, row: LearningResource) -> dict:
    node = db.get(KbNode, row.skill_node_id)
    return {**learning.public_row(row), "skill_node_id": row.skill_node_id, "skill_title": node.title if node else None,
            "created_by": row.created_by}


def _catalogue_error(error: learning.CatalogueError) -> HTTPException:
    return HTTPException(status_code=422, detail={"row": error.row, "message": error.message})


@router.get(BASE + "/learning-resources")
def get_resources(company_id: int, member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    rows = db.query(LearningResource).filter_by(company_id=company_id).order_by(LearningResource.id).all()
    return [_resource_out(db, row) for row in rows]


async def _read_limited(request: Request) -> bytes:
    limit = max_upload_bytes()
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"The body is larger than the {limit // (1024 * 1024)} MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


async def _raw_items(request: Request) -> list:
    """One route takes a JSON object or list, a multipart `file` field, or a text/csv body."""
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type == "multipart/form-data":
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise HTTPException(status_code=422, detail={"row": 0, "message": "Send the CSV in a field named file"})
        return learning.parse_csv(await read_upload(file, CSV_TYPES))
    data = await _read_limited(request)
    if content_type in CSV_TYPES:
        return learning.parse_csv(data)
    try:
        parsed = json.loads(data)
    except ValueError:
        raise HTTPException(status_code=422, detail={"row": 0, "message": "The body is not valid JSON"}) from None
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    raise HTTPException(status_code=422, detail={"row": 0, "message": "Send a resource or a list of resources"})


def _save(db: Session, company_id: int, items: list, user_id: int) -> dict:
    try:
        created, updated, rows = learning.save(db, company_id, items, user_id)
    except learning.CatalogueError as error:
        db.rollback()
        raise _catalogue_error(error)
    db.commit()
    return {"created": created, "updated": updated, "items": [_resource_out(db, row) for row in rows]}


@router.post(BASE + "/learning-resources", status_code=201)
async def post_resources(company_id: int, request: Request, member: CompanyMember = Depends(require_member("hr")),
                         db: Session = Depends(get_db)):
    user_id = member.user_id
    try:
        items = await _raw_items(request)
    except learning.CatalogueError as error:
        raise _catalogue_error(error)
    return await run_in_threadpool(_save, db, company_id, items, user_id)


def _resource(db: Session, company_id: int, resource_id: int) -> LearningResource:
    row = db.query(LearningResource).filter_by(id=resource_id, company_id=company_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Learning resource not found")
    return row


@router.patch(BASE + "/learning-resources/{resource_id}")
def patch_resource(company_id: int, resource_id: int, body: ResourcePatchIn,
                   member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    row = _resource(db, company_id, resource_id)
    try:
        learning.update(db, row, body.model_dump(exclude_unset=True), member.user_id)
    except learning.CatalogueError as error:
        db.rollback()
        raise _catalogue_error(error)
    db.commit()
    return _resource_out(db, row)


@router.delete(BASE + "/learning-resources/{resource_id}", status_code=204)
def delete_resource(company_id: int, resource_id: int, member: CompanyMember = Depends(require_member("hr")),
                    db: Session = Depends(get_db)):
    learning.delete(db, _resource(db, company_id, resource_id), member.user_id)
    db.commit()
    return Response(status_code=204)
