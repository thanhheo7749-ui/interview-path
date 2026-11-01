import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jose import jwt

from app.auth.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    mark_password_changed,
    token_predates_password_change,
    verify_password,
)
from app.cli import main
from app.core.rate_limit import limiter
from app.database.sql_models import Company, CompanyMember, User
from tests.helpers import auth_header, make_user

TEMP = "temporary-pass-123"
NEW = "brand-new-password"
BACKEND_APP = Path(__file__).resolve().parents[1] / "app"


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
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
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


# Sessions and password changes

def _token(email, issued_ago=None):
    """A signed token. issued_ago=None leaves out iat, as tokens from before this claim existed do."""
    claims = {"sub": email, "exp": int(time.time()) + 3600}
    if issued_ago is not None:
        claims["iat"] = int(time.time()) - issued_ago
    return {"Authorization": f"Bearer {jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)}"}


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _statuses(client, headers, company_id):
    return [
        client.get("/api/me", headers=headers).status_code,
        client.get(f"/api/companies/{company_id}", headers=headers).status_code,
        client.get("/api/my-profile", headers=headers).status_code,
    ]


def _clear_flag(db, email):
    db.query(User).filter_by(email=email).one().must_change_password = False
    db.commit()


def _admin_headers(db):
    make_user(db, "root@example.test", role="admin")
    return auth_header("root@example.test")


def test_token_has_an_integer_issued_at():
    before = int(time.time())
    claims = jwt.decode(create_access_token({"sub": "a@example.test"}), SECRET_KEY, algorithms=[ALGORITHM])
    assert isinstance(claims["iat"], int)
    assert before <= claims["iat"] <= int(time.time())


def test_a_change_refuses_older_tokens_and_returns_one_that_works(client, flagged, db):
    email, company_id = flagged
    old = _token(email, issued_ago=60)
    response = client.post("/api/me/password", headers=old, json={"current_password": TEMP, "new_password": NEW})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert _statuses(client, old, company_id) == [401, 401, 401]
    assert client.post(
        "/api/me/password", headers=old, json={"current_password": NEW, "new_password": "yet-another-password"},
    ).status_code == 401
    assert _statuses(client, _bearer(body["access_token"]), company_id) == [200, 200, 200]
    db.expire_all()
    assert db.query(User).filter_by(email=email).one().password_changed_at is not None


def test_signing_in_after_the_change_works(client, flagged):
    email, company_id = flagged
    client.post("/api/me/password", headers=_token(email, 60), json={"current_password": TEMP, "new_password": NEW})
    login = client.post("/api/login", json={"email": email, "password": NEW})
    assert _statuses(client, _bearer(login.json()["access_token"]), company_id) == [200, 200, 200]


def test_a_refused_change_leaves_the_session_alone(client, flagged, db):
    email, _ = flagged
    old = _token(email, issued_ago=60)
    assert client.post(
        "/api/me/password", headers=old, json={"current_password": "wrong-password", "new_password": NEW},
    ).status_code == 401
    assert client.get("/api/me", headers=old).status_code == 200
    db.expire_all()
    assert db.query(User).filter_by(email=email).one().password_changed_at is None


def test_a_user_who_never_changed_a_password_is_unaffected(client, flagged, db):
    email, company_id = flagged
    _clear_flag(db, email)
    assert _statuses(client, _token(email, issued_ago=86400), company_id) == [200, 200, 200]
    assert _statuses(client, _token(email), company_id) == [200, 200, 200]


def test_a_token_without_issued_at_is_refused_only_once_a_change_is_recorded(client, flagged, db):
    email, company_id = flagged
    _clear_flag(db, email)
    no_iat = _token(email)
    assert _statuses(client, no_iat, company_id) == [200, 200, 200]
    db.query(User).filter_by(email=email).one().password_changed_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    assert _statuses(client, no_iat, company_id) == [401, 401, 401]


@pytest.mark.parametrize("zone", ["UTC", "Asia/Ho_Chi_Minh", "America/New_York"])
def test_a_naive_change_time_is_read_as_utc_in_any_server_timezone(monkeypatch, zone):
    monkeypatch.setenv("TZ", zone)
    time.tzset()
    try:
        changed = int(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp())
        naive = datetime(2026, 1, 1, 12, 0, 0)
        assert token_predates_password_change({"iat": changed - 1}, naive) is True
        assert token_predates_password_change({"iat": changed}, naive) is False
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()


def test_an_aware_change_time_is_compared_by_its_instant():
    aware = datetime(2026, 1, 1, 19, 0, 0, tzinfo=timezone(timedelta(hours=7)))
    changed = int(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp())
    assert token_predates_password_change({"iat": changed - 1}, aware) is True
    assert token_predates_password_change({"iat": changed}, aware) is False


def test_the_change_time_has_no_fraction_a_database_could_round_up(db):
    # MySQL DATETIME rounds fractions to the nearest second, which could land after the token issued next.
    user = make_user(db, "round@example.test")
    mark_password_changed(user)
    assert user.password_changed_at.microsecond == 0


def test_only_the_security_module_decodes_tokens():
    offenders = [
        str(path.relative_to(BACKEND_APP)) for path in BACKEND_APP.rglob("*.py")
        if "jwt.decode" in path.read_text(encoding="utf-8") and path.name != "security.py"
    ]
    assert offenders == []


def test_an_admin_password_change_ends_older_sessions(client, db):
    headers = _admin_headers(db)
    target = make_user(db, "member@example.test")
    old = _token(target.email, issued_ago=60)
    response = client.put(f"/api/admin/users/{target.id}", headers=headers, json={"password": "chosen-by-admin"})
    assert response.status_code == 200
    db.expire_all()
    assert db.get(User, target.id).password_changed_at is not None
    assert client.get("/api/me", headers=old).status_code == 401


# Passwords chosen by an admin

def test_admin_creating_a_user_forces_a_password_change(client, db):
    response = client.post(
        "/api/admin/users", headers=_admin_headers(db),
        json={"email": "made@example.test", "password": "chosen-by-admin", "full_name": "Made"},
    )
    assert response.status_code == 200
    assert db.query(User).filter_by(email="made@example.test").one().must_change_password is True


def test_admin_changing_a_password_forces_a_password_change(client, db):
    headers = _admin_headers(db)
    target = make_user(db, "member@example.test")
    assert client.put(f"/api/admin/users/{target.id}", headers=headers, json={"password": "chosen-by-admin"}).status_code == 200
    db.expire_all()
    assert db.get(User, target.id).must_change_password is True
    login = client.post("/api/login", json={"email": target.email, "password": "chosen-by-admin"})
    assert login.json()["must_change_password"] is True


@pytest.mark.parametrize("payload", [{"full_name": "Renamed"}, {"password": ""}])
def test_admin_edit_without_a_new_password_touches_neither_field(client, db, payload):
    headers = _admin_headers(db)
    target = make_user(db, "member@example.test")
    old = _token(target.email, issued_ago=60)
    assert client.put(f"/api/admin/users/{target.id}", headers=headers, json=payload).status_code == 200
    db.expire_all()
    user = db.get(User, target.id)
    assert user.must_change_password is False
    assert user.password_changed_at is None
    assert client.get("/api/me", headers=old).status_code == 200
