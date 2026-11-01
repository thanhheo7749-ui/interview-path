import pytest

from app.auth.security import get_password_hash, verify_password
from app.cli import main
from app.core.rate_limit import limiter
from app.database.sql_models import Company, CompanyMember, User
from tests.helpers import auth_header, make_user

TEMP = "temporary-pass-123"
NEW = "brand-new-password"


@pytest.fixture
def flagged(db):
    user = User(
        email="temp@example.test", full_name="Temp", hashed_password=get_password_hash(TEMP), must_change_password=True,
    )
    company = Company(slug="acme", name="Acme")
    db.add_all([user, company])
    db.commit()
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    return user.email, company.id


def test_a_plain_user_has_no_flag(db):
    assert make_user(db, "plain@example.test").must_change_password is False


def test_login_and_me_report_the_flag(client, flagged):
    email, _ = flagged
    login = client.post("/api/login", json={"email": email, "password": TEMP})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    me = client.get("/api/me", headers=auth_header(email))
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True


def test_company_routes_are_refused_until_the_password_changes(client, flagged):
    email, company_id = flagged
    response = client.get(f"/api/companies/{company_id}", headers=auth_header(email))
    assert response.status_code == 403
    assert response.json()["detail"] == "password_change_required"


def test_change_clears_the_flag_and_replaces_the_password(client, flagged):
    email, company_id = flagged
    headers = auth_header(email)
    response = client.post("/api/me/password", headers=headers, json={"current_password": TEMP, "new_password": NEW})
    assert response.status_code == 200
    assert client.get("/api/me", headers=headers).json()["must_change_password"] is False
    assert client.get(f"/api/companies/{company_id}", headers=headers).status_code == 200
    assert client.post("/api/login", json={"email": email, "password": TEMP}).status_code == 401
    login = client.post("/api/login", json={"email": email, "password": NEW})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is False


def test_wrong_current_password_is_401_and_changes_nothing(client, flagged, db):
    email, _ = flagged
    response = client.post(
        "/api/me/password", headers=auth_header(email), json={"current_password": "wrong-password", "new_password": NEW},
    )
    assert response.status_code == 401
    user = db.query(User).filter_by(email=email).one()
    assert user.must_change_password is True
    assert verify_password(TEMP, user.hashed_password)


def test_short_new_password_is_422(client, flagged):
    email, _ = flagged
    response = client.post(
        "/api/me/password", headers=auth_header(email), json={"current_password": TEMP, "new_password": "123456789"},
    )
    assert response.status_code == 422


def test_reusing_the_temporary_password_does_not_clear_the_flag(client, flagged, db):
    email, _ = flagged
    response = client.post("/api/me/password", headers=auth_header(email), json={"current_password": TEMP, "new_password": TEMP})
    assert response.status_code == 422
    assert db.query(User).filter_by(email=email).one().must_change_password is True


def test_change_requires_login(client):
    assert client.post("/api/me/password", json={"current_password": TEMP, "new_password": NEW}).status_code == 401


def test_change_works_for_a_user_without_a_company(client, db):
    db.add(User(email="solo@example.test", full_name="Solo", hashed_password=get_password_hash(TEMP)))
    db.commit()
    response = client.post(
        "/api/me/password", headers=auth_header("solo@example.test"), json={"current_password": TEMP, "new_password": NEW},
    )
    assert response.status_code == 200


def test_change_is_rate_limited(client, flagged):
    email, _ = flagged
    headers = auth_header(email)
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            client.post("/api/me/password", headers=headers, json={"current_password": "wrong-password", "new_password": NEW}).status_code
            for _ in range(11)
        ]
    finally:
        limiter.enabled = False
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_member_created_with_a_temporary_password_is_flagged(client, db):
    company = Company(slug="co", name="Co")
    db.add(company)
    db.commit()
    hr = make_user(db, "hr@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    db.commit()
    created = client.post(
        f"/api/companies/{company.id}/members", headers=auth_header(hr.email), json={"email": "new@example.test", "role": "employee"},
    )
    assert created.status_code == 201
    assert created.json()["temporary_password"]
    assert db.query(User).filter_by(email="new@example.test").one().must_change_password is True


def test_adding_an_existing_account_leaves_its_flag_alone(client, db):
    company = Company(slug="co", name="Co")
    db.add(company)
    db.commit()
    hr = make_user(db, "hr@example.test")
    make_user(db, "old@example.test")
    db.add(CompanyMember(company_id=company.id, user_id=hr.id, role="hr"))
    db.commit()
    created = client.post(
        f"/api/companies/{company.id}/members", headers=auth_header(hr.email), json={"email": "old@example.test", "role": "employee"},
    )
    assert created.status_code == 201
    db.expire_all()
    assert db.query(User).filter_by(email="old@example.test").one().must_change_password is False


def test_cli_created_hr_is_flagged(db, capsys):
    args = ["create-company", "--slug", "sori", "--name", "Sori", "--hr-email", "hr@sori.test", "--hr-name", "HR"]
    assert main(args) == 0
    assert db.query(User).filter_by(email="hr@sori.test").one().must_change_password is True


def test_registered_candidate_is_not_flagged(client, db):
    response = client.post("/api/register", json={"email": "c@example.test", "password": "long-enough-pw", "full_name": "C"})
    assert response.status_code == 200
    assert db.query(User).filter_by(email="c@example.test").one().must_change_password is False


def test_registration_requires_ten_characters_with_a_readable_error(client, db):
    response = client.post("/api/register", json={"email": "c@example.test", "password": "123456789", "full_name": "C"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert "10" in response.json()["detail"]
    assert db.query(User).filter_by(email="c@example.test").first() is None
