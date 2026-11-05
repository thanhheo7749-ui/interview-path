"""UTC conversion and validation for a job's interview scheduling window. No DB access, pure functions."""
from datetime import datetime, timezone
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


def check(enabled: bool, start: datetime | None, end: datetime | None, tz: str | None) -> None:
    """Raises 422 if scheduling is enabled without a valid window, or an enabled window's timezone name is not a
    real IANA zone. Disabled scheduling passes regardless of what the (unused) bounds and timezone hold."""
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


def is_open(job, now: datetime) -> bool:
    """True if the job has no scheduling window, or `now` falls inside it. Bounds and `now` may each be naive or
    aware; all three are normalized to naive UTC before comparing, so no side can raise `TypeError` against another."""
    if not job.scheduling_enabled:
        return True
    start, end, now = to_utc(job.interview_window_start), to_utc(job.interview_window_end), to_utc(now)
    return start <= now <= end


def payload(job) -> dict | None:
    """Window as aware-UTC values for JSON, or `None` when scheduling is disabled."""
    if not job.scheduling_enabled:
        return None
    return {
        "start": as_aware(job.interview_window_start),
        "end": as_aware(job.interview_window_end),
        "timezone": job.interview_window_timezone,
    }
