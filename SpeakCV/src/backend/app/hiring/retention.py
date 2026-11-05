"""Deletes candidates' personal data, and keeps the statuses Block 5 metrics need. No step here calls AI."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_

from app.core import storage
from app.database.database import SessionLocal
from app.database.sql_models import (
    Application, AssistantQuestion, AuditLog, CandidateBrief, Company, CompanyMember, Consent, CultureNote, CvClaim,
    InterviewScorecard, Job, Notification, ReapplyGuard, RejectionFeedback, RequirementResult, ScreeningCache, VoiceSession,
    VoiceTurn,
)
from app.bridges import intake
from app.hiring import audit, consents, notify, reapply_guard, voice
from app.hiring.state import advance
from app.posthire import feedback

logger = logging.getLogger(__name__)

UNDECIDED_RETENTION_DAYS = consents.UNDECIDED_RETENTION_DAYS
QUESTION_RETENTION_DAYS = 180
CANDIDATE_AUDIENCE = "candidate"
REMINDER_AFTER_DAYS = 3
SECONDS_BETWEEN_RUNS = 24 * 60 * 60
TRIGGER_RETENTION = "retention"
TRIGGER_CANDIDATE = "candidate_request"
ANONYMIZED = "application_anonymized"
REMINDER_QUEUED = "reminder_queued"
REMINDER = {
    "en": ("Your interview for {title} is waiting", "You have not started your short recorded interview for {title} yet. It is still open."),
    "vi": ("Buổi phỏng vấn cho vị trí {title} đang chờ bạn", "Bạn chưa bắt đầu buổi phỏng vấn ngắn có ghi âm cho vị trí {title}. Buổi phỏng vấn vẫn đang mở."),
}

# Every text column and link to a user in models_hiring is in exactly one list. test_hiring_retention fails on a new one.
# Cleared when an application is anonymized: to NULL, or to "" where the column cannot be NULL.
ERASED = {
    "applications": (
        "candidate_user_id", "cv_file_path", "cv_text_raw", "cv_text_blind", "cv_blind_hash", "processing_error",
        "cv_status_reason", "cv_status_correction_reason", "ai_suggestion", "withdraw_reason",
    ),
    "requirement_results": ("quote",),
    "cv_claims": ("text", "quote", "evidence_quote"),
    "voice_sessions": ("owner_user_id", "plan"),  # the plan holds question text, which quotes the CV
    "voice_turns": ("question_text", "source_ref", "audio_path", "question_audio_path", "transcript"),
    "culture_notes": ("note", "quote"),
    "consents": ("user_id",),
    "candidate_briefs": ("content",),  # original quotes and recording times
    "interview_scorecards": ("requirement_scores", "notes"),
    # Not tied to one application: cleared on the candidate's last deletion at the company, and by age. See _erase_question.
    "assistant_questions": ("user_id", "question", "embedding"),
    "rejection_feedbacks": ("draft",),  # it quotes the candidate's answers
    # Nothing is cleared on these three. Each one's own rules decide how long it stays: see KEPT.
    "talent_pool_entries": (),
    "onboarding_plans": (),
    "probation_outcomes": (),
}
# Whole rows go. A notification's user_id cannot be NULL, and a cache row is nothing but quotes and claims.
DELETED_ROWS = ("screening_cache", "notifications")
# Stay, because they hold no personal content once the columns above are cleared.
KEPT = {
    "jobs": (
        "title", "slug", "description", "status", "interview_languages", "created_by",
        "interview_window_timezone",  # the company's own scheduling setting, not candidate content
    ),
    "job_requirements": ("text", "visibility"),  # the company's own
    "job_channel_links": ("channel", "token"),  # the company's own
    "applications": (
        "alias",  # a per-company number with no link left to the user; keeping it stops it being reissued
        "cv_suffix", "source_channel", "stage", "cv_status", "interview_band", "analysis_status", "hr_decision",
        "final_outcome",
        "cv_status_corrected_by", "hr_decided_by",  # HR staff, not the candidate
    ),
    "requirement_results": ("source", "status"),
    "cv_claims": ("status",),
    "voice_sessions": ("purpose", "language", "status"),
    "voice_turns": ("question_source", "transcript_status"),
    "consents": ("purpose", "text_version", "language"),
    "audit_log": (
        "action", "target_type", "ai_provider", "ai_model", "prompt_version",
        "payload",  # HR's free-text reasons are stripped by _strip_audit_reasons; nothing else there is personal
        "actor_user_id",  # HR staff stay; a candidate's own is cleared by _unlink_audit
    ),
    "assistant_questions": ("audience", "language", "state", "top_score", "embedding_model"),  # no content once cleared
    "reapply_guards": ("key_hash",),  # a keyed hash, stated in the consent text; removed after REAPPLY_DAYS
    "rejection_feedbacks": ("language", "status", "approved_by"),
    # A separate talent_pool consent keeps these until the entry ends, whatever happens to the application.
    "talent_pool_entries": ("candidate_user_id", "retained_cv_text", "embedding_model", "status"),
    "onboarding_plans": ("employee_user_id", "status", "approved_by"),  # an employee's plan, not candidate evidence
    "probation_outcomes": ("result", "recorded_by"),  # feeds Reality Check, and holds no personal content
}


def has_extension(db, application) -> bool:
    """Whether a consent extends this application's retention. The talent pool does not: its consent keeps a masked copy
    on the entry, and audio and transcripts still go on time. See app.posthire.talent_pool."""
    return False


def _as_naive(value: datetime) -> datetime:
    """The database stores naive UTC on both SQLite and MySQL."""
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _naive_utc(now: datetime | None) -> datetime:
    return _as_naive(now or datetime.now(timezone.utc))


def _cutoffs(retention_days: int, now: datetime) -> tuple[datetime, datetime]:
    return now - timedelta(days=retention_days), now - timedelta(days=UNDECIDED_RETENTION_DAYS)


def _due_ids(db, company_id: int, retention_days: int, now: datetime) -> list[int]:
    decided_before, submitted_before = _cutoffs(retention_days, now)
    rows = (
        db.query(Application.id)
        .filter(
            Application.company_id == company_id,
            Application.anonymized_at.is_(None),
            or_(
                Application.hr_decided_at < decided_before,
                Application.hr_decided_at.is_(None) & (Application.created_at < submitted_before),
            ),
        )
        .order_by(Application.id)
        .all()
    )
    return [row[0] for row in rows]


def _is_due(application, retention_days: int, now: datetime) -> bool:
    if application.anonymized_at is not None:
        return False
    decided_before, submitted_before = _cutoffs(retention_days, now)
    if application.hr_decided_at is not None:
        return _as_naive(application.hr_decided_at) < decided_before
    return _as_naive(application.created_at) < submitted_before


def _erase(row) -> None:
    for name in ERASED[row.__tablename__]:
        setattr(row, name, None if row.__table__.c[name].nullable else "")


def _has_another_live(db, application, user_id: int) -> bool:
    """Whether the user has another application at this company that is not anonymized."""
    return (
        db.query(Application.id)
        .filter(
            Application.company_id == application.company_id, Application.candidate_user_id == user_id,
            Application.id != application.id, Application.anonymized_at.is_(None),
        )
        .first()
    ) is not None


def _delete_notifications(db, application, user_id: int | None) -> None:
    """Notifications pointing at this application go. An old row with no link goes by the former rule: while the user
    has another live application at this company, only one naming this job goes; the rest go with the last one."""
    db.query(Notification).filter(Notification.application_id == application.id).delete(synchronize_session=False)
    if user_id is None:
        return
    rows = db.query(Notification).filter(
        Notification.company_id == application.company_id, Notification.user_id == user_id,
        Notification.application_id.is_(None),
    )
    if _has_another_live(db, application, user_id):
        title = db.get(Job, application.job_id).title
        rows = rows.filter(or_(Notification.subject.contains(title, autoescape=True),
                               Notification.body.contains(title, autoescape=True)))
    rows.delete(synchronize_session=False)


def _unlink_audit(db, application, user_id: int) -> None:
    """The candidate's own actions keep their row and lose the link. A candidate who is also a member of the
    company keeps what they did as staff, so only rows about this application change."""
    rows = db.query(AuditLog).filter(AuditLog.company_id == application.company_id, AuditLog.actor_user_id == user_id)
    is_member = db.query(CompanyMember.id).filter_by(company_id=application.company_id, user_id=user_id).first()
    if is_member is not None:
        rows = rows.filter(AuditLog.target_type == "application", AuditLog.target_id == application.id)
    rows.update({AuditLog.actor_user_id: None}, synchronize_session=False)


def _strip_audit_reasons(db, application_id: int) -> None:
    """HR's reason is free text and may name the candidate. The fact that one existed stays."""
    rows = db.query(AuditLog).filter(AuditLog.target_type == "application", AuditLog.target_id == application_id)
    for row in rows:
        payload = row.payload or {}
        if "reason" in payload:
            row.payload = {
                **{key: value for key, value in payload.items() if key != "reason"},
                **({"has_reason": True} if payload["reason"] else {}),
            }


def _erase_question(row) -> None:
    _erase(row)
    row.resolved = True  # it was a gap only for as long as HR could read what was asked


def _forget_questions(db, application, user_id: int) -> None:
    """On a candidate's deletion, once nothing of theirs remains at this company. Their staff questions are not touched."""
    if _has_another_live(db, application, user_id):
        return
    for row in db.query(AssistantQuestion).filter(
        AssistantQuestion.company_id == application.company_id, AssistantQuestion.user_id == user_id,
        AssistantQuestion.audience == CANDIDATE_AUDIENCE,
    ):
        _erase_question(row)


def _guard_reapply(db, application, user_id: int, had_session: bool) -> None:
    """An interview seen or a decision made must not be undone by deleting. Past the limit there is nothing to guard."""
    if not had_session and application.hr_decision == "pending":
        return
    applied_at = _as_naive(application.created_at)
    if applied_at > _naive_utc(None) - timedelta(days=consents.REAPPLY_DAYS):
        reapply_guard.remember(db, user_id, application.job_id, applied_at)


def _delete_cache(db, application_id: int, blind_hash: str | None) -> None:
    if not blind_hash:
        return
    in_use = (
        db.query(Application.id)
        .filter(Application.cv_blind_hash == blind_hash, Application.id != application_id)
        .first()
    )
    if in_use is None:
        db.query(ScreeningCache).filter(ScreeningCache.blind_hash == blind_hash).delete(synchronize_session=False)


def _stop_cv_job(application) -> None:
    """A CV job in flight gives way once the stage leaves cv_processing, so it cannot write the text back."""
    if application.stage == "submitted":
        advance(application, "cv_processing")
    if application.stage == "cv_processing":
        advance(application, "cv_failed")


def _delete_files(cv_path: str | None, audio_paths: list[str]) -> None:
    if cv_path:
        storage.delete(cv_path)
    if audio_paths:
        from app.hiring import recordings  # Imported here, so a run with no audio does not depend on it.

        for path in audio_paths:
            recordings.delete(path)


def _settle_talent_pool(db, application, user_id: int | None, trigger: str) -> None:
    from app.posthire import talent_pool  # Imported here: talent_pool is built on this module.

    talent_pool.on_application_anonymized(db, application, user_id, by_candidate=trigger == TRIGGER_CANDIDATE)


def _expire_talent_pool(db) -> int:
    from app.posthire import talent_pool

    return talent_pool.expire(db)


def anonymize_application(db, application, *, trigger: str = TRIGGER_RETENTION, only_if=None, commit: bool = True) -> bool:
    """Commits, unless the caller owns the transaction and the application has no file to delete. Files go after the rows
    are flushed and before the commit: if a file cannot be deleted, the caller rolls back and the paths survive for a
    retry, and a file already deleted is no obstacle to that retry.

    Discards anything pending and ends the session's snapshot before locking, as `voice._lock` does. Under MySQL's
    REPEATABLE READ the plain reads below would otherwise come from a snapshot older than an answer stored while this
    waited for the lock, and the audio and transcript would stay for good. Any check of the caller's must be repeated
    under this lock, so it is passed as `only_if`. With commit=False the caller's own work is in this transaction and it
    has locked the row, so neither happens. Returns False if `only_if` refused; an application already gone counts as done.
    """
    application_id = application.id
    if commit:
        db.rollback()
        application = _locked(db, application_id)
    if application is None or application.anonymized_at is not None:
        if commit:
            db.rollback()
        return only_if is None
    if only_if is not None and not only_if(application):
        if commit:
            db.rollback()
        return False
    user_id = application.candidate_user_id
    blind_hash = application.cv_blind_hash
    cv_path = application.cv_file_path
    sessions = db.query(VoiceSession).filter_by(application_id=application_id).all()
    session_ids = [session.id for session in sessions]
    turns = db.query(VoiceTurn).filter(VoiceTurn.session_id.in_(session_ids)).all() if session_ids else []
    audio_paths = [path for turn in turns for path in (turn.audio_path, turn.question_audio_path) if path]
    if user_id is not None:
        _guard_reapply(db, application, user_id, bool(session_ids))

    for model in (RequirementResult, CvClaim, CultureNote, Consent, CandidateBrief, InterviewScorecard, RejectionFeedback):
        for row in db.query(model).filter_by(application_id=application_id):
            _erase(row)
    for session in sessions:
        if session.status in voice.ACTIVE_STATUSES:
            session.status = voice.ABANDONED  # nothing resumes it, and no sweep or poll counts it again
    for row in (*sessions, *turns):
        _erase(row)
    _delete_notifications(db, application, user_id)
    _settle_talent_pool(db, application, user_id, trigger)
    if user_id is not None:
        if trigger == TRIGGER_CANDIDATE:
            _forget_questions(db, application, user_id)  # after the pool: an invitation it retracts no longer counts as live
        _unlink_audit(db, application, user_id)
    _strip_audit_reasons(db, application_id)
    _stop_cv_job(application)
    _erase(application)
    application.anonymized_at = _naive_utc(None)
    audit.record(db, application.company_id, None, ANONYMIZED, "application", application_id, payload={"trigger": trigger})
    db.flush()
    _delete_cache(db, application_id, blind_hash)
    _delete_files(cv_path, audio_paths)
    if commit:
        db.commit()
    return True


def try_anonymize(db, application, *, trigger: str, only_if=None) -> bool:
    """False, with everything rolled back, when it could not finish. Only the type is logged: text can hold content."""
    application_id = application.id
    try:
        return anonymize_application(db, application, trigger=trigger, only_if=only_if)
    except Exception as exc:
        db.rollback()
        logger.warning("Could not anonymize application %s: %s", application_id, type(exc).__name__)
        return False


def _locked(db, application_id: int) -> Application | None:
    # A locking read returns the latest committed row, not this transaction's snapshot.
    return (
        db.query(Application).filter(Application.id == application_id)
        .populate_existing().with_for_update().first()
    )


def _anonymize_if_due(db, application_id: int, retention_days: int, now: datetime) -> bool:
    def due(row) -> bool:
        return _is_due(row, retention_days, now) and not has_extension(db, row)

    application = _locked(db, application_id)
    if application is None or not due(application):
        db.rollback()
        return False
    return try_anonymize(db, application, trigger=TRIGGER_RETENTION, only_if=due)


def _purge_unused_cache(db) -> None:
    """A CV job whose AI call ended after its application was deleted still commits a cache row. Nothing uses it."""
    in_use = db.query(Application.id).filter(Application.cv_blind_hash == ScreeningCache.blind_hash).exists()
    db.query(ScreeningCache).filter(~in_use).delete(synchronize_session=False)
    db.commit()


def _expire_questions(db, now: datetime) -> None:
    """Candidates' questions go by age, whatever became of any application. Staff questions stay."""
    rows = db.query(AssistantQuestion).filter(
        AssistantQuestion.audience == CANDIDATE_AUDIENCE,
        AssistantQuestion.created_at < now - timedelta(days=QUESTION_RETENTION_DAYS),
        or_(AssistantQuestion.question != "", AssistantQuestion.user_id.isnot(None)),
    )
    for row in rows:
        _erase_question(row)
    db.commit()


def _expire_guards(db, now: datetime) -> None:
    db.query(ReapplyGuard).filter(
        ReapplyGuard.applied_at < now - timedelta(days=consents.REAPPLY_DAYS),
    ).delete(synchronize_session=False)
    db.commit()


def run(db, now=None) -> int:
    """Anonymize everything past its date, and return how many. Commits, one application at a time."""
    now = _naive_utc(now)
    db.commit()  # end any transaction, so the lists below see what other sessions committed
    count = 0
    for company_id, retention_days in db.query(Company.id, Company.retention_days).order_by(Company.id).all():
        for application_id in _due_ids(db, company_id, retention_days, now):
            try:
                count += _anonymize_if_due(db, application_id, retention_days, now)
            except Exception as exc:
                db.rollback()
                logger.warning("Could not check application %s: %s", application_id, type(exc).__name__)
    for name, step in (
        ("unused screening results", lambda: _purge_unused_cache(db)),
        ("old candidate questions", lambda: _expire_questions(db, now)),
        ("old re-apply guards", lambda: _expire_guards(db, now)),
    ):
        try:
            step()
        except Exception as exc:
            db.rollback()
            logger.warning("Could not clear %s: %s", name, type(exc).__name__)
    return count


def counts(db, company, now=None) -> dict:
    now = _naive_utc(now)
    due_ids = _due_ids(db, company.id, company.retention_days, now)
    due = db.query(Application).filter(Application.id.in_(due_ids), Application.is_simulated.is_(False)).all() if due_ids else []
    real = db.query(Application.id).filter(Application.company_id == company.id, Application.is_simulated.is_(False))
    live = real.filter(Application.anonymized_at.is_(None)).count()
    gone = real.filter(Application.anonymized_at.isnot(None)).count()
    return {
        "retention_days": company.retention_days,
        "undecided_retention_days": UNDECIDED_RETENTION_DAYS,
        "awaiting_deletion": live,
        "due_now": sum(1 for application in due if not has_extension(db, application)),
        "anonymized": gone,
    }


def _invited_at(db, application) -> datetime:
    """Assessing is the last step before the invitation, and a re-upload repeats it. The row has no date of its own."""
    assessed = (
        db.query(AuditLog.created_at)
        .filter(AuditLog.action == "cv_assessed", AuditLog.target_type == "application", AuditLog.target_id == application.id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    return _as_naive(assessed[0] if assessed is not None else application.created_at)


def _queue_reminder(db, application_id: int, cutoff: datetime) -> bool:
    application = _locked(db, application_id)
    if (
        application is None or application.stage != "invited" or application.anonymized_at is not None
        or application.candidate_user_id is None
        or db.query(VoiceSession.id).filter_by(application_id=application_id).first() is not None
        or db.query(AuditLog.id).filter_by(action=REMINDER_QUEUED, target_type="application", target_id=application_id).first() is not None
        or consents.was_withdrawn(db, application_id, "cv_processing")  # the interview can no longer start
        or _invited_at(db, application) >= cutoff
    ):
        db.rollback()
        return False
    company = db.get(Company, application.company_id)
    title = db.get(Job, application.job_id).title
    language = company.default_locale if company.default_locale in REMINDER else "en"
    subject, body = REMINDER[language]
    notify.enqueue(db, application.company_id, application.candidate_user_id, "reminder", language,
                   subject.format(title=title), body.format(title=title), application_id=application_id)
    audit.record(db, application.company_id, None, REMINDER_QUEUED, "application", application_id)
    db.commit()
    return True


def send_reminders(db, now=None) -> int:
    """Queue one reminder per application, three days after an invitation with no session. Commits."""
    cutoff = _naive_utc(now) - timedelta(days=REMINDER_AFTER_DAYS)
    db.commit()  # end any transaction, so the list below sees what other sessions committed
    rows = (
        db.query(Application.id)
        .filter(Application.stage == "invited", Application.anonymized_at.is_(None),
                Application.candidate_user_id.isnot(None), Application.created_at < cutoff)
        .order_by(Application.id)
        .all()
    )
    count = 0
    for (application_id,) in rows:
        try:
            count += _queue_reminder(db, application_id, cutoff)
        except Exception as exc:
            db.rollback()
            logger.warning("Could not queue a reminder for application %s: %s", application_id, type(exc).__name__)
    return count


def _daily_pass() -> None:
    db = SessionLocal()
    try:
        for step in (voice.sweep_abandoned, intake.sweep_terminal, run, _expire_talent_pool, send_reminders, feedback.send_overdue_notices,
                     notify.send_pending):
            try:
                step(db)
            except Exception as exc:
                db.rollback()
                logger.warning("A daily retention step failed: %s", type(exc).__name__)
    finally:
        db.close()


async def _daily_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(_daily_pass)
        except Exception as exc:
            logger.warning("The daily retention pass failed: %s", type(exc).__name__)
        await asyncio.sleep(SECONDS_BETWEEN_RUNS)


def start_daily_task(app) -> asyncio.Task | None:
    """Start the daily loop from lifespan, which cancels the returned task on shutdown. Never runs under APP_ENV=test."""
    if os.environ.get("APP_ENV") == "test":
        return None
    return asyncio.create_task(_daily_loop(), name="retention")
