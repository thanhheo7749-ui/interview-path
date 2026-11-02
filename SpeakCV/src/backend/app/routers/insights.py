"""Measurement routes for HR. Every lookup filters on company_id. Routes that run AI are plain `def`."""
import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.core.uploads import read_upload
from app.database.database import get_db
from app.database.models_insights import ChannelCost
from app.database.sql_models import Application, CompanyMember, Job
from app.insights import channels, commentary

router = APIRouter()

BASE = "/api/companies/{company_id}"
MAX_COST_ITEMS = 1000
CSV_TYPES = {"text/csv", "text/plain", "application/vnd.ms-excel"}
CSV_COLUMNS = ["channel", "period_month", "amount_vnd"]
SMALL_SAMPLE_NOTES = {
    "en": "Sample too small, treat as a hint",
    "vi": "Mẫu quá nhỏ, chỉ nên xem như gợi ý",
}


class CostItem(BaseModel):
    channel: str = Field(min_length=1, max_length=50, pattern=r"^\s*[A-Za-z0-9_\-]+\s*$")
    period_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount_vnd: int = Field(ge=0, le=10**13)


class CostsIn(BaseModel):
    job_id: int
    items: list[CostItem] = Field(max_length=MAX_COST_ITEMS)


def _job(db: Session, company_id: int, job_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _has(db: Session, company_id: int, job_id: int, simulated: bool) -> bool:
    return db.query(Application.id).filter(
        Application.company_id == company_id, Application.job_id == job_id,
        Application.is_simulated.is_(simulated)).first() is not None


class CommentaryIn(BaseModel):
    data: Literal["real", "simulated"] | None = None
    language: Literal["en", "vi"] = "en"


def _view(db: Session, company_id: int, job_id: int, data: str | None):
    """The job, the choice of real or simulated data, and the table, all computed by code."""
    job = _job(db, company_id, job_id)
    has_real = _has(db, company_id, job_id, False)
    has_simulated = _has(db, company_id, job_id, True)
    simulated = (data == "simulated") if data else (not has_real and has_simulated)
    table = channels.channel_table(db, company_id, job_id, simulated)
    return {"id": job.id, "title": job.title}, has_real, has_simulated, simulated, table


@router.get(BASE + "/jobs/{job_id}/channels")
def get_channels(company_id: int, job_id: int, data: Literal["real", "simulated"] | None = None,
                 language: Literal["en", "vi"] = "en",
                 member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    """The table only. No AI call: commentary comes from POST .../channels/commentary on request."""
    job, has_real, has_simulated, simulated, table = _view(db, company_id, job_id, data)
    return {
        "job": job,
        "simulated": simulated,
        "has_real": has_real,
        "has_simulated": has_simulated,
        "table": table.as_dict(),
        "small_sample_note": SMALL_SAMPLE_NOTES[language] if any(row.small_sample for row in table.rows) else None,
    }


@router.post(BASE + "/jobs/{job_id}/channels/commentary")
def post_channel_commentary(company_id: int, job_id: int, body: CommentaryIn,
                            member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    """Recomputes the table in code, then asks the AI to explain it. `observations` is null when it cannot."""
    table = _view(db, company_id, job_id, body.data)[4]
    db.rollback()  # end the read transaction: the AI call below must not run inside one
    notes = commentary.explain(table, body.language, company_id)
    return {"observations": notes.observations if notes else None}


def _unprocessable(detail) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _parse_csv(raw: bytes) -> list[CostItem]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _unprocessable([{"line": 1, "message": "The file must be UTF-8 text"}])
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None or [name.strip().lower() for name in header] != CSV_COLUMNS:
        raise _unprocessable([{"line": 1, "message": f"The first line must be: {','.join(CSV_COLUMNS)}"}])
    items, errors = [], []
    for fields in reader:
        if not any(field.strip() for field in fields):
            continue
        line = reader.line_num
        if len(items) + len(errors) >= MAX_COST_ITEMS:
            raise _unprocessable([{"line": line, "message": f"At most {MAX_COST_ITEMS} rows"}])
        if len(fields) != len(CSV_COLUMNS):
            errors.append({"line": line, "message": "Expected 3 columns"})
            continue
        try:
            items.append(CostItem(channel=fields[0], period_month=fields[1].strip(), amount_vnd=fields[2].strip()))
        except ValidationError as error:
            first = error.errors()[0]
            errors.append({"line": line, "message": f"{first['loc'][-1]}: {first['msg']}"})
    if errors:
        raise _unprocessable(errors)
    return items


def _save_costs(db: Session, company_id: int, job_id: int, items: list[CostItem], source: str) -> int:
    _job(db, company_id, job_id)
    latest = {(item.channel.strip().lower(), item.period_month): item.amount_vnd for item in items}
    for (channel, month), amount in latest.items():
        row = db.query(ChannelCost).filter(
            ChannelCost.company_id == company_id, ChannelCost.job_id == job_id, ChannelCost.channel == channel,
            ChannelCost.period_month == month).first()
        if row is None:
            db.add(ChannelCost(company_id=company_id, job_id=job_id, channel=channel, period_month=month,
                               amount_vnd=amount, source=source))
        else:  # a simulated figure in this slot is replaced by the real one
            row.amount_vnd = amount
            row.source = source
    db.commit()
    return len(latest)


@router.post(BASE + "/channel-costs")
async def post_channel_costs(company_id: int, request: Request,
                             member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    """JSON `{job_id, items: [{channel, period_month, amount_vnd}]}`, or multipart with `job_id` and a CSV `file`."""
    if (request.headers.get("content-type") or "").startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise _unprocessable([{"line": 1, "message": "Attach a CSV file as `file`"}])
        try:
            job_id = int(form.get("job_id"))
        except (TypeError, ValueError):
            raise _unprocessable([{"line": 0, "message": "job_id is required"}])
        items = _parse_csv(await read_upload(upload, CSV_TYPES))
        source = "csv"
    else:
        try:
            body = CostsIn.model_validate(await request.json())
        except ValueError as error:  # bad JSON or a failed check
            detail = json.loads(error.json()) if isinstance(error, ValidationError) else "Invalid JSON"
            raise _unprocessable(detail)
        job_id, items, source = body.job_id, body.items, "manual"
    saved = await run_in_threadpool(_save_costs, db, company_id, job_id, items, source)
    return {"saved": saved}
