"""HR-only document upload and ingestion job status. Every lookup filters on company_id."""
import os
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.brain import ingestion
from app.core.uploads import DOCUMENT_TYPES, read_upload
from app.database.database import get_db
from app.database.models_brain import VISIBILITIES
from app.database.sql_models import CompanyMember, Department, KbDocument, KbIngestionJob

router = APIRouter()

KB = "/api/companies/{company_id}/kb"
SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


def _document_out(document: KbDocument) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "language": document.language,
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
        result.append({**_document_out(document), "job": _job_out(job)})
    return result


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
    job = _get_job(db, company_id, job_id)
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="Only a failed job can be retried")
    ingestion.clear_document_output(db, job.document_id)
    db.commit()
    new_job = ingestion.start_job(db, job.document_id)
    background_tasks.add_task(ingestion.run_job, new_job.id)
    return _job_out(new_job)
