"""Document ingestion. Every extracted item is verified against its source text and starts as a draft."""
import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.types import AIError
from app.brain import contradiction, org_sync, retriever, review, vectors
from app.brain.chunking import chunk_pages
from app.brain.extraction import ExtractedEdge, ExtractedNode, ExtractionResult, extract_chunk
from app.brain.text import guess_language, normalise_title, quote_in, shares_span, verified_quote
from app.bridges import discrimination
from app.core import storage
from app.core.text_extract import NoExtractableText, extract_pages
from app.database.database import SessionLocal
from app.database.models_brain import DEFAULT_VISIBILITY_BY_TYPE, stricter_layer
from app.database.sql_models import KbChunk, KbDocument, KbEdge, KbIngestionJob, KbNode, KbNodeSource

logger = logging.getLogger(__name__)

EMBED_BATCH = 64
KNOWN_TITLE_CAP = 200
GENERIC_ERROR = "Processing this document failed. Please retry."
INTERRUPTED = "Interrupted by a restart. Retry to run it again."
INACTIVE = ("rejected", "superseded")
LANGUAGE_SAMPLE_CHARS = 4000
MAX_TEXT_COLUMN_BYTES = 65535  # MySQL TEXT
ALWAYS_BOUNDED = ("title",)
FACT_BOUNDED = ("fact_value", "fact_unit", "scope_text")
# Spec section 2. Extraction cannot produce part_of.
RELATION_ENDS = {
    "has_role": ({"department"}, {"role"}),
    "requires": ({"role"}, {"requirement", "skill"}),
    "holds": ({"company", "department"}, {"value"}),
    "shown_by": ({"value"}, {"behavior"}),
    "expects": ({"role"}, {"behavior"}),
    "applies_to": ({"policy", "process"}, {"company", "department", "role"}),
    "states": ({"policy"}, {"fact"}),
    "has_note": ({"role"}, {"private_note"}),
}


def create_document(
    db: Session, company_id: int, member_user_id: int | None, *, title: str, data: bytes, suffix: str,
    visibility: str, department_id: int | None, language: str | None, effective_date: date | None,
    source_type: str = "upload",
) -> KbDocument:
    path = storage.save_bytes(company_id, "documents", suffix, data)
    document = KbDocument(
        company_id=company_id, department_id=department_id, title=title,
        # Empty until the job has read the text: raw bytes of a PDF or DOCX say nothing about the language.
        language=language or "",
        source_type=source_type, file_path=path, visibility=visibility, effective_date=effective_date,
        uploaded_by=member_user_id, status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def start_job(db: Session, document_id: int) -> KbIngestionJob:
    job = KbIngestionJob(document_id=document_id, status="queued", progress=0)
    db.add(job)
    document = db.get(KbDocument, document_id)
    document.status = "processing"
    db.commit()
    db.refresh(job)
    return job


def fail_interrupted_jobs() -> int:
    db = SessionLocal()
    try:
        jobs = db.query(KbIngestionJob).filter(KbIngestionJob.status.in_(("queued", "running"))).all()
        for job in jobs:
            job.status = "failed"
            job.error = INTERRUPTED
            document = db.get(KbDocument, job.document_id)
            # A retry of failed chunks runs on a document that keeps its status and everything it already has.
            if document is not None and document.status == "processing":
                document.status = "failed"
        db.commit()
        return len(jobs)
    finally:
        db.close()


def clear_document_output(db: Session, document_id: int, edge_ids=()) -> None:
    """Remove a document's chunks, their sources and any draft left with no source. A published node left with no source
    in a settled document cannot stay readable, so it is rejected and its conflicts close. Does not commit.

    Call with the document locked. The nodes are locked before their source rows, the order review reads them in."""
    chunk_ids = [row[0] for row in db.query(KbChunk.id).filter(KbChunk.document_id == document_id)]
    if chunk_ids:
        node_ids = {row[0] for row in db.query(KbNodeSource.node_id).filter(KbNodeSource.chunk_id.in_(chunk_ids))}
        nodes = review.lock_nodes(db, node_ids)
        db.query(KbNodeSource).filter(KbNodeSource.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
        rejected: dict[int, int] = {}
        for node_id, node in nodes.items():
            has_source = db.query(KbNodeSource.id).filter(KbNodeSource.node_id == node_id).first()
            if node.status == "draft" and not has_source:
                db.query(KbEdge).filter(
                    or_(KbEdge.source_node_id == node_id, KbEdge.target_node_id == node_id)
                ).delete(synchronize_session=False)
                db.delete(node)
            elif node.status == "published" and not review.has_settled_source(db, node_id):
                node.status = "rejected"
                contradiction.on_node_rejected(db, node_id)
                rejected[node_id] = node.company_id
        db.flush()
        for company_id in set(rejected.values()):
            review.settle_edges(db, company_id, set(rejected))
            contradiction.bump_kb_version(db, company_id)
        db.query(KbChunk).filter(KbChunk.id.in_(chunk_ids)).delete(synchronize_session=False)
    if edge_ids:
        db.query(KbEdge).filter(KbEdge.id.in_(list(edge_ids)), KbEdge.status == "draft").delete(synchronize_session=False)


def _parse_date(value: str, fallback):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return fallback


def _check_contradictions(db: Session, company_id: int, node_ids: list[int]) -> int:
    """Looks for conflicts with the new facts. Returns the number of failed checks, for the job's failed_chunks."""
    try:
        contradiction.check_new_facts(db, company_id, node_ids)
    except AIError:
        db.rollback()
        return 1
    return 0


def run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(KbIngestionJob, job_id)
        if job is None:
            return
        document = db.get(KbDocument, job.document_id)
        created_edges: list[int] = []
        try:
            _run(db, job, document, created_edges)
        except Exception as exc:  # noqa: BLE001 - every failure must end the job cleanly
            db.rollback()
            message = str(exc) if isinstance(exc, NoExtractableText) else GENERIC_ERROR
            if not isinstance(exc, (NoExtractableText, AIError)):
                logger.exception("Ingestion job %s failed", job_id)
            review.lock_document(db, document.id)
            clear_document_output(db, document.id, created_edges)
            job = db.get(KbIngestionJob, job_id)
            job.status = "failed"
            job.error = message
            db.get(KbDocument, document.id).status = "failed"
            db.commit()
    finally:
        db.close()


def start_failed_retry(db: Session, job: KbIngestionJob) -> None:
    """Queue a job to re-run only what it recorded as failed. Commits."""
    job.status, job.progress, job.error = "queued", 0, None
    db.commit()


def run_failed_retry(job_id: int) -> None:
    """Re-extract only the chunks a job recorded as failed, then re-run the contradiction check.

    All the AI calls for extraction, the guard and embedding come first, then the writing is one transaction, so a
    failure leaves the document as it was and the job can be retried again."""
    db = SessionLocal()
    try:
        job = db.get(KbIngestionJob, job_id)
        if job is None:
            return
        try:
            _run_failed(db, job, db.get(KbDocument, job.document_id))
        except Exception as exc:  # noqa: BLE001 - every failure must end the job cleanly
            db.rollback()
            if not isinstance(exc, (AIError, _GraphChangedDuringChecks)):
                logger.exception("Retry of ingestion job %s failed", job_id)
            job = db.get(KbIngestionJob, job_id)
            job.status = "failed"
            job.error = GENERIC_ERROR
            db.commit()
    finally:
        db.close()


class _GraphChangedDuringChecks(Exception):
    """A node this retry meant to merge into was rejected or edited during its AI calls, so an item now needs a new node
    the checks never saw. Nothing is written, and the job can be retried."""


def _set_progress(db: Session, job: KbIngestionJob, value: int) -> None:
    job.progress = value
    db.commit()


@dataclass
class _Graph:
    """The company's live nodes by title, plus what this run adds to them."""

    company_id: int
    document: KbDocument
    department_node: KbNode | None
    anchor: KbNode | None
    by_key: dict[tuple[str, str], list[KbNode]]
    by_title: dict[str, list[KbNode]]
    known_titles: list[str]
    document_chunks: list[tuple[int, str]]
    sources: set[tuple[int, int, str]]  # (node id, chunk id, quote) already held for this document's chunks
    new_nodes: list[KbNode] = field(default_factory=list)
    created_edges: list[int] = field(default_factory=list)
    dropped: int = 0


def _load_graph(db: Session, document: KbDocument, created_edges: list[int]) -> _Graph:
    company_id = document.company_id
    org_sync.sync_org_nodes(db, company_id)
    company_node = org_sync.org_node_for(db, company_id, None)
    department_node = org_sync.org_node_for(db, company_id, document.department_id) if document.department_id else None

    existing = (
        db.query(KbNode)
        .filter(KbNode.company_id == company_id, KbNode.status.notin_(INACTIVE))
        .order_by(KbNode.id)
        .all()
    )
    by_key: dict[tuple[str, str], list[KbNode]] = {}
    by_title: dict[str, list[KbNode]] = {}
    for node in existing:
        title = normalise_title(node.title)
        by_key.setdefault((node.type, title), []).append(node)
        by_title.setdefault(title, []).append(node)
    known_titles = [
        n.title for n in existing if n.type in ("company", "department") or n.status == "published"
    ][:KNOWN_TITLE_CAP]
    document_chunks = [
        (row.id, row.text)
        for row in db.query(KbChunk.id, KbChunk.text).filter(KbChunk.document_id == document.id).order_by(KbChunk.position)
    ]
    sources = {
        (row.node_id, row.chunk_id, row.quote)
        for row in db.query(KbNodeSource.node_id, KbNodeSource.chunk_id, KbNodeSource.quote)
        .join(KbChunk, KbNodeSource.chunk_id == KbChunk.id)
        .filter(KbChunk.document_id == document.id)
    }
    return _Graph(
        company_id=company_id, document=document, department_node=department_node,
        anchor=department_node or company_node, by_key=by_key, by_title=by_title, known_titles=known_titles,
        document_chunks=document_chunks, sources=sources, created_edges=created_edges,
    )


def _is_fact(item: ExtractedNode) -> bool:
    return item.fact_kind != "none"


def _node_is_storable(item: ExtractedNode) -> bool:
    """Whether the item fits its columns. MySQL refuses an over-long value and would fail the whole job."""
    if not item.title.strip():
        return False
    bounded = ALWAYS_BOUNDED + (FACT_BOUNDED if _is_fact(item) else ())
    for name in bounded:
        if len(getattr(item, name).strip()) > KbNode.__table__.c[name].type.length:
            return False
    return len(item.body.encode("utf-8")) <= MAX_TEXT_COLUMN_BYTES


def _node_is_verified(item: ExtractedNode, chunk_text: str) -> bool:
    if not verified_quote(item.quote, chunk_text):
        return False
    return not _is_fact(item) or contradiction.value_in_quote(item.fact_kind, item.fact_value, item.quote)


def _same_item(item: ExtractedNode, node: KbNode) -> bool:
    """Same type and title merge, but a fact only with the same value and unit. Otherwise its quote would be a false
    source of the other value, and the disagreement would never reach the Radar."""
    if not _is_fact(item) or node.fact_kind is None:
        return not _is_fact(item) and node.fact_kind is None
    return node.fact_kind == item.fact_kind and contradiction.same_value(
        item.fact_kind, item.fact_value, item.fact_unit, node.fact_value, node.fact_unit
    )


def _live_match(db: Session, graph: _Graph, item: ExtractedNode) -> KbNode | None:
    """The node this item merges into. Read again and held until this chunk commits: HR may have rejected or edited it
    since the graph was loaded, and a rejected node takes no new source. The item then starts a new draft."""
    candidates = graph.by_key.get((item.type, normalise_title(item.title)), [])
    for candidate in list(candidates):
        if review.lock_nodes(db, [candidate.id]).get(candidate.id) is None or candidate.status in INACTIVE:
            candidates.remove(candidate)
        elif _same_item(item, candidate):
            return candidate
    return None


def _build_node(graph: _Graph, item: ExtractedNode) -> KbNode:
    document = graph.document
    is_fact = _is_fact(item)
    # Committed before its check runs, and HR can see it by then: until an answer is stored it needs HR's confirmation.
    guarded = item.type in discrimination.GUARDED_TYPES
    return KbNode(
        company_id=graph.company_id, department_id=document.department_id, type=item.type,
        title=item.title.strip(), body=item.body, language=document.language,
        visibility=stricter_layer(DEFAULT_VISIBILITY_BY_TYPE[item.type], document.visibility),
        status="draft", effective_date=_parse_date(item.effective_date, document.effective_date),
        fact_kind=item.fact_kind if is_fact else None, fact_value=item.fact_value.strip() if is_fact else None,
        fact_unit=item.fact_unit.strip() if is_fact else None, scope_text=item.scope_text.strip() if is_fact else None,
        guard_category=discrimination.UNCHECKED if guarded else None,
        guard_reason=discrimination.UNCHECKED_REASON if guarded else None,
    )


def _new_node(db: Session, graph: _Graph, item: ExtractedNode) -> KbNode:
    node = _build_node(graph, item)
    db.add(node)
    db.flush()
    title = normalise_title(node.title)
    graph.by_key.setdefault((node.type, title), []).append(node)
    graph.by_title.setdefault(title, []).append(node)
    graph.new_nodes.append(node)
    return node


def chunks_sharing_quote(quote: str, chunks: list[str]) -> list[int]:
    """Positions of the chunks that say any of the quote: each chunk holding all of it, and the neighbours on either
    side for as long as they share a span. Chunks overlap, so the next one can start in the middle of the quote.

    Walking out from a holder means a chance match at the edge of a chunk elsewhere in the document does not count."""
    linked: set[int] = set()
    for index, text in enumerate(chunks):
        if not quote_in(quote, text):
            continue
        linked.add(index)
        for step in (-1, 1):
            neighbour = index + step
            while 0 <= neighbour < len(chunks) and shares_span(quote, chunks[neighbour]):
                linked.add(neighbour)
                neighbour += step
    return sorted(linked)


def _add_sources(db: Session, graph: _Graph, node: KbNode, quote: str) -> None:
    """Link the node to every chunk of this document that says any of the quote. Retrieval decides whether a chunk may
    be read from the nodes linked to it, so a chunk left out here would serve the part of the quote it holds."""
    texts = [text for _, text in graph.document_chunks]
    for index in chunks_sharing_quote(quote, texts):
        chunk_id = graph.document_chunks[index][0]
        key = (node.id, chunk_id, quote)
        if key not in graph.sources:
            graph.sources.add(key)
            db.add(KbNodeSource(node_id=node.id, chunk_id=chunk_id, quote=quote))


def _resolve_edge_end(graph: _Graph, refs: dict[str, KbNode], ref: str, types: set[str]) -> KbNode | None:
    """The node a ref names: this chunk's own first, then any node with that title, preferring the type allowed here."""
    name = normalise_title(ref)
    own = refs.get(name)
    if own is not None:
        return own
    named = graph.by_title.get(name, [])
    return next((node for node in named if node.type in types), named[0] if named else None)


def _edge_is_allowed(relation: str, source: KbNode, target: KbNode) -> bool:
    sources, targets = RELATION_ENDS[relation]
    return source.type in sources and target.type in targets


def _apply_edge(db: Session, graph: _Graph, refs: dict[str, KbNode], item: ExtractedEdge, chunk_text: str,
                links: set[tuple[int, str]]) -> None:
    sources, targets = RELATION_ENDS[item.relation]
    source = _resolve_edge_end(graph, refs, item.source_ref, sources)
    target = _resolve_edge_end(graph, refs, item.target_ref, targets)
    if (
        not verified_quote(item.quote, chunk_text) or source is None or target is None or source.id == target.id
        or not _edge_is_allowed(item.relation, source, target)
    ):
        graph.dropped += 1
        return
    duplicate = db.query(KbEdge.id).filter_by(
        company_id=graph.company_id, source_node_id=source.id, target_node_id=target.id, relation=item.relation
    ).first()
    if duplicate is None:
        edge = KbEdge(
            company_id=graph.company_id, source_node_id=source.id, target_node_id=target.id,
            relation=item.relation, must_have=item.must_have if item.relation == "requires" else None,
            status="draft",
        )
        db.add(edge)
        db.flush()
        graph.created_edges.append(edge.id)
    links.add((source.id, item.relation))
    links.add((target.id, item.relation))


def _apply_extraction(db: Session, graph: _Graph, chunk: KbChunk, result: ExtractionResult) -> None:
    refs: dict[str, KbNode] = {}
    chunk_new: list[KbNode] = []
    for item in result.nodes:
        if not _node_is_storable(item) or not _node_is_verified(item, chunk.text):
            graph.dropped += 1
            continue
        node = _live_match(db, graph, item)
        if node is None:
            node = _new_node(db, graph, item)
            chunk_new.append(node)
        _add_sources(db, graph, node, item.quote)
        refs[normalise_title(item.ref)] = node

    links: set[tuple[int, str]] = set()  # (node id, relation) for connectivity checks, as source or target
    for item in result.edges:
        _apply_edge(db, graph, refs, item, chunk.text, links)

    department_node, anchor = graph.department_node, graph.anchor
    for node in chunk_new:
        if node.type == "role" and department_node is not None and (node.id, "has_role") not in links:
            _link(db, graph, department_node.id, node.id, "has_role")
        elif node.type == "value" and anchor is not None and (node.id, "holds") not in links:
            _link(db, graph, anchor.id, node.id, "holds")
        elif node.type in ("policy", "process") and anchor is not None and (node.id, "applies_to") not in links:
            _link(db, graph, node.id, anchor.id, "applies_to")


@dataclass
class _NodeChecks:
    """What the AI said about node texts, keyed by those texts."""

    guards: dict[str, discrimination.GuardResult | None] = field(default_factory=dict)
    embeddings: dict[str, tuple] = field(default_factory=dict)


def _guard_text(node: KbNode) -> str:
    return f"{node.title}\n{node.body}"


def _check_nodes(nodes: list[KbNode], company_id: int) -> _NodeChecks:
    """The AI calls for new nodes, run with nothing written: a vendor call must not hold locks. A failed discrimination
    check comes back as "unchecked" and never fails the job."""
    checks = _NodeChecks()
    for node in nodes:
        if node.type in discrimination.GUARDED_TYPES and _guard_text(node) not in checks.guards:
            checks.guards[_guard_text(node)] = discrimination.check(_guard_text(node), company_id)
    texts = list(dict.fromkeys(retriever.node_text(node) for node in nodes))
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start:start + EMBED_BATCH]
        result = gateway.embed(batch, "document", "kb_embed", company_id)
        for text, vector in zip(batch, result.vectors):
            checks.embeddings[text] = (vectors.encode(vector), result.model, result.dimension)
    return checks


def _store_checks(graph: _Graph, checks: _NodeChecks) -> None:
    """Flag new requirement, skill and behavior nodes that ask for a protected trait, and store every embedding. A
    flagged node stays a draft that HR can only reject or rewrite."""
    for node in graph.new_nodes:
        if node.type in discrimination.GUARDED_TYPES:
            result = checks.guards[_guard_text(node)]
            node.guard_category = result.category if result else None
            node.guard_reason = result.reason if result else None
        node.embedding, node.embedding_model, node.embedding_dim = checks.embeddings[retriever.node_text(node)]


def _possible_new_nodes(graph: _Graph, extracted: list[tuple[KbChunk, ExtractionResult]]) -> list[KbNode]:
    """Unsaved nodes for every item _apply_extraction could add. The graph only grows while it runs, so an item that
    matches nothing there has no match here either, and this list holds every node it can create."""
    possible = []
    for chunk, result in extracted:
        for item in result.nodes:
            if not _node_is_storable(item) or not _node_is_verified(item, chunk.text):
                continue
            named = graph.by_key.get((item.type, normalise_title(item.title)), [])
            if not any(_same_item(item, candidate) for candidate in named):
                possible.append(_build_node(graph, item))
    return possible


def _finish_job(db: Session, job: KbIngestionJob, document: KbDocument, failed_chunk_ids: list[int],
                check_failed: bool, dropped: int) -> None:
    """Record the outcome. A document with nothing left to decide is published, unless the job could not read all of it:
    then HR decides. What failed stays on the job."""
    review.lock_document(db, document.id)
    job.dropped_items = dropped
    job.failed_chunk_ids = failed_chunk_ids
    job.contradiction_check_failed = check_failed
    job.failed_chunks = len(failed_chunk_ids) + int(check_failed)
    job.progress = 100
    if document.status == "processing":
        document.status = "review"
    db.flush()
    if review.finish_document_if_decided(db, document.id):
        contradiction.bump_kb_version(db, document.company_id)
    decided = document.status == "published" and not review.has_drafts(db, document)
    job.status = "done" if decided and not job.failed_chunks else "review"
    db.commit()


def _run(db: Session, job: KbIngestionJob, document: KbDocument, created_edges: list[int]) -> None:
    company_id = document.company_id
    job.status, job.progress, job.error = "running", 5, None
    db.commit()

    data = storage.read_bytes(document.file_path)
    suffix = "." + document.file_path.rsplit(".", 1)[-1]
    pages = extract_pages(data, suffix)
    if not document.language:
        document.language = guess_language("\n".join(text for _, text in pages)[:LANGUAGE_SAMPLE_CHARS])
    chunks = chunk_pages(pages)

    chunk_rows: list[KbChunk] = []
    embedded = []
    for start in range(0, len(chunks), EMBED_BATCH):
        embedded.append(gateway.embed([c.text for c in chunks[start:start + EMBED_BATCH]], "document", "kb_embed", company_id))
    for result, offset in zip(embedded, range(0, len(chunks), EMBED_BATCH)):
        for index, vector in enumerate(result.vectors):
            chunk = chunks[offset + index]
            row = KbChunk(
                company_id=company_id, document_id=document.id, position=chunk.position, page=chunk.page,
                text=chunk.text, embedding=vectors.encode(vector), embedding_model=result.model,
                embedding_dim=result.dimension,
            )
            db.add(row)
            chunk_rows.append(row)
    db.commit()
    _set_progress(db, job, 20)

    graph = _load_graph(db, document, created_edges)
    failed: list[int] = []
    total = max(len(chunk_rows), 1)

    for position, chunk in enumerate(chunk_rows, 1):
        try:
            result = extract_chunk(chunk.text, document.language, graph.known_titles, company_id)
        except AIError:
            failed.append(chunk.id)
        else:
            _apply_extraction(db, graph, chunk, result)
        job.dropped_items = graph.dropped
        job.failed_chunks = len(failed)
        job.failed_chunk_ids = list(failed)
        _set_progress(db, job, 20 + int(70 * position / total))

    # Every chunk's rows are committed above, so these AI calls hold nothing.
    _store_checks(graph, _check_nodes(graph.new_nodes, company_id))
    db.commit()
    _set_progress(db, job, 95)

    check_failed = bool(_check_contradictions(db, company_id, [n.id for n in graph.new_nodes]))
    _finish_job(db, job, document, failed, check_failed, graph.dropped)


def _run_failed(db: Session, job: KbIngestionJob, document: KbDocument) -> None:
    job_id = job.id
    company_id = document.company_id
    retry_ids = list(job.failed_chunk_ids or [])
    recheck_document = job.contradiction_check_failed
    job.status, job.progress, job.error = "running", 5, None
    db.commit()

    graph = _load_graph(db, document, [])
    graph.dropped = job.dropped_items
    chunks = (
        db.query(KbChunk)
        .filter(KbChunk.id.in_(retry_ids or [-1]), KbChunk.document_id == document.id)
        .order_by(KbChunk.position)
        .all()
    )
    failed: list[int] = []
    extracted: list[tuple[KbChunk, ExtractionResult]] = []
    for chunk in chunks:
        try:
            extracted.append((chunk, extract_chunk(chunk.text, document.language, graph.known_titles, company_id)))
        except AIError:
            failed.append(chunk.id)
    checks = _check_nodes(_possible_new_nodes(graph, extracted), company_id)
    for chunk, result in extracted:
        _apply_extraction(db, graph, chunk, result)
    if any(retriever.node_text(node) not in checks.embeddings for node in graph.new_nodes):
        raise _GraphChangedDuringChecks
    _store_checks(graph, checks)
    new_ids = [n.id for n in graph.new_nodes]
    dropped = graph.dropped
    db.commit()

    # The earlier check may have stopped at any node of this document, and repeating it costs only unpaired facts.
    check_ids = sorted(review.document_node_ids(db, company_id, document.id)) if recheck_document else new_ids
    check_failed = bool(_check_contradictions(db, company_id, check_ids))
    job = db.get(KbIngestionJob, job_id)
    document = db.get(KbDocument, job.document_id)
    _finish_job(db, job, document, failed, check_failed, dropped)


def _link(db: Session, graph: _Graph, source_id: int, target_id: int, relation: str) -> None:
    edge = KbEdge(
        company_id=graph.company_id, source_node_id=source_id, target_node_id=target_id, relation=relation,
        status="draft",
    )
    db.add(edge)
    db.flush()
    graph.created_edges.append(edge.id)
