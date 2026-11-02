"""HR-only document upload and ingestion job status. Every lookup filters on company_id."""
import os
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.brain import ingestion, review
from app.core.uploads import DOCUMENT_TYPES, read_upload
from app.database.database import get_db
from app.database.models_brain import VISIBILITIES
from app.database.sql_models import CompanyMember, Department, KbDocument, KbIngestionJob

router = APIRouter()

KB = "/api/companies/{company_id}/kb"
SUFFIXES = {".pdf", ".docx", ".txt", ".md"}
RETRYABLE_STATUSES = ("review", "published")


def _document_out(document: KbDocument) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "language": document.language or None,  # None until the job has read the text and guessed it
        "source_type": document.source_type,
        "visibility": document.visibility,
        "department_id": document.department_id,
        "effective_date": document.effective_date.isoformat() if document.effective_date else None,
        "status": document.status,
        "created_at": document.created_at.isoformat() if document.created_at else None,
    }


def _job_out(job: KbIngestionJob | None) -> dict | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "document_id": job.document_id,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "dropped_items": job.dropped_items,
        "failed_chunks": job.failed_chunks,
        "failed_chunk_ids": job.failed_chunk_ids or [],
        "contradiction_check_failed": bool(job.contradiction_check_failed),
    }


def _get_job(db: Session, company_id: int, job_id: int) -> KbIngestionJob:
    job = (
        db.query(KbIngestionJob)
        .join(KbDocument, KbDocument.id == KbIngestionJob.document_id)
        .filter(KbIngestionJob.id == job_id, KbDocument.company_id == company_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _lock_job(db: Session, company_id: int, job_id: int) -> tuple[KbIngestionJob, KbDocument, bool]:
    """The job, its document and whether it is the document's latest job, read under the document's row lock.

    The locked reads return committed rows, so a second request cannot act on what the first one read. The caller's
    commit releases the lock."""
    document_id = _get_job(db, company_id, job_id).document_id
    document = db.query(KbDocument).filter(KbDocument.id == document_id).populate_existing().with_for_update().one()
    job = db.query(KbIngestionJob).filter(KbIngestionJob.id == job_id).populate_existing().with_for_update().one()
    latest = (
        db.query(KbIngestionJob.id)
        .filter(KbIngestionJob.document_id == document_id)
        .order_by(KbIngestionJob.id.desc())
        .with_for_update()
        .first()
    )
    return job, document, latest[0] == job.id


@router.post(f"{KB}/documents", status_code=201)
async def upload_document(
    company_id: int,
    background_tasks: BackgroundTasks,
    title: str = Form(..., min_length=1, max_length=255),
    visibility: str = Form(...),
    department_id: int | None = Form(None),
    language: str | None = Form(None, max_length=10),
    effective_date: date | None = Form(None),
    file: UploadFile = File(...),
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    if visibility not in VISIBILITIES:
        raise HTTPException(status_code=422, detail=f"visibility must be one of: {', '.join(VISIBILITIES)}")
    if department_id is not None:
        found = db.query(Department.id).filter(Department.id == department_id, Department.company_id == company_id).first()
        if found is None:
            raise HTTPException(status_code=404, detail="Department not found")
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in SUFFIXES:
        raise HTTPException(status_code=415, detail="Only .pdf, .docx, .txt and .md files are supported")
    data = await read_upload(file, DOCUMENT_TYPES)

    document = ingestion.create_document(
        db, company_id, member.user_id, title=title.strip(), data=data, suffix=suffix, visibility=visibility,
        department_id=department_id, language=(language or "").strip() or None, effective_date=effective_date,
    )
    job = ingestion.start_job(db, document.id)
    background_tasks.add_task(ingestion.run_job, job.id)
    return {"document": _document_out(document), "job": _job_out(job)}


@router.get(f"{KB}/documents")
def list_documents(company_id: int, _: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    documents = db.query(KbDocument).filter(KbDocument.company_id == company_id).order_by(KbDocument.id.desc()).all()
    result = []
    for document in documents:
        job = (
            db.query(KbIngestionJob)
            .filter(KbIngestionJob.document_id == document.id)
            .order_by(KbIngestionJob.id.desc())
            .first()
        )
        result.append({**_document_out(document), "job": _job_out(job),
                       "publish_hold": review.publish_hold(db, document, job)})
    return result


@router.post(f"{KB}/documents/{{document_id}}/unpublish")
def unpublish_document(
    company_id: int,
    document_id: int,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    try:
        counts = review.unpublish_document(db, company_id, document_id)
        db.commit()
    except review.ReviewError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {"document": _document_out(db.get(KbDocument, document_id)), **counts}


@router.get(f"{KB}/jobs/{{job_id}}")
def get_job(company_id: int, job_id: int, _: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    return _job_out(_get_job(db, company_id, job_id))


@router.post(f"{KB}/jobs/{{job_id}}/retry")
def retry_job(
    company_id: int,
    job_id: int,
    background_tasks: BackgroundTasks,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    job, document, is_latest = _lock_job(db, company_id, job_id)
    if job.status != "failed" or document.status != "failed" or not is_latest:
        db.rollback()
        raise HTTPException(status_code=409, detail="Only the latest job of a failed document can be retried")
    # Cleared and restarted in one commit, so a repeat of this request finds the document no longer failed.
    ingestion.clear_document_output(db, job.document_id)
    new_job = ingestion.start_job(db, job.document_id)
    background_tasks.add_task(ingestion.run_job, new_job.id)
    return _job_out(new_job)


@router.post(f"{KB}/jobs/{{job_id}}/retry-failed")
def retry_failed_chunks(
    company_id: int,
    job_id: int,
    background_tasks: BackgroundTasks,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    job, document, is_latest = _lock_job(db, company_id, job_id)
    if (
        not is_latest or document.status not in RETRYABLE_STATUSES or job.status in ("queued", "running")
        or not (job.failed_chunk_ids or job.contradiction_check_failed)
    ):
        db.rollback()
        raise HTTPException(status_code=409, detail="This job has nothing that can be retried")
    ingestion.start_failed_retry(db, job)
    background_tasks.add_task(ingestion.run_failed_retry, job.id)
    return _job_out(job)
