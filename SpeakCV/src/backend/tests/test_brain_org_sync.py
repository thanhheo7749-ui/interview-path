import pytest

from app.brain import org_sync
from app.database.sql_models import Company, CompanyMember, KbEdge, KbNode
from tests.helpers import auth_header, make_user


@pytest.fixture
def setup(db):
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    user = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    return company, auth_header("hr@example.test")


def nodes(db, company, type_):
    db.expire_all()
    return db.query(KbNode).filter_by(company_id=company.id, type=type_).all()


def make_dept(client, company, headers, name, parent_id=None):
    response = client.post(
        f"/api/companies/{company.id}/departments", json={"name": name, "parent_id": parent_id}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_sync_creates_company_node_once(db, setup):
    company, _ = setup
    org_sync.sync_org_nodes(db, company.id)
    org_sync.sync_org_nodes(db, company.id)
    [node] = nodes(db, company, "company")
    assert (node.title, node.status, node.visibility) == ("Acme", "published", "public")


def test_departments_get_nodes_and_part_of_edges(client, db, setup):
    company, headers = setup
    parent = make_dept(client, company, headers, "Eng")
    child = make_dept(client, company, headers, "Platform", parent)
    by_dept = {n.department_id: n for n in nodes(db, company, "department")}
    assert set(by_dept) == {parent, child}
    assert all(n.status == "published" and n.visibility == "public" for n in by_dept.values())
    [company_node] = nodes(db, company, "company")
    edges = {(e.source_node_id, e.target_node_id): e for e in db.query(KbEdge).filter_by(relation="part_of")}
    assert set(edges) == {(by_dept[parent].id, company_node.id), (by_dept[child].id, by_dept[parent].id)}
    assert all(e.status == "published" for e in edges.values())


def test_rename_updates_title_and_move_updates_edge(client, db, setup):
    company, headers = setup
    a = make_dept(client, company, headers, "A")
    b = make_dept(client, company, headers, "B")
    client.patch(
        f"/api/companies/{company.id}/departments/{a}", json={"name": "Alpha", "parent_id": b}, headers=headers
    )
    by_dept = {n.department_id: n for n in nodes(db, company, "department")}
    assert by_dept[a].title == "Alpha"
    edge = db.query(KbEdge).filter_by(source_node_id=by_dept[a].id).one()
    assert edge.target_node_id == by_dept[b].id


def test_delete_marks_node_superseded(client, db, setup):
    company, headers = setup
    a = make_dept(client, company, headers, "A")
    assert client.delete(f"/api/companies/{company.id}/departments/{a}", headers=headers).status_code == 204
    [node] = nodes(db, company, "department")
    assert node.status == "superseded"


def test_kb_version_increases_only_on_change(client, db, setup):
    company, headers = setup

    def version():
        db.expire_all()
        return db.get(Company, company.id).kb_version

    org_sync.sync_org_nodes(db, company.id)
    first = version()
    assert first > 0
    org_sync.sync_org_nodes(db, company.id)
    assert version() == first
    make_dept(client, company, headers, "A")
    assert version() > first
