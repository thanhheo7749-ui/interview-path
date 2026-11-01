"""Walks every route under /api/companies/{company_id}. New routes are covered automatically."""
import re

import pytest
from fastapi.testclient import TestClient

from app.database.sql_models import Company, CompanyMember
from app.main import create_app
from tests.helpers import auth_header, iter_routes, make_user, route_path

PREFIX = "/api/companies/{company_id}"


def company_routes(app):
    found = []
    for route in iter_routes(app):
        path = route_path(route)
        if path.startswith(PREFIX):
            for method in (getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}:
                found.append((method, path))
    return sorted(found)


def fill(path, company_id):
    path = path.replace("{company_id}", str(company_id))
    return re.sub(r"\{[^}]+\}", "1", path)


@pytest.fixture
def two_companies(db):
    a = Company(slug="a", name="A")
    b = Company(slug="b", name="B")
    db.add_all([a, b])
    db.commit()
    hr_a = make_user(db, "hr-a@example.test")
    db.add(CompanyMember(company_id=a.id, user_id=hr_a.id, role="hr"))
    db.commit()
    return a.id, b.id


def test_there_are_routes_to_check():
    assert len(company_routes(create_app(legacy_b2c=True))) >= 10


def test_nothing_under_the_companies_path_escapes_this_walk():
    """A route named {id} rather than {company_id}, or a websocket, would not be checked below."""
    for route in iter_routes(create_app(legacy_b2c=True)):
        path = route_path(route)
        if path.startswith("/api/companies/"):
            assert path.startswith(PREFIX) and getattr(route, "methods", None), f"{path} is not covered by this file"


def test_member_of_another_company_gets_403_everywhere(two_companies):
    _, b_id = two_companies
    app = create_app(legacy_b2c=True)
    client = TestClient(app)
    headers = auth_header("hr-a@example.test")
    for method, path in company_routes(app):
        response = client.request(method, fill(path, b_id), headers=headers, json={})
        assert response.status_code == 403, f"{method} {path} returned {response.status_code}"


def test_anonymous_gets_401_everywhere(two_companies):
    _, b_id = two_companies
    app = create_app(legacy_b2c=True)
    client = TestClient(app)
    for method, path in company_routes(app):
        response = client.request(method, fill(path, b_id), json={})
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}"


def test_platform_admin_has_no_implicit_company_access(db, two_companies):
    _, b_id = two_companies
    make_user(db, "root@example.test", role="admin")
    client = TestClient(create_app())
    response = client.get(f"/api/companies/{b_id}", headers=auth_header("root@example.test"))
    assert response.status_code == 403


def test_a_nonexistent_company_looks_the_same_as_a_forbidden_one(two_companies):
    client = TestClient(create_app())
    response = client.get("/api/companies/999999", headers=auth_header("hr-a@example.test"))
    assert response.status_code == 403
