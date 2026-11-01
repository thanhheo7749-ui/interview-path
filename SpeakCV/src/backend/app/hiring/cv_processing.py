"""The background job that reads, masks, assesses and labels a CV. Every candidate ends up invited or may retry."""
import logging

from app.ai.types import AIError
from app.core import storage
from app.core.text_extract import NoExtractableText
from app.database.database import SessionLocal
from app.database.sql_models import Application, Company, Job, User
from app.hiring import identity, notify, screening
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


def _locked(db, application_id: int) -> Application | None:
    # A locking read returns the latest committed row, not this transaction's snapshot.
    return (
        db.query(Application).filter(Application.id == application_id)
        .populate_existing().with_for_update().first()
    )


def _locked_processing(db, application_id: int) -> Application:
    application = _locked(db, application_id)
    if application is None or application.stage != "cv_processing":
        raise _NoLongerProcessing
    return application


def _claim(db, application_id: int) -> bool:
    """Only one job may process an application. A second task for it finds the stage moved on, and stops."""
    application = _locked(db, application_id)
    if application is None:
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
    application.cv_text_raw = None
    application.cv_text_blind = None
    application.cv_blind_hash = None
    application.hidden_text_detected = False
    db.commit()
    return True


def _process(db, application_id: int) -> None:
    application = db.get(Application, application_id)
    path, suffix, company_id = application.cv_file_path, application.cv_suffix, application.company_id
    user = db.get(User, application.candidate_user_id) if application.candidate_user_id is not None else None
    known_terms = identity.registered_terms(user.full_name, user.email) if user is not None else []
    db.commit()  # hold no snapshot or lock while reading the file or calling AI

    cv = extract_cv(storage.read_bytes(path), suffix)
    masked = identity.mask(cv.text, company_id=company_id, known_terms=known_terms)

    application = _locked_processing(db, application_id)
    application.cv_text_raw = cv.text
    application.cv_text_blind = masked.blind_text
    application.cv_blind_hash = masked.blind_hash
    application.hidden_text_detected = cv.hidden_detected
    db.commit()

    result = screening.assess(db, application)
    status, reasons = screening.label(result.requirements, result.assessed_requirements)

    application = _locked_processing(db, application_id)
    application.cv_status = status
    application.cv_status_reason = reasons
    advance(application, "invited")
    job = db.get(Job, application.job_id)
    company = db.get(Company, application.company_id)
    if application.candidate_user_id is not None:
        language = company.default_locale if company.default_locale in INVITATION else "en"
        subject, body = INVITATION[language]
        notify.enqueue(db, application.company_id, application.candidate_user_id, "invited", language,
                       subject.format(title=job.title), body.format(title=job.title))
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
    """Never raises. Exception text can quote the CV or the model's output, so only its type is logged."""
    db = SessionLocal()
    try:
        if not _claim(db, application_id):
            return
        try:
            _process(db, application_id)
        except _NoLongerProcessing:
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
