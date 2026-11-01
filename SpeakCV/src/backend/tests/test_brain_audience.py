import pytest

from app.brain import audience as aud
from app.database.sql_models import Company, CompanyMember, Department, KbDocument, KbNode
from tests.helpers import make_user


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme")
    other = Company(slug="other", name="Other")
    db.add_all([company, other])
    db.commit()
    eng = Department(company_id=company.id, name="Engineering")
    db.add(eng)
    db.commit()
    backend = Department(company_id=company.id, parent_id=eng.id, name="Backend")
    sales = Department(company_id=company.id, name="Sales")
    db.add_all([backend, sales])
    db.commit()

    def node(title, visibility, department_id=None, status="published", company_id=company.id):
        row = KbNode(company_id=company_id, department_id=department_id, type="fact", title=title,
                     language="en", visibility=visibility, status=status)
        db.add(row)
        return row

    node("public", "public")
    node("internal", "internal")
    node("conf-backend", "confidential", backend.id)
    node("conf-sales", "confidential", sales.id)
    node("conf-companywide", "confidential")
    node("draft-public", "public", status="draft")
    node("other-company", "public", company_id=other.id)
    db.commit()
    return {"company": company, "eng": eng, "backend": backend, "sales": sales}


def titles(db, a):
    rows = db.query(KbNode).filter(aud.node_filter(a)).all()
    return {row.title for row in rows}


def _member(db, world, role, department_id=None):
    user = make_user(db, f"{role}{department_id}@example.test")
    member = CompanyMember(company_id=world["company"].id, user_id=user.id, role=role, department_id=department_id)
    db.add(member)
    db.commit()
    return member


def test_candidate_reads_only_public(db, world):
    assert titles(db, aud.candidate(world["company"].id)) == {"public"}


def test_employee_reads_public_and_internal(db, world):
    assert titles(db, aud.for_member(db, _member(db, world, "employee"))) == {"public", "internal"}


def test_manager_reads_confidential_in_their_subtree_only(db, world):
    a = aud.for_member(db, _member(db, world, "manager", world["eng"].id))
    assert titles(db, a) == {"public", "internal", "conf-backend"}


def test_manager_without_a_department_sees_no_confidential(db, world):
    assert titles(db, aud.for_member(db, _member(db, world, "manager"))) == {"public", "internal"}


def test_hr_reads_all_published_in_this_company(db, world):
    expected = {"public", "internal", "conf-backend", "conf-sales", "conf-companywide"}
    assert titles(db, aud.for_member(db, _member(db, world, "hr"))) == expected


def test_view_as_goes_through_the_same_rules(db, world):
    assert titles(db, aud.simulated(db, world["company"].id, "candidate", None)) == {"public"}
    assert titles(db, aud.simulated(db, world["company"].id, "manager", world["sales"].id)) == {"public", "internal", "conf-sales"}


def test_view_as_rejects_an_unknown_audience(db, world):
    with pytest.raises(ValueError):
        aud.simulated(db, world["company"].id, "root", None)


def test_view_as_rejects_a_department_from_another_company(db, world):
    other_dept = Department(company_id=world["company"].id + 1, name="Elsewhere")
    db.add(other_dept)
    db.commit()
    with pytest.raises(ValueError):
        aud.simulated(db, world["company"].id, "manager", other_dept.id)


def test_visible_node_ids_query_matches_filter(db, world):
    a = aud.candidate(world["company"].id)
    ids = {r[0] for r in db.execute(aud.visible_node_ids_query(db, a)).all()}
    assert ids == {r.id for r in db.query(KbNode).filter(aud.node_filter(a)).all()}


def test_document_filter_decides_on_real_rows_for_every_kind(db, world):
    company_id = world["company"].id
    backend, sales = world["backend"].id, world["sales"].id

    def document(title, visibility, department_id=None, status="published", owner=company_id):
        db.add(KbDocument(company_id=owner, department_id=department_id, title=title, language="en",
                          visibility=visibility, status=status))

    document("public", "public")
    document("internal", "internal")
    document("conf-backend", "confidential", backend)
    document("conf-sales", "confidential", sales)
    document("conf-companywide", "confidential")
    document("review-public", "public", status="review")
    document("other-company", "public", owner=company_id + 1)
    db.commit()

    def seen(audience):
        return {row.title for row in db.query(KbDocument).filter(aud.document_filter(audience)).all()}

    everyone = {"public"}
    staff = everyone | {"internal"}
    assert seen(aud.Audience(company_id, "candidate")) == everyone
    assert seen(aud.Audience(company_id, "employee")) == staff
    assert seen(aud.Audience(company_id, "manager")) == staff
    assert seen(aud.Audience(company_id, "manager", frozenset({backend}))) == staff | {"conf-backend"}
    assert seen(aud.Audience(company_id, "hr")) == staff | {"conf-backend", "conf-sales", "conf-companywide"}
