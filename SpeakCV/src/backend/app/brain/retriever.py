"""The only module that reads kb_* tables for AI context.

Permission filtering happens in SQL through app.brain.audience. Whatever a query did not return
cannot reach a prompt. The vector cache holds no text and is only ever read by ids a filtered
query has just returned, so it cannot widen what an audience sees.
"""
import threading
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.config import get_config
from app.brain import audience as aud
from app.brain import vectors
from app.brain.audience import Audience
from app.brain.text import keyword_scores, tokenise
from app.database.sql_models import Company, KbChunk, KbConflict, KbDocument, KbEdge, KbNode, KbNodeSource

VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
MAX_HOPS = 2
HOP_DECAY = 0.5
NOT_SHARED_TITLE = "Company document (not shared)"
REQUIREMENT_TYPES = ("requirement", "skill")


@dataclass(frozen=True)
class Citation:
    title: str
    page: int | None
    effective_date: date | None
    shared: bool


NOT_SHARED = Citation(NOT_SHARED_TITLE, None, None, False)


@dataclass(frozen=True)
class ContextItem:
    ref: str
    kind: str
    text: str
    score: float
    node_type: str | None
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class ContextBundle:
    items: tuple[ContextItem, ...]
    best_score: float
    conflicted_refs: frozenset[str]


@dataclass(frozen=True)
class RoleRequirement:
    node_id: int
    type: str
    title: str
    body: str
    must_have: bool
    visibility: str


@dataclass(frozen=True)
class ProfileItem:
    node_id: int
    type: str
    title: str
    body: str


@dataclass(frozen=True)
class RoleProfile:
    role_node_id: int
    title: str
    body: str
    department_id: int | None
    requirements: tuple[RoleRequirement, ...]
    values: tuple[ProfileItem, ...]
    behaviors: tuple[ProfileItem, ...]


class NoEmbeddingsError(RuntimeError):
    pass


# (company_id, model, kb_version, "node" | "chunk") -> {row id -> vector}. Never text.
_vector_cache: dict[tuple[int, str, int, str], dict[int, np.ndarray]] = {}
_cache_lock = threading.Lock()


def clear_vector_cache() -> None:
    with _cache_lock:
        _vector_cache.clear()


def _cache_entry(company_id: int, model: str, version: int, kind: str) -> dict[int, np.ndarray]:
    with _cache_lock:
        for key in [key for key in _vector_cache if key[0] == company_id and key[2] != version]:
            del _vector_cache[key]
        return _vector_cache.setdefault((company_id, model, version, kind), {})


def _load_vectors(cached: dict[int, np.ndarray], wanted: list[int], fetch_blobs) -> dict[int, np.ndarray]:
    """Return vectors for exactly the wanted ids, which a filtered query has just returned."""
    missing = [row_id for row_id in wanted if row_id not in cached]
    if missing:
        for row_id, blob in fetch_blobs(missing):
            if blob is not None:
                cached[row_id] = vectors.decode(blob)
    return {row_id: cached[row_id] for row_id in wanted if row_id in cached}


def _allowed_nodes(db: Session, audience: Audience):
    return (
        db.query(KbNode.id, KbNode.title, KbNode.body, KbNode.type, KbNode.visibility, KbNode.department_id,
                 KbNode.embedding_model)
        .filter(aud.node_filter(audience))
        .order_by(KbNode.id)
        .all()
    )


def _allowed_chunks_query(db: Session, audience: Audience, *columns):
    return (
        db.query(*columns)
        .join(KbDocument, KbChunk.document_id == KbDocument.id)
        .filter(aud.chunk_filter(audience))
    )


def _allowed_chunks(db: Session, audience: Audience):
    return (
        _allowed_chunks_query(db, audience, KbChunk.id, KbChunk.text, KbChunk.page, KbChunk.embedding_model,
                              KbDocument.title.label("document_title"), KbDocument.effective_date)
        .order_by(KbChunk.id)
        .all()
    )


def _visible_edges(db: Session, audience: Audience) -> list[KbEdge]:
    visible = aud.visible_node_ids_query(db, audience)
    return (
        db.query(KbEdge)
        .filter(
            KbEdge.company_id == audience.company_id,
            KbEdge.status == "published",
            KbEdge.source_node_id.in_(visible),
            KbEdge.target_node_id.in_(visible),
        )
        .order_by(KbEdge.id)
        .all()
    )


def _node_text(row) -> str:
    return f"{row.title}\n{row.body}" if row.body else row.title


def search(db: Session, audience: Audience, query: str, top_k: int = 8, char_budget: int = 6000,
           *, query_vector=None) -> ContextBundle:
    model = get_config().slot("embedding").model
    if query_vector is None:
        query_vector = gateway.embed([query], kind="query", feature="kb_query_embed",
                                     company_id=audience.company_id).vectors[0]
    query_array = np.asarray(query_vector, dtype="<f4")

    # Read before the rows: if a re-embed commits in between, new vectors under the old version are
    # dropped at the next search, while old vectors under the new version would stay until the next change.
    version = db.query(Company.kb_version).filter(Company.id == audience.company_id).scalar() or 0
    nodes = {row.id: row for row in _allowed_nodes(db, audience)}
    chunks = {row.id: row for row in _allowed_chunks(db, audience)}
    if not nodes and not chunks:
        return ContextBundle((), 0.0, frozenset())

    node_vectors = _load_vectors(
        _cache_entry(audience.company_id, model, version, "node"),
        [row.id for row in nodes.values() if row.embedding_model == model],
        lambda ids: db.query(KbNode.id, KbNode.embedding)
        .filter(aud.node_filter(audience), KbNode.embedding_model == model, KbNode.id.in_(ids)).all(),
    )
    chunk_vectors = _load_vectors(
        _cache_entry(audience.company_id, model, version, "chunk"),
        [row.id for row in chunks.values() if row.embedding_model == model],
        lambda ids: _allowed_chunks_query(db, audience, KbChunk.id, KbChunk.embedding)
        .filter(KbChunk.embedding_model == model, KbChunk.id.in_(ids)).all(),
    )
    comparable = [(f"n{row_id}", vector) for row_id, vector in node_vectors.items() if vector.size == query_array.size]
    comparable += [(f"c{row_id}", vector) for row_id, vector in chunk_vectors.items() if vector.size == query_array.size]
    if not comparable:
        # Rows never embedded, such as company and department nodes, are not candidates and not a mismatch.
        if any(row.embedding_model is not None for row in [*nodes.values(), *chunks.values()]):
            raise NoEmbeddingsError(f"No embeddings for model {model}. Run make reembed.")
        return ContextBundle((), 0.0, frozenset())

    texts = {f"n{row.id}": _node_text(row) for row in nodes.values()}
    texts.update({f"c{row.id}": row.text for row in chunks.values()})

    refs = [ref for ref, _ in comparable]
    cosine = vectors.cosine_matrix(query_array, np.stack([vector for _, vector in comparable]))
    keyword = keyword_scores(tokenise(query), [tokenise(texts[ref]) for ref in refs])
    combined = {ref: float(VECTOR_WEIGHT * cosine[i] + KEYWORD_WEIGHT * keyword[i]) for i, ref in enumerate(refs)}

    top = sorted(refs, key=lambda ref: (-combined[ref], ref))[:max(top_k, 0)]
    scores = {ref: combined[ref] for ref in top}
    seeds = {int(ref[1:]): scores[ref] for ref in top if ref.startswith("n")}
    for node_id, score in _expand(db, audience, seeds, set(nodes)).items():
        ref = f"n{node_id}"
        scores[ref] = max(scores.get(ref, score), score)

    ordered = sorted(scores, key=lambda ref: (-scores[ref], ref))
    selected = _within_budget(ordered, texts, char_budget)
    node_ids = [int(ref[1:]) for ref in selected if ref.startswith("n")]
    node_citations = _node_citations(db, audience, node_ids)

    items = []
    for ref, text in selected.items():
        row_id = int(ref[1:])
        if ref.startswith("n"):
            items.append(ContextItem(ref, "node", text, scores[ref], nodes[row_id].type, node_citations.get(row_id, ())))
        else:
            row = chunks[row_id]
            citation = Citation(row.document_title, row.page, row.effective_date, True)
            items.append(ContextItem(ref, "chunk", text, scores[ref], None, (citation,)))

    return ContextBundle(
        items=tuple(items),
        best_score=items[0].score if items else 0.0,
        conflicted_refs=_conflicted_refs(db, audience, node_ids),
    )


def _expand(db: Session, audience: Audience, seeds: dict[int, float], allowed: set[int]) -> dict[int, float]:
    """Neighbours within MAX_HOPS of a seed, through allowed nodes only, each with its best decayed score."""
    relevant = {node_id: score for node_id, score in seeds.items() if score > 0}
    if not relevant:
        return {}
    neighbours: dict[int, set[int]] = {}
    for edge in _visible_edges(db, audience):
        if edge.source_node_id in allowed and edge.target_node_id in allowed:
            neighbours.setdefault(edge.source_node_id, set()).add(edge.target_node_id)
            neighbours.setdefault(edge.target_node_id, set()).add(edge.source_node_id)

    found: dict[int, float] = {}
    for seed, seed_score in relevant.items():
        seen = {seed}
        frontier = {seed}
        for hop in range(1, MAX_HOPS + 1):
            frontier = {n for current in frontier for n in neighbours.get(current, ())} - seen
            seen |= frontier
            score = seed_score * HOP_DECAY ** hop
            for node_id in frontier:
                found[node_id] = max(found.get(node_id, score), score)
    return found


def _within_budget(ordered: list[str], texts: dict[str, str], char_budget: int) -> dict[str, str]:
    """Add items by rank until the budget is reached. The first is always kept, truncated to the budget."""
    selected: dict[str, str] = {}
    used = 0
    for ref in ordered:
        text = texts[ref]
        if not selected:
            text = text[:max(char_budget, 0)]
        elif used + len(text) > char_budget:
            break
        selected[ref] = text
        used += len(text)
    return selected


def _node_citations(db: Session, audience: Audience, node_ids: list[int]) -> dict[int, tuple[Citation, ...]]:
    if not node_ids:
        return {}
    sources = (
        db.query(KbNodeSource.node_id, KbChunk.document_id, KbChunk.page)
        .join(KbChunk, KbNodeSource.chunk_id == KbChunk.id)
        .filter(KbNodeSource.node_id.in_(node_ids))
        .order_by(KbNodeSource.id)
        .all()
    )
    # A source is judged on company and layer only: a published node may outlive its document's status.
    # Titles of documents that fail this are never loaded.
    shared = {
        row.id: row
        for row in db.query(KbDocument.id, KbDocument.title, KbDocument.effective_date).filter(
            KbDocument.id.in_(list({source.document_id for source in sources})),
            KbDocument.company_id == audience.company_id,
            aud._layer_filter(audience, KbDocument.visibility, KbDocument.department_id),
        )
    }
    citations: dict[int, dict[Citation, None]] = {}
    for source in sources:
        document = shared.get(source.document_id)
        citation = Citation(document.title, source.page, document.effective_date, True) if document else NOT_SHARED
        citations.setdefault(source.node_id, {})[citation] = None
    return {node_id: tuple(found) for node_id, found in citations.items()}


def _conflicted_refs(db: Session, audience: Audience, node_ids: list[int]) -> frozenset[str]:
    if not node_ids:
        return frozenset()
    rows = (
        db.query(KbConflict.node_a_id, KbConflict.node_b_id)
        .filter(
            KbConflict.company_id == audience.company_id,
            KbConflict.status == "open",
            or_(KbConflict.node_a_id.in_(node_ids), KbConflict.node_b_id.in_(node_ids)),
        )
        .all()
    )
    in_conflict = {node_id for row in rows for node_id in row}
    return frozenset(f"n{node_id}" for node_id in node_ids if node_id in in_conflict)


def visible_conflicts(db: Session, audience: Audience, refs) -> dict[str, tuple[Citation, ...]]:
    """For each ref in an open conflict whose two sides this audience may both read, the citations of both sides.

    conflicted_refs also flags a node whose other side is hidden. Such a conflict is left out here, so that
    neither its existence nor its source can reach this audience.
    """
    node_ids = {int(ref[1:]) for ref in refs if ref.startswith("n")}
    if not node_ids:
        return {}
    visible = aud.visible_node_ids_query(db, audience)
    rows = (
        db.query(KbConflict.node_a_id, KbConflict.node_b_id)
        .filter(
            KbConflict.company_id == audience.company_id,
            KbConflict.status == "open",
            KbConflict.node_a_id.in_(visible),
            KbConflict.node_b_id.in_(visible),
            or_(KbConflict.node_a_id.in_(node_ids), KbConflict.node_b_id.in_(node_ids)),
        )
        .order_by(KbConflict.id)
        .all()
    )
    citations = _node_citations(db, audience, list({node_id for row in rows for node_id in row}))
    found: dict[str, dict[Citation, None]] = {}
    for node_a, node_b in rows:
        both = dict.fromkeys((*citations.get(node_a, ()), *citations.get(node_b, ())))
        for node_id in {node_a, node_b} & node_ids:
            found.setdefault(f"n{node_id}", {}).update(both)
    return {ref: tuple(sources) for ref, sources in found.items()}


def role_profile(db: Session, audience: Audience, role_node_id: int) -> RoleProfile | None:
    nodes = {row.id: row for row in _allowed_nodes(db, audience)}
    role = nodes.get(role_node_id)
    if role is None or role.type != "role":
        return None

    edges = _visible_edges(db, audience)

    def targets(sources: set[int], relation: str, types: tuple[str, ...]) -> set[int]:
        return {
            edge.target_node_id
            for edge in edges
            if edge.relation == relation and edge.source_node_id in sources
            and edge.target_node_id in nodes and nodes[edge.target_node_id].type in types
        }

    must_have: dict[int, bool] = {}
    for edge in edges:
        if edge.relation == "requires" and edge.source_node_id == role_node_id:
            target = nodes.get(edge.target_node_id)
            if target is not None and target.type in REQUIREMENT_TYPES:
                must_have[target.id] = must_have.get(target.id, False) or bool(edge.must_have)

    holders = {
        edge.source_node_id
        for edge in edges
        if edge.relation == "has_role" and edge.target_node_id == role_node_id
        and edge.source_node_id in nodes and nodes[edge.source_node_id].type == "department"
    }
    frontier = holders
    while frontier:
        frontier = targets(frontier, "part_of", ("department", "company")) - holders
        holders = holders | frontier

    value_ids = targets(holders, "holds", ("value",))
    behavior_ids = targets({role_node_id}, "expects", ("behavior",)) | targets(value_ids, "shown_by", ("behavior",))

    requirements = sorted(must_have, key=lambda node_id: (not must_have[node_id], nodes[node_id].title, node_id))
    return RoleProfile(
        role_node_id=role.id,
        title=role.title,
        body=role.body,
        department_id=role.department_id,
        requirements=tuple(
            RoleRequirement(node_id, nodes[node_id].type, nodes[node_id].title, nodes[node_id].body,
                            must_have[node_id], nodes[node_id].visibility)
            for node_id in requirements
        ),
        values=_profile_items(nodes, value_ids),
        behaviors=_profile_items(nodes, behavior_ids),
    )


def _profile_items(nodes: dict, node_ids: set[int]) -> tuple[ProfileItem, ...]:
    ordered = sorted(node_ids, key=lambda node_id: (nodes[node_id].title, node_id))
    return tuple(ProfileItem(n, nodes[n].type, nodes[n].title, nodes[n].body) for n in ordered)


def visible_graph(db: Session, audience: Audience) -> tuple[list[KbNode], list[KbEdge]]:
    nodes = db.query(KbNode).filter(aud.node_filter(audience)).order_by(KbNode.id).all()
    return nodes, _visible_edges(db, audience)
