"""A small company graph for the JD Studio tests."""
import json
from types import SimpleNamespace

from app.ai import gateway
from app.brain import vectors
from app.database.sql_models import (
    Company, CompanyMember, Department, HiringRequest, JobDraft, KbChunk, KbDocument, KbEdge, KbNode, KbNodeSource,
)
from tests.helpers import make_user

CANARY = "CANARY-CONFIDENTIAL-NOTE-5521"
CHUNK_CANARY = "CANARY-CHUNK-SOURCING-CONFIDENTIAL-8842"
POLICY_CANARY = "CANARY-INTERNAL-POLICY-3310"


class Builder:
    def __init__(self, db, company_id):
        self.db = db
        self.company_id = company_id

    def node(self, title, body="", type="fact", visibility="public", status="published", department_id=None,
             fact_kind=None, fact_value=None, fact_unit=None, company_id=None):
        company_id = company_id or self.company_id
        result = gateway.embed([f"{title}\n{body}"], "document", "test_setup", company_id)
        row = KbNode(company_id=company_id, department_id=department_id, type=type, title=title, body=body,
                     language="en", visibility=visibility, status=status, fact_kind=fact_kind,
                     fact_value=fact_value, fact_unit=fact_unit, embedding=vectors.encode(result.vectors[0]),
                     embedding_model=result.model, embedding_dim=result.dimension)
        self.db.add(row)
        self.db.commit()
        return row

    def edge(self, source, target, relation, must_have=None):
        self.db.add(KbEdge(company_id=self.company_id, source_node_id=source.id, target_node_id=target.id,
                           relation=relation, must_have=must_have, status="published"))
        self.db.commit()


def make_world(db, with_leave_fact=True):
    company = Company(slug="acme", name="Acme")
    other = Company(slug="other", name="Other")
    db.add_all([company, other])
    db.commit()
    eng = Department(company_id=company.id, name="Engineering")
    sales = Department(company_id=company.id, name="Sales")
    db.add_all([eng, sales])
    db.commit()

    b = Builder(db, company.id)
    company_node = b.node("Acme", type="company")
    dept_node = b.node("Engineering", type="department", department_id=eng.id)
    b.edge(dept_node, company_node, "part_of")
    role = b.node("Backend Developer", "Builds the APIs of our hiring platform", type="role", department_id=eng.id)
    b.edge(dept_node, role, "has_role")
    python = b.node("Python experience", "Needs 3 years of Python experience", type="requirement")
    docker = b.node("Docker", "Builds and ships containers", type="skill")
    b.edge(role, python, "requires", must_have=True)
    b.edge(role, docker, "requires", must_have=False)
    leave = None
    if with_leave_fact:
        leave = b.node("Employees get 12 days of annual leave", "", type="fact",
                       fact_kind="number", fact_value="12", fact_unit="days")
    internal = b.node("Remote policy", f"Remote work needs approval {POLICY_CANARY}", type="policy",
                      visibility="internal")
    note = b.node("Pay note", f"The salary band is secret {CANARY}", type="private_note",
                  visibility="confidential", department_id=eng.id)
    b.edge(role, note, "has_note")

    careers = KbDocument(company_id=company.id, title="Careers page", language="en", visibility="public",
                         status="published")
    db.add(careers)
    db.commit()
    text = f"Backend Developer pay: {CHUNK_CANARY}"
    result = gateway.embed([text], "document", "test_setup", company.id)
    chunk = KbChunk(company_id=company.id, document_id=careers.id, position=0, text=text,
                    embedding=vectors.encode(result.vectors[0]), embedding_model=result.model,
                    embedding_dim=result.dimension)
    db.add(chunk)
    db.commit()
    db.add(KbNodeSource(node_id=note.id, chunk_id=chunk.id, quote="pay"))
    db.commit()

    hr = make_user(db, "hr@acme.test")
    manager = make_user(db, "mgr@acme.test")
    other_manager = make_user(db, "mgr2@acme.test")
    outsider = make_user(db, "hr@other.test")
    db.add_all([
        CompanyMember(company_id=company.id, user_id=hr.id, role="hr"),
        CompanyMember(company_id=company.id, user_id=manager.id, role="manager", department_id=eng.id),
        CompanyMember(company_id=company.id, user_id=other_manager.id, role="manager", department_id=sales.id),
        CompanyMember(company_id=other.id, user_id=outsider.id, role="hr"),
    ])
    request = HiringRequest(company_id=company.id, department_id=eng.id, title="Backend Developer",
                            manager_user_id=manager.id, created_by=hr.id)
    db.add(request)
    db.commit()
    return SimpleNamespace(
        company=company, other=other, eng=eng, sales=sales, role=role, python=python, docker=docker, leave=leave,
        internal=internal, note=note, hr=hr, manager=manager, other_manager=other_manager, outsider=outsider,
        request=request, builder=b,
    )


def line(line_id, sources, en="Line", vi="Dong", ko="Jul", is_requirement=False, must_have=False, **extra):
    return {"id": line_id, "text": {"en": en, "vi": vi, "ko": ko}, "source_node_ids": list(sources),
            "hr_confirmed": None, "is_requirement": is_requirement, "must_have": must_have,
            "conflict_dismissed": [], **extra}


def make_draft(db, company_id, lines, request_id=None, status="draft"):
    draft = JobDraft(company_id=company_id, hiring_request_id=request_id, version=1, lines=lines,
                     requirement_lines=[], lint=[], failed_languages=[], status=status)
    db.add(draft)
    db.commit()
    return draft


def ai_line(line_id, sources, en="Line", vi="Dong", ko="Jul", is_requirement=False, must_have=False):
    return {"id": line_id, "en": en, "vi": vi, "ko": ko, "source_node_ids": list(sources),
            "is_requirement": is_requirement, "must_have": must_have}


def generate_json(lines):
    return json.dumps({"lines": lines}, ensure_ascii=False)


def assistant_json(lines, summary="Done", proposals=()):
    return json.dumps({"lines": lines, "summary": summary, "proposals": list(proposals)}, ensure_ascii=False)
