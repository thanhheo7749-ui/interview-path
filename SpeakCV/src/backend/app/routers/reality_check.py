"""Requirement Reality Check. HR only, read only: it suggests and never edits a requirement."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.database.database import get_db
from app.database.models_bridges import JobDraft
from app.database.sql_models import Company, CompanyMember, Job
from app.insights import reality_check

router = APIRouter()

BASE = "/api/companies/{company_id}"
SIMULATED_BANNER = "Simulated data"


@router.get(BASE + "/jobs/{job_id}/reality-check")
def get_reality_check(company_id: int, job_id: int, data: Literal["real", "simulated"] = Query("real"),
                      member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    if db.query(Job.id).filter(Job.id == job_id, Job.company_id == company_id).first() is None:
        raise HTTPException(status_code=404, detail="Job not found")
    simulated = data == "simulated"
    rows = reality_check.report(db, company_id, job_id, simulated)
    draft = (db.query(JobDraft.id).filter(JobDraft.company_id == company_id, JobDraft.job_id == job_id)
             .order_by(JobDraft.id.desc()).first())
    return {
        "draft_id": draft[0] if draft else None, "simulated": simulated, "banner": SIMULATED_BANNER if simulated else None,
        "thresholds": reality_check.thresholds(db.get(Company, company_id)),
        "rows": [row.as_dict() for row in rows],
    }
