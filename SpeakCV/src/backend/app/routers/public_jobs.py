"""Public job page. No login. Returns only public requirements and stores nothing about the visitor."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.sql_models import Company, Job, JobChannelLink
from app.hiring import interview_window, jobs
from app.schemas.jobs import PublicJob

router = APIRouter()


@router.get("/api/public/jobs/{slug}", response_model=PublicJob)
def public_job(slug: str, src: Optional[str] = None, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.slug == slug, Job.status.in_(("published", "closed"))).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    company = db.get(Company, job.company_id)
    is_open = interview_window.can_apply_now(job, datetime.now(timezone.utc))
    if src and job.status == "published":
        # Atomic increment; an unknown token matches nothing and is ignored.
        db.execute(
            update(JobChannelLink)
            .where(JobChannelLink.token == src[:64], JobChannelLink.job_id == job.id)
            .values(click_count=JobChannelLink.click_count + 1)
        )
        db.commit()
    return {
        "slug": job.slug, "title": job.title, "description": job.description, "company_name": company.name, "company_slug": company.slug,
        "is_sample": company.is_sample, "interview_languages": job.interview_languages or [],
        "status": job.status, "can_apply": is_open,
        "requirements": [
            {"text": r.text, "must_have": r.must_have}
            for r in jobs.active_requirements(db, job.id) if r.visibility == "public"
        ],
    }
