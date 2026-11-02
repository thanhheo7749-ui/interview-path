"""HR review of extracted knowledge. Only HR actions (or the sample-only auto approve) publish a node.

Every function here works inside the caller's transaction and does not commit, except `auto_approve_document`
which has no request around it, `recheck_edited_facts` which runs after the caller's commit, and `apply_decisions`
which ends the transaction before its AI calls."""
from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.types import AIError
from app.brain import contradiction, retriever, vectors
from app.brain.text import normalise_title
from app.bridges import discrimination
from app.database.models_brain import VISIBILITIES
from app.database.sql_models import Company, KbChunk, KbDocument, KbEdge, KbIngestionJob, KbNode, KbNodeSource

MERGE_COSINE = 0.90
ORG_TYPES = ("company", "department")
EDITABLE = ("title", "body", "visibility", "fact_value", "fact_unit", "scope_text")
# A change to what a fact says: it looks for contradictions again, and its embedded text changes.
FACT_CHECKED = ("title", "body", "fact_value", "fact_unit", "scope_text")
# A change to the claim itself: a pair HR dismissed before no longer answers for it.
FACT_CLAIM = ("fact_value", "fact_unit", "scope_text")
LIVE = ("draft", "published")
DEAD = ("rejected", "superseded")
# What each review action may be applied to. Published knowledge can be corrected or retracted, not published again.
ACTION_STATUSES = {"accept": ("draft",), "merge": ("draft",), "edit": LIVE, "reject": LIVE}
UNPUBLISHABLE = ("review", "published")
ACTIVE_JOB = ("queued", "running")
CHANGED_DURING_CHECK = "This item changed while it was being checked. Please try again."


class ReviewError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# ---------- reading ----------

def document_node_ids(db: Session, company_id: int, document_id: int) -> set[int]:
    rows = (
        db.query(KbNodeSource.node_id)
        .join(KbChunk, KbNodeSource.chunk_id == KbChunk.id)
        .filter(KbChunk.document_id == document_id, KbChunk.company_id == company_id)
        .distinct()
    )
    return {row[0] for row in rows}


def documents_of_nodes(db: Session, company_id: int, node_ids) -> set[int]:
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
        query = query.filter(KbNode.id.in_(document_node_ids(db, company_id, document_id) or {-1}))
    return query.order_by(KbNode.id).all()


def node_sources(db: Session, company_id: int, node_ids: list[int]) -> dict[int, list[dict]]:
    if not node_ids:
        return {}
    rows = (
        db.query(KbNodeSource.node_id, KbNodeSource.quote, KbChunk.page, KbDocument.title, KbDocument.effective_date)
        .join(KbChunk, KbNodeSource.chunk_id == KbChunk.id)
        .join(KbDocument, KbChunk.document_id == KbDocument.id)
        .filter(KbNodeSource.node_id.in_(node_ids), KbChunk.company_id == company_id)
        .order_by(KbNodeSource.id)
    )
    out: dict[int, list[dict]] = {}
    for node_id, quote, page, title, effective_date in rows:
        out.setdefault(node_id, []).append({
            "quote": quote, "page": page, "document_title": title,
            "effective_date": effective_date.isoformat() if effective_date else None,
        })
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

def publish_node(db: Session, node: KbNode, user_id: int) -> None:
    """Stamp and publish one node. Does not commit. The caller moves the knowledge version, once per request."""
    node.status = "published"
    node.approved_by = user_id
    node.approved_at = func.now()


def settle_edges(db: Session, company_id: int, node_ids: set[int]) -> None:
    """Publish draft edges whose ends are both published; reject draft or published edges with a dead end."""
    ids = list(node_ids) or [-1]
    edges = db.query(KbEdge).filter(
        KbEdge.company_id == company_id, KbEdge.status.in_(("draft", "published")),
        or_(KbEdge.source_node_id.in_(ids), KbEdge.target_node_id.in_(ids)),
    ).order_by(KbEdge.id).all()
    for edge in edges:
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


def has_drafts(db: Session, document: KbDocument) -> bool:
    pending = document_node_ids(db, document.company_id, document.id)
    return bool(pending) and db.query(KbNode.id).filter(
        KbNode.id.in_(list(pending)), KbNode.company_id == document.company_id, KbNode.status == "draft",
        KbNode.type.notin_(ORG_TYPES),
    ).first() is not None


def finish_document_if_decided(db: Session, document_id: int) -> bool:
    """A reviewed document becomes published once none of its nodes is still a draft (even if all were rejected,
    so its chunks stay available). Returns True when it changed."""
    document = db.get(KbDocument, document_id)
    if document is None or document.status != "review" or has_drafts(db, document):
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
    # A node held by the discrimination guard (flagged, or not checked) waits for HR.
    nodes = [n for n in draft_nodes(db, company.id, document_id) if n.guard_category is None]
    for node in nodes:
        publish_node(db, node, user_id)
    db.flush()
    settle_edges(db, company.id, {n.id for n in nodes})
    finish_document_if_decided(db, document_id)
    contradiction.bump_kb_version(db, company.id)
    db.commit()


def unpublish_document(db: Session, company_id: int, document_id: int) -> dict:
    """Withdraw a document. Its chunks leave retrieval, which requires a published document. Nodes that rest on it
    alone are rejected; nodes with other sources stay and stop citing it. Does not commit."""
    document = (
        db.query(KbDocument)
        .filter(KbDocument.id == document_id, KbDocument.company_id == company_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if document is None:
        raise ReviewError(404, "Document not found")
    if document.status not in UNPUBLISHABLE:
        raise ReviewError(409, "Only a document in review or published can be unpublished")
    if db.query(KbIngestionJob.id).filter(
        KbIngestionJob.document_id == document_id, KbIngestionJob.status.in_(ACTIVE_JOB)
    ).with_for_update().first():
        raise ReviewError(409, "This document has a job in progress")

    node_ids = document_node_ids(db, company_id, document_id)
    nodes = db.query(KbNode).filter(KbNode.id.in_(list(node_ids) or [-1]), KbNode.status.in_(LIVE)).order_by(KbNode.id).all()
    chunk_ids = select(KbChunk.id).where(KbChunk.document_id == document_id)
    rejected: set[int] = set()
    for node in nodes:
        elsewhere = (
            db.query(KbNodeSource.id)
            .join(KbChunk, KbNodeSource.chunk_id == KbChunk.id)
            .filter(KbNodeSource.node_id == node.id, KbChunk.document_id != document_id)
            .first()
        )
        if elsewhere:
            db.query(KbNodeSource).filter(
                KbNodeSource.node_id == node.id, KbNodeSource.chunk_id.in_(chunk_ids)
            ).delete(synchronize_session=False)
        else:
            node.status = "rejected"
            contradiction.on_node_rejected(db, node.id)
            rejected.add(node.id)
    document.status = "withdrawn"
    db.flush()
    settle_edges(db, company_id, rejected)
    contradiction.bump_kb_version(db, company_id)
    return {"rejected_nodes": len(rejected), "kept_nodes": len(nodes) - len(rejected)}


# ---------- deciding ----------

@dataclass
class _AiAnswers:
    """What the AI said about the texts a request will leave, keyed by those texts."""

    guards: dict[tuple[str, str], discrimination.GuardResult | None] = field(default_factory=dict)
    embeddings: dict[str, list[float]] = field(default_factory=dict)
    model: str | None = None
    dimension: int | None = None

    def stored_guard(self, node) -> discrimination.GuardResult | None:
        try:
            return self.guards[(node.title, node.body)]
        except KeyError:
            raise ReviewError(409, CHANGED_DURING_CHECK) from None


def _embed_nodes(nodes: list[KbNode], answers: _AiAnswers) -> None:
    for node in nodes:
        vector = answers.embeddings.get(retriever.node_text(node))
        if vector is None:
            raise ReviewError(409, CHANGED_DURING_CHECK)
        node.embedding = vectors.encode(vector)
        node.embedding_model = answers.model
        node.embedding_dim = answers.dimension


def _apply_fields(item, node: KbNode, reembed: dict[int, KbNode], edited_facts: dict[int, KbNode],
                 changed_claims: set[int]) -> None:
    for name in EDITABLE:
        value = getattr(item, name)
        if value is None:
            continue
        if name == "visibility" and value not in VISIBILITIES:
            raise ReviewError(422, f"Unknown visibility: {value}")
        changed = value != getattr(node, name)
        if changed and (name in ("title", "body") or (node.fact_kind and name in FACT_CHECKED)):
            reembed[node.id] = node
        if changed and name in FACT_CHECKED and node.fact_kind:
            edited_facts[node.id] = node
        if changed and name in FACT_CLAIM and node.fact_kind:
            changed_claims.add(node.id)
        setattr(node, name, value)


def _guard(node: KbNode, item, before: tuple[str, str], publishing: bool, check) -> None:
    """The discrimination guard for a node that is edited or published. Raises ReviewError(409) when the node would
    become, or stay, a published requirement that asks for a protected trait. Edits are re-checked; unchanged text keeps
    its flag, so asking again cannot draw a different answer from the classifier."""
    if node.type not in discrimination.GUARDED_TYPES:
        return
    held = node.guard_category
    if (node.title, node.body) == before:
        if held is None or not publishing or node.status == "published":
            return
        if held == discrimination.UNCHECKED:
            if not getattr(item, "confirm_unchecked", False):
                raise ReviewError(409, "The automatic discrimination check did not run for this item. "
                                       "Edit it or confirm that it was reviewed.")
            node.guard_category = node.guard_reason = None
            return
        raise ReviewError(409, f"Blocked ({held}): {node.guard_reason}")
    result = check(node)
    node.guard_category = result.category if result else None
    node.guard_reason = result.reason if result else None
    if result is not None and not result.unchecked and publishing:
        raise ReviewError(409, f"Blocked ({result.category}): {result.reason}")


def _load_for(db: Session, company_id: int, node_id: int, action: str) -> KbNode:
    node = db.query(KbNode).filter(KbNode.id == node_id, KbNode.company_id == company_id).first()
    if node is None or node.type in ORG_TYPES:
        raise ReviewError(404, "Node not found")
    if node.status not in ACTION_STATUSES[action]:
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


def _ask_ai_first(db: Session, company_id: int, items) -> _AiAnswers:
    """Get every AI answer apply_decisions will need before it writes, because a vendor call must not hold locks.

    Ends the transaction, then plays the items on plain copies of their nodes to find the text each one leaves. It stops
    at an item that will be refused: the request then needs no embedding. apply_decisions reads the nodes again, and
    refuses an item whose text has no answer here, because another request changed it during the calls."""
    node_ids = {item.node_id for item in items if item.action != "publish_document"}
    columns = (*EDITABLE, "id", "type", "status", "fact_kind", "guard_category", "guard_reason")
    copies = {
        node.id: SimpleNamespace(**{name: getattr(node, name) for name in columns})
        for node in db.query(KbNode).filter(KbNode.id.in_(node_ids), KbNode.company_id == company_id)
    }
    db.commit()

    answers = _AiAnswers()

    def ask_guard(node) -> discrimination.GuardResult | None:
        key = (node.title, node.body)
        if key not in answers.guards:
            answers.guards[key] = discrimination.check(f"{node.title}\n{node.body}", company_id)
        return answers.guards[key]

    reembed: dict[int, SimpleNamespace] = {}
    for item in items:
        if item.action == "publish_document":
            continue
        node = copies.get(item.node_id)
        if node is None or node.type in ORG_TYPES or node.status not in ACTION_STATUSES[item.action]:
            return answers
        if item.action in ("reject", "merge"):
            node.status = "rejected"
            continue
        before = (node.title, node.body)
        try:
            _apply_fields(item, node, reembed, {}, set())
            _guard(node, item, before, item.action == "accept" or node.status == "published", ask_guard)
        except ReviewError:
            return answers
        if item.action == "accept":
            node.status = "published"
    if reembed:
        texts = list(dict.fromkeys(retriever.node_text(node) for node in reembed.values()))
        result = gateway.embed(texts, "document", "kb_embed", company_id)
        answers.embeddings = dict(zip(texts, result.vectors))
        answers.model, answers.dimension = result.model, result.dimension
    return answers


def apply_decisions(db: Session, company_id: int, user_id: int, items) -> dict[int, bool]:
    """Apply review items in order. Raises ReviewError; the caller rolls back so a bad item changes nothing.

    Commits once before writing anything, to end the transaction before the AI calls, so the caller must have nothing
    pending that it may yet discard. Returns the live facts this request edited, each with whether its value, unit or
    scope changed. The caller commits, then passes them to recheck_edited_facts."""
    answers = _ask_ai_first(db, company_id, items)
    touched: set[int] = set()
    documents: set[int] = set()
    reembed: dict[int, KbNode] = {}
    edited_facts: dict[int, KbNode] = {}
    changed_claims: set[int] = set()
    explicit_documents: list[int] = []
    changed = False

    for item in items:
        if item.action == "publish_document":
            explicit_documents.append(item.document_id)
            continue
        node = _load_for(db, company_id, item.node_id, item.action)
        documents |= documents_of_nodes(db, company_id, {node.id})
        touched.add(node.id)
        if item.action == "edit":
            before = (node.title, node.body)
            _apply_fields(item, node, reembed, edited_facts, changed_claims)
            _guard(node, item, before, node.status == "published", answers.stored_guard)
            changed = changed or node.status == "published"
        elif item.action == "accept":
            before = (node.title, node.body)
            _apply_fields(item, node, reembed, edited_facts, changed_claims)
            _guard(node, item, before, True, answers.stored_guard)
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

    # After every item, so an edit of both sides in one request is compared on the final values.
    for node in edited_facts.values():
        if node.status in LIVE and contradiction.close_conflicts_settled_by_edit(db, node, user_id):
            changed = True
    _embed_nodes(list(reembed.values()), answers)
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
    if changed or reembed or edited_facts:
        contradiction.bump_kb_version(db, company_id)
    return {node.id: node.id in changed_claims for node in edited_facts.values() if node.status in LIVE}


def recheck_edited_facts(db: Session, company_id: int, edited: dict[int, bool]) -> list[str]:
    """Look for new contradictions after an edit is committed, so a failed check cannot undo it. Returns warnings.

    The request has already moved kb_version, so opening a conflict here does not move it again. A pair HR dismissed
    is looked at again only when the fact's value, unit or scope changed: the dismissal answered for the old claim."""
    warnings = []
    for node_id, claim_changed in edited.items():
        try:
            contradiction.check_new_facts(db, company_id, [node_id], bump_version=False, recheck_dismissed=claim_changed)
        except AIError:
            db.rollback()
            warnings.append(f"The edit to node {node_id} was saved, but its contradiction check did not finish.")
    return warnings
