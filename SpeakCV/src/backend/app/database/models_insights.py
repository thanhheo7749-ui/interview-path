"""Block 5 tables: what hiring cost and how it turned out, and what happens to candidates afterwards."""
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.sql import func

from .database import Base

CHANNEL_COST_SOURCES = ("manual", "csv", "simulated")
# channel_costs has no is_simulated column. Real and simulated figures stay apart through this source value.
SIMULATED_COST_SOURCE = "simulated"
FEEDBACK_STATUSES = ("draft", "approved", "sent")
TALENT_POOL_STATUSES = ("active", "expired", "left")
ONBOARDING_STATUSES = ("draft", "approved", "active")
ONBOARDING_PHASES = (30, 60, 90)
PROBATION_RESULTS = ("passed", "failed", "extended")

__all__ = [
    "CHANNEL_COST_SOURCES", "SIMULATED_COST_SOURCE", "FEEDBACK_STATUSES", "TALENT_POOL_STATUSES",
    "ONBOARDING_STATUSES", "ONBOARDING_PHASES", "PROBATION_RESULTS",
    "ChannelCost", "RejectionFeedback", "LearningResource", "TalentPoolEntry", "OnboardingPlan", "OnboardingItem",
    "ProbationOutcome",
]


class ChannelCost(Base):
    __tablename__ = "channel_costs"
    # MySQL and SQLite both allow repeated NULLs here, so a row with no job_id must be checked by code.
    __table_args__ = (
        UniqueConstraint("company_id", "job_id", "channel", "period_month", name="uq_channel_cost"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    channel = Column(String(50), nullable=False)
    period_month = Column(String(7), nullable=False)  # YYYY-MM
    amount_vnd = Column(BigInteger, nullable=False)
    source = Column(String(20), nullable=False, default="manual")  # see CHANNEL_COST_SOURCES


class RejectionFeedback(Base):
    __tablename__ = "rejection_feedbacks"
    __table_args__ = (UniqueConstraint("application_id", name="uq_rejection_feedback_application"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(String(10), nullable=False)
    draft = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # see FEEDBACK_STATUSES
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    # A draft node can be deleted when its document is re-ingested. Its catalogue rows go with it, and do not block that.
    skill_node_id = Column(Integer, ForeignKey("kb_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(2000), nullable=False)
    provider = Column(String(100), nullable=False, default="")
    language = Column(String(10), nullable=False, default="en")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class TalentPoolEntry(Base):
    __tablename__ = "talent_pool_entries"
    __table_args__ = (UniqueConstraint("source_application_id", name="uq_talent_pool_source_application"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    # Every link cascades: with no candidate or no consent there is no basis to keep the retained CV.
    candidate_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_id = Column(Integer, ForeignKey("consents.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active")  # see TALENT_POOL_STATUSES
    # The application's blind text is erased when it is anonymized, so the consented copy lives here until the entry ends.
    retained_cv_text = Column(Text, nullable=True)
    embedding = Column(LargeBinary, nullable=True)
    embedding_model = Column(String(100), nullable=True)


class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"
    __table_args__ = (UniqueConstraint("application_id", name="uq_onboarding_plan_application"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    used_interview_data = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="draft")  # see ONBOARDING_STATUSES
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OnboardingItem(Base):
    __tablename__ = "onboarding_items"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    phase = Column(Integer, nullable=False)  # see ONBOARDING_PHASES
    title = Column(Text, nullable=False)
    source_node_id = Column(Integer, ForeignKey("kb_nodes.id", ondelete="SET NULL"), nullable=True)
    learning_resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="SET NULL"), nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    done_at = Column(DateTime(timezone=True), nullable=True)
    from_interview = Column(Boolean, nullable=False, default=False)  # built from the hire's interview gaps; withdrawal deletes it


class ProbationOutcome(Base):
    __tablename__ = "probation_outcomes"
    __table_args__ = (UniqueConstraint("application_id", name="uq_probation_outcome_application"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    result = Column(String(20), nullable=False)  # see PROBATION_RESULTS
    recorded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
