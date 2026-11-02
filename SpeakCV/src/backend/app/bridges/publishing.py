"""Approval and publishing of a job draft.

HR submits, the manager assigned to the draft's request approves, or sends it back with a comment, and HR publishes. A
draft with no request goes to the managers of its department. Lint is re-run at submit and at publish, because an
approval only covers the text that was approved: any edit returns the draft to "draft"."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.brain import audience as aud
from app.brain import retriever
from app.bridges import jd_studio, lint
from app.bridges.lint import LANGS
from app.database.sql_models import (
    ChannelContent, Company, CompanyMember, HiringRequest, Job, JobDraft, JobDraftMessage, KbNode,
)
from app.hiring import audit, jobs

FALLBACK_LANG = "en"
MAX_TITLE = 255


class PublishError(ValueError):
    """Carries an HTTP status and a detail (text, or a dict with the lint issues)."""

    def __init__(self, status_code: int, detail):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def department_id(db: Session, draft: JobDraft) -> int | None:
    """The department a draft belongs to: its request's, else the department of the role it cites."""
    if draft.hiring_request_id:
        request = db.query(HiringRequest).filter(HiringRequest.id == draft.hiring_request_id,
                                                 HiringRequest.company_id == draft.company_id).first()
        return request.department_id if request else None
    cited = {i for item in draft.lines or [] for i in item.get("source_node_ids") or []}
    nodes = retriever.visible_graph(db, aud.Audience(draft.company_id, "hr"))[0]
    return next((n.department_id for n in nodes if n.id in cited and n.type == "role"), None)


def _request_of(db: Session, draft: JobDraft) -> HiringRequest | None:
    if draft.hiring_request_id is None:
        return None
    return db.query(HiringRequest).filter(HiringRequest.id == draft.hiring_request_id,
                                          HiringRequest.company_id == draft.company_id).first()


def manages(db: Session, draft: JobDraft, member: CompanyMember) -> bool:
    """A request's drafts belong to its assigned manager, whatever their department. A draft with no request belongs to
    the managers of the department of the role it cites."""
    if draft.hiring_request_id is not None:
        request = _request_of(db, draft)
        return request is not None and request.manager_user_id == member.user_id
    department = department_id(db, draft)
    return department is not None and department in aud.department_subtree(db, draft.company_id, member.department_id)


def _check_not_cancelled(request: HiringRequest | None) -> None:
    if request is not None and request.status == "cancelled":
        raise PublishError(409, "The hiring request of this draft was cancelled.")


def default_language(company: Company) -> str:
    locale = (company.default_locale or "").lower().split("-")[0]
    return locale if locale in LANGS else FALLBACK_LANG


def line_in(item: dict, lang: str) -> str:
    """A line in one language, falling back to the first language it has."""
    return ((item.get("text") or {}).get(lang) or "").strip() or lint.primary_text(item)


def _blockers(draft: JobDraft) -> dict | None:
    issues = [i for i in draft.lint or [] if i["severity"] == lint.BLOCK]
    failed = jd_studio._failed_languages(draft.lines or [])
    if draft.lines and not issues and not failed:
        return None
    parts = []
    if not draft.lines:
        parts.append("The draft has no lines.")
    if issues:
        parts.append("Lint blocks this draft.")
    if failed:
        parts.append(f"These languages are incomplete: {', '.join(failed)}.")
    return {"message": " ".join(parts), "issues": issues, "failed_languages": failed}


def _check_clean(db: Session, draft: JobDraft) -> None:
    lint.run(db, draft)
    blockers = _blockers(draft)
    if blockers is not None:
        raise PublishError(409, blockers)


def submit(db: Session, draft: JobDraft, user_id: int) -> JobDraft:
    if draft.status != "draft":
        raise PublishError(409, f"A draft in status {draft.status} cannot be submitted.")
    _check_not_cancelled(_request_of(db, draft))
    version = draft.version
    _check_clean(db, draft)
    lint.lock_row(db, draft)
    if draft.version != version or draft.status != "draft":
        raise PublishError(409, "The draft changed while it was being checked. Please try again.")
    _check_not_cancelled(_request_of(db, draft))
    draft.status = "manager_review"
    if draft.submitted_at is None:
        draft.submitted_at = datetime.now(timezone.utc)
    audit.record(db, draft.company_id, user_id, "job_draft.submitted", "job_draft", draft.id, {"version": draft.version})
    db.commit()
    return draft


def _lock_for_manager(db: Session, draft: JobDraft, member: CompanyMember) -> None:
    lint.lock_row(db, draft)
    if not manages(db, draft, member):
        raise PublishError(404, "Draft not found")
    if draft.status != "manager_review":
        raise PublishError(409, "Only a draft submitted for review can be approved or sent back.")


def approve(db: Session, draft: JobDraft, member: CompanyMember, version: int) -> JobDraft:
    """The approver approves the version they read: `version` is the one their page shows."""
    _lock_for_manager(db, draft, member)
    if draft.version != version:
        raise PublishError(409, "The draft changed since you read it. Please read it again.")
    _check_not_cancelled(_request_of(db, draft))
    draft.status = "approved"
    draft.approved_by = member.user_id
    audit.record(db, draft.company_id, member.user_id, "job_draft.approved", "job_draft", draft.id,
                 {"version": draft.version})
    db.commit()
    return draft


def request_changes(db: Session, draft: JobDraft, member: CompanyMember, comment: str) -> JobDraft:
    """The approver sends the draft back to HR with a comment, which HR reads in JD Studio. The assistant never reads it."""
    _lock_for_manager(db, draft, member)
    draft.status = "draft"
    feedback = JobDraftMessage(company_id=draft.company_id, job_draft_id=draft.id, role=jd_studio.MANAGER_FEEDBACK,
                               content=comment, created_by=member.user_id)
    db.add(feedback)
    db.flush()
    audit.record(db, draft.company_id, member.user_id, "job_draft.changes_requested", "job_draft", draft.id,
                 {"version": draft.version, "message_id": feedback.id})
    db.commit()
    return draft


def _requirements(db: Session, draft: JobDraft, lang: str) -> list[dict]:
    """Requirements from the requirement lines. node_id is the first source, when it is a node of this company."""
    cited = [i for item in draft.lines or [] for i in item.get("source_node_ids") or []]
    real = {row.id for row in db.query(KbNode.id).filter(KbNode.company_id == draft.company_id, KbNode.id.in_(cited))}
    result = []
    for item in draft.lines or []:
        if item.get("is_requirement"):
            sources = item.get("source_node_ids") or []
            result.append({"text": line_in(item, lang), "must_have": bool(item.get("must_have")),
                           "visibility": "public", "node_id": sources[0] if sources and sources[0] in real else None})
    return result


def _description(draft: JobDraft, lang: str) -> str:
    return "\n".join(text for item in draft.lines or [] if (text := line_in(item, lang)))


def _role_node_id(db: Session, draft: JobDraft) -> int | None:
    cited = jd_studio._cited_ids(draft)
    nodes = {n.id: n for n in retriever.visible_graph(db, aud.Audience(draft.company_id, "hr"))[0]}
    return next((i for i in cited if i in nodes and nodes[i].type == "role"), None)


def _existing_job(db: Session, draft: JobDraft, request: HiringRequest | None, lock: bool = False) -> Job | None:
    job_id = draft.job_id or (request.job_id if request else None)
    if job_id is None:
        return None
    query = db.query(Job).filter(Job.id == job_id, Job.company_id == draft.company_id)
    job = (query.populate_existing().with_for_update() if lock else query).first()
    if job is None:
        raise PublishError(404, "The job of this draft no longer exists.")
    if job.status == "closed":
        raise PublishError(409, "A closed job cannot be published again.")
    return job


def _new_job(db: Session, draft: JobDraft, lang: str, user_id: int) -> Job:
    title = (jd_studio._draft_title(db, draft) or "Job")[:MAX_TITLE]
    job = Job(company_id=draft.company_id, department_id=department_id(db, draft),
              role_node_id=_role_node_id(db, draft), title=title, description="", status="draft", version=1,
              interview_languages=[lang], created_by=user_id)
    db.add(job)
    db.flush()
    return job


def _lock_for_publish(db: Session, draft: JobDraft, version: int) -> HiringRequest | None:
    """Take the draft's row after the AI calls, and its request's, and read them as they are now. Raises PublishError(409)
    if the draft was edited during the calls: what was checked is no longer what it says. A publish that got here first
    has left a job on them, which the caller reuses."""
    request_id = draft.hiring_request_id
    lint.lock_row(db, draft)
    if draft.version != version or draft.status not in ("approved", "published"):
        raise PublishError(409, "The draft changed while it was being checked. Please try again.")
    if request_id is None:
        return None
    return db.query(HiringRequest).filter(HiringRequest.id == request_id, HiringRequest.company_id == draft.company_id) \
        .populate_existing().with_for_update().first()


def publish(db: Session, draft: JobDraft, user_id: int, version: int) -> tuple[Job, list[str]]:
    """Create or update the job from an approved draft. Returns the job and the requirement warnings. `version` is the one
    the page shows, so what goes out is what HR looked at.

    job.version rises only when the requirements changed, so an application in progress keeps its version."""
    if draft.status != "approved":
        raise PublishError(409, "The manager must approve the draft before it is published.")
    if draft.version != version:
        raise PublishError(409, "The draft changed since you read it. Please read it again.")
    _check_not_cancelled(_request_of(db, draft))
    _check_clean(db, draft)
    company = db.get(Company, draft.company_id)
    request = _request_of(db, draft)
    lang = default_language(company)
    try:
        job = _existing_job(db, draft, request)
        requirements = _requirements(db, draft, lang)
        # Before the first write: this can call the AI, and a vendor call must not hold locks.
        checked = jobs.check_requirements(db, draft.company_id, job.id if job else None, requirements)
        request = _lock_for_publish(db, draft, version)
        _check_not_cancelled(request)
        job = _existing_job(db, draft, request, lock=True) or _new_job(db, draft, lang, user_id)
        job.description = _description(draft, lang)
        warnings = jobs.update_requirements(db, job, requirements, checked)
        if job.status == "draft":
            warnings = [*warnings, *jobs.publish(db, job, company)]
    except jobs.JobError as error:
        db.rollback()
        raise PublishError(error.status_code, error.detail) from error
    except PublishError:
        db.rollback()
        raise
    # Channel content was written from the lines of the version before: it is not served again, and HR regenerates it.
    db.query(ChannelContent).filter(ChannelContent.job_draft_id == draft.id,
                                    ChannelContent.company_id == draft.company_id).delete(synchronize_session=False)
    draft.job_id = job.id
    draft.status = "published"
    if request is not None:
        request.status = "published"
        request.job_id = job.id
    audit.record(db, draft.company_id, user_id, "job_draft.published", "job_draft", draft.id,
                 {"job_id": job.id, "job_version": job.version, "draft_version": draft.version})
    db.commit()
    return job, warnings
