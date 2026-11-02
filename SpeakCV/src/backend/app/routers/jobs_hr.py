"""HR job management under a company. Every lookup by ID also filters on company_id."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.database.database import get_db
from app.database.sql_models import Company, CompanyMember, Department, Job, JobChannelLink, KbNode
from app.hiring import audit, jobs
from app.schemas.jobs import (
    ChannelOut, ChannelsIn, JobCreate, JobOut, JobPatch, JobSummary, Prefill, RoleOption,
)

router = APIRouter()

JOBS = "/api/companies/{company_id}/jobs"


def _get_job(db: Session, company_id: int, job_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _check_department(db: Session, company_id: int, department_id) -> None:
    if department_id is None:
        return
    if db.query(Department.id).filter(Department.id == department_id, Department.company_id == company_id).first() is None:
        raise HTTPException(status_code=404, detail="Department not found")


def _check_nodes(db: Session, company_id: int, node_ids: set[int]) -> None:
    if not node_ids:
        return
    found = {row[0] for row in db.query(KbNode.id).filter(KbNode.company_id == company_id, KbNode.id.in_(node_ids))}
    if found != node_ids:
        raise HTTPException(status_code=404, detail="Knowledge node not found")


def _out(db: Session, job: Job, warnings: list[str] | None = None) -> dict:
    channels = db.query(JobChannelLink).filter_by(job_id=job.id, company_id=job.company_id).order_by(JobChannelLink.id).all()
    return {
        "id": job.id, "title": job.title, "slug": job.slug, "status": job.status, "version": job.version,
        "department_id": job.department_id, "published_at": job.published_at, "description": job.description,
        "role_node_id": job.role_node_id, "interview_languages": job.interview_languages or [],
        "requirements": jobs.active_requirements(db, job.id),
        "channels": [ChannelOut.model_validate(c, from_attributes=True) for c in channels],
        "warnings": list(warnings or []),
    }


def _translate(error: jobs.JobError):
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.get(JOBS + "/role-options", response_model=list[RoleOption])
def role_options(company_id: int, member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    rows = (
        db.query(KbNode, Department)
        .outerjoin(Department, (Department.id == KbNode.department_id) & (Department.company_id == company_id))
        .filter(KbNode.company_id == company_id, KbNode.type == "role", KbNode.status == "published")
        .order_by(KbNode.title, KbNode.id)
        .all()
    )
    return [
        {"id": node.id, "title": node.title, "department_id": node.department_id,
         "department_name": department.name if department else None}
        for node, department in rows
    ]


@router.get(JOBS + "/prefill", response_model=Prefill)
def prefill(company_id: int, role_node_id: int, member: CompanyMember = Depends(require_member("hr")),
            db: Session = Depends(get_db)):
    result = jobs.prefill(db, company_id, role_node_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return result


@router.post(JOBS, response_model=JobOut, status_code=201)
def create_job(company_id: int, body: JobCreate, member: CompanyMember = Depends(require_member("hr")),
               db: Session = Depends(get_db)):
    _check_department(db, company_id, body.department_id)
    node_ids = {r.node_id for r in body.requirements if r.node_id is not None}
    if body.role_node_id is not None:
        node_ids.add(body.role_node_id)
    _check_nodes(db, company_id, node_ids)
    try:
        checked = jobs.check_requirements(db, company_id, None, body.requirements)  # before the first write: it can call AI
    except jobs.JobError as error:
        db.rollback()
        raise _translate(error) from error
    job = Job(
        company_id=company_id, department_id=body.department_id, role_node_id=body.role_node_id, title=body.title,
        description=body.description, status="draft", version=1, interview_languages=list(body.interview_languages),
        created_by=member.user_id,
    )
    db.add(job)
    db.flush()
    try:
        warnings = jobs.update_requirements(db, job, body.requirements, checked)
    except jobs.JobError as error:
        db.rollback()
        raise _translate(error) from error
    audit.record(db, company_id, member.user_id, "job.create", "job", job.id)
    db.commit()
    return _out(db, job, warnings)


@router.get(JOBS, response_model=list[JobSummary])
def list_jobs(company_id: int, member: CompanyMember = Depends(require_member()), db: Session = Depends(get_db)):
    return db.query(Job).filter(Job.company_id == company_id).order_by(Job.id.desc()).all()


@router.get(JOBS + "/{job_id}", response_model=JobOut)
def get_job(company_id: int, job_id: int, member: CompanyMember = Depends(require_member()),
            db: Session = Depends(get_db)):
    return _out(db, _get_job(db, company_id, job_id))


@router.patch(JOBS + "/{job_id}", response_model=JobOut)
def patch_job(company_id: int, job_id: int, body: JobPatch, member: CompanyMember = Depends(require_member("hr")),
              db: Session = Depends(get_db)):
    job = _get_job(db, company_id, job_id)
    if job.status == "closed":
        raise HTTPException(status_code=409, detail="A closed job cannot be edited")
    fields = body.model_fields_set
    if "department_id" in fields:
        _check_department(db, company_id, body.department_id)
    warnings: list[str] = []
    checked = None
    if body.requirements is not None:
        _check_nodes(db, company_id, {r.node_id for r in body.requirements if r.node_id is not None})
        try:
            checked = jobs.check_requirements(db, company_id, job.id, body.requirements)  # before any write: it can call AI
        except jobs.JobError as error:
            db.rollback()
            raise _translate(error) from error
    if "department_id" in fields:
        job.department_id = body.department_id
    if checked is not None:
        try:
            warnings = jobs.update_requirements(db, job, body.requirements, checked)
        except jobs.JobError as error:
            db.rollback()
            raise _translate(error) from error
    if body.title is not None:
        job.title = body.title
    if body.description is not None:
        job.description = body.description
    if body.interview_languages is not None:
        job.interview_languages = list(body.interview_languages)
    audit.record(db, company_id, member.user_id, "job.update", "job", job.id)
    db.commit()
    return _out(db, job, warnings)


@router.post(JOBS + "/{job_id}/publish", response_model=JobOut)
def publish_job(company_id: int, job_id: int, member: CompanyMember = Depends(require_member("hr")),
                db: Session = Depends(get_db)):
    job = _get_job(db, company_id, job_id)
    company = db.get(Company, company_id)
    try:
        jobs.publish(db, job, company)
    except jobs.JobError as error:
        raise _translate(error)
    audit.record(db, company_id, member.user_id, "job.publish", "job", job.id)
    db.commit()
    return _out(db, job)


@router.post(JOBS + "/{job_id}/close", response_model=JobOut)
def close_job(company_id: int, job_id: int, member: CompanyMember = Depends(require_member("hr")),
              db: Session = Depends(get_db)):
    job = _get_job(db, company_id, job_id)
    if job.status != "published":
        raise HTTPException(status_code=409, detail="Only a published job can be closed")
    job.status = "closed"
    audit.record(db, company_id, member.user_id, "job.close", "job", job.id)
    db.commit()
    return _out(db, job)


@router.post(JOBS + "/{job_id}/channels", response_model=list[ChannelOut])
def add_channels(company_id: int, job_id: int, body: ChannelsIn,
                 member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    for _ in range(len(body.channels) + 1):
        try:
            links = jobs.ensure_channels(db, _get_job(db, company_id, job_id), body.channels)
            db.commit()
            return links
        except IntegrityError:
            db.rollback()  # another request added one first; the next read comes after this and sees its link
    raise HTTPException(status_code=503, detail="Please try again.")
