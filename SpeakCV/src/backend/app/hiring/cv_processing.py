"""The background job that reads, masks, assesses and labels a CV. Every candidate ends up invited or may retry."""
import logging

from app.ai.types import AIError
from app.core import storage
from app.core.text_extract import NoExtractableText
from app.database.database import SessionLocal
from app.database.sql_models import Application, Company, Job, User
from app.hiring import consents, identity, notify, screening
from app.hiring.hidden_text import CvTooLarge, extract_cv
from app.hiring.state import InvalidTransition, advance

logger = logging.getLogger(__name__)

TRY_AGAIN = "We could not process your CV right now. Please try again."
INTERRUPTED = "Processing was interrupted. Please upload your CV again."
INVITATION = {
    "en": ("Your next step for {title}", "We have read your CV for {title}. Your next step is a short recorded interview."),
    "vi": ("Bước tiếp theo cho vị trí {title}", "Chúng tôi đã đọc CV của bạn cho vị trí {title}. Bước tiếp theo là một buổi phỏng vấn ngắn có ghi âm."),
}


class _NoLongerProcessing(Exception):
    """The application left cv_processing while this job ran, so this job gives way."""


# What the candidate may be told about a failed CV: a fixed code per kind of failure, never the text of the failure.
# The app turns the code into its own words. A message not listed here is "unknown".
_FAILURE_KINDS = (
    ("consent_withdrawn", ("withdrew consent",)),
    ("no_text", ("no extractable text",)),
    ("unreadable", ("could not read this file", "cannot be read", "not utf-8 text")),
    ("too_large", ("pages. please upload a shorter", "when unpacked")),
    ("try_again", (TRY_AGAIN.lower(),)),
    ("interrupted", (INTERRUPTED.lower(),)),
)


def failure_reason(message: str | None) -> str | None:
    if not message:
        return None
    lowered = message.lower()
    return next((kind for kind, needles in _FAILURE_KINDS if any(needle in lowered for needle in needles)), "unknown")


def _locked(db, application_id: int) -> Application | None:
    # A locking read returns the latest committed row, not this transaction's snapshot.
    return (
        db.query(Application).filter(Application.id == application_id)
        .populate_existing().with_for_update().first()
    )


def _locked_processing(db, application_id: int) -> Application:
    application = _locked(db, application_id)
    if application is None or application.stage != "cv_processing" or application.anonymized_at is not None:
        raise _NoLongerProcessing
    return application


def _claim(db, application_id: int, keep_text: bool = False) -> bool:
    """Only one job may process an application. A second task for it finds the stage moved on, and stops.

    `keep_text` is for an invitation from the talent pool, whose masked text and flags were set when it was created.
    """
    application = _locked(db, application_id)
    # The lock comes first in this transaction, so the read of the consent sees a withdrawal committed before it.
    if application is None or application.anonymized_at is not None or consents.was_withdrawn(db, application_id, "cv_processing"):
        db.rollback()
        return False
    try:
        advance(application, "cv_processing")
    except InvalidTransition:
        db.rollback()
        return False
    application.processing_error = None
    application.cv_status = None
    application.cv_status_reason = None
    if not keep_text:
        application.cv_text_raw = None
        application.cv_text_blind = None
        application.cv_blind_hash = None
        application.hidden_text_detected = False
    db.commit()
    return True


def _assess_and_label(db, application, application_id: int) -> Application:
    """Assess CV against requirements. Moves to cv_hold if 0% of must-haves are met/partial, else invited."""
    from datetime import datetime, timezone

    result = screening.assess(db, application)
    status, reasons = screening.label(result.requirements, result.assessed_requirements)

    must_ids = {r.id for r in result.assessed_requirements if r.must_have}
    matched_must = any(
        item.requirement_id in must_ids and item.status in ("met", "partial")
        for item in result.requirements
    )
    target_stage = "cv_hold" if (must_ids and not matched_must) else "invited"

    application = _locked_processing(db, application_id)
    application.cv_status = status
    application.cv_status_reason = reasons
    advance(application, target_stage)
    if target_stage == "invited":
        application.invited_at = datetime.now(timezone.utc)
    return application


def _process(db, application_id: int) -> None:
    application = db.get(Application, application_id)
    path, suffix, company_id = application.cv_file_path, application.cv_suffix, application.company_id
    user = db.get(User, application.candidate_user_id) if application.candidate_user_id is not None else None
    fallback_name = application.candidate_name or (user.full_name if user is not None else None)
    fallback_email = application.candidate_email or (user.email if user is not None else None)
    known_terms = identity.registered_terms(fallback_name, fallback_email)
    db.commit()  # hold no snapshot or lock while reading the file or calling AI

    cv = extract_cv(storage.read_bytes(path), suffix)
    contact = identity.extract_contact_info(cv.text, fallback_name=fallback_name, fallback_email=fallback_email)
    masked = identity.mask(cv.text, company_id=company_id, known_terms=known_terms)

    application = _locked_processing(db, application_id)
    application.cv_text_raw = cv.text
    application.cv_text_blind = masked.blind_text
    application.cv_blind_hash = masked.blind_hash
    application.hidden_text_detected = cv.hidden_detected
    application.candidate_name = contact.name or application.candidate_name
    application.candidate_email = contact.email or application.candidate_email
    application.candidate_phone = contact.phone or application.candidate_phone
    application.contact_hash = contact.contact_hash or application.contact_hash
    db.commit()

    application = _assess_and_label(db, application, application_id)
    job = db.get(Job, application.job_id)
    company = db.get(Company, application.company_id)
    if application.stage == "invited" and application.candidate_user_id is not None:
        language = company.default_locale if company.default_locale in INVITATION else "en"
        subject, body = INVITATION[language]
        notify.enqueue(db, application.company_id, application.candidate_user_id, "invited", language,
                       subject.format(title=job.title), body.format(title=job.title), application_id=application_id)
    db.commit()


def _process_blind_text(db, application_id: int, blind_text: str) -> None:
    """Masking is skipped, as the text is already masked. The candidate was told when HR sent the invitation."""
    application = _locked_processing(db, application_id)
    application.cv_text_blind = blind_text
    application.cv_blind_hash = identity.hash_of(blind_text)
    db.commit()
    _assess_and_label(db, application, application_id)
    db.commit()


def _fail(db, application_id: int, message: str) -> None:
    application = _locked(db, application_id)
    if application is None or application.stage != "cv_processing":
        db.rollback()
        return
    advance(application, "cv_failed")
    application.processing_error = message
    db.commit()


def run(application_id: int) -> None:
    _run(application_id, _process)


def run_from_blind_text(application_id: int, blind_text: str) -> None:
    """For an invitation from the talent pool: no upload and no masking, then assess, label and invite."""
    _run(application_id, lambda db, target: _process_blind_text(db, target, blind_text), keep_text=True)


def _run(application_id: int, process, keep_text: bool = False) -> None:
    """Never raises. Exception text can quote the CV or the model's output, so only its type is logged."""
    db = SessionLocal()
    try:
        if not _claim(db, application_id, keep_text=keep_text):
            return
        try:
            process(db, application_id)
            notify.deliver_pending()  # the invitation leaves now, not at the next daily run; never raises
        except (_NoLongerProcessing, screening.ApplicationDeleted):
            db.rollback()
        except (NoExtractableText, CvTooLarge) as exc:
            db.rollback()
            _fail(db, application_id, str(exc))  # only fixed messages from text_extract and hidden_text
        except Exception as exc:
            db.rollback()
            if not isinstance(exc, AIError):
                logger.warning("CV processing failed for application %s: %s", application_id, type(exc).__name__)
            _fail(db, application_id, TRY_AGAIN)
    except Exception as exc:
        db.rollback()
        logger.warning("CV processing could not finish for application %s: %s", application_id, type(exc).__name__)
    finally:
        db.close()


def fail_interrupted() -> int:
    """At startup, nothing can still be running. Move stuck applications to where the candidate can retry."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Application).filter(Application.stage.in_(("submitted", "cv_processing")))
            .with_for_update().all()
        )
        for application in rows:
            if application.stage == "submitted":
                advance(application, "cv_processing")
            advance(application, "cv_failed")
            application.processing_error = INTERRUPTED
        db.commit()
        return len(rows)
    finally:
        db.close()
