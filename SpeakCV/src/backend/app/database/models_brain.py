from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.sql import false, func

from .database import Base

VISIBILITIES = ("public", "internal", "confidential")  # from most to least open
NODE_TYPES = ("company", "department", "role", "requirement", "skill", "value", "behavior",
              "policy", "process", "fact", "private_note")
EXTRACTABLE_NODE_TYPES = tuple(t for t in NODE_TYPES if t not in {"company", "department"})
RELATIONS = ("part_of", "has_role", "requires", "holds", "shown_by", "expects", "applies_to", "states", "has_note")
FACT_KINDS = ("number", "date", "boolean")
DEFAULT_VISIBILITY_BY_TYPE = {
    "company": "public", "department": "public", "role": "public", "requirement": "public", "skill": "public",
    "value": "public", "behavior": "public", "policy": "internal", "process": "internal", "fact": "internal",
    "private_note": "confidential",
}



def stricter_layer(a: str, b: str) -> str:
    return a if VISIBILITIES.index(a) >= VISIBILITIES.index(b) else b


__all__ = [
    "stricter_layer", "VISIBILITIES", "NODE_TYPES", "RELATIONS", "EXTRACTABLE_NODE_TYPES", "FACT_KINDS", "DEFAULT_VISIBILITY_BY_TYPE",
    "KbDocument", "KbIngestionJob", "KbChunk", "KbNode", "KbNodeSource", "KbEdge", "KbConflict", "AssistantQuestion",
]


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    language = Column(String(10), nullable=False)
    source_type = Column(String(20), nullable=False, default="upload")  # upload | intake
    file_path = Column(String(500), nullable=True)
    visibility = Column(String(20), nullable=False)
    effective_date = Column(Date, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="processing")  # processing | review | published | failed | withdrawn
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KbIngestionJob(Base):
    __tablename__ = "kb_ingestion_jobs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="queued")  # queued | running | review | failed | done
    progress = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    dropped_items = Column(Integer, nullable=False, default=0)
    failed_chunks = Column(Integer, nullable=False, default=0)  # chunks in failed_chunk_ids, plus 1 for a failed check
    failed_chunk_ids = Column(JSON, nullable=False, default=list)
    contradiction_check_failed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    page = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_dim = Column(Integer, nullable=True)


class KbNode(Base):
    __tablename__ = "kb_nodes"
    __table_args__ = (Index("ix_kb_nodes_company_status", "company_id", "status"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    type = Column(String(20), nullable=False)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False, default="")
    language = Column(String(10), nullable=False)
    visibility = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft | published | rejected | superseded
    effective_date = Column(Date, nullable=True)
    fact_kind = Column(String(20), nullable=True)
    fact_value = Column(String(255), nullable=True)
    fact_unit = Column(String(50), nullable=True)
    scope_text = Column(String(500), nullable=True)
    embedding = Column(LargeBinary, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_dim = Column(Integer, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    # Set by the discrimination guard (app.bridges.discrimination): a category, or "unchecked" when the AI check failed.
    guard_category = Column(String(30), nullable=True)
    guard_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KbNodeSource(Base):
    __tablename__ = "kb_node_sources"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("kb_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("kb_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    quote = Column(Text, nullable=False)
    # HR changed the claim this source was extracted for, so its chunk still says the old value and no audience reads it.
    stale = Column(Boolean, nullable=False, default=False, server_default=false())


class KbEdge(Base):
    __tablename__ = "kb_edges"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(Integer, ForeignKey("kb_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(Integer, ForeignKey("kb_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relation = Column(String(20), nullable=False)
    must_have = Column(Boolean, nullable=True)
    status = Column(String(20), nullable=False, default="draft")  # draft | published | rejected


class KbConflict(Base):
    __tablename__ = "kb_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    node_a_id = Column(Integer, ForeignKey("kb_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    node_b_id = Column(Integer, ForeignKey("kb_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="open")  # open | resolved | dismissed
    resolution = Column(String(20), nullable=True)  # a | b | different_scope | node_rejected | node_superseded | edit_resolved
    resolved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AssistantQuestion(Base):
    __tablename__ = "assistant_questions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    audience = Column(String(20), nullable=False)
    question = Column(Text, nullable=False)
    language = Column(String(10), nullable=False)
    answered = Column(Boolean, nullable=False)
    state = Column(String(20), nullable=True)  # answered, conflict, not_found or failed; NULL on older rows
    top_score = Column(String(32), nullable=True)
    embedding = Column(LargeBinary, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
