"""JD Studio routes: generate a draft, edit it by hand or with the assistant, confirm lines, read lint.
Every lookup filters on company_id. A manager reads a draft once it was first submitted, if they are the one assigned to
its request or, for a draft with no request, a manager of its department. Anyone else gets a 404."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_member
from app.brain import audience as aud
from app.brain import retriever
from app.bridges import channels, jd_studio, lint, publishing
from app.database.database import get_db
from app.database.sql_models import CompanyMember, HiringRequest, JobDraft, JobDraftMessage, KbNode
from app.schemas.bridges import (
    AcknowledgeIn, AssistantIn, DraftFromRequestIn, DraftFromRoleIn, DraftPatchIn, DraftVersionIn, RequestChangesIn,
)

router = APIRouter()

BASE = "/api/companies/{company_id}"


def _translate(error: jd_studio.JdStudioError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


def _get_draft(db: Session, member: CompanyMember, draft_id: int) -> JobDraft:
    draft = db.query(JobDraft).filter(JobDraft.id == draft_id, JobDraft.company_id == member.company_id).first()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if member.role == "manager" and (draft.submitted_at is None or not publishing.manages(db, draft, member)):
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def _node_titles(db: Session, draft: JobDraft, reader: aud.Audience) -> dict[int, str]:
    """Titles of the nodes the lines cite or lint names, that this reader may read; the audience filter runs in SQL."""
    ids = {i for item in draft.lines or [] for i in item.get("source_node_ids") or []}
    ids |= {issue["node_id"] for issue in draft.lint or [] if issue.get("node_id") is not None}
    if not ids:
        return {}
    rows = db.query(KbNode.id, KbNode.title).filter(KbNode.id.in_(ids), aud.node_filter(reader)).all()
    return dict(rows)


def _line_out(item: dict, titles: dict[int, str]) -> dict:
    sources = [{"node_id": i, "title": titles.get(i)} for i in item.get("source_node_ids") or []]
    return {**item, "sources": sources, "label": jd_studio.CONFIRMED_LABEL if item.get("hr_confirmed") else None}


def _draft_out(db: Session, draft: JobDraft, member: CompanyMember | None = None) -> dict:
    # Without a member (a path that is HR-only) the reader is HR of the draft's company.
    reader = aud.for_member(db, member) if member is not None else aud.Audience(draft.company_id, "hr")
    titles = _node_titles(db, draft, reader)
    rows = (db.query(JobDraftMessage)
            .filter(JobDraftMessage.job_draft_id == draft.id, JobDraftMessage.company_id == draft.company_id,
                    JobDraftMessage.role.in_(("user", "assistant", jd_studio.MANAGER_FEEDBACK)))
            .order_by(JobDraftMessage.id).all())
    issues = [{**item, "node_title": titles.get(item.get("node_id"))} for item in draft.lint or []]
    body = {
        "id": draft.id, "hiring_request_id": draft.hiring_request_id, "job_id": draft.job_id,
        "version": draft.version, "status": draft.status,
        "lines": [_line_out(item, titles) for item in draft.lines or []],
        "requirement_lines": draft.requirement_lines or [],
        "failed_languages": draft.failed_languages or [],
        "lint": issues, "blocks_publish": any(i["severity"] == "block" for i in issues),
        "manager_feedback": [{"comment": m.content, "by": m.created_by,
                              "created_at": m.created_at.isoformat() if m.created_at else None}
                             for m in rows if m.role == jd_studio.MANAGER_FEEDBACK],
        "approved_by": draft.approved_by,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }
    if reader.kind == "manager":  # HR's working material stays with HR
        return body
    return {
        **body,
        "rejected": list(getattr(draft, "rejected_lines", [])),
        "proposals": jd_studio.pending_proposals(db, draft),
        "messages": [{"role": m.role, "content": m.content, "summary": m.summary,
                      "created_at": m.created_at.isoformat() if m.created_at else None}
                     for m in rows if m.role != jd_studio.MANAGER_FEEDBACK],
    }


@router.post(BASE + "/hiring-requests/{req_id}/drafts")
def create_from_request(company_id: int, req_id: int, body: DraftFromRequestIn | None = None,
                        member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    request = db.query(HiringRequest).filter(HiringRequest.id == req_id, HiringRequest.company_id == company_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Hiring request not found")
    if request.status == "cancelled":
        raise HTTPException(status_code=409, detail="This hiring request was cancelled")
    source = jd_studio.job_context(db, request)
    if body is not None and body.role_node_id is not None:
        source = jd_studio.JobContext(company_id, request.title, body.role_node_id, request.id)
    try:
        return _draft_out(db, jd_studio.generate(db, source, member.user_id))
    except jd_studio.JdStudioError as error:
        raise _translate(error) from error


@router.post(BASE + "/job-drafts")
def create_from_role(company_id: int, body: DraftFromRoleIn, member: CompanyMember = Depends(require_member("hr")),
                     db: Session = Depends(get_db)):
    nodes = {n.id: n for n in retriever.visible_graph(db, aud.candidate(company_id))[0]}
    role = nodes.get(body.role_node_id)
    if role is None or role.type != "role":
        raise HTTPException(status_code=404, detail="Role not found")
    source = jd_studio.JobContext(company_id, body.title or role.title, role.id, None)
    try:
        return _draft_out(db, jd_studio.generate(db, source, member.user_id))
    except jd_studio.JdStudioError as error:
        raise _translate(error) from error


@router.get(BASE + "/job-drafts/{draft_id}")
def read_draft(company_id: int, draft_id: int, member: CompanyMember = Depends(require_member("hr", "manager")),
               db: Session = Depends(get_db)):
    return _draft_out(db, _get_draft(db, member, draft_id), member)


@router.patch(BASE + "/job-drafts/{draft_id}")
def patch_draft(company_id: int, draft_id: int, body: DraftPatchIn,
                member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        patches = [item.model_dump(exclude_unset=True) for item in body.lines]
        return _draft_out(db, jd_studio.edit_lines(db, draft, patches, member.user_id))
    except jd_studio.JdStudioError as error:
        db.rollback()
        raise _translate(error) from error


@router.post(BASE + "/job-drafts/{draft_id}/assistant")
def assistant(company_id: int, draft_id: int, body: AssistantIn, member: CompanyMember = Depends(require_member("hr")),
              db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        result = jd_studio.revise(db, draft, body.message, member.user_id)
    except jd_studio.JdStudioError as error:
        db.rollback()
        raise _translate(error) from error
    return {**_draft_out(db, result.draft), "summary": result.summary, "needs_confirmation": result.needs_confirmation}


@router.post(BASE + "/job-drafts/{draft_id}/lines/{line_id}/confirm")
def confirm_line(company_id: int, draft_id: int, line_id: str, member: CompanyMember = Depends(require_member("hr")),
                 db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        return _draft_out(db, jd_studio.confirm_line(db, draft, line_id, member.user_id))
    except jd_studio.JdStudioError as error:
        db.rollback()
        raise _translate(error) from error


@router.post(BASE + "/job-drafts/{draft_id}/lint")
def rerun_lint(company_id: int, draft_id: int, member: CompanyMember = Depends(require_member("hr")),
               db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    lint.run(db, draft)
    return _draft_out(db, draft)


@router.post(BASE + "/job-drafts/{draft_id}/lint/acknowledge")
def acknowledge_unchecked(company_id: int, draft_id: int, body: AcknowledgeIn | None = None,
                          member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    lint.acknowledge_unchecked(db, draft, member.user_id, body.line_id if body else None)
    lint.run(db, draft)
    return _draft_out(db, draft)


def _publish_error(error: publishing.PublishError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.post(BASE + "/job-drafts/{draft_id}/submit")
def submit_draft(company_id: int, draft_id: int, member: CompanyMember = Depends(require_member("hr")),
                 db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        publishing.submit(db, draft, member.user_id)
    except publishing.PublishError as error:
        db.rollback()
        raise _publish_error(error) from error
    return _draft_out(db, draft)


@router.post(BASE + "/job-drafts/{draft_id}/approve")
def approve_draft(company_id: int, draft_id: int, body: DraftVersionIn,
                  member: CompanyMember = Depends(require_member("manager")), db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        publishing.approve(db, draft, member, body.version)
    except publishing.PublishError as error:
        db.rollback()
        raise _publish_error(error) from error
    return _draft_out(db, draft, member)


@router.post(BASE + "/job-drafts/{draft_id}/request-changes")
def request_changes(company_id: int, draft_id: int, body: RequestChangesIn,
                    member: CompanyMember = Depends(require_member("manager")), db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        publishing.request_changes(db, draft, member, body.comment)
    except publishing.PublishError as error:
        db.rollback()
        raise _publish_error(error) from error
    return _draft_out(db, draft, member)


@router.post(BASE + "/job-drafts/{draft_id}/publish")
def publish_draft(company_id: int, draft_id: int, body: DraftVersionIn,
                  member: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        job, warnings = publishing.publish(db, draft, member.user_id, body.version)
    except publishing.PublishError as error:
        db.rollback()
        raise _publish_error(error) from error
    return {**_draft_out(db, draft), "job": {"id": job.id, "slug": job.slug, "version": job.version,
                                              "status": job.status}, "warnings": warnings}


@router.get(BASE + "/job-drafts/{draft_id}/channels")
def read_channels(company_id: int, draft_id: int, member: CompanyMember = Depends(require_member("hr")),
                  db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        return {"channels": channels.read(db, draft)}
    except publishing.PublishError as error:
        raise _publish_error(error) from error


@router.post(BASE + "/job-drafts/{draft_id}/channels/generate")
def generate_channels(company_id: int, draft_id: int, member: CompanyMember = Depends(require_member("hr")),
                      db: Session = Depends(get_db)):
    draft = _get_draft(db, member, draft_id)
    try:
        return {"channels": channels.generate(db, draft, member.user_id)}
    except publishing.PublishError as error:
        db.rollback()
        raise _publish_error(error) from error
