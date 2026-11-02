from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.sql import func

from .database import Base

__all__ = [
    "Job", "JobRequirement", "JobChannelLink", "Application", "ScreeningCache", "RequirementResult", "CvClaim",
    "VoiceSession", "VoiceTurn", "CultureNote", "Consent", "AuditLog", "Notification", "ReapplyGuard",
]


def _created_at():
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    role_node_id = Column(Integer, ForeignKey("kb_nodes.id"), nullable=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(150), unique=True, nullable=True, index=True)
    description = Column(Text, nullable=False, default="")
    status = Column(String(30), nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    interview_languages = Column(JSON, nullable=False, default=list)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = _created_at()


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("kb_nodes.id"), nullable=True)
    text = Column(Text, nullable=False)
    must_have = Column(Boolean, nullable=False, default=False)
    visibility = Column(String(20), nullable=False, default="public")
    position = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)


class JobChannelLink(Base):
    __tablename__ = "job_channel_links"
    __table_args__ = (UniqueConstraint("job_id", "channel", name="uq_job_channel"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    click_count = Column(Integer, nullable=False, default=0)
    created_at = _created_at()


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("company_id", "alias", name="uq_application_alias"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    job_version = Column(Integer, nullable=False, default=1)
    candidate_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    alias = Column(String(20), nullable=False)
    source_channel = Column(String(50), nullable=True)
    cv_file_path = Column(String(500), nullable=True)
    cv_suffix = Column(String(10), nullable=True)
    cv_text_raw = Column(Text, nullable=True)
    cv_text_blind = Column(Text, nullable=True)
    cv_blind_hash = Column(String(64), nullable=True, index=True)
    hidden_text_detected = Column(Boolean, nullable=False, default=False)
    stage = Column(String(30), nullable=False, default="submitted")
    processing_error = Column(Text, nullable=True)
    cv_status = Column(String(20), nullable=True)  # meets | not_met
    cv_status_reason = Column(JSON, nullable=True)
    cv_status_corrected_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cv_status_correction_reason = Column(Text, nullable=True)
    interview_band = Column(String(20), nullable=True)  # many | few
    analysis_status = Column(String(20), nullable=True)  # pending | running | done | failed | not_taken
    ai_suggestion = Column(Text, nullable=True)
    # Written only by app/hiring/decisions.py (POST .../decision).
    hr_decision = Column(String(20), nullable=False, default="pending")  # pending | approved | rejected
    hr_decided_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hr_decided_at = Column(DateTime(timezone=True), nullable=True)
    fast_tracked = Column(Boolean, nullable=False, default=False)
    withdraw_reason = Column(Text, nullable=True)
    final_outcome = Column(String(30), nullable=True)
    is_simulated = Column(Boolean, nullable=False, default=False)
    anonymized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = _created_at()


class ScreeningCache(Base):
    __tablename__ = "screening_cache"
    __table_args__ = (
        UniqueConstraint("blind_hash", "job_id", "job_version", "prompt_version", "model", name="uq_screening_cache"),
    )

    id = Column(Integer, primary_key=True, index=True)
    blind_hash = Column(String(64), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    job_version = Column(Integer, nullable=False)
    prompt_version = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    result = Column(JSON, nullable=False)


class RequirementResult(Base):
    __tablename__ = "requirement_results"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("job_requirements.id"), nullable=False, index=True)
    source = Column(String(20), nullable=False)  # cv | interview
    status = Column(String(30), nullable=False)
    quote = Column(Text, nullable=True)
    voice_turn_id = Column(Integer, ForeignKey("voice_turns.id"), nullable=True)


class CvClaim(Base):
    __tablename__ = "cv_claims"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    quote = Column(Text, nullable=False)
    status = Column(String(30), nullable=True)
    evidence_quote = Column(Text, nullable=True)
    voice_turn_id = Column(Integer, ForeignKey("voice_turns.id"), nullable=True)


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(20), nullable=False)  # screening | intake
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    language = Column(String(10), nullable=False)
    status = Column(String(30), nullable=False, default="created")
    plan = Column(JSON, nullable=True)
    restart_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    active_seconds = Column(Integer, nullable=False, default=0, server_default="0")
    last_activity_at = Column(DateTime(timezone=True), nullable=True)


class VoiceTurn(Base):
    __tablename__ = "voice_turns"
    __table_args__ = (UniqueConstraint("session_id", "position", name="uq_voice_turn_position"),)

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_source = Column(String(30), nullable=False)
    source_ref = Column(String(100), nullable=True)
    is_followup = Column(Boolean, nullable=False, default=False)
    parent_position = Column(Integer, nullable=True)
    audio_path = Column(String(500), nullable=True)
    audio_seconds = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)
    transcript_status = Column(String(30), nullable=False, default="pending")
    silent_count = Column(Integer, nullable=False, default=0)
    stt_failures = Column(Integer, nullable=False, default=0)
    created_at = _created_at()
    answered_at = Column(DateTime(timezone=True), nullable=True)


class CultureNote(Base):
    __tablename__ = "culture_notes"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    value_node_id = Column(Integer, ForeignKey("kb_nodes.id"), nullable=False)
    note = Column(Text, nullable=False)
    quote = Column(Text, nullable=False)
    voice_turn_id = Column(Integer, ForeignKey("voice_turns.id"), nullable=False)


class Consent(Base):
    __tablename__ = "consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    purpose = Column(String(50), nullable=False)
    text_version = Column(String(30), nullable=False)
    language = Column(String(10), nullable=True)  # NULL when the client did not say which text it showed
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    target_type = Column(String(50), nullable=False)
    target_id = Column(Integer, nullable=True)
    ai_provider = Column(String(50), nullable=True)
    ai_model = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = _created_at()


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    kind = Column(String(50), nullable=False)
    language = Column(String(10), nullable=False, default="en")
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending", index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)


class ReapplyGuard(Base):
    """Stops a deleted application resetting the 90-day limit. A keyed hash of user and job, and the date applied:
    nothing else about the person. Retention removes the row when the 90 days are over."""
    __tablename__ = "reapply_guards"

    id = Column(Integer, primary_key=True)
    key_hash = Column(String(64), nullable=False, index=True)
    applied_at = Column(DateTime(timezone=True), nullable=False)
