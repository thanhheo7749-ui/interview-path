import pytest
from fastapi.testclient import TestClient

from app.database.sql_models import Company, CompanyMember, Department, User
from app.main import create_app
from tests.helpers import auth_header, make_user


@pytest.fixture
def api():
    return TestClient(create_app())


@pytest.fixture
def company(db):
    row = Company(slug="acme", name="Acme", is_sample=True)
    db.add(row)
    db.commit()
    return row.id


@pytest.fixture
def people(db, company):
    result = {}
    for role in ("hr", "manager", "employee"):
        user = make_user(db, f"{role}@example.test")
        db.add(CompanyMember(company_id=company, user_id=user.id, role=role))
        result[role] = auth_header(user.email)
    db.commit()
    return result


ENDPOINTS = [
    ("GET", "/api/companies/{c}", {"hr", "manager", "employee"}, 200),
    ("PATCH", "/api/companies/{c}", {"hr"}, 200),
    ("GET", "/api/companies/{c}/departments", {"hr", "manager", "employee"}, 200),
    ("POST", "/api/companies/{c}/departments", {"hr"}, 201),
    ("GET", "/api/companies/{c}/members", {"hr"}, 200),
]


@pytest.mark.parametrize("method,path,allowed,ok_status", ENDPOINTS)
def test_role_matrix(api, company, people, method, path, allowed, ok_status):
    for role, headers in people.items():
        body = {"name": f"Dept {role}"} if method == "POST" else {"name": f"Name {role}"} if method == "PATCH" else None
        response = api.request(method, path.format(c=company), headers=headers, json=body)
        assert response.status_code == (ok_status if role in allowed else 403), f"{role} {method} {path}"


def test_me_lists_memberships(api, company, people):
    body = api.get("/api/me", headers=people["hr"]).json()
    assert body["email"] == "hr@example.test"
    assert body["memberships"] == [
        {
            "member_id": body["memberships"][0]["member_id"],
            "company_id": company,
            "company_slug": "acme",
            "company_name": "Acme",
            "is_sample": True,
            "role": "hr",
            "department_id": None,
        }
    ]


def test_me_for_a_candidate_has_no_memberships(api, db):
    make_user(db, "cand@example.test")
    assert api.get("/api/me", headers=auth_header("cand@example.test")).json()["memberships"] == []


def test_patch_company_cannot_change_protected_fields(api, db, company, people):
    response = api.patch(
        f"/api/companies/{company}",
        headers=people["hr"],
        json={"name": "New", "slug": "hacked", "is_sample": False, "kb_version": 99},
    )
    assert response.status_code == 200
    db.expire_all()
    row = db.get(Company, company)
    assert (row.name, row.slug, row.is_sample, row.kb_version) == ("New", "acme", True, 0)


def test_department_tree_rules(api, company, people):
    url = f"/api/companies/{company}/departments"
    parent = api.post(url, headers=people["hr"], json={"name": "Engineering"}).json()
    child = api.post(url, headers=people["hr"], json={"name": "Backend", "parent_id": parent["id"]}).json()

    assert api.post(url, headers=people["hr"], json={"name": "Engineering"}).status_code == 409
    assert api.delete(f"{url}/{parent['id']}", headers=people["hr"]).status_code == 409

    assert api.patch(f"{url}/{parent['id']}", headers=people["hr"], json={"parent_id": child["id"]}).status_code == 409
    assert api.patch(f"{url}/{child['id']}", headers=people["hr"], json={"parent_id": child["id"]}).status_code == 409

    assert api.delete(f"{url}/{child['id']}", headers=people["hr"]).status_code == 204
    assert api.delete(f"{url}/{parent['id']}", headers=people["hr"]).status_code == 204


def test_department_parent_must_belong_to_this_company(api, db, company, people):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    foreign = Department(company_id=other.id, name="Foreign")
    db.add(foreign)
    db.commit()
    url = f"/api/companies/{company}/departments"
    assert api.post(url, headers=people["hr"], json={"name": "X", "parent_id": foreign.id}).status_code == 404
    assert api.patch(f"{url}/{foreign.id}", headers=people["hr"], json={"name": "Y"}).status_code == 404


def test_department_with_a_member_cannot_be_deleted(api, db, company, people):
    url = f"/api/companies/{company}/departments"
    dept = api.post(url, headers=people["hr"], json={"name": "Ops"}).json()
    members = api.get(f"/api/companies/{company}/members", headers=people["hr"]).json()
    employee = next(m for m in members if m["role"] == "employee")
    api.patch(f"/api/companies/{company}/members/{employee['id']}", headers=people["hr"], json={"department_id": dept["id"]})
    assert api.delete(f"{url}/{dept['id']}", headers=people["hr"]).status_code == 409


def test_add_member_for_a_new_email_creates_a_user_and_returns_the_password_once(api, db, company, people):
    url = f"/api/companies/{company}/members"
    response = api.post(url, headers=people["hr"], json={"email": "new@example.test", "full_name": "New", "role": "employee"})
    assert response.status_code == 201
    assert response.json()["temporary_password"]
    assert db.query(User).filter_by(email="new@example.test").count() == 1
    listed = api.get(url, headers=people["hr"]).json()
    assert all("temporary_password" not in row for row in listed)


def test_add_member_for_an_existing_user_never_touches_their_password(api, db, company, people):
    user = make_user(db, "exists@example.test")
    original_hash = user.hashed_password
    response = api.post(f"/api/companies/{company}/members", headers=people["hr"], json={"email": "exists@example.test", "role": "employee"})
    assert response.status_code == 201
    assert response.json()["temporary_password"] is None
    db.expire_all()
    assert db.get(User, user.id).hashed_password == original_hash


def test_add_member_twice_conflicts_and_bad_role_is_rejected(api, db, company, people):
    url = f"/api/companies/{company}/members"
    assert api.post(url, headers=people["hr"], json={"email": "employee@example.test", "role": "employee"}).status_code == 409
    assert api.post(url, headers=people["hr"], json={"email": "x@example.test", "role": "owner"}).status_code == 422


def test_removed_member_loses_access_immediately_with_the_same_token(api, company, people):
    headers = people["employee"]
    assert api.get(f"/api/companies/{company}", headers=headers).status_code == 200
    members = api.get(f"/api/companies/{company}/members", headers=people["hr"]).json()
    employee = next(m for m in members if m["role"] == "employee")
    assert api.delete(f"/api/companies/{company}/members/{employee['id']}", headers=people["hr"]).status_code == 204
    assert api.get(f"/api/companies/{company}", headers=headers).status_code == 403


def test_the_last_hr_cannot_be_removed_or_demoted(api, company, people):
    url = f"/api/companies/{company}/members"
    hr = next(m for m in api.get(url, headers=people["hr"]).json() if m["role"] == "hr")
    assert api.delete(f"{url}/{hr['id']}", headers=people["hr"]).status_code == 409
    assert api.patch(f"{url}/{hr['id']}", headers=people["hr"], json={"role": "employee"}).status_code == 409

    api.post(url, headers=people["hr"], json={"email": "hr2@example.test", "role": "hr"})
    assert api.patch(f"{url}/{hr['id']}", headers=people["hr"], json={"role": "employee"}).status_code == 200


def test_member_from_another_company_cannot_be_edited(api, db, company, people):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    stranger = make_user(db, "stranger@example.test")
    foreign = CompanyMember(company_id=other.id, user_id=stranger.id, role="employee")
    db.add(foreign)
    db.commit()
    url = f"/api/companies/{company}/members/{foreign.id}"
    assert api.patch(url, headers=people["hr"], json={"role": "hr"}).status_code == 404
    assert api.delete(url, headers=people["hr"]).status_code == 404


def test_deleted_user_with_a_valid_token_gets_401(api, db, company):
    ghost = make_user(db, "ghost@example.test")
    headers = auth_header(ghost.email)
    db.delete(ghost)
    db.commit()
    assert api.get(f"/api/companies/{company}", headers=headers).status_code == 401


@pytest.fixture
def foreign_department(db):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    row = Department(company_id=other.id, name="Foreign")
    db.add(row)
    db.commit()
    return row.id


def test_foreign_department_cannot_be_deleted_or_used_as_a_new_parent(api, db, company, people, foreign_department):
    url = f"/api/companies/{company}/departments"
    own = api.post(url, headers=people["hr"], json={"name": "Own"}).json()
    assert api.delete(f"{url}/{foreign_department}", headers=people["hr"]).status_code == 404
    assert api.patch(f"{url}/{own['id']}", headers=people["hr"], json={"parent_id": foreign_department}).status_code == 404
    db.expire_all()
    assert db.get(Department, foreign_department).name == "Foreign"
    assert db.get(Department, own["id"]).parent_id is None


def test_member_cannot_be_placed_in_a_foreign_department(api, db, company, people, foreign_department):
    url = f"/api/companies/{company}/members"
    created = api.post(url, headers=people["hr"], json={"email": "z@example.test", "role": "employee", "department_id": foreign_department})
    assert created.status_code == 404
    assert db.query(User).filter_by(email="z@example.test").count() == 0

    employee = next(m for m in api.get(url, headers=people["hr"]).json() if m["role"] == "employee")
    assert api.patch(f"{url}/{employee['id']}", headers=people["hr"], json={"department_id": foreign_department}).status_code == 404
    db.expire_all()
    assert db.get(CompanyMember, employee["id"]).department_id is None


def test_members_list_shows_only_this_company(api, db, company, people):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    stranger = make_user(db, "stranger@example.test")
    db.add(CompanyMember(company_id=other.id, user_id=stranger.id, role="hr"))
    db.commit()
    emails = {m["email"] for m in api.get(f"/api/companies/{company}/members", headers=people["hr"]).json()}
    assert "stranger@example.test" not in emails
    assert len(emails) == 3


def test_departments_list_shows_only_this_company(api, company, people, foreign_department):
    assert api.get(f"/api/companies/{company}/departments", headers=people["hr"]).json() == []


def test_a_member_of_two_companies_keeps_each_role_separate(api, db, company, people):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    employee = db.query(User).filter_by(email="employee@example.test").one()
    db.add(CompanyMember(company_id=other.id, user_id=employee.id, role="hr"))
    db.commit()
    assert api.get(f"/api/companies/{other.id}/members", headers=people["employee"]).status_code == 200
    assert api.get(f"/api/companies/{company}/members", headers=people["employee"]).status_code == 403


def test_patch_null_means_top_level_and_omitted_means_unchanged(api, db, company, people):
    url = f"/api/companies/{company}/departments"
    parent = api.post(url, headers=people["hr"], json={"name": "Parent"}).json()
    child = api.post(url, headers=people["hr"], json={"name": "Child", "parent_id": parent["id"]}).json()

    renamed = api.patch(f"{url}/{child['id']}", headers=people["hr"], json={"name": "Renamed"})
    assert renamed.json()["parent_id"] == parent["id"]
    moved = api.patch(f"{url}/{child['id']}", headers=people["hr"], json={"parent_id": None})
    assert moved.json() == {"id": child["id"], "company_id": company, "parent_id": None, "name": "Renamed"}


def test_explicit_null_on_a_required_field_changes_nothing(api, db, company, people):
    url = f"/api/companies/{company}"
    assert api.patch(url, headers=people["hr"], json={"name": None}).status_code == 200
    db.expire_all()
    assert db.get(Company, company).name == "Acme"

    dept = api.post(f"{url}/departments", headers=people["hr"], json={"name": "Ops"}).json()
    assert api.patch(f"{url}/departments/{dept['id']}", headers=people["hr"], json={"name": None}).json()["name"] == "Ops"

    members = api.get(f"{url}/members", headers=people["hr"]).json()
    employee = next(m for m in members if m["role"] == "employee")
    assert api.patch(f"{url}/members/{employee['id']}", headers=people["hr"], json={"role": None}).json()["role"] == "employee"


def test_a_sibling_name_clash_on_rename_or_move_conflicts(api, company, people):
    url = f"/api/companies/{company}/departments"
    parent = api.post(url, headers=people["hr"], json={"name": "Parent"}).json()
    top = api.post(url, headers=people["hr"], json={"name": "Same"}).json()
    other = api.post(url, headers=people["hr"], json={"name": "Other"}).json()
    nested = api.post(url, headers=people["hr"], json={"name": "Same", "parent_id": parent["id"]})
    assert nested.status_code == 201

    assert api.patch(f"{url}/{other['id']}", headers=people["hr"], json={"name": "Same"}).status_code == 409
    assert api.patch(f"{url}/{top['id']}", headers=people["hr"], json={"parent_id": parent["id"]}).status_code == 409
    assert api.patch(f"{url}/{top['id']}", headers=people["hr"], json={"name": "Same"}).status_code == 200


def test_add_member_normalises_the_email_and_rejects_a_blank_one(api, db, company, people):
    url = f"/api/companies/{company}/members"
    created = api.post(url, headers=people["hr"], json={"email": "  Mixed@Example.TEST ", "role": "employee"})
    assert created.status_code == 201
    assert created.json()["email"] == "mixed@example.test"
    assert api.post(url, headers=people["hr"], json={"email": "MIXED@example.test", "role": "employee"}).status_code == 409
    assert api.post(url, headers=people["hr"], json={"email": "     ", "role": "employee"}).status_code == 422
    assert db.query(User).filter_by(email="").count() == 0


def test_temporary_password_logs_in(api, company, people):
    url = f"/api/companies/{company}/members"
    password = api.post(url, headers=people["hr"], json={"email": "login@example.test", "role": "employee"}).json()["temporary_password"]
    login = api.post("/api/login", json={"email": "login@example.test", "password": password})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    refused = api.get(f"/api/companies/{company}", headers=headers)
    assert (refused.status_code, refused.json()["detail"]) == (403, "password_change_required")
    changed = api.post("/api/me/password", headers=headers, json={"current_password": password, "new_password": "my-own-password"})
    assert changed.status_code == 200
    assert api.get(f"/api/companies/{company}", headers=headers).status_code == 200


def test_an_invalid_token_gets_401(api, company):
    response = api.get(f"/api/companies/{company}", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_add_member_reports_whether_the_account_already_existed(api, db, company, people):
    url = f"/api/companies/{company}/members"
    fresh = api.post(url, headers=people["hr"], json={"email": "fresh@example.test", "role": "employee"}).json()
    assert fresh["existing_account"] is False
    make_user(db, "old@example.test")
    old = api.post(url, headers=people["hr"], json={"email": "old@example.test", "role": "employee"}).json()
    assert old["existing_account"] is True
    assert old["temporary_password"] is None


def _admin(db):
    make_user(db, "root@example.test", role="admin")
    return auth_header("root@example.test")


def test_admin_cannot_delete_the_only_hr_of_a_company(api, db, company, people):
    hr_user = db.query(User).filter_by(email="hr@example.test").one()
    response = api.delete(f"/api/admin/users/{hr_user.id}", headers=_admin(db))
    assert response.status_code == 409
    assert "Acme" in response.json()["detail"]
    assert db.query(User).filter_by(id=hr_user.id).count() == 1
    assert db.query(CompanyMember).filter_by(user_id=hr_user.id).count() == 1


def test_admin_deleting_a_user_removes_their_memberships(api, db, company, people):
    employee = db.query(User).filter_by(email="employee@example.test").one()
    uid = employee.id
    assert api.delete(f"/api/admin/users/{uid}", headers=_admin(db)).status_code == 200
    db.expire_all()
    assert db.query(User).filter_by(id=uid).count() == 0
    assert db.query(CompanyMember).filter_by(user_id=uid).count() == 0


def test_admin_can_delete_one_of_several_hr_members(api, db, company, people):
    other = make_user(db, "hr2@example.test")
    db.add(CompanyMember(company_id=company, user_id=other.id, role="hr"))
    db.commit()
    assert api.delete(f"/api/admin/users/{other.id}", headers=_admin(db)).status_code == 200


def test_emails_are_case_insensitive_across_register_login_and_members(api, db, company, people):
    assert api.post("/api/register", json={"email": "Foo@X.test", "password": "pw-1234567", "full_name": "Foo"}).status_code == 200
    assert api.post("/api/login", json={"email": "foo@x.test", "password": "pw-1234567"}).status_code == 200
    assert api.post("/api/login", json={"email": "FOO@x.test", "password": "pw-1234567"}).status_code == 200
    assert api.post("/api/register", json={"email": "foo@x.test", "password": "pw-1234567", "full_name": "Foo"}).status_code == 400
    added = api.post(f"/api/companies/{company}/members", headers=people["hr"], json={"email": "FOO@x.test", "role": "employee"})
    assert added.status_code == 201
    assert added.json()["existing_account"] is True
    assert db.query(User).filter(User.email.ilike("foo@x.test")).count() == 1


def test_existing_mixed_case_account_still_logs_in(api, db):
    from app.auth.security import get_password_hash
    db.add(User(email="Legacy@X.test", full_name="L", hashed_password=get_password_hash("pw-1234567")))
    db.commit()
    response = api.post("/api/login", json={"email": "legacy@x.test", "password": "pw-1234567"})
    assert response.status_code == 200
    assert api.get("/api/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}).status_code == 200


@pytest.mark.parametrize("field,blank", [("name", "   "), ("default_locale", "   ")])
def test_company_fields_blank_after_stripping_are_refused(api, company, people, field, blank):
    response = api.patch(f"/api/companies/{company}", headers=people["hr"], json={field: blank})
    assert response.status_code == 422


def test_company_name_and_locale_are_stripped(api, company, people):
    response = api.patch(f"/api/companies/{company}", headers=people["hr"], json={"name": "  Acme Two ", "default_locale": " vi "})
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["default_locale"]) == ("Acme Two", "vi")


def test_department_name_is_stripped_and_blank_is_refused(api, company, people):
    base = f"/api/companies/{company}/departments"
    assert api.post(base, headers=people["hr"], json={"name": "   "}).status_code == 422
    created = api.post(base, headers=people["hr"], json={"name": "  Sales "})
    assert created.json()["name"] == "Sales"
    assert api.patch(f"{base}/{created.json()['id']}", headers=people["hr"], json={"name": "  "}).status_code == 422


def test_member_name_is_stripped_and_blank_is_refused(api, company, people):
    base = f"/api/companies/{company}/members"
    assert api.post(base, headers=people["hr"], json={"email": "b@x.test", "role": "employee", "full_name": "  "}).status_code == 422
    created = api.post(base, headers=people["hr"], json={"email": "n@x.test", "role": "employee", "full_name": " Nam "})
    assert created.json()["full_name"] == "Nam"
    assert api.post(base, headers=people["hr"], json={"email": "o@x.test", "role": "employee", "full_name": None}).status_code == 201
