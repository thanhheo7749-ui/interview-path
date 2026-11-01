# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

from sqlalchemy import CheckConstraint, Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Date, Boolean, UniqueConstraint
from sqlalchemy.sql import false, func
from .database import Base

# 1. Users table (login credentials only)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    full_name = Column(String(255))
    hashed_password = Column(String(255))
    role = Column(String(50), default="user")
    credits = Column(Integer, default=50)
    plan = Column(String(20), default="free")
    last_token_reset_date = Column(Date, default=func.current_date())
    must_change_password = Column(Boolean, default=False, server_default=false(), nullable=False)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)

# 2. UserProfile table (detailed user info)
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    github = Column(String(255), nullable=True)
    linkedin = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)
    avatar = Column(Text, nullable=True)
    master_cv_text = Column(Text, nullable=True)
    master_cv_structured = Column(JSON, nullable=True)

# 3. Experience table
class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    company_name = Column(String(255))
    position = Column(String(255))
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=False)
    description = Column(Text, nullable=True)

# 4. Education table
class Education(Base):
    __tablename__ = "educations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    school_name = Column(String(255))
    degree = Column(String(255))
    major = Column(String(255))
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

# 5. Interview history table
class InterviewHistory(Base):
    __tablename__ = "interview_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255), nullable=True)
    position = Column(String(255))
    score = Column(Float)
    overall_feedback = Column(Text)
    details = Column(JSON)
    interview_type = Column(String(50), default="free")
    question_limit = Column(Integer, default=0)
    time_limit = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 6. JD Templates table
class JDTemplate(Base):
    __tablename__ = "jd_templates"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 7. System config table
class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, index=True)
    setting_value = Column(Text)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# 8. Transaction history table (credits)
class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer)
    transaction_type = Column(String(50)) # e.g. 'add_credits', 'consume_credits'
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 9. Support messages table (live support)
class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    admin_id = Column(Integer, nullable=True) # ID of the responding admin, if any
    message = Column(Text)
    sender_type = Column(String(20)) # 'user' or 'admin'
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 10. Transactions table (VNPAY)
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount = Column(Integer)
    txn_ref = Column(String(100), unique=True, index=True)
    status = Column(String(50), default="pending") # 'pending', 'success', 'failed'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 11. Company Questions table (crowdsourced interview questions)
class CompanyQuestion(Base):
    __tablename__ = "company_questions"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), index=True)
    position = Column(String(200))
    question_text = Column(Text)
    difficulty = Column(String(50), default="medium")  # easy, medium, hard
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_approved = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 12. AI Brain versions
class AIBrainVersion(Base):
    __tablename__ = "ai_brain_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(100), unique=True, index=True)
    name = Column(String(255), default="speakcv-interviewer-brain")
    status = Column(String(20), default="draft")  # draft | active | archived
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# 13. AI Brain nodes
class AIBrainNode(Base):
    __tablename__ = "ai_brain_nodes"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("ai_brain_versions.id"), index=True)
    node_key = Column(String(150), index=True)
    node_type = Column(String(50), index=True)
    label = Column(String(255))
    content = Column(Text)
    tags = Column(JSON, default=[])
    weight = Column(Float, default=0.7)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 14. AI Brain edges
class AIBrainEdge(Base):
    __tablename__ = "ai_brain_edges"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("ai_brain_versions.id"), index=True)
    edge_key = Column(String(150), index=True)
    source_node_key = Column(String(150), index=True)
    target_node_key = Column(String(150), index=True)
    edge_type = Column(String(50), index=True)
    weight = Column(Float, default=0.7)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 15. AI Brain ingestion jobs
class AIBrainIngestionJob(Base):
    __tablename__ = "ai_brain_ingestion_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_key = Column(String(120), unique=True, index=True)
    version_id = Column(Integer, ForeignKey("ai_brain_versions.id"), index=True)
    source_filename = Column(String(255))
    source_type = Column(String(20))  # txt | md | docx
    raw_text = Column(Text)
    status = Column(String(30), default="uploaded")  # uploaded | parsing | ready_for_review | applied | rejected
    summary = Column(JSON, default={})
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 16. AI Brain ingestion candidates
class AIBrainIngestionCandidate(Base):
    __tablename__ = "ai_brain_ingestion_candidates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("ai_brain_ingestion_jobs.id"), index=True)
    candidate_kind = Column(String(10), index=True)  # node | edge
    payload = Column(JSON)
    confidence = Column(Float, default=0.0)
    accepted = Column(Boolean, default=False)
    rejected = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 17. AI Brain ingestion files
class AIBrainIngestionFile(Base):
    __tablename__ = "ai_brain_ingestion_files"

    id = Column(Integer, primary_key=True, index=True)
    file_key = Column(String(120), unique=True, index=True)
    filename = Column(String(255))
    content_type = Column(String(120))
    raw_text = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    company_id = Column(Integer, nullable=True, index=True)
    feature = Column(String(100), nullable=False, index=True)
    slot = Column(String(20), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    audio_seconds = Column(Float, nullable=False, default=0.0)
    characters = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False)
    error_type = Column(String(100), nullable=True)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_sample = Column(Boolean, nullable=False, default=False)
    default_locale = Column(String(10), nullable=False, default="en")
    retention_days = Column(Integer, nullable=False, default=90)
    kb_version = Column(Integer, nullable=False, default=0)
    band_must_have_pct = Column(Integer, nullable=False, default=70, server_default="70")
    band_claims_pct = Column(Integer, nullable=False, default=50, server_default="50")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("company_id", "parent_id", "name", name="uq_department_sibling_name"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CompanyMember(Base):
    __tablename__ = "company_members"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_member"),
        CheckConstraint("role IN ('hr', 'manager', 'employee')", name="ck_company_member_role"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

from .models_brain import *  # noqa: F401,F403,E402
from .models_hiring import *  # noqa: F401,F403,E402
