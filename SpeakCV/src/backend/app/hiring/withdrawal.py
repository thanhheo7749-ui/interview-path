"""What withdrawing a consent does. My Data states this to the candidate in the same terms; change them together.

Recording: the session ends, analysis is cancelled, and the audio, transcripts and everything drawn from them go. The
application reaches HR with a neutral marker, and HR decides freely. No step is AI, and nothing here judges the person.
CV processing: no further AI works on the CV, and no new CV is taken. Results already produced stay.

Transactions follow `voice._lock`: end the snapshot, lock the application, then the session, so the plain reads below
see what an upload or analysis committed while this waited. Commits. Files go after the flush and before the commit, as
in `retention.anonymize_application`: if one cannot be deleted, the rollback keeps the paths for a retry.
"""
from datetime import datetime, timezone

from app.database.sql_models import (
    Application, CandidateBrief, Consent, CultureNote, CvClaim, Job, RejectionFeedback, RequirementResult, VoiceSession,
    VoiceTurn,
)
from app.hiring import audit, consents, recordings, voice
from app.hiring.state import CONSENT_WITHDRAWN, advance

RECORDING = "recording_screening"
CV_PROCESSING = "cv_processing"
ONBOARDING_USE = "onboarding_use"  # locks the application first, as create_plan does, but changes nothing on it
# Withdrawing these changes the application itself. Any other purpose keeps to its own rules, in consents.withdraw.
LOCKS_APPLICATION = (RECORDING, CV_PROCESSING)
CV_STOPPED = "You withdrew consent to CV processing, so we stopped reading this CV."


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _lock_application(db, application_id: int | None) -> Application | None:
    if application_id is None:
        return None
    return db.query(Application).filter(Application.id == application_id).populate_existing().with_for_update().first()


def _send_to_hr(application) -> None:
    if application.stage == "session_completed":
        advance(application, "analyzing")
    if application.stage in ("invited", "session_in_progress", "analyzing"):
        advance(application, "ready_for_hr")


def _erase_recording(db, application) -> list[str]:
    """Returns the audio files to delete."""
    now = _now()
    sessions = (
        db.query(VoiceSession).filter(VoiceSession.application_id == application.id)
        .populate_existing().with_for_update().all()
    )
    session_ids = [session.id for session in sessions]
    for session in sessions:
        if session.status in voice.ACTIVE_STATUSES:
            session.status = voice.ABANDONED
            session.finished_at = now
    turns = db.query(VoiceTurn).filter(VoiceTurn.session_id.in_(session_ids)).all() if session_ids else []
    paths = [path for turn in turns for path in (turn.audio_path, turn.question_audio_path) if path]
    for turn in turns:
        turn.audio_path = turn.question_audio_path = turn.transcript = turn.audio_seconds = turn.stt_started_at = None
        if turn.is_followup:
            turn.question_text = ""  # written from the candidate's answer
    return paths


def _erase_results(db, application) -> None:
    application_id = application.id
    db.query(RequirementResult).filter_by(application_id=application_id, source="interview").delete(synchronize_session=False)
    db.query(CultureNote).filter_by(application_id=application_id).delete(synchronize_session=False)
    db.query(CandidateBrief).filter_by(application_id=application_id).delete(synchronize_session=False)
    for claim in db.query(CvClaim).filter_by(application_id=application_id):
        claim.status = claim.evidence_quote = claim.voice_turn_id = None  # the claim itself comes from the CV, and stays
    application.interview_band = None
    application.ai_suggestion = None
    _erase_feedback(db, application)


def _erase_feedback(db, application) -> None:
    """A rejection message quotes the answers. HR can draft again, from the CV alone. One already sent stays on record as
    sent, in the plain wording, so no quote is left and the candidate's page still holds a message."""
    from app.posthire import feedback  # Imported here: feedback is built on the hiring modules.

    row = db.query(RejectionFeedback).filter_by(application_id=application.id).populate_existing().with_for_update().first()
    if row is None:
        return
    if row.status == "sent":
        row.draft = feedback.template(row.language, db.get(Job, application.job_id).title)
    else:
        db.delete(row)


def _withdraw_recording(db, application) -> None:
    paths = _erase_recording(db, application)
    _erase_results(db, application)
    _send_to_hr(application)
    application.analysis_status = CONSENT_WITHDRAWN
    db.flush()
    for path in paths:
        recordings.delete(path)


def _stop_cv_work(application) -> None:
    """A CV job in flight gives way once the stage leaves cv_processing, and cv_processing._claim starts no new one."""
    if application.stage == "submitted":
        advance(application, "cv_processing")
    if application.stage == "cv_processing":
        advance(application, "cv_failed")
        application.processing_error = CV_STOPPED


def withdraw(db, consent_id: int, user_id: int) -> Consent | None:
    """None if this user holds no such consent. Withdrawing again changes nothing. Every consent of that purpose on the
    application goes together: a restarted interview has a second one, and either could otherwise keep the recording."""
    db.rollback()
    found = db.query(Consent.application_id, Consent.purpose).filter(Consent.id == consent_id, Consent.user_id == user_id).first()
    db.rollback()
    if found is None:
        return None
    application = (_lock_application(db, found.application_id)
                   if found.purpose in LOCKS_APPLICATION or found.purpose == ONBOARDING_USE else None)
    consent = (
        db.query(Consent).filter(Consent.id == consent_id, Consent.user_id == user_id)
        .populate_existing().with_for_update().first()
    )
    if consent is None or consent.withdrawn_at is not None:
        db.rollback()
        return consent
    company_id = consent.company_id
    if found.purpose not in LOCKS_APPLICATION:
        consents.withdraw(db, consent_id, user_id)
        # A consent with no user left belongs to an anonymized application, so this row must not name them either.
        audit.record(db, company_id, user_id if consent.user_id else None, "consent_withdrawn", "consent", consent_id,
                     payload={"purpose": found.purpose})
        db.commit()
        return consent
    now = _now()
    consent.withdrawn_at = now
    if application is not None:
        (
            db.query(Consent)
            .filter(Consent.application_id == application.id, Consent.purpose == consent.purpose, Consent.withdrawn_at.is_(None),
                    Consent.id != consent.id)
            .update({Consent.withdrawn_at: now}, synchronize_session=False)
        )
        if consent.purpose == RECORDING:
            _withdraw_recording(db, application)
        elif consent.purpose == CV_PROCESSING:
            _stop_cv_work(application)
    audit.record(db, consent.company_id, user_id, "consent_withdrawn", "consent", consent.id, payload={"purpose": consent.purpose})
    db.commit()
    return consent

