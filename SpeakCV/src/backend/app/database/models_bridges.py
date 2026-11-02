from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base

HIRING_REQUEST_STATUSES = ("open", "intake_in_progress", "intake_done", "drafting", "published", "cancelled")
JOB_DRAFT_STATUSES = ("draft", "manager_review", "approved", "published")

__all__ = [
    "HIRING_REQUEST_STATUSES", "JOB_DRAFT_STATUSES",
    "HiringRequest", "JobDraft", "JobDraftMessage", "ChannelContent", "CandidateBrief", "InterviewScorecard",
]


def _created_at():
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HiringRequest(Base):
    __tablename__ = "hiring_requests"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="open")  # see HIRING_REQUEST_STATUSES
    intake_session_id = Column(Integer, ForeignKey("voice_sessions.id", ondelete="SET NULL"), nullable=True)
    intake_document_id = Column(Integer, ForeignKey("kb_documents.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = _created_at()


class JobDraft(Base):
    __tablename__ = "job_drafts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    hiring_request_id = Column(Integer, ForeignKey("hiring_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    # Description lines per language: {"id", "text": {"en", "vi", "ko"}, "source_node_ids", "hr_confirmed"}.
    lines = Column(JSON, nullable=False, default=list)
    requirement_lines = Column(JSON, nullable=False, default=list)
    lint = Column(JSON, nullable=False, default=list)
    failed_languages = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="draft")  # see JOB_DRAFT_STATUSES
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)  # the first submit: a manager reads nothing before it
    created_at = _created_at()


class JobDraftMessage(Base):
    __tablename__ = "job_draft_messages"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_draft_id = Column(Integer, ForeignKey("job_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = _created_at()


class ChannelContent(Base):
    __tablename__ = "channel_contents"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_draft_id = Column(Integer, ForeignKey("job_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    language = Column(String(10), nullable=False)
    body = Column(Text, nullable=False)
    link_id = Column(Integer, ForeignKey("job_channel_links.id", ondelete="SET NULL"), nullable=True)
    created_at = _created_at()


class CandidateBrief(Base):
    __tablename__ = "candidate_briefs"
    __table_args__ = (UniqueConstraint("application_id", name="uq_candidate_briefs_application"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(String(10), nullable=False)
    content = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="draft")  # draft | sent
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = _created_at()


class InterviewScorecard(Base):
    __tablename__ = "interview_scorecards"
    __table_args__ = (UniqueConstraint("application_id", "manager_user_id", name="uq_scorecards_application_manager"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requirement_scores = Column(JSON, nullable=False, default=list)
    recommendation = Column(String(20), nullable=False)  # hire | no_hire
    notes = Column(Text, nullable=False, default="")
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
