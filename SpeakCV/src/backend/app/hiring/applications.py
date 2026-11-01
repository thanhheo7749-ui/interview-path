"""Creating applications. AI plays no part here: every rule is checked by code."""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.core import storage
from app.core.text_extract import NoExtractableText
from app.database.sql_models import Application, Job, JobChannelLink, User
from app.hiring import consents
from app.hiring.hidden_text import extract_cv

MAX_CV_CHARS = 20_000
# A Text column on MySQL holds 64 KB. 20,000 characters of up to 3 bytes fit; 4-byte characters might not.
MAX_CV_BYTES = 65_000
REAPPLY_DAYS = 90
ALIAS_ATTEMPTS = 5
_ALIAS = re.compile(r"^#A(\d+)$")
DIRECT = "direct"


class JobNotOpen(Exception):
    pass


class AlreadyApplied(Exception):
    def __init__(self, reapply_after: datetime):
        super().__init__("Already applied")
        self.reapply_after = reapply_after


class CvTooLong(Exception):
    pass


def ensure_cv_fits(file_bytes: bytes, suffix: str) -> None:
    """Refuse before anything is stored. A file with no text passes: the job records why, and the candidate re-uploads."""
    try:
        text = extract_cv(file_bytes, suffix).text
    except NoExtractableText:
        return
    if len(text) > MAX_CV_CHARS or len(text.encode("utf-8")) > MAX_CV_BYTES:
        raise CvTooLong(f"Your CV has too much text. Please shorten it to {MAX_CV_CHARS:,} characters or fewer.")


def next_alias(db, company_id: int) -> str:
    aliases = db.query(Application.alias).filter(Application.company_id == company_id).all()
    numbers = [int(match[1]) for (alias,) in aliases if (match := _ALIAS.match(alias or ""))]
    return f"#A{max(numbers, default=0) + 1}"


def _channel(db, job_id: int, src_token: str | None) -> str:
    if not src_token:
        return DIRECT
    link = db.query(JobChannelLink).filter(JobChannelLink.job_id == job_id, JobChannelLink.token == src_token).first()
    return link.channel if link is not None else DIRECT


def _check_reapply(db, user_id: int, job_id: int) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recent = (
        db.query(Application.created_at)
        .filter(
            Application.candidate_user_id == user_id, Application.job_id == job_id,
            Application.created_at > now - timedelta(days=REAPPLY_DAYS),
        )
        .order_by(Application.created_at.desc())
        .first()
    )
    if recent is not None:
        raise AlreadyApplied(recent[0] + timedelta(days=REAPPLY_DAYS))


def create_application(db, user, job, file_bytes, suffix, src_token, consent_version) -> Application:
    """Commits. Discards anything the session has pending, because each attempt needs a new transaction."""
    user_id, job_id = user.id, job.id
    path = None
    last_error = None
    try:
        for _ in range(ALIAS_ATTEMPTS):
            # Ends any snapshot, and the lock comes first in the new transaction, so the reads below happen after
            # the lock and see an application another request of this user committed while this one waited.
            db.rollback()
            db.query(User.id).filter(User.id == user_id).with_for_update().one()
            job = db.get(Job, job_id)
            if job.status != "published":
                raise JobNotOpen
            _check_reapply(db, user_id, job_id)
            if path is None:
                path = storage.save_bytes(job.company_id, "cv", suffix, file_bytes)
            application = Application(
                company_id=job.company_id, job_id=job_id, job_version=job.version, candidate_user_id=user_id,
                alias=next_alias(db, job.company_id), source_channel=_channel(db, job_id, src_token),
                cv_file_path=path, cv_suffix=suffix, stage="submitted",
            )
            db.add(application)
            try:
                db.flush()
                consents.record(db, user_id, job.company_id, application.id, "cv_processing", consent_version)
                db.commit()
                return application
            except IntegrityError as exc:  # two applications took the same alias; the rollback above allows a new read
                last_error = exc
                db.rollback()
        raise last_error
    except Exception:
        if path is not None:
            storage.delete(path)
        raise
