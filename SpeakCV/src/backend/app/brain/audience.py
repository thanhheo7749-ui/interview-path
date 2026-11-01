from dataclasses import dataclass, field

from sqlalchemy import and_, or_, select, true
from sqlalchemy.orm import Session

from app.database.sql_models import CompanyMember, Department, KbDocument, KbNode

KINDS = ("candidate", "employee", "manager", "hr")


@dataclass(frozen=True)
class Audience:
    company_id: int
    kind: str
    department_ids: frozenset[int] = field(default_factory=frozenset)


def department_subtree(db: Session, company_id: int, department_id: int | None) -> frozenset[int]:
    if department_id is None:
        return frozenset()
    rows = db.query(Department.id, Department.parent_id).filter(Department.company_id == company_id).all()
    children: dict[int | None, list[int]] = {}
    for dept_id, parent_id in rows:
        children.setdefault(parent_id, []).append(dept_id)
    if department_id not in {dept_id for dept_id, _ in rows}:
        return frozenset()
    found, stack = set(), [department_id]
    while stack:
        current = stack.pop()
        if current not in found:
            found.add(current)
            stack.extend(children.get(current, []))
    return frozenset(found)


def candidate(company_id: int) -> Audience:
    return Audience(company_id=company_id, kind="candidate")


def for_member(db: Session, member: CompanyMember) -> Audience:
    departments = frozenset()
    if member.role == "manager":
        departments = department_subtree(db, member.company_id, member.department_id)
    return Audience(company_id=member.company_id, kind=member.role, department_ids=departments)


def simulated(db: Session, company_id: int, view_as: str, department_id: int | None) -> Audience:
    """HR-only view-as. Uses the same rules, read-only."""
    if view_as not in KINDS:
        raise ValueError(f"Unknown audience: {view_as}")
    departments = frozenset()
    if view_as == "manager" and department_id is not None:
        departments = department_subtree(db, company_id, department_id)
        if not departments:
            raise ValueError("That department is not in this company")
    return Audience(company_id=company_id, kind=view_as, department_ids=departments)


def _layer_filter(audience: Audience, visibility_column, department_column):
    if audience.kind == "hr":
        return true()
    if audience.kind == "manager":
        return or_(
            visibility_column.in_(("public", "internal")),
            and_(visibility_column == "confidential", department_column.in_(audience.department_ids)),
        )
    if audience.kind == "employee":
        return visibility_column.in_(("public", "internal"))
    return visibility_column == "public"


def node_filter(audience: Audience):
    return and_(
        KbNode.company_id == audience.company_id,
        KbNode.status == "published",
        _layer_filter(audience, KbNode.visibility, KbNode.department_id),
    )


def document_filter(audience: Audience):
    return and_(
        KbDocument.company_id == audience.company_id,
        KbDocument.status == "published",
        _layer_filter(audience, KbDocument.visibility, KbDocument.department_id),
    )


def visible_node_ids_query(db: Session, audience: Audience):
    """Select of node ids the audience may read; filtering happens in SQL."""
    return select(KbNode.id).where(node_filter(audience))
