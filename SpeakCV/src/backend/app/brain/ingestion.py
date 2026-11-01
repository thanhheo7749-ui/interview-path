"""Document ingestion. Every extracted item is verified against its source text and starts as a draft."""
import logging
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.types import AIError
from app.brain import contradiction, org_sync, vectors
from app.brain.chunking import chunk_pages
from app.brain.extraction import extract_chunk
from app.brain.text import guess_language, normalise_title, quote_in
from app.core import storage
from app.core.text_extract import NoExtractableText, extract_pages
from app.database.database import SessionLocal
from app.database.models_brain import DEFAULT_VISIBILITY_BY_TYPE, VISIBILITIES
from app.database.sql_models import KbChunk, KbDocument, KbEdge, KbIngestionJob, KbNode, KbNodeSource

logger = logging.getLogger(__name__)

EMBED_BATCH = 64
KNOWN_TITLE_CAP = 200
GENERIC_ERROR = "Processing this document failed. Please retry."
INTERRUPTED = "Interrupted by a restart. Retry to run it again."
INACTIVE = ("rejected", "superseded")


def create_document(
    db: Session, company_id: int, member_user_id: int | None, *, title: str, data: bytes, suffix: str,
    visibility: str, department_id: int | None, language: str | None, effective_date: date | None,
    source_type: str = "upload",
) -> KbDocument:
    path = storage.save_bytes(company_id, "documents", suffix, data)
    document = KbDocument(
        company_id=company_id, department_id=department_id, title=title,
        language=language or guess_language(data[:2000].decode("utf-8", errors="ignore")),
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
        jobs = db.query(KbIngestionJob).filter(KbIngestionJob.status == "running").all()
        for job in jobs:
            job.status = "failed"
            job.error = INTERRUPTED
            document = db.get(KbDocument, job.document_id)
            if document is not None:
                document.status = "failed"
        db.commit()
        return len(jobs)
    finally:
        db.close()


def clear_document_output(db: Session, document_id: int, edge_ids=()) -> None:
    """Remove a document's chunks, their sources and any draft left with no source. Does not commit."""
    chunk_ids = [row[0] for row in db.query(KbChunk.id).filter(KbChunk.document_id == document_id)]
    if chunk_ids:
        node_ids = {row[0] for row in db.query(KbNodeSource.node_id).filter(KbNodeSource.chunk_id.in_(chunk_ids))}
        db.query(KbNodeSource).filter(KbNodeSource.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
        for node_id in node_ids:
            node = db.get(KbNode, node_id)
            has_source = db.query(KbNodeSource.id).filter(KbNodeSource.node_id == node_id).first()
            if node is not None and node.status == "draft" and not has_source:
                db.query(KbEdge).filter(
                    or_(KbEdge.source_node_id == node_id, KbEdge.target_node_id == node_id)
                ).delete(synchronize_session=False)
                db.delete(node)
        db.query(KbChunk).filter(KbChunk.id.in_(chunk_ids)).delete(synchronize_session=False)
    if edge_ids:
        db.query(KbEdge).filter(KbEdge.id.in_(list(edge_ids)), KbEdge.status == "draft").delete(synchronize_session=False)


def _stricter(a: str, b: str) -> str:
    return a if VISIBILITIES.index(a) >= VISIBILITIES.index(b) else b


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
            clear_document_output(db, document.id, created_edges)
            job = db.get(KbIngestionJob, job_id)
            job.status = "failed"
            job.error = message
            db.get(KbDocument, document.id).status = "failed"
            db.commit()
    finally:
        db.close()


def _set_progress(db: Session, job: KbIngestionJob, value: int) -> None:
    job.progress = value
    db.commit()


def _run(db: Session, job: KbIngestionJob, document: KbDocument, created_edges: list[int]) -> None:
    company_id = document.company_id
    job.status, job.progress, job.error = "running", 5, None
    db.commit()

    data = storage.read_bytes(document.file_path)
    suffix = "." + document.file_path.rsplit(".", 1)[-1]
    chunks = chunk_pages(extract_pages(data, suffix))

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

    org_sync.sync_org_nodes(db, company_id)
    company_node = org_sync.org_node_for(db, company_id, None)
    department_node = org_sync.org_node_for(db, company_id, document.department_id) if document.department_id else None
    anchor = department_node or company_node

    existing = db.query(KbNode).filter(KbNode.company_id == company_id, KbNode.status.notin_(INACTIVE)).all()
    index: dict[tuple[str, str], KbNode] = {(n.type, normalise_title(n.title)): n for n in existing}
    by_title: dict[str, KbNode] = {}
    for node in existing:
        by_title.setdefault(normalise_title(node.title), node)
    known_titles = [
        n.title for n in existing if n.type in ("company", "department") or n.status == "published"
    ][:KNOWN_TITLE_CAP]

    new_nodes: list[KbNode] = []
    dropped = failed = 0
    total = max(len(chunk_rows), 1)

    for position, chunk in enumerate(chunk_rows, 1):
        try:
            result = extract_chunk(chunk.text, document.language, known_titles, company_id)
        except AIError:
            failed += 1
            job.failed_chunks = failed
            _set_progress(db, job, 20 + int(70 * position / total))
            continue

        refs: dict[str, KbNode] = {}
        chunk_new: list[KbNode] = []
        for item in result.nodes:
            if not quote_in(item.quote, chunk.text):
                dropped += 1
                continue
            key = (item.type, normalise_title(item.title))
            node = index.get(key)
            if node is None:
                is_fact = item.fact_kind != "none"
                node = KbNode(
                    company_id=company_id, department_id=document.department_id, type=item.type,
                    title=item.title.strip(), body=item.body, language=document.language,
                    visibility=_stricter(DEFAULT_VISIBILITY_BY_TYPE[item.type], document.visibility),
                    status="draft", effective_date=_parse_date(item.effective_date, document.effective_date),
                    fact_kind=item.fact_kind if is_fact else None, fact_value=item.fact_value if is_fact else None,
                    fact_unit=item.fact_unit if is_fact else None, scope_text=item.scope_text if is_fact else None,
                )
                db.add(node)
                db.flush()
                index[key] = node
                by_title.setdefault(key[1], node)
                new_nodes.append(node)
                chunk_new.append(node)
            db.add(KbNodeSource(node_id=node.id, chunk_id=chunk.id, quote=item.quote))
            refs[normalise_title(item.ref)] = node

        links: set[tuple[int, str]] = set()  # (node id, relation) for connectivity checks, as source or target
        for item in result.edges:
            source = refs.get(normalise_title(item.source_ref)) or by_title.get(normalise_title(item.source_ref))
            target = refs.get(normalise_title(item.target_ref)) or by_title.get(normalise_title(item.target_ref))
            if not quote_in(item.quote, chunk.text) or source is None or target is None or source.id == target.id:
                dropped += 1
                continue
            duplicate = db.query(KbEdge.id).filter_by(
                company_id=company_id, source_node_id=source.id, target_node_id=target.id, relation=item.relation
            ).first()
            if duplicate is None:
                edge = KbEdge(
                    company_id=company_id, source_node_id=source.id, target_node_id=target.id,
                    relation=item.relation, must_have=item.must_have if item.relation == "requires" else None,
                    status="draft",
                )
                db.add(edge)
                db.flush()
                created_edges.append(edge.id)
            links.add((source.id, item.relation))
            links.add((target.id, item.relation))

        for node in chunk_new:
            if node.type == "role" and department_node is not None and (node.id, "has_role") not in links:
                _link(db, company_id, department_node.id, node.id, "has_role", created_edges)
            elif node.type == "value" and anchor is not None and (node.id, "holds") not in links:
                _link(db, company_id, anchor.id, node.id, "holds", created_edges)
            elif node.type in ("policy", "process") and anchor is not None and (node.id, "applies_to") not in links:
                _link(db, company_id, node.id, anchor.id, "applies_to", created_edges)

        job.dropped_items = dropped
        job.failed_chunks = failed
        _set_progress(db, job, 20 + int(70 * position / total))

    for start in range(0, len(new_nodes), EMBED_BATCH):
        batch = new_nodes[start:start + EMBED_BATCH]
        result = gateway.embed([f"{n.title}\n{n.body}" for n in batch], "document", "kb_embed", company_id)
        for node, vector in zip(batch, result.vectors):
            node.embedding = vectors.encode(vector)
            node.embedding_model = result.model
            node.embedding_dim = result.dimension
    db.commit()
    _set_progress(db, job, 95)

    failed += _check_contradictions(db, company_id, [n.id for n in new_nodes])

    job.dropped_items, job.failed_chunks = dropped, failed
    job.status, job.progress = "review", 100
    document.status = "review"
    db.commit()


def _link(db: Session, company_id: int, source_id: int, target_id: int, relation: str, created: list[int]) -> None:
    edge = KbEdge(
        company_id=company_id, source_node_id=source_id, target_node_id=target_id, relation=relation, status="draft"
    )
    db.add(edge)
    db.flush()
    created.append(edge.id)
