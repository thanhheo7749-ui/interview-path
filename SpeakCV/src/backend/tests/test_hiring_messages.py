"""What a candidate is told: whether email is on, why a CV failed, and when notifications leave."""
import pytest

from app.database.sql_models import Notification
from app.hiring import cv_processing, decisions, notify
from app.hiring.hidden_text import CvTooLarge
from tests.helpers import auth_header
from tests.test_hiring_apply import CANDIDATE, apply, fresh, make_pdf, world  # noqa: F401


def mine(client):
    return client.get("/api/me/applications", headers=auth_header(CANDIDATE)).json()[0]


# I-12. The app knows whether email is on


def test_the_response_says_email_is_off_without_smtp(client, world, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    apply(client)
    assert mine(client)["email_enabled"] is False


def test_the_response_says_email_is_on_with_smtp(client, world, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    apply(client)
    assert mine(client)["email_enabled"] is True


def test_the_detail_route_carries_the_flag_too(client, world, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    application_id = apply(client).json()["id"]
    body = client.get(f"/api/applications/{application_id}", headers=auth_header(CANDIDATE)).json()
    assert body["email_enabled"] is True


def _decided(db, application_id, decision):
    application = fresh(db, application_id)
    application.stage = "ready_for_hr"
    application.hr_decision = decision
    db.commit()


def test_an_approved_candidate_is_given_their_account_email_to_show(client, world, db):
    application_id = apply(client).json()["id"]
    _decided(db, application_id, "approved")
    body = mine(client)
    assert body["decision"] == "approved" and body["contact_email"] == CANDIDATE


@pytest.mark.parametrize("decision", ["rejected", "pending"])
def test_the_email_is_not_sent_for_any_other_state(client, world, db, decision):
    application_id = apply(client).json()["id"]
    _decided(db, application_id, decision)
    assert mine(client)["contact_email"] is None


def test_the_approval_email_names_the_next_step_and_does_not_send_people_back_to_the_app():
    for language, texts in decisions.NOTIFICATIONS.items():
        subject, body = texts["approved"]
        assert "Open the app" not in body and "Hãy mở ứng dụng" not in body
    assert "contact you" in decisions.NOTIFICATIONS["en"]["approved"][1]
    assert "liên hệ" in decisions.NOTIFICATIONS["vi"]["approved"][1]


# M-8. Why a CV failed


@pytest.mark.parametrize("message,reason", [
    ("This PDF has no extractable text. Scanned documents are not supported.", "no_text"),
    ("This file has no extractable text. Scanned documents are not supported.", "no_text"),
    ("This file has no extractable text.", "no_text"),
    ("We could not read this file. Please upload a PDF or DOCX that opens normally.", "unreadable"),
    ("This file cannot be read. It may be damaged or password protected. Upload a new copy.", "unreadable"),
    ("This file is not UTF-8 text. Save it as UTF-8 and upload it again.", "unreadable"),
    ("This PDF has more than 30 pages. Please upload a shorter CV.", "too_large"),
    ("This DOCX is larger than 50 MB when unpacked. Please upload a smaller file.", "too_large"),
    (cv_processing.TRY_AGAIN, "try_again"),
    (cv_processing.INTERRUPTED, "interrupted"),
    ("Traceback (most recent call last): secret CV words", "unknown"),
])
def test_a_failed_cv_gets_a_fixed_reason_code_never_the_raw_text(client, world, db, message, reason):
    application_id = apply(client).json()["id"]
    application = fresh(db, application_id)
    application.stage = "cv_failed"
    application.processing_error = message
    db.commit()
    body = mine(client)
    assert body["status"] == "cv_unreadable" and body["failure_reason"] == reason


def test_a_cv_that_did_not_fail_has_no_reason(client, world):
    apply(client)
    assert mine(client)["failure_reason"] is None


def test_every_message_the_processing_writes_has_a_reason():
    from app.core import text_extract
    from app.hiring import hidden_text

    messages = [text_extract.EMPTY, text_extract.NO_PDF_TEXT, text_extract.NOT_UTF8, text_extract.UNREADABLE,
                hidden_text.UNREADABLE, hidden_text.NO_TEXT, cv_processing.TRY_AGAIN, cv_processing.INTERRUPTED,
                str(CvTooLarge(f"This PDF has more than {hidden_text.MAX_PDF_PAGES} pages. Please upload a shorter CV.")),
                "This DOCX is larger than 50 MB when unpacked. Please upload a smaller file."]
    assert all(cv_processing.failure_reason(message) != "unknown" for message in messages)


# M-13. Notifications leave when they are queued


def test_a_cv_that_finished_processing_delivers_the_invitation_at_once(client, world, monkeypatch):
    delivered = []
    monkeypatch.setattr(notify, "deliver_pending", lambda: delivered.append(1))
    apply(client)
    assert delivered


def test_deliver_pending_sends_through_send_pending_and_never_raises(db, monkeypatch):
    calls = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setattr(notify, "send_pending", lambda session: calls.append(session) or 0)
    notify.deliver_pending()
    assert len(calls) == 1

    def broken(_session):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(notify, "send_pending", broken)
    notify.deliver_pending()


def test_deliver_pending_does_nothing_without_smtp(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setattr(notify, "send_pending", lambda session: pytest.fail("no SMTP, so nothing to send"))
    notify.deliver_pending()
