"""Approval and publishing of a job draft.

HR submits, the manager of the draft's department approves, HR publishes. Lint is re-run at submit and at publish,
because an approval only covers the text that was approved: any edit returns the draft to "draft"."""
from sqlalchemy.orm import Session

from app.brain import audience as aud
from app.brain import retriever
from app.bridges import jd_studio, lint
from app.bridges.lint import LANGS
from app.database.sql_models import Company, CompanyMember, HiringRequest, Job, JobDraft, KbNode
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
    _check_clean(db, draft)
    draft.status = "manager_review"
    audit.record(db, draft.company_id, user_id, "job_draft.submitted", "job_draft", draft.id, {"version": draft.version})
    db.commit()
    return draft


def approve(db: Session, draft: JobDraft, member: CompanyMember) -> JobDraft:
    """Only a manager of the draft's department (or of a department above it) approves."""
    department = department_id(db, draft)
    if department is None or department not in aud.department_subtree(db, draft.company_id, member.department_id):
        raise PublishError(403, "Only the manager of this department can approve the draft.")
    if draft.status != "manager_review":
        raise PublishError(409, "Only a draft submitted for review can be approved.")
    draft.status = "approved"
    draft.approved_by = member.user_id
    audit.record(db, draft.company_id, member.user_id, "job_draft.approved", "job_draft", draft.id,
                 {"version": draft.version})
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


def _job_for(db: Session, draft: JobDraft, request: HiringRequest | None, lang: str, user_id: int) -> Job:
    job_id = draft.job_id or (request.job_id if request else None)
    if job_id is not None:
        job = db.query(Job).filter(Job.id == job_id, Job.company_id == draft.company_id).first()
        if job is None:
            raise PublishError(404, "The job of this draft no longer exists.")
        if job.status == "closed":
            raise PublishError(409, "A closed job cannot be published again.")
        return job
    title = (jd_studio._draft_title(db, draft) or "Job")[:MAX_TITLE]
    job = Job(company_id=draft.company_id, department_id=department_id(db, draft),
              role_node_id=_role_node_id(db, draft), title=title, description="", status="draft", version=1,
              interview_languages=[lang], created_by=user_id)
    db.add(job)
    db.flush()
    return job


def publish(db: Session, draft: JobDraft, user_id: int) -> tuple[Job, list[str]]:
    """Create or update the job from an approved draft. Returns the job and the requirement warnings.

    job.version rises only when the requirements changed, so an application in progress keeps its version."""
    if draft.status != "approved":
        raise PublishError(409, "The manager must approve the draft before it is published.")
    _check_clean(db, draft)
    company = db.get(Company, draft.company_id)
    request = None
    if draft.hiring_request_id:
        request = db.query(HiringRequest).filter(HiringRequest.id == draft.hiring_request_id,
                                                 HiringRequest.company_id == draft.company_id).first()
    lang = default_language(company)
    try:
        job = _job_for(db, draft, request, lang, user_id)
        job.description = _description(draft, lang)
        warnings = jobs.update_requirements(db, job, _requirements(db, draft, lang))
        if job.status == "draft":
            jobs.publish(db, job, company)
    except jobs.JobError as error:
        db.rollback()
        raise PublishError(error.status_code, error.detail) from error
    except PublishError:
        db.rollback()
        raise
    draft.job_id = job.id
    draft.status = "published"
    if request is not None:
        request.status = "published"
        request.job_id = job.id
    audit.record(db, draft.company_id, user_id, "job_draft.published", "job_draft", draft.id,
                 {"job_id": job.id, "job_version": job.version, "draft_version": draft.version})
    db.commit()
    return job, warnings
