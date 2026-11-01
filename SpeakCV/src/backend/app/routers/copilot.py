"""Policy Copilot, Ask the Company and the gap list. The audience always comes from the server, never the request.

Routes that call the AI gateway are plain def, so they run in the threadpool and do not block the event loop.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app.auth.dependencies import get_authenticated_user, require_member
from app.brain import audience as aud
from app.brain import copilot, gaps
from app.brain.audience import Audience
from app.brain.retriever import NoEmbeddingsError
from app.core.rate_limit import ASK_LIMIT, limiter, user_key
from app.database.database import get_db
from app.database.sql_models import Company, CompanyMember, User

router = APIRouter()

KB = "/api/companies/{company_id}/kb"
REEMBED_MESSAGE = "Company knowledge is not available for search yet. The operator needs to run make reembed."


class AskBody(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


def _ask(db: Session, audience: Audience, question: str, user_id: int) -> copilot.CopilotResponse:
    try:
        return copilot.ask(db, audience, question, user_id)
    except NoEmbeddingsError:
        raise HTTPException(status_code=503, detail=REEMBED_MESSAGE) from None


@router.post("/api/companies/{company_id}/copilot/ask")
def ask_copilot(body: AskBody, member: CompanyMember = Depends(require_member()), db: Session = Depends(get_db)):
    return _ask(db, aud.for_member(db, member), body.question, member.user_id)


@router.post("/api/public/companies/{slug}/ask")
@limiter.limit(ASK_LIMIT, key_func=user_key)
def ask_the_company(
    request: Request,
    slug: str,
    body: AskBody,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    company_id = db.query(Company.id).filter(Company.slug == slug).scalar()
    if company_id is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return _ask(db, aud.candidate(company_id), body.question, user.id)


@router.get(f"{KB}/gaps")
def list_gaps(company_id: int, _: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    return [
        {"group_id": group.group_id, "sample_question": group.sample_question, "count": group.count}
        for group in gaps.list_gaps(db, company_id)
    ]


@router.post(f"{KB}/gaps/{{group_id}}/resolve")
def resolve_gap(
    company_id: int,
    group_id: int,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    resolved = gaps.resolve_group(db, company_id, group_id)
    if resolved == 0:
        raise HTTPException(status_code=404, detail="Gap group not found")
    return {"resolved": resolved}
