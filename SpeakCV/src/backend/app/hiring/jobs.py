"""Job posting logic: versioned requirements, publishing and tracked channel links."""
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.brain import audience as aud
from app.brain import retriever
from app.bridges import discrimination
from app.database.sql_models import Company, Job, JobChannelLink, JobRequirement, RequirementResult


NO_PUBLIC_REQUIREMENT = "no_public_requirement"


class JobError(ValueError):
    """Carries an HTTP-friendly status so routers can translate it."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def active_requirements(db: Session, job_id: int) -> list[JobRequirement]:
    return (
        db.query(JobRequirement)
        .filter(JobRequirement.job_id == job_id, JobRequirement.active.is_(True))
        .order_by(JobRequirement.position, JobRequirement.id)
        .all()
    )


def requirements_for(db: Session, application) -> list[JobRequirement]:
    """What this application is measured against: the rows its results name, whatever the job has become since.

    A later edit makes new rows and leaves these alone, so it changes nothing for this application, and a requirement
    added later is not part of it. Only before the CV was assessed are there no results, and then the job's current
    rows apply."""
    named = db.query(RequirementResult.requirement_id).filter(RequirementResult.application_id == application.id)
    rows = (
        db.query(JobRequirement)
        .filter(JobRequirement.id.in_(named), JobRequirement.job_id == application.job_id)
        .order_by(JobRequirement.position, JobRequirement.id)
        .all()
    )
    return rows or active_requirements(db, application.job_id)


def scored_requirements(db: Session, application) -> list[JobRequirement]:
    """The requirements the interview asks about and its band measures: public only, the must-haves if there are any.

    A job with no public requirement gives an empty list, so its band is always `few`, and publishing it warns HR."""
    public = [row for row in requirements_for(db, application) if row.visibility == "public"]
    return [row for row in public if row.must_have] or public


def visible_requirements(db: Session, job_id: int, viewer: aud.Audience) -> list[JobRequirement]:
    """The job's current requirements that this audience may read."""
    return (
        db.query(JobRequirement)
        .join(Job, Job.id == JobRequirement.job_id)
        .filter(JobRequirement.job_id == job_id, JobRequirement.active.is_(True), aud.requirement_filter(viewer))
        .order_by(JobRequirement.position, JobRequirement.id)
        .all()
    )


def _key(text, must_have, visibility, node_id) -> tuple:
    return (text, bool(must_have), visibility, node_id)


def _field(item, name, default=None):
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _active_by_key(db: Session, job_id: int | None) -> dict[tuple, list[JobRequirement]]:
    unmatched: dict[tuple, list[JobRequirement]] = {}
    if job_id is not None:
        for row in active_requirements(db, job_id):
            unmatched.setdefault(_key(row.text, row.must_have, row.visibility, row.node_id), []).append(row)
    return unmatched


@dataclass(frozen=True)
class CheckedRequirements:
    """The result of check_requirements, which update_requirements needs before it writes."""

    texts: frozenset[str]
    warnings: list[str]


def check_requirements(db: Session, company_id: int, job_id: int | None, items) -> CheckedRequirements:
    """Check the text of every row that update_requirements would add. Pass job_id None for a job not created yet.

    This can call the AI, so run it before the request's first write: a vendor call must not hold locks. Raises
    JobError(422) for a requirement that asks for a protected trait. Its warnings name texts the automatic check could
    not look at: HR typed them, so they are not blocked."""
    remaining = {key: len(rows) for key, rows in _active_by_key(db, job_id).items()}
    warnings = []
    texts = set()
    for item in items:
        key = _key(_field(item, "text"), _field(item, "must_have", False), _field(item, "visibility", "public"),
                   _field(item, "node_id"))
        if remaining.get(key):
            remaining[key] -= 1
            continue
        result = discrimination.check(key[0], company_id)
        texts.add(key[0])
        if result is None:
            continue
        if result.unchecked:
            warnings.append(f"The discrimination check could not run for: {key[0][:80]}")
        else:
            raise JobError(422, f"Requirement not allowed ({result.category}): {result.reason}")
    return CheckedRequirements(frozenset(texts), warnings)


def update_requirements(db: Session, job: Job, items, checked: CheckedRequirements) -> list[str]:
    """Unchanged rows stay, removed or changed rows go inactive, new rows are added. Any difference bumps version once.

    Old rows are kept (inactive) so results that point at them stay valid. Calls no AI: `checked` comes from
    check_requirements. Raises JobError(409) when a row to add was not checked, because another request changed the
    job's requirements after the check, and the caller rolls back. Returns the warnings of the check.
    """
    existing_any = db.query(JobRequirement.id).filter(JobRequirement.job_id == job.id).first() is not None
    unmatched = _active_by_key(db, job.id)

    changed = False
    for position, item in enumerate(items):
        key = _key(_field(item, "text"), _field(item, "must_have", False), _field(item, "visibility", "public"),
                   _field(item, "node_id"))
        matches = unmatched.get(key)
        if matches:
            matches.pop(0).position = position
        else:
            if key[0] not in checked.texts:
                raise JobError(409, "The requirements changed while they were being checked. Please try again.")
            changed = True
            db.add(JobRequirement(
                company_id=job.company_id, job_id=job.id, node_id=key[3], text=key[0], must_have=key[1],
                visibility=key[2], position=position, active=True,
            ))
    for rows in unmatched.values():
        for row in rows:
            row.active = False
            changed = True
    # The first requirements a job ever gets are its initial state, not an edit.
    if changed and existing_any:
        job.version += 1
    db.flush()
    return checked.warnings


def prefill(db: Session, company_id: int, role_node_id: int) -> dict | None:
    """HR sees every layer, so confidential requirements are returned with their visibility for HR to review."""
    audience = aud.simulated(db, company_id, "hr", None)
    profile = retriever.role_profile(db, audience, role_node_id)
    if profile is None:
        return None
    return {
        "role_node_id": profile.role_node_id,
        "title": profile.title,
        "description": profile.body,
        "department_id": profile.department_id,
        "requirements": [
            {"text": item.body.strip() or item.title, "must_have": item.must_have,
             "visibility": item.visibility, "node_id": item.node_id}
            for item in profile.requirements
        ],
    }


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def publish(db: Session, job: Job, company: Company) -> list[str]:
    """Returns warning codes for HR. The portal words them."""
    if job.status != "draft":
        raise JobError(409, "Only a draft job can be published")
    if not (job.description or "").strip():
        raise JobError(422, "A job needs a description before it is published")
    requirements = active_requirements(db, job.id)
    if not requirements:
        raise JobError(422, "A job needs at least one requirement before it is published")
    base = _slugify(f"{company.slug} {job.title}")[:130].strip("-") or "job"
    slug = f"{base}-{secrets.token_hex(3)}"
    while db.query(Job.id).filter(Job.slug == slug).first() is not None:
        slug = f"{base}-{secrets.token_hex(4)}"
    job.slug = slug
    job.status = "published"
    job.published_at = datetime.now(timezone.utc)
    db.flush()
    return [] if any(row.visibility == "public" for row in requirements) else [NO_PUBLIC_REQUIREMENT]


def ensure_channels(db: Session, job: Job, channels: list[str]) -> list[JobChannelLink]:
    result = []
    for channel in dict.fromkeys(channels):
        link = db.query(JobChannelLink).filter_by(job_id=job.id, company_id=job.company_id, channel=channel).first()
        if link is None:
            link = JobChannelLink(company_id=job.company_id, job_id=job.id, channel=channel,
                                  token=secrets.token_urlsafe(16))
            db.add(link)
        result.append(link)
    db.flush()
    return result
