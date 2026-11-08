"""Creating applications. AI plays no part here: every rule is checked by code."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.auth import security
from app.core import storage
from app.core.text_extract import NoExtractableText
from app.database.sql_models import Application, Job, JobChannelLink, User
from app.hiring import consents, identity, reapply_guard
from app.hiring.hidden_text import CvTooLarge, extract_cv

MAX_CV_CHARS = 20_000
# A Text column on MySQL holds 64 KB. 20,000 characters of up to 3 bytes fit; 4-byte characters might not.
MAX_CV_BYTES = 65_000
REAPPLY_DAYS = consents.REAPPLY_DAYS
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
    except CvTooLarge as exc:
        raise CvTooLong(str(exc)) from exc
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


def default_candidate_password(email: str | None) -> str:
    local = (email or "candidate").split("@")[0]
    prefix = re.sub(r"[^a-zA-Z0-9]", "", local)[:6].capitalize() or "Cand"
    return f"UV@{prefix}2026!"


def deterministic_claim_token(application: Application) -> str:
    key = f"claim:{application.company_id}:{application.job_id}:{application.alias}:{application.candidate_email or application.id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def issue_claim_token(application: Application) -> str:
    raw = deterministic_claim_token(application)
    application.claim_token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw


def resolve_or_create_candidate_user(db, email: str, full_name: str | None = None) -> User:
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if user is not None:
        if full_name and not user.full_name:
            user.full_name = full_name.strip()[:255]
            db.flush()
        return user
    user = User(
        email=clean_email,
        full_name=(full_name or clean_email.split("@")[0]).strip()[:255],
        hashed_password=security.get_password_hash(default_candidate_password(clean_email)),
        role="user",
    )
    db.add(user)
    db.flush()
    return user


def check_reapply(db, user_id: int, job_id: int) -> None:
    from sqlalchemy import exists, or_
    from app.database.sql_models import VoiceSession

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    has_session = exists().where(VoiceSession.application_id == Application.id)
    recent = (
        db.query(Application.created_at)
        .filter(
            Application.candidate_user_id == user_id, Application.job_id == job_id,
            Application.created_at > now - timedelta(days=REAPPLY_DAYS),
            or_(Application.stage != "withdrawn", has_session, Application.hr_decided_at.isnot(None)),
        )
        .order_by(Application.created_at.desc())
        .first()
    )
    if recent is not None:
        raise AlreadyApplied(recent[0] + timedelta(days=REAPPLY_DAYS))
    # A deleted application left this instead: its row no longer names the user.
    until = reapply_guard.blocked_until(db, user_id, job_id)
    if until is not None and until > now:
        raise AlreadyApplied(until)


def create_application(db, user, job, file_bytes, suffix, src_token, consent_version, consent_language=None) -> Application:
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
            check_reapply(db, user_id, job_id)
            if path is None:
                path = storage.save_bytes(job.company_id, "cv", suffix, file_bytes)
            application = Application(
                company_id=job.company_id, job_id=job_id, job_version=job.version, candidate_user_id=user_id,
                alias=next_alias(db, job.company_id), source_channel=_channel(db, job_id, src_token),
                cv_file_path=path, cv_suffix=suffix, stage="submitted",
                candidate_email=user.email, candidate_name=user.full_name,
            )
            issue_claim_token(application)
            db.add(application)
            try:
                db.flush()
                consents.record(db, user_id, job.company_id, application.id, "cv_processing", consent_version,
                                language=consent_language)
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


def import_cv_file(
    db, job: Job, file_bytes: bytes, suffix: str, source_channel: str, fallback_name: str | None = None
) -> tuple[str, Application | None, str | None]:
    """Import a single CV file for a job. Returns (status, application, claim_token) where status is
    'imported', 'duplicate', or 'missing_contact'."""
    ensure_cv_fits(file_bytes, suffix)
    raw_text = ""
    hidden_detected = False
    try:
        extracted = extract_cv(file_bytes, suffix)
        raw_text = extracted.text
        hidden_detected = extracted.hidden_detected
    except NoExtractableText:
        raw_text = ""

    contact = identity.extract_contact_info(raw_text, fallback_name=fallback_name)
    text_hash = identity.hash_of(raw_text) if raw_text.strip() else None

    if contact.contact_hash:
        dup = (
            db.query(Application)
            .filter(
                Application.job_id == job.id,
                Application.contact_hash == contact.contact_hash,
                Application.stage != "withdrawn",
                Application.anonymized_at.is_(None),
            )
            .first()
        )
        if dup is not None:
            return "duplicate", dup, None

    if text_hash:
        dup_text = (
            db.query(Application)
            .filter(
                Application.job_id == job.id,
                Application.cv_blind_hash == text_hash,
                Application.stage != "withdrawn",
                Application.anonymized_at.is_(None),
            )
            .first()
        )
        if dup_text is not None:
            return "duplicate", dup_text, None

    user = resolve_or_create_candidate_user(db, contact.email, contact.name) if contact.email else None
    if user is not None:
        try:
            check_reapply(db, user.id, job.id)
        except AlreadyApplied:
            existing = (
                db.query(Application)
                .filter(Application.job_id == job.id, Application.candidate_user_id == user.id)
                .order_by(Application.id.desc())
                .first()
            )
            return "duplicate", existing, None

    path = storage.save_bytes(job.company_id, "cv", suffix, file_bytes)
    initial_stage = "submitted" if contact.email else "missing_contact"
    application = Application(
        company_id=job.company_id,
        job_id=job.id,
        job_version=job.version,
        candidate_user_id=user.id if user is not None else None,
        candidate_name=contact.name,
        candidate_email=contact.email,
        candidate_phone=contact.phone,
        contact_hash=contact.contact_hash,
        alias=next_alias(db, job.company_id),
        source_channel=(source_channel or "direct").strip().lower()[:32],
        cv_file_path=path,
        cv_suffix=suffix,
        cv_text_raw=raw_text or None,
        cv_text_blind=raw_text or None,
        cv_blind_hash=text_hash,
        hidden_text_detected=hidden_detected,
        stage=initial_stage,
    )
    raw_token = issue_claim_token(application)
    db.add(application)
    db.flush()
    if user is not None:
        consents.record(db, user.id, job.company_id, application.id, "cv_processing", consents.VERSION)
    db.commit()
    return ("imported" if contact.email else "missing_contact"), application, raw_token
