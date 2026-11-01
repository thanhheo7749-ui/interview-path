import pytest

from app.database.sql_models import Company
from app.hiring import consents
from tests.helpers import make_user


def _setup(db):
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    return company, make_user(db, email="c@example.com")


@pytest.mark.parametrize("purpose", ["cv_processing", "recording_screening"])
@pytest.mark.parametrize("language", ["en", "vi"])
def test_current_text_exists(purpose, language):
    text = consents.current_text(purpose, language)
    assert text.version and text.text


def test_cv_processing_text_mentions_raw_cv_masking():
    text = consents.current_text("cv_processing", "en").text.lower()
    assert "original cv" in text and "identif" in text


def test_recording_text_states_purpose_viewers_and_retention():
    text = consents.current_text("recording_screening", "en", retention_days=45).text
    assert "45" in text and "HR" in text and "recorded" in text
    assert "45" in consents.current_text("recording_screening", "vi", retention_days=45).text


def test_unknown_purpose_raises():
    with pytest.raises(ValueError):
        consents.current_text("marketing", "en")


def test_record_has_active_and_withdraw(db):
    company, user = _setup(db)
    assert not consents.has_active(db, user.id, "recording_screening")
    consent = consents.record(db, user.id, company.id, None, "recording_screening", "2026-11-01")
    db.commit()
    assert consents.has_active(db, user.id, "recording_screening")
    assert consents.has_active(db, user.id, "recording_screening", company_id=company.id)
    assert not consents.has_active(db, user.id, "recording_screening", application_id=999)
    consents.withdraw(db, consent.id, user.id)
    db.commit()
    assert consent.withdrawn_at is not None
    assert not consents.has_active(db, user.id, "recording_screening")


def test_withdraw_other_users_consent_raises(db):
    company, user = _setup(db)
    other = make_user(db, email="o@example.com")
    consent = consents.record(db, user.id, company.id, None, "cv_processing", "2026-11-01")
    db.commit()
    with pytest.raises(PermissionError):
        consents.withdraw(db, consent.id, other.id)


def test_record_unknown_purpose_raises(db):
    company, user = _setup(db)
    with pytest.raises(ValueError):
        consents.record(db, user.id, company.id, None, "marketing", "x")
