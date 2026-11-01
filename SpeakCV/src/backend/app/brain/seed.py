"""Seeds the two fictional sample companies through the real ingestion pipeline.

With the fake bulk slot the graph comes from the authored ground truth, not from AI extraction.
Everything under seed/sample_companies is invented. None of it is real company data.
"""
import os
import secrets
from datetime import date
from pathlib import Path

import yaml
from sqlalchemy import func

from app.ai.config import get_config
from app.brain import fake_demo, ingestion, org_sync
from app.database.database import SessionLocal
from app.database.sql_models import (
    Company, CompanyMember, Department, Job, KbConflict, KbDocument, KbEdge, KbIngestionJob, KbNode, User,
)

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "seed" / "sample_companies"
ORG_TYPES = ("company", "department")
EXTRACTION_DEFAULTS = {
    "body": "", "fact_kind": "none", "fact_value": "", "fact_unit": "", "scope_text": "", "effective_date": "",
}


class SeedError(RuntimeError):
    pass


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _fixture(truth: dict) -> tuple[list[dict], list[dict]]:
    nodes = []
    for item in truth.get("extraction", []):
        node = {**EXTRACTION_DEFAULTS, **item}
        node.setdefault("ref", node["title"])
        nodes.append(node)
    edges = [{"must_have": False, **edge} for edge in truth.get("edges", [])]
    return nodes, edges


class _Passwords:
    """One hash per run, so seeding stays fast. The generated password is printed once and never stored in clear."""

    def __init__(self):
        self.configured = os.environ.get("SAMPLE_USER_PASSWORD", "").strip()
        self.generated: str | None = None
        self._hash: str | None = None

    def hashed(self) -> str:
        from app.auth.security import get_password_hash

        if self._hash is None:
            password = self.configured
            if not password:
                self.generated = password = secrets.token_urlsafe(12)
            self._hash = get_password_hash(password)
        return self._hash


def _ensure_company(db, spec: dict) -> Company:
    company = db.query(Company).filter(Company.slug == spec["slug"]).first()
    if company is None:
        company = Company(
            slug=spec["slug"], name=spec["name"], is_sample=True, default_locale=spec.get("default_locale", "en")
        )
        db.add(company)
        db.commit()
    elif not company.is_sample:
        raise SeedError(f"The company '{spec['slug']}' exists and is not a sample company. Refusing to touch it.")
    return company


def _ensure_departments(db, company: Company, specs: list[dict]) -> dict[str, Department]:
    by_name: dict[str, Department] = {}
    for spec in specs:
        parent = by_name.get(spec["parent"]) if spec.get("parent") else None
        if spec.get("parent") and parent is None:
            raise SeedError(f"Department '{spec['name']}' names the unknown parent '{spec['parent']}'.")
        parent_id = parent.id if parent else None
        department = db.query(Department).filter_by(company_id=company.id, parent_id=parent_id, name=spec["name"]).first()
        if department is None:
            department = Department(company_id=company.id, parent_id=parent_id, name=spec["name"])
            db.add(department)
            db.flush()
        by_name[spec["name"]] = department
    db.commit()
    return by_name


def _ensure_users(db, company: Company, specs: list[dict], departments, passwords: _Passwords) -> dict[str, User]:
    users: dict[str, User] = {}
    for spec in specs:
        email = spec["email"].strip().lower()
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if user is None:
            user = User(email=email, full_name=spec["name"], hashed_password=passwords.hashed())
            db.add(user)
            db.flush()
        member = db.query(CompanyMember).filter_by(company_id=company.id, user_id=user.id).first()
        if member is None:
            department = departments.get(spec.get("department")) if spec.get("department") else None
            db.add(CompanyMember(
                company_id=company.id, user_id=user.id, role=spec["role"],
                department_id=department.id if department else None,
            ))
        users[spec["role"]] = users.get(spec["role"], user)
    db.commit()
    return users


def _seed_company(db, folder: Path, passwords: _Passwords, auto_approve: bool, uses_fake_bulk: bool) -> dict:
    spec = _load_yaml(folder / "company.yaml")
    truth = _load_yaml(folder / "ground_truth.yaml")
    company = _ensure_company(db, spec)
    departments = _ensure_departments(db, company, spec.get("departments", []))
    users = _ensure_users(db, company, spec.get("users", []), departments, passwords)
    org_sync.sync_org_nodes(db, company.id)
    hr = users.get("hr")

    if uses_fake_bulk:
        fake_demo.load_extraction_fixture(*_fixture(truth))

    created = skipped = 0
    for entry in spec.get("documents", []):
        if db.query(KbDocument.id).filter_by(company_id=company.id, title=entry["title"]).first():
            skipped += 1
            continue
        department = departments.get(entry.get("department")) if entry.get("department") else None
        effective = entry.get("effective_date")
        document = ingestion.create_document(
            db, company.id, hr.id if hr else None, title=entry["title"],
            data=(folder / entry["file"]).read_bytes(), suffix=Path(entry["file"]).suffix,
            visibility=entry.get("visibility", "internal"), department_id=department.id if department else None,
            language=entry.get("language"), effective_date=date.fromisoformat(str(effective)) if effective else None,
        )
        job = ingestion.start_job(db, document.id)
        ingestion.run_job(job.id)
        created += 1

    if auto_approve:
        from app.brain.review import auto_approve_document

        # The pipeline wrote in another session. End this transaction so the query below sees all of it.
        db.commit()
        for document in db.query(KbDocument).filter_by(company_id=company.id, status="review").order_by(KbDocument.id).all():
            auto_approve_document(db, document.id, hr.id if hr else None)

    db.commit()
    _seed_job(db, company)
    return _summary(db, company, created, skipped)


def _seed_job(db, company: Company) -> None:
    """One published Backend Developer job per sample company. Skipped when the company already has a job."""
    from app.brain import audience as aud
    from app.brain import retriever
    from app.hiring import jobs

    # The pipeline wrote in another session. End this transaction so the reads below see it.
    db.commit()
    if db.query(Job.id).filter_by(company_id=company.id).first() is not None:
        return
    role = db.query(KbNode).filter_by(
        company_id=company.id, type="role", title="Backend Developer", status="published"
    ).order_by(KbNode.id).first()
    if role is None:
        return
    profile = retriever.role_profile(db, aud.simulated(db, company.id, "hr", None), role.id)
    if profile is None or not profile.requirements:
        return
    job = Job(
        company_id=company.id, department_id=role.department_id, role_node_id=role.id, title=role.title,
        description=role.body, status="draft", version=1, interview_languages=["vi", "en", "ko"],
    )
    db.add(job)
    db.flush()
    jobs.update_requirements(db, job, [
        {"text": item.body.strip() or item.title, "must_have": item.must_have, "visibility": item.visibility,
         "node_id": item.node_id}
        for item in profile.requirements
    ])
    jobs.publish(db, job, company)
    jobs.ensure_channels(db, job, ["company_site", "linkedin", "referral"])
    db.commit()


def _summary(db, company: Company, created: int, skipped: int) -> dict:
    live = KbNode.status.notin_(("rejected", "superseded"))
    document_ids = [row[0] for row in db.query(KbDocument.id).filter_by(company_id=company.id)]
    dropped = db.query(func.coalesce(func.sum(KbIngestionJob.dropped_items), 0)).filter(
        KbIngestionJob.document_id.in_(document_ids)
    ).scalar() if document_ids else 0
    return {
        "slug": company.slug,
        "documents_created": created,
        "documents_skipped": skipped,
        "nodes": db.query(KbNode).filter(KbNode.company_id == company.id, live, KbNode.type.notin_(ORG_TYPES)).count(),
        "published_nodes": db.query(KbNode).filter_by(company_id=company.id, status="published").count(),
        "edges": db.query(KbEdge).filter(KbEdge.company_id == company.id, KbEdge.status != "rejected").count(),
        "open_conflicts": db.query(KbConflict).filter_by(company_id=company.id, status="open").count(),
        "dropped_items": int(dropped or 0),
    }


def seed_samples(auto_approve: bool = False, only: str | None = None) -> list[dict]:
    folders = sorted(p for p in SAMPLES_DIR.iterdir() if (p / "company.yaml").is_file())
    if only:
        folders = [p for p in folders if p.name == only]
        if not folders:
            raise SeedError(f"No sample company '{only}'.")

    config = get_config()
    uses_fake_bulk = config.slot("bulk").provider == "fake"
    if uses_fake_bulk:
        fake_demo.install()

    passwords = _Passwords()
    results = []
    db = SessionLocal()
    try:
        for folder in folders:
            results.append(_seed_company(db, folder, passwords, auto_approve, uses_fake_bulk))
    finally:
        db.close()

    for result in results:
        print(
            f"{result['slug']}: {result['nodes']} nodes ({result['published_nodes']} published), {result['edges']} edges, "
            f"{result['open_conflicts']} open conflicts, {result['dropped_items']} dropped items, "
            f"{result['documents_created']} documents added, {result['documents_skipped']} already present."
        )
    print(f"AI provider for extraction: {config.slot('bulk').provider}; embeddings: {config.slot('embedding').provider}.")
    if uses_fake_bulk:
        print("The graph comes from authored ground truth, not from AI extraction.")
    if not auto_approve:
        print("Drafts are waiting in the review queue. Re-run with --auto-approve to publish them (sample companies only).")
    if passwords.generated:
        print(f"Generated sample user password (shown once): {passwords.generated}")
    return results
