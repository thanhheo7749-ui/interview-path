import pytest

from app.auth import security
from app.auth.security import MAX_PASSWORD_LENGTH, get_password_hash
from app.database.sql_models import User
from tests.helpers import auth_header, make_user

GOOD = "a-good-password"
TOO_LONG = "x" * (MAX_PASSWORD_LENGTH + 1)
LONGEST = "x" * MAX_PASSWORD_LENGTH


def test_the_limit_is_128():
    assert MAX_PASSWORD_LENGTH == 128


def register(client, password):
    return client.post("/api/register", json={"email": "new@example.test", "password": password, "full_name": "New"})


def test_register_refuses_a_password_over_the_limit(client):
    assert register(client, TOO_LONG).status_code == 422


def test_register_accepts_a_password_at_the_limit(client):
    assert register(client, LONGEST).status_code == 200


@pytest.fixture
def user(db):
    row = User(email="u@example.test", full_name="U", hashed_password=get_password_hash(GOOD))
    db.add(row)
    db.commit()
    return row


def test_change_refuses_a_new_password_over_the_limit(client, user):
    body = {"current_password": GOOD, "new_password": TOO_LONG}
    response = client.post("/api/me/password", json=body, headers=auth_header(user.email))
    assert response.status_code == 422


def test_change_accepts_a_new_password_at_the_limit(client, user):
    body = {"current_password": GOOD, "new_password": LONGEST}
    assert client.post("/api/me/password", json=body, headers=auth_header(user.email)).status_code == 200


def test_admin_member_creation_refuses_a_password_over_the_limit(client, db):
    make_user(db, "root@example.test", role="admin")
    headers = auth_header("root@example.test")
    body = {"email": "m@example.test", "password": TOO_LONG, "full_name": "M"}
    assert client.post("/api/admin/users", json=body, headers=headers).status_code == 422


def test_login_refuses_an_over_long_password_with_401_and_does_not_hash_it(client, user, monkeypatch):
    called = []
    monkeypatch.setattr(security, "verify_password", lambda *args: called.append(args) or True)
    body = {"email": user.email, "password": TOO_LONG}
    assert client.post("/api/login", json=body).status_code == 401
    assert called == []


def test_login_still_works_at_the_limit(client, db):
    db.add(User(email="long@example.test", full_name="L", hashed_password=get_password_hash(LONGEST)))
    db.commit()
    assert client.post("/api/login", json={"email": "long@example.test", "password": LONGEST}).status_code == 200
