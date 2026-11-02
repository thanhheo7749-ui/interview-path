from types import SimpleNamespace

import pytest

from app.database.sql_models import Application, Company, Consent, Job
from app.hiring import consents
from tests.helpers import auth_header, make_user


def _setup(db):
    company = Company(slug="acme", name="Acme")
    db.add(company)
    db.commit()
    return company, make_user(db, email="c@example.com")


@pytest.mark.parametrize("purpose", ["cv_processing", "recording_screening"])
@pytest.mark.parametrize("language", ["en", "vi", "ko"])
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


# The text a candidate is shown, built from the application


@pytest.fixture
def owned(db):
    company = Company(slug="acme", name="Acme", retention_days=30)
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend", slug="acme-backend", description="d", status="published",
              interview_languages=["ko", "vi", "en"])
    db.add(job)
    db.flush()
    user = make_user(db, "c@example.com")
    make_user(db, "o@example.com")
    application = Application(company_id=company.id, job_id=job.id, candidate_user_id=user.id, alias="#A1", stage="invited",
                              cv_status="not_met", cv_text_blind="blind")
    db.add(application)
    db.commit()
    return SimpleNamespace(id=application.id, user_id=user.id, company_id=company.id)


def consent_url(owned, purpose="recording_screening", language=None):
    tail = f"?language={language}" if language else ""
    return f"/api/applications/{owned.id}/consents/{purpose}{tail}"


@pytest.mark.parametrize("language,days,after_decision,undecided", [
    ("en", "30 days", "after the decision", "180 days after you applied"),
    ("vi", "30 ngày", "sau khi có quyết định", "180 ngày sau khi bạn ứng tuyển"),
    ("ko", "30일", "결정 후", "지원 후 180일"),
])
def test_the_application_route_uses_that_companys_retention(client, owned, language, days, after_decision, undecided):
    response = client.get(consent_url(owned, language=language), headers=auth_header("c@example.com"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == consents.VERSION and body["language"] == language
    for piece in (days, after_decision, undecided):
        assert piece in body["text"]
    assert "90" not in body["text"]


def test_a_language_with_no_text_returns_english_and_says_so(client, owned):
    body = client.get(consent_url(owned, language="fr"), headers=auth_header("c@example.com")).json()
    assert body["language"] == "en"
    assert "after the decision" in body["text"]


def test_the_application_route_is_for_the_owner_only(client, owned):
    assert client.get(consent_url(owned)).status_code == 401
    assert client.get(consent_url(owned), headers=auth_header("o@example.com")).status_code == 404


def test_the_application_route_refuses_an_unknown_purpose(client, owned):
    assert client.get(consent_url(owned, "marketing"), headers=auth_header("c@example.com")).status_code == 404


def test_the_general_route_also_says_which_language_it_returned(client, owned):
    response = client.get("/api/consents/cv_processing?language=ko", headers=auth_header("c@example.com"))
    assert response.json()["language"] == "ko"
    fallback = client.get("/api/consents/cv_processing?language=fr", headers=auth_header("c@example.com"))
    assert fallback.json()["language"] == "en"


def test_the_ledger_records_the_language_of_the_text_returned(client, db, owned):
    headers = auth_header("c@example.com")
    shown = client.get(consent_url(owned, language="fr"), headers=headers).json()
    response = client.post(f"/api/screening/{owned.id}/start", headers=headers, json={
        "consent_version": shown["version"], "language": "vi", "consent_language": shown["language"],
    })
    assert response.status_code == 200, response.text
    db.rollback()
    assert db.query(Consent).filter_by(purpose="recording_screening").one().language == "en"


def test_the_ledger_stores_english_for_a_language_with_no_text(db, owned):
    row = consents.record(db, owned.user_id, owned.company_id, owned.id, "cv_processing", consents.VERSION, language="fr")
    assert row.language == "en"
    assert consents.record(db, owned.user_id, owned.company_id, owned.id, "cv_processing", consents.VERSION).language is None


@pytest.mark.parametrize("language,words", [
    ("en", "one-way code"), ("vi", "mã một chiều"), ("ko", "단방향 코드"),
])
def test_the_application_consent_mentions_the_reapply_guard(language, words):
    text = consents.current_text("cv_processing", language).text
    assert words in text and "90" in text


@pytest.mark.parametrize("purpose", ["talent_pool", "onboarding_use"])
def test_a_purpose_with_no_korean_text_returns_english_and_says_so(client, owned, db, purpose):
    response = client.get(f"/api/consents/{purpose}?language=ko", headers=auth_header("c@example.com"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["language"] == "en" and body["version"] == consents.VERSION
    assert consents.CONSENT_TEXTS[(purpose, "en")] == body["text"]
    application_route = client.get(consent_url(owned, purpose, "ko"), headers=auth_header("c@example.com"))
    assert application_route.json()["language"] == "en"
    row = consents.record(db, owned.user_id, owned.company_id, owned.id, purpose, consents.VERSION, language="ko")
    assert row.language == "en"


def test_every_text_formats_in_every_language_it_has():
    for (purpose, language) in consents.CONSENT_TEXTS:
        text = consents.current_text(purpose, language).text
        assert "{" not in text and consents.current_text(purpose, language).language == language

