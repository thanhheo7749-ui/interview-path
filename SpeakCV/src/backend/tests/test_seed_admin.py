from app.auth.security import verify_password
from app.database.sql_models import User
from app.main import seed_admin


def test_seed_creates_admin_when_absent(db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.test")
    monkeypatch.setenv("ADMIN_PASSWORD", "first-password")
    seed_admin()
    user = db.query(User).filter_by(email="ops@example.test").one()
    assert user.role == "admin"
    assert verify_password("first-password", user.hashed_password)


def test_seed_never_overwrites_an_existing_user(db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.test")
    monkeypatch.setenv("ADMIN_PASSWORD", "first-password")
    seed_admin()
    monkeypatch.setenv("ADMIN_PASSWORD", "second-password")
    seed_admin()
    db.expire_all()
    user = db.query(User).filter_by(email="ops@example.test").one()
    assert verify_password("first-password", user.hashed_password)


def test_seed_does_nothing_without_configuration(db, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    seed_admin()
    assert db.query(User).count() == 0
