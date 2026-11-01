"""HR-only review queue and the permission-filtered graph. Plain `def` routes: they may call the AI gateway."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.brain import audience as aud
from app.brain import retriever, review
from app.database.database import get_db
from app.database.sql_models import CompanyMember, KbDocument, KbNode

router = APIRouter()

KB = "/api/companies/{company_id}/kb"


class DecisionItem(BaseModel):
    action: Literal["accept", "edit", "reject", "merge", "publish_document"]
    node_id: int | None = None
    into_node_id: int | None = None
    document_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, max_length=20000)
    visibility: str | None = Field(default=None, max_length=20)
    fact_value: str | None = Field(default=None, max_length=255)
    fact_unit: str | None = Field(default=None, max_length=50)
    scope_text: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _required_ids(self):
        if self.action == "publish_document":
            if self.document_id is None:
                raise ValueError("document_id is required")
        elif self.node_id is None:
            raise ValueError("node_id is required")
        if self.action == "merge" and self.into_node_id is None:
            raise ValueError("into_node_id is required")
        return self


class DecideBody(BaseModel):
    items: list[DecisionItem] = Field(min_length=1, max_length=500)


def _node_out(node: KbNode, sources: list[dict]) -> dict:
    return {
        "id": node.id, "type": node.type, "title": node.title, "body": node.body, "visibility": node.visibility,
        "language": node.language, "fact_kind": node.fact_kind, "fact_value": node.fact_value,
        "fact_unit": node.fact_unit, "scope_text": node.scope_text, "department_id": node.department_id,
        "sources": sources,
    }


@router.get(f"{KB}/review")
def review_queue(
    company_id: int,
    document_id: int | None = None,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    if document_id is not None and not db.query(KbDocument.id).filter(
        KbDocument.id == document_id, KbDocument.company_id == company_id
    ).first():
        raise HTTPException(status_code=404, detail="Document not found")
    nodes = review.draft_nodes(db, company_id, document_id)
    sources = review.node_sources(db, company_id, [n.id for n in nodes])
    edges = review.draft_edges(db, company_id, {n.id for n in nodes} if document_id is not None else None)
    end_ids = {e.source_node_id for e in edges} | {e.target_node_id for e in edges}
    titles = {
        row.id: row.title for row in db.query(KbNode.id, KbNode.title).filter(
            KbNode.company_id == company_id, KbNode.id.in_(list(end_ids) or [-1])
        )
    }
    return {
        "nodes": [_node_out(n, sources.get(n.id, [])) for n in nodes],
        "edges": [
            {
                "id": e.id, "source_node_id": e.source_node_id, "target_node_id": e.target_node_id,
                "source_title": titles.get(e.source_node_id), "target_title": titles.get(e.target_node_id),
                "relation": e.relation, "must_have": e.must_have,
            }
            for e in edges
        ],
        "merge_proposals": review.merge_proposals(db, company_id, nodes),
    }


@router.post(f"{KB}/review/decide")
def decide(
    company_id: int,
    body: DecideBody,
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    try:
        review.apply_decisions(db, company_id, member.user_id, body.items)
        db.commit()
    except review.ReviewError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception:
        db.rollback()
        raise
    return {"ok": True, "applied": len(body.items)}


@router.get(f"{KB}/graph")
def graph(
    company_id: int,
    view_as: str | None = Query(default=None),
    department_id: int | None = None,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    try:
        audience = aud.simulated(db, company_id, view_as or "hr", department_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    nodes, edges = retriever.visible_graph(db, audience)
    return {
        "nodes": [{"id": str(n.id), "layer": n.visibility, "type": n.type, "title": n.title} for n in nodes],
        "links": [
            {"source": str(e.source_node_id), "target": str(e.target_node_id), "relation": e.relation} for e in edges
        ],
    }
