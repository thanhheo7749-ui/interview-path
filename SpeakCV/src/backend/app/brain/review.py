"""HR review of extracted knowledge. Only HR actions (or the sample-only auto approve) publish a node.

Every function here works inside the caller's transaction and does not commit, except `auto_approve_document`
which has no request around it."""
import numpy as np
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.ai import gateway
from app.brain import contradiction, vectors
from app.brain.text import normalise_title
from app.database.models_brain import VISIBILITIES
from app.database.sql_models import Company, KbChunk, KbDocument, KbEdge, KbNode, KbNodeSource

MERGE_COSINE = 0.90
ORG_TYPES = ("company", "department")
EDITABLE = ("title", "body", "visibility", "fact_value", "fact_unit", "scope_text")
LIVE = ("draft", "published")
DEAD = ("rejected", "superseded")


class ReviewError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# ---------- reading ----------

def _document_node_ids(db: Session, company_id: int, document_id: int) -> set[int]:
    rows = (
        db.query(KbNodeSource.node_id)
        .join(KbChunk, KbNodeSource.chunk_id == KbChunk.id)
        .filter(KbChunk.document_id == document_id, KbChunk.company_id == company_id)
        .distinct()
    )
    return {row[0] for row in rows}


def _documents_of_nodes(db: Session, company_id: int, node_ids) -> set[int]:
    if not node_ids:
        return set()
    rows = (
        db.query(KbChunk.document_id)
        .join(KbNodeSource, KbNodeSource.chunk_id == KbChunk.id)
        .filter(KbNodeSource.node_id.in_(list(node_ids)), KbChunk.company_id == company_id)
        .distinct()
    )
    return {row[0] for row in rows}


def draft_nodes(db: Session, company_id: int, document_id: int | None = None) -> list[KbNode]:
    query = db.query(KbNode).filter(
        KbNode.company_id == company_id, KbNode.status == "draft", KbNode.type.notin_(ORG_TYPES)
    )
    if document_id is not None:
        query = query.filter(KbNode.id.in_(_document_node_ids(db, company_id, document_id) or {-1}))
    return query.order_by(KbNode.id).all()


def node_sources(db: Session, company_id: int, node_ids: list[int]) -> dict[int, list[dict]]:
    if not node_ids:
        return {}
    rows = (
        db.query(KbNodeSource.node_id, KbNodeSource.quote, KbChunk.page, KbDocument.title)
        .join(KbChunk, KbNodeSource.chunk_id == KbChunk.id)
        .join(KbDocument, KbChunk.document_id == KbDocument.id)
        .filter(KbNodeSource.node_id.in_(node_ids), KbChunk.company_id == company_id)
        .order_by(KbNodeSource.id)
    )
    out: dict[int, list[dict]] = {}
    for node_id, quote, page, title in rows:
        out.setdefault(node_id, []).append({"quote": quote, "page": page, "document_title": title})
    return out


def draft_edges(db: Session, company_id: int, node_ids: set[int] | None) -> list[KbEdge]:
    query = db.query(KbEdge).filter(KbEdge.company_id == company_id, KbEdge.status == "draft")
    if node_ids is not None:
        ids = list(node_ids) or [-1]
        query = query.filter(or_(KbEdge.source_node_id.in_(ids), KbEdge.target_node_id.in_(ids)))
    return query.order_by(KbEdge.id).all()


def merge_proposals(db: Session, company_id: int, drafts: list[KbNode]) -> list[dict]:
    """Best look-alike for each draft: same type, different normalised title, cosine of at least 0.90."""
    proposals = []
    for node in drafts:
        if node.embedding is None:
            continue
        candidates = [
            c for c in db.query(KbNode).filter(
                KbNode.company_id == company_id, KbNode.id != node.id, KbNode.type == node.type,
                KbNode.status.in_(LIVE), KbNode.embedding.isnot(None), KbNode.embedding_model == node.embedding_model,
                KbNode.embedding_dim == node.embedding_dim,
            ).order_by(KbNode.id)
            if normalise_title(c.title) != normalise_title(node.title)
        ]
        if not candidates:
            continue
        scores = vectors.cosine_matrix(
            vectors.decode(node.embedding), np.stack([vectors.decode(c.embedding) for c in candidates])
        )
        best = int(np.argmax(scores))
        if scores[best] >= MERGE_COSINE:
            target = candidates[best]
            proposals.append({
                "node_id": node.id, "node_title": node.title, "into_node_id": target.id,
                "into_title": target.title, "into_status": target.status, "cosine": round(float(scores[best]), 4),
            })
    return proposals


# ---------- publishing ----------

def _bump_to(db: Session, company_id: int, value: int) -> None:
    company = db.get(Company, company_id)
    if company is not None:
        company.kb_version = value


def _version(db: Session, company_id: int) -> int:
    company = db.get(Company, company_id)
    return (company.kb_version or 0) if company is not None else 0


def publish_node(db: Session, node: KbNode, user_id: int) -> None:
    """Stamp and publish one node, and bump the knowledge version. Does not commit.

    Callers that publish several nodes in one request reset the version afterwards so it moves once."""
    node.status = "published"
    node.approved_by = user_id
    node.approved_at = func.now()
    _bump_to(db, node.company_id, _version(db, node.company_id) + 1)


def settle_edges(db: Session, company_id: int, node_ids: set[int]) -> None:
    """Publish draft edges whose ends are both published; reject those with a dead end."""
    for edge in draft_edges(db, company_id, node_ids):
        ends = {
            row.id: row.status for row in db.query(KbNode.id, KbNode.status).filter(
                KbNode.company_id == company_id, KbNode.id.in_([edge.source_node_id, edge.target_node_id])
            )
        }
        statuses = [ends.get(edge.source_node_id), ends.get(edge.target_node_id)]
        if any(s is None or s in DEAD for s in statuses):
            edge.status = "rejected"
        elif all(s == "published" for s in statuses):
            edge.status = "published"


def finish_document_if_decided(db: Session, document_id: int) -> bool:
    """A reviewed document becomes published once none of its nodes is still a draft (even if all were rejected,
    so its chunks stay available). Returns True when it changed."""
    document = db.get(KbDocument, document_id)
    if document is None or document.status != "review":
        return False
    pending = _document_node_ids(db, document.company_id, document_id)
    if pending and db.query(KbNode.id).filter(
        KbNode.id.in_(list(pending)), KbNode.company_id == document.company_id, KbNode.status == "draft",
        KbNode.type.notin_(ORG_TYPES),
    ).first():
        return False
    document.status = "published"
    return True


def auto_approve_document(db: Session, document_id: int, user_id: int) -> None:
    """Sample companies only: accept every draft node and edge of a document. Commits."""
    document = db.get(KbDocument, document_id)
    if document is None:
        raise ValueError(f"Unknown document: {document_id}")
    company = db.get(Company, document.company_id)
    if company is None or not company.is_sample:
        raise PermissionError("Auto approve is only allowed for the sample company")
    start = _version(db, company.id)
    nodes = draft_nodes(db, company.id, document_id)
    for node in nodes:
        publish_node(db, node, user_id)
    db.flush()
    settle_edges(db, company.id, {n.id for n in nodes})
    finish_document_if_decided(db, document_id)
    _bump_to(db, company.id, start + 1)
    db.commit()


# ---------- deciding ----------

def _embed_nodes(db: Session, company_id: int, nodes: list[KbNode]) -> None:
    if not nodes:
        return
    result = gateway.embed([f"{n.title}\n{n.body}" for n in nodes], "document", "kb_embed", company_id)
    for node, vector in zip(nodes, result.vectors):
        node.embedding = vectors.encode(vector)
        node.embedding_model = result.model
        node.embedding_dim = result.dimension


def _apply_fields(item, node: KbNode, reembed: dict[int, KbNode]) -> None:
    for name in EDITABLE:
        value = getattr(item, name)
        if value is None:
            continue
        if name == "visibility" and value not in VISIBILITIES:
            raise ReviewError(422, f"Unknown visibility: {value}")
        if name in ("title", "body") and value != getattr(node, name):
            reembed[node.id] = node
        setattr(node, name, value)


def _load_draft(db: Session, company_id: int, node_id: int) -> KbNode:
    node = db.query(KbNode).filter(KbNode.id == node_id, KbNode.company_id == company_id).first()
    if node is None or node.type in ORG_TYPES:
        raise ReviewError(404, "Node not found")
    if node.status != "draft":
        raise ReviewError(409, "This item was already reviewed")
    return node


def _merge(db: Session, company_id: int, node: KbNode, into_id: int, user_id: int) -> None:
    target = db.query(KbNode).filter(KbNode.id == into_id, KbNode.company_id == company_id).first()
    if target is None or target.type in ORG_TYPES:
        raise ReviewError(422, "The merge target must be a node of this company")
    if target.id == node.id:
        raise ReviewError(422, "A node cannot be merged into itself")
    if target.type != node.type:
        raise ReviewError(422, "The merge target must have the same type")
    if target.status not in LIVE:
        raise ReviewError(422, "The merge target is not active")
    have = {(row[0], row[1]) for row in db.query(KbNodeSource.chunk_id, KbNodeSource.quote).filter(KbNodeSource.node_id == target.id)}
    for source in db.query(KbNodeSource).filter(KbNodeSource.node_id == node.id).all():
        if (source.chunk_id, source.quote) in have:
            db.delete(source)
        else:
            source.node_id = target.id
            have.add((source.chunk_id, source.quote))
    edges = db.query(KbEdge).filter(
        KbEdge.company_id == company_id, or_(KbEdge.source_node_id == node.id, KbEdge.target_node_id == node.id)
    ).order_by(KbEdge.id).all()
    for edge in edges:
        source_id = target.id if edge.source_node_id == node.id else edge.source_node_id
        target_id = target.id if edge.target_node_id == node.id else edge.target_node_id
        twin = db.query(KbEdge.id).filter(
            KbEdge.company_id == company_id, KbEdge.source_node_id == source_id, KbEdge.target_node_id == target_id,
            KbEdge.relation == edge.relation, KbEdge.id != edge.id,
        ).first()
        if source_id == target_id or twin is not None:
            db.delete(edge)
        else:
            edge.source_node_id, edge.target_node_id = source_id, target_id
        db.flush()
    node.status = "rejected"
    contradiction.on_node_rejected(db, node.id)


def apply_decisions(db: Session, company_id: int, user_id: int, items) -> None:
    """Apply review items in order. Raises ReviewError; the caller rolls back so a bad item changes nothing."""
    start = _version(db, company_id)
    touched: set[int] = set()
    documents: set[int] = set()
    reembed: dict[int, KbNode] = {}
    explicit_documents: list[int] = []
    changed = False

    for item in items:
        if item.action == "publish_document":
            explicit_documents.append(item.document_id)
            continue
        node = _load_draft(db, company_id, item.node_id)
        documents |= _documents_of_nodes(db, company_id, {node.id})
        touched.add(node.id)
        if item.action == "edit":
            _apply_fields(item, node, reembed)
        elif item.action == "accept":
            _apply_fields(item, node, reembed)
            publish_node(db, node, user_id)
            changed = True
        elif item.action == "reject":
            node.status = "rejected"
            contradiction.on_node_rejected(db, node.id)
            changed = True
        elif item.action == "merge":
            _merge(db, company_id, node, item.into_node_id, user_id)
            touched.add(item.into_node_id)
            changed = True
        db.flush()

    _embed_nodes(db, company_id, list(reembed.values()))
    db.flush()
    settle_edges(db, company_id, touched)
    db.flush()
    for document_id in documents:
        finish_document_if_decided(db, document_id)
    for document_id in explicit_documents:
        document = db.query(KbDocument).filter(
            KbDocument.id == document_id, KbDocument.company_id == company_id
        ).first()
        if document is None:
            raise ReviewError(404, "Document not found")
        if document_id in documents and document.status == "published":
            continue
        if document.status != "review" or not finish_document_if_decided(db, document_id):
            raise ReviewError(409, "This document still has items to review or is not waiting for review")
        changed = True
    if changed or reembed:
        _bump_to(db, company_id, start + 1)
