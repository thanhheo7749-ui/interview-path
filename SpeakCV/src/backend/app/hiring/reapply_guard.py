"""Deleting an application must not reset the 90-day limit on applying to the same job again.

A decided privacy trade-off, stated in the application consent. When an application with a started session or an HR
decision is deleted, one row keeps a keyed hash of user and job, and the date applied. The key comes from the app's
secret, so the row cannot be matched to a person or job without it. Retention removes the row after the 90 days.
"""
import hashlib
import hmac
from datetime import datetime, timedelta

from app.core import settings
from app.database.sql_models import ReapplyGuard
from app.hiring.consents import REAPPLY_DAYS

_KEY_CONTEXT = b"speakcv/reapply-guard/v1"


def key_hash(user_id: int, job_id: int) -> str:
    key = hmac.new(settings.secret_key().encode(), _KEY_CONTEXT, hashlib.sha256).digest()
    return hmac.new(key, f"{user_id}:{job_id}".encode(), hashlib.sha256).hexdigest()


def remember(db, user_id: int, job_id: int, applied_at: datetime) -> None:
    """Adds the row to the session. The caller commits."""
    db.add(ReapplyGuard(key_hash=key_hash(user_id, job_id), applied_at=applied_at))


def blocked_until(db, user_id: int, job_id: int) -> datetime | None:
    """When this user may apply to this job again, if a guard holds. The limit counts from the original application,
    so deleting neither shortens nor extends it. Whether that date has passed is the caller's to compare."""
    latest = (
        db.query(ReapplyGuard.applied_at).filter(ReapplyGuard.key_hash == key_hash(user_id, job_id))
        .order_by(ReapplyGuard.applied_at.desc()).first()
    )
    return latest[0] + timedelta(days=REAPPLY_DAYS) if latest is not None else None
