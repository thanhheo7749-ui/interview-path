"""HR-only list and resolution of contradictions between facts. Every lookup filters on company_id."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.brain import contradiction, review
from app.database.database import get_db
from app.database.sql_models import CompanyMember, KbConflict, KbNode

router = APIRouter()

KB = "/api/companies/{company_id}/kb"


class ResolveBody(BaseModel):
    action: Literal["a", "b", "different_scope"]


def _node_out(node: KbNode | None, sources: dict[int, list[dict]]) -> dict | None:
    if node is None:
        return None
    return {
        "id": node.id, "title": node.title, "status": node.status, "fact_kind": node.fact_kind,
        "fact_value": node.fact_value, "fact_unit": node.fact_unit, "scope_text": node.scope_text,
        "visibility": node.visibility, "sources": sources.get(node.id, []),
    }


def _conflict_out(db: Session, conflict: KbConflict) -> dict:
    sources = review.node_sources(db, conflict.company_id, [conflict.node_a_id, conflict.node_b_id])
    return {
        "id": conflict.id, "status": conflict.status, "resolution": conflict.resolution,
        "created_at": conflict.created_at.isoformat() if conflict.created_at else None,
        "node_a": _node_out(db.get(KbNode, conflict.node_a_id), sources),
        "node_b": _node_out(db.get(KbNode, conflict.node_b_id), sources),
    }


@router.get(f"{KB}/conflicts")
def list_conflicts(company_id: int, _: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    rows = (
        db.query(KbConflict)
        .filter(KbConflict.company_id == company_id, KbConflict.status == "open")
        .order_by(KbConflict.id)
        .all()
    )
    return [_conflict_out(db, row) for row in rows]


@router.post(f"{KB}/conflicts/{{conflict_id}}/resolve")
def resolve_conflict(
    company_id: int,
    conflict_id: int,
    body: ResolveBody,
    member: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    # Not locked here: resolve takes its documents and nodes first, then this row, as every other path does.
    conflict = db.query(KbConflict).filter(KbConflict.id == conflict_id, KbConflict.company_id == company_id).first()
    if conflict is None:
        raise HTTPException(status_code=404, detail="Conflict not found")
    user_id = member.user_id
    try:
        return _conflict_out(db, contradiction.resolve(db, conflict, body.action, user_id))
    except contradiction.ConflictClosed as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This conflict is already closed") from exc
    except contradiction.ConflictNotLive as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="One side of this conflict is no longer active") from exc
    except review.ReviewError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
