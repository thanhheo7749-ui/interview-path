import smtplib

from app.database.sql_models import Company
from app.hiring import notify
from tests.helpers import make_user


def _setup(db):
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    return company, make_user(db, email="c@example.com")


def test_enqueue_creates_pending_row(db):
    company, user = _setup(db)
    row = notify.enqueue(db, company.id, user.id, "invited", "en", "Hi", "Body")
    db.commit()
    assert row.id and row.status == "pending" and row.sent_at is None


def test_send_pending_without_smtp_host_sends_nothing(db, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    company, user = _setup(db)
    row = notify.enqueue(db, company.id, user.id, "invited", "en", "Hi", "Body")
    db.commit()
    assert notify.send_pending(db) == 0
    db.refresh(row)
    assert row.status == "pending"


class FakeSMTP:
    sent = []
    fail_for = set()

    def __init__(self, host, port, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, *a):
        pass

    def send_message(self, msg):
        if msg["To"] in FakeSMTP.fail_for:
            raise smtplib.SMTPException("boom")
        FakeSMTP.sent.append(msg["To"])


def test_send_pending_sends_and_marks_sent(db, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent, FakeSMTP.fail_for = [], set()
    company, user = _setup(db)
    row = notify.enqueue(db, company.id, user.id, "invited", "en", "Hi", "Body")
    db.commit()
    assert notify.send_pending(db) == 1
    db.refresh(row)
    assert row.status == "sent" and row.sent_at is not None
    assert FakeSMTP.sent == ["c@example.com"]


def test_failure_keeps_pending_and_others_still_send(db, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent, FakeSMTP.fail_for = [], {"c@example.com"}
    company, user = _setup(db)
    other = make_user(db, email="d@example.com")
    bad = notify.enqueue(db, company.id, user.id, "invited", "en", "Hi", "Body")
    good = notify.enqueue(db, company.id, other.id, "invited", "en", "Hi", "Body")
    db.commit()
    assert notify.send_pending(db) == 1
    db.refresh(bad)
    db.refresh(good)
    assert bad.status == "pending" and good.status == "sent"
