#!/usr/bin/env bash
# aidemo setup.preflight — runs before every take (probe/record/render).
# Keeps the "Senior Backend Engineer" hiring-request demo deterministic by
# deleting any leftover draft/request from a previous take before this one
# creates a fresh one (same title every run == same selectors every run).
set -euo pipefail

docker exec speakcv_backend python -c "
from app.database.database import SessionLocal
from app.database.sql_models import Company
from app.database.models_bridges import HiringRequest, JobDraft, JobDraftMessage

db = SessionLocal()
try:
    company = db.query(Company).filter(Company.slug == 'daehan-precision').first()
    if company:
        drafts = db.query(JobDraft).filter(
            JobDraft.company_id == company.id, JobDraft.title == 'Senior Backend Engineer'
        ).all()
        draft_ids = [d.id for d in drafts]
        if draft_ids:
            db.query(JobDraftMessage).filter(JobDraftMessage.job_draft_id.in_(draft_ids)).delete(synchronize_session=False)
            db.query(JobDraft).filter(JobDraft.id.in_(draft_ids)).delete(synchronize_session=False)
        db.query(HiringRequest).filter(
            HiringRequest.company_id == company.id, HiringRequest.title == 'Senior Backend Engineer'
        ).delete(synchronize_session=False)
        db.commit()
        print(f'reseed: cleared {len(draft_ids)} draft(s) + matching hiring request(s)')
    else:
        print('reseed: company daehan-precision not found (skipping)')
finally:
    db.close()
"
