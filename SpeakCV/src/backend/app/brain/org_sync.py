"""Keeps one company node and one department node per department, with part_of edges between them."""
from sqlalchemy.orm import Session

from app.database.sql_models import Company, Department, KbEdge, KbNode


def org_node_for(db: Session, company_id: int, department_id: int | None) -> KbNode | None:
    """The company node, or the node of one department. Superseded nodes are ignored."""
    query = db.query(KbNode).filter(KbNode.company_id == company_id, KbNode.status != "superseded")
    if department_id is None:
        return query.filter(KbNode.type == "company").first()
    return query.filter(KbNode.type == "department", KbNode.department_id == department_id).first()


def retire_department_node(db: Session, company_id: int, department_id: int) -> None:
    """Call before deleting a department. The node stays as history, detached from the deleted row."""
    node = org_node_for(db, company_id, department_id)
    if node is None:
        return
    node.status = "superseded"
    node.department_id = None
    company = db.get(Company, company_id)
    company.kb_version = (company.kb_version or 0) + 1


def _new_node(db: Session, company_id: int, type_: str, title: str, language: str, department_id) -> KbNode:
    node = KbNode(
        company_id=company_id, department_id=department_id, type=type_, title=title, body="",
        language=language, visibility="public", status="published",
    )
    db.add(node)
    db.flush()
    return node


def sync_org_nodes(db: Session, company_id: int) -> None:
    company = db.get(Company, company_id)
    if company is None:
        return
    language = company.default_locale or "en"
    changed = False

    company_node = org_node_for(db, company_id, None)
    if company_node is None:
        company_node = _new_node(db, company_id, "company", company.name, language, None)
        changed = True
    elif company_node.title != company.name:
        company_node.title = company.name
        changed = True

    departments = db.query(Department).filter(Department.company_id == company_id).order_by(Department.id).all()
    nodes: dict[int, KbNode] = {}
    for department in departments:
        node = org_node_for(db, company_id, department.id)
        if node is None:
            node = _new_node(db, company_id, "department", department.name, language, department.id)
            changed = True
        elif node.title != department.name:
            node.title = department.name
            changed = True
        nodes[department.id] = node

    for department in departments:
        node = nodes[department.id]
        parent = nodes.get(department.parent_id) if department.parent_id is not None else company_node
        parent = parent or company_node
        edges = db.query(KbEdge).filter(
            KbEdge.company_id == company_id, KbEdge.relation == "part_of", KbEdge.source_node_id == node.id
        ).all()
        if len(edges) == 1 and edges[0].target_node_id == parent.id and edges[0].status == "published":
            continue
        for edge in edges:
            db.delete(edge)
        db.add(KbEdge(
            company_id=company_id, source_node_id=node.id, target_node_id=parent.id,
            relation="part_of", status="published",
        ))
        changed = True

    if changed:
        company.kb_version = (company.kb_version or 0) + 1
    db.commit()
