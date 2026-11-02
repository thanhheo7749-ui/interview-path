"""Human decisions about an application. `decide` is the only code that writes `hr_decision` on a real application.

Nothing here calls AI, and AI output never reaches this module. Callers own the transaction and commit.
"""
from datetime import datetime, timezone

from app.database.sql_models import Company, Job, VoiceSession
from app.hiring import audit, notify
from app.hiring.state import InvalidTransition, advance

DECISIONS = ("approved", "rejected")
CV_STATUSES = ("meets", "not_met")

# One plain message per decision and language. It names no reason, label or band.
NOTIFICATIONS = {
    "en": {
        "approved": ("An update on {title}", "There is an update on your application for {title}. Open the app to see it."),
        "rejected": ("An update on {title}",
                     "Thank you for your time and interest in {title}. The hiring team has decided not to move forward "
                     "with your application."),
    },
    "vi": {
        "approved": ("Cập nhật về vị trí {title}", "Có cập nhật mới về hồ sơ của bạn cho vị trí {title}. Hãy mở ứng dụng để xem."),
        "rejected": ("Cập nhật về vị trí {title}",
                     "Cảm ơn bạn đã dành thời gian và quan tâm đến vị trí {title}. Rất tiếc, đội ngũ tuyển dụng quyết định "
                     "không tiếp tục với hồ sơ của bạn."),
    },
}


class DecisionError(ValueError):
    """Carries an HTTP-friendly status so routers can translate it."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def visible_to_candidate(application) -> str | None:
    """The decision the candidate may see once HR has made it: approved or rejected, never a reason, label or band."""
    if application.stage == "ready_for_hr" and application.hr_decision in DECISIONS:
        return application.hr_decision
    return None


def _notify(db, application, decision: str) -> None:
    """The only place a decision becomes a candidate notification."""
    if application.candidate_user_id is None:
        return
    company = db.get(Company, application.company_id)
    language = company.default_locale if company.default_locale in NOTIFICATIONS else "en"
    title = db.get(Job, application.job_id).title
    subject, body = NOTIFICATIONS[language][decision]
    notify.enqueue(db, application.company_id, application.candidate_user_id, "decision", language,
                   subject.format(title=title), body.format(title=title), application_id=application.id)


def _check_not_anonymized(application) -> None:
    if application.anonymized_at is not None:
        raise DecisionError(409, "This application's personal data has been deleted")


def decide(db, application, decision, actor_user_id, reason=None) -> None:
    if decision not in DECISIONS:
        raise DecisionError(422, "Decision must be approved or rejected")
    _check_not_anonymized(application)
    if application.stage != "ready_for_hr":
        raise DecisionError(409, "This application is not ready for a decision")
    if application.hr_decision != "pending":
        raise DecisionError(409, "This application already has a decision")
    application.hr_decision = decision
    application.hr_decided_by = actor_user_id
    application.hr_decided_at = datetime.now(timezone.utc)
    audit.record(db, application.company_id, actor_user_id, "hr_decision", "application", application.id,
                 payload={"decision": decision, "reason": reason})
    _notify(db, application, decision)
    db.flush()


def record_simulated(application, decision: str, decided_at: datetime) -> None:
    """For the simulator's labelled rows, which no person decided: no actor, no audit row and no notification."""
    if not application.is_simulated:
        raise ValueError("Only a simulated application can take a simulated decision")
    if decision not in DECISIONS:
        raise ValueError("Decision must be approved or rejected")
    application.hr_decision = decision
    application.hr_decided_at = decided_at


def correct_cv_status(db, application, cv_status, actor_user_id, reason) -> None:
    if cv_status not in CV_STATUSES:
        raise DecisionError(422, "CV status must be meets or not_met")
    if not (reason or "").strip():
        raise DecisionError(422, "A reason is required")
    _check_not_anonymized(application)
    if application.cv_status is None:
        raise DecisionError(409, "This application has no CV label yet")
    previous = application.cv_status
    application.cv_status = cv_status
    application.cv_status_corrected_by = actor_user_id
    application.cv_status_correction_reason = reason.strip()
    audit.record(db, application.company_id, actor_user_id, "cv_status_corrected", "application", application.id,
                 payload={"from": previous, "to": cv_status, "reason": reason.strip()})
    db.flush()


def reveal(db, application, actor_user_id) -> dict:
    """Identity leaves the system only through here, and every call is logged."""
    from app.database.sql_models import User

    user = db.get(User, application.candidate_user_id) if application.candidate_user_id else None
    if user is None:
        raise DecisionError(404, "Identity is no longer available")
    audit.record(db, application.company_id, actor_user_id, "identity_revealed", "application", application.id)
    db.flush()
    return {"name": user.full_name, "email": user.email}


def grant_restart(db, application, actor_user_id) -> None:
    """One restart per application. The old session and its audio stay as they are."""
    _check_not_anonymized(application)
    if application.stage != "ready_for_hr" or application.hr_decision != "pending":
        raise DecisionError(409, "A restart can only be granted while the application awaits review")
    sessions = (
        db.query(VoiceSession)
        .filter(VoiceSession.application_id == application.id, VoiceSession.company_id == application.company_id,
                VoiceSession.purpose == "screening")
        .order_by(VoiceSession.id.desc()).all()
    )
    if not sessions:
        raise DecisionError(409, "There is no session to restart")
    if any((session.restart_count or 0) > 0 for session in sessions):
        raise DecisionError(409, "A restart was already granted")
    sessions[0].restart_count = 1
    advance(application, "invited")
    application.interview_band = None
    application.analysis_status = None
    application.ai_suggestion = None
    audit.record(db, application.company_id, actor_user_id, "restart_granted", "application", application.id,
                 payload={"session_id": sessions[0].id})
    db.flush()


def fast_track(db, application, actor_user_id) -> None:
    """Skip the interview. No AI runs, and the application reaches HR with no interview evidence."""
    _check_not_anonymized(application)
    try:
        if application.stage != "invited":
            raise InvalidTransition("not invited")
        advance(application, "ready_for_hr")
    except InvalidTransition:
        raise DecisionError(409, "Only an invited application can be fast-tracked") from None
    application.fast_tracked = True
    audit.record(db, application.company_id, actor_user_id, "fast_tracked", "application", application.id)
    db.flush()
