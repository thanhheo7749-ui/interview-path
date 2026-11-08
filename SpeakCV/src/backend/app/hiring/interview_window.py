"""UTC conversion and validation for a job's interview scheduling window. No DB access, pure functions."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

INVALID_INTERVIEW_WINDOW = "INVALID_INTERVIEW_WINDOW"
OUTSIDE_INTERVIEW_WINDOW = "OUTSIDE_INTERVIEW_WINDOW"


def to_utc(dt: datetime | None) -> datetime | None:
    """Aware datetime -> naive UTC for storage. Naive (already from the DB) is returned as is."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt is not None and dt.tzinfo is not None else dt


def as_aware(dt: datetime | None) -> datetime | None:
    """Naive UTC from the DB -> aware UTC (`+00:00`) for JSON output."""
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def check(
    enabled: bool, start: datetime | None, end: datetime | None, tz: str | None, sla_hours: int | None = None
) -> None:
    """Raises 422 if scheduling is enabled without a valid window, or an enabled window's timezone name is not a
    real IANA zone, or sla_hours is non-positive."""
    if sla_hours is not None and sla_hours <= 0:
        raise HTTPException(status_code=422, detail={
            "code": INVALID_INTERVIEW_WINDOW, "message": "Interview SLA hours must be greater than 0.",
        })
    if not enabled:
        return
    if start is None or end is None or start >= end:
        raise HTTPException(status_code=422, detail={
            "code": INVALID_INTERVIEW_WINDOW, "message": "Interview window requires a start before an end.",
        })
    if tz is not None:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(status_code=422, detail={
                "code": INVALID_INTERVIEW_WINDOW, "message": f"'{tz}' is not a valid timezone name.",
            })


def can_apply_now(job, now: datetime) -> bool:
    """False when the job is not published or its fixed interview window has already ended."""
    if getattr(job, "status", None) != "published":
        return False
    if job.scheduling_enabled and job.interview_window_end is not None:
        if to_utc(now) > to_utc(job.interview_window_end):
            return False
    return True


def is_open(job, now: datetime, application=None) -> bool:
    """True if `now` satisfies the job's fixed scheduling window (when enabled) and per-application SLA (when set)."""
    now_utc = to_utc(now)
    if job.scheduling_enabled:
        start, end = to_utc(job.interview_window_start), to_utc(job.interview_window_end)
        if start is not None and end is not None and not (start <= now_utc <= end):
            return False
    sla_hours = getattr(job, "interview_sla_hours", None)
    invited_at = getattr(application, "invited_at", None) if application is not None else None
    if sla_hours and invited_at is not None:
        start_sla = to_utc(invited_at)
        end_sla = start_sla + timedelta(hours=int(sla_hours))
        if now_utc > end_sla:
            return False
    return True


def payload(job, application=None) -> dict | None:
    """Window as aware-UTC values for JSON, or `None` when neither fixed scheduling nor per-app SLA applies."""
    if job.scheduling_enabled and job.interview_window_start is not None and job.interview_window_end is not None:
        return {
            "start": as_aware(job.interview_window_start),
            "end": as_aware(job.interview_window_end),
            "timezone": job.interview_window_timezone,
        }
    sla_hours = getattr(job, "interview_sla_hours", None)
    invited_at = getattr(application, "invited_at", None) if application is not None else None
    if sla_hours and invited_at is not None:
        start_dt = as_aware(invited_at)
        return {
            "start": start_dt,
            "end": start_dt + timedelta(hours=int(sla_hours)),
            "timezone": job.interview_window_timezone or "UTC",
        }
    return None
