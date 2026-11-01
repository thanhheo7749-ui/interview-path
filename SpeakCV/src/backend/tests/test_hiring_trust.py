import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ai import gateway
from app.ai.providers import fake
from app.database.sql_models import (
    Application, AuditLog, Company, CompanyMember, Consent, CvClaim, Job, JobRequirement, RequirementResult,
)
from app.hiring import fairness, identity, retention, screening
from tests.helpers import auth_header, make_user

CANDIDATE = "candidate@example.test"
OTHER = "other@example.test"
HR = "hr@example.test"
RAW = (
    "Canaryname Zebrawski\n"
    "Email: canary.zebrawski@example.test\n"
    "Mr. Zebrawski built a FastAPI service. He used Docker for 2 years.\n"
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme", default_locale="en", retention_days=30)
    rival = Company(slug="rival", name="Rival", default_locale="en")
    db.add_all([company, rival])
    db.commit()
    job = Job(company_id=company.id, title="Backend Developer", slug="acme-backend", description="d", status="published",
              version=2, interview_languages=["en"])
    rival_job = Job(company_id=rival.id, title="Rival job", slug="rival-job", description="d", status="published",
                    interview_languages=["en"])
    db.add_all([job, rival_job])
    db.commit()
    requirement = JobRequirement(company_id=company.id, job_id=job.id, text="FastAPI", must_have=True, position=0)
    db.add(requirement)
    hr, rival_hr, manager = make_user(db, HR), make_user(db, "hr@rival.test"), make_user(db, "manager@example.test")
    db.add_all([
        CompanyMember(company_id=company.id, user_id=hr.id, role="hr"),
        CompanyMember(company_id=company.id, user_id=manager.id, role="manager"),
        CompanyMember(company_id=rival.id, user_id=rival_hr.id, role="hr"),
    ])
    db.commit()
    return SimpleNamespace(
        company_id=company.id, rival_id=rival.id, job_id=job.id, rival_job_id=rival_job.id, requirement_id=requirement.id,
        hr_id=hr.id, candidate_id=make_user(db, CANDIDATE).id, other_id=make_user(db, OTHER).id,
    )


def url(world, tail):
    return f"/api/companies/{world.company_id}/trust/{tail}"


def hr():
    return auth_header(HR)


def application_row(db, world, alias="#A1", **columns):
    fields = dict(company_id=world.company_id, job_id=world.job_id, job_version=2, alias=alias,
                  candidate_user_id=world.candidate_id, stage="invited")
    row = Application(**{**fields, **columns})
    db.add(row)
    db.commit()
    return row


# 1. Consents


def test_consents_list_purpose_version_dates_and_alias_with_no_email(client, db, world):
    application = application_row(db, world)
    withdrawn = utcnow().replace(microsecond=0)
    db.add_all([
        Consent(user_id=world.candidate_id, company_id=world.company_id, application_id=application.id,
                purpose="cv_processing", text_version="2026-11-01"),
        Consent(user_id=world.candidate_id, company_id=world.company_id, application_id=application.id,
                purpose="recording_screening", text_version="2026-11-01", withdrawn_at=withdrawn),
    ])
    db.commit()
    response = client.get(url(world, "consents"), headers=hr())
    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["purpose"] for item in items} == {"cv_processing", "recording_screening"}
    first = next(item for item in items if item["purpose"] == "recording_screening")
    assert first["version"] == "2026-11-01"
    assert first["alias"] == "#A1"
    assert first["granted_at"]
    assert first["withdrawn_at"].startswith(withdrawn.isoformat()[:19])
    assert CANDIDATE not in response.text
    assert "user_id" not in response.text
    assert "email" not in response.text


def test_consents_are_scoped_to_this_company(client, db, world):
    db.add(Consent(user_id=world.candidate_id, company_id=world.rival_id, purpose="cv_processing", text_version="rival"))
    db.commit()
    assert client.get(url(world, "consents"), headers=hr()).json()["items"] == []


def test_an_anonymized_consent_stays_in_the_ledger_under_its_alias(client, db, world):
    application = application_row(db, world)
    db.add(Consent(user_id=world.candidate_id, company_id=world.company_id, application_id=application.id,
                   purpose="cv_processing", text_version="v1"))
    db.commit()
    retention.anonymize_application(db, application)
    items = client.get(url(world, "consents"), headers=hr()).json()["items"]
    assert [item["alias"] for item in items] == ["#A1"]


# 2. Audit


def audit_row(db, world, action, company_id=None, **columns):
    row = AuditLog(company_id=company_id or world.company_id, action=action, target_type="application", target_id=1, **columns)
    db.add(row)
    db.commit()
    return row


def test_audit_lists_decisions_ai_reveals_and_playback_newest_first(client, db, world):
    now = utcnow().replace(microsecond=0)
    audit_row(db, world, "application_decided", actor_user_id=world.hr_id, created_at=now - timedelta(hours=4))
    audit_row(db, world, "cv_assessed", ai_provider="fake", ai_model="fake-bulk", prompt_version="cv-assess-1",
              created_at=now - timedelta(hours=3))
    audit_row(db, world, "identity_revealed", actor_user_id=world.hr_id, created_at=now - timedelta(hours=2))
    audit_row(db, world, "audio_played", actor_user_id=world.hr_id, created_at=now - timedelta(hours=1))
    body = client.get(url(world, "audit"), headers=hr()).json()
    assert [item["action"] for item in body["items"]] == ["audio_played", "identity_revealed", "cv_assessed", "application_decided"]
    assert body["total"] == 4
    suggestion = body["items"][2]
    assert (suggestion["ai_provider"], suggestion["ai_model"], suggestion["prompt_version"]) == ("fake", "fake-bulk", "cv-assess-1")
    assert body["items"][0]["actor_user_id"] == world.hr_id


def test_audit_rows_at_the_same_second_keep_newest_first(client, db, world):
    now = utcnow().replace(microsecond=0)
    first = audit_row(db, world, "first", created_at=now)
    second = audit_row(db, world, "second", created_at=now)
    ids = [item["id"] for item in client.get(url(world, "audit"), headers=hr()).json()["items"]]
    assert ids == [second.id, first.id]


def test_audit_is_paginated(client, db, world):
    from app.routers import trust

    for index in range(trust.PAGE_SIZE + 3):
        db.add(AuditLog(company_id=world.company_id, action=f"a{index}", target_type="t", target_id=index))
    db.commit()
    first = client.get(url(world, "audit?page=1"), headers=hr()).json()
    second = client.get(url(world, "audit?page=2"), headers=hr()).json()
    assert len(first["items"]) == trust.PAGE_SIZE
    assert len(second["items"]) == 3
    assert first["total"] == second["total"] == trust.PAGE_SIZE + 3
    assert second["page"] == 2
    assert not {item["id"] for item in first["items"]} & {item["id"] for item in second["items"]}
    assert client.get(url(world, "audit?page=0"), headers=hr()).status_code == 422


def test_audit_filters_by_action(client, db, world):
    audit_row(db, world, "audio_played")
    audit_row(db, world, "identity_revealed")
    body = client.get(url(world, "audit?action=audio_played"), headers=hr()).json()
    assert [item["action"] for item in body["items"]] == ["audio_played"]
    assert body["total"] == 1


def test_audit_is_scoped_to_this_company(client, db, world):
    audit_row(db, world, "ours")
    audit_row(db, world, "theirs", company_id=world.rival_id)
    body = client.get(url(world, "audit"), headers=hr()).json()
    assert [item["action"] for item in body["items"]] == ["ours"]
    assert body["total"] == 1


def test_audit_never_names_a_candidate_as_the_actor(client, db, world):
    audit_row(db, world, "application_withdrawn", actor_user_id=world.candidate_id)
    item = client.get(url(world, "audit"), headers=hr()).json()["items"][0]
    assert item["actor_user_id"] is None
    assert item["action"] == "application_withdrawn"


# 3. Retention


def test_retention_reports_days_and_counts(client, db, world):
    due = utcnow() - timedelta(days=31)
    application_row(db, world, "#A1", hr_decision="approved", hr_decided_at=due)
    application_row(db, world, "#A2", created_at=utcnow() - timedelta(days=181))
    application_row(db, world, "#A3")
    application_row(db, world, "#A4", anonymized_at=utcnow(), candidate_user_id=None)
    application_row(db, world, "#A5", company_id=world.rival_id, job_id=world.rival_job_id, created_at=utcnow() - timedelta(days=181))
    response = client.get(url(world, "retention"), headers=hr())
    assert response.status_code == 200
    assert response.json() == {
        "retention_days": 30, "undecided_retention_days": 180, "awaiting_deletion": 3, "due_now": 2, "anonymized": 1,
    }


def test_retention_due_count_leaves_out_extended_applications(client, db, world, monkeypatch):
    application_row(db, world, "#A1", created_at=utcnow() - timedelta(days=181))
    monkeypatch.setattr(retention, "has_extension", lambda _db, _application: True)
    assert client.get(url(world, "retention"), headers=hr()).json()["due_now"] == 0


# Access


@pytest.mark.parametrize("email", [CANDIDATE, "manager@example.test", "hr@rival.test"])
@pytest.mark.parametrize("method,tail", [
    ("get", "consents"), ("get", "audit"), ("get", "retention"), ("post", "fairness-check"),
])
def test_trust_routes_are_hr_of_this_company_only(client, world, email, method, tail):
    kwargs = {"json": {"application_id": 1}} if method == "post" else {}
    response = getattr(client, method)(url(world, tail), headers=auth_header(email), **kwargs)
    assert response.status_code == 403


def test_trust_routes_need_a_login(client, world):
    assert client.get(url(world, "audit")).status_code == 401


# 4. Fairness check


def masker(names, gender_terms):
    return json.dumps({"names": names, "gender_terms": gender_terms, "ages": [], "addresses": []}, ensure_ascii=False)


ORIGINAL_NAMES = ["Canaryname Zebrawski", "Zebrawski", "Canaryname"]
ORIGINAL_GENDER = ["Mr.", "He"]


def handles_both(_system, messages, _schema):
    """Lists whatever identity the CV holds, as a working masker does."""
    text = messages[-1]["content"]
    if "Canaryname" in text:
        return masker(ORIGINAL_NAMES, ORIGINAL_GENDER)
    return masker([fairness.WOMAN.name, fairness.MAN.name], ["Ms.", "She", "Mr.", "He"])


def misses_the_swapped_name(_system, messages, _schema):
    if "Canaryname" in messages[-1]["content"]:
        return masker(ORIGINAL_NAMES, ORIGINAL_GENDER)
    return masker([], ["Ms.", "She"])


@pytest.fixture
def spy(monkeypatch):
    calls = []
    real = gateway.generate_structured

    def wrapper(slot, system, messages, schema, max_output_tokens, feature, company_id=None):
        calls.append(SimpleNamespace(feature=feature, prompt=messages[-1]["content"]))
        return real(slot, system, messages, schema, max_output_tokens, feature, company_id)

    monkeypatch.setattr(gateway, "generate_structured", wrapper)
    return calls


def screened(db, world, alias="#A1", responder=handles_both):
    """An application masked and assessed the way cv_processing does it, leaving the cache row in place."""
    fake.register("cv_mask", responder)
    masked = identity.mask(RAW, company_id=world.company_id)
    application = application_row(db, world, alias, cv_text_raw=RAW, cv_text_blind=masked.blind_text,
                                  cv_blind_hash=masked.blind_hash, cv_status="meets")
    fake.enqueue("cv_assess", json.dumps({
        "requirements": [{"requirement_id": world.requirement_id, "status": "met", "quote": "built a FastAPI service"}],
        "claims": [{"text": "Docker for 2 years", "quote": "used Docker for 2 years"}],
    }))
    screening.assess(db, application)
    db.commit()
    return application


def test_fairness_identity_swap_gives_the_same_blind_text_and_result(client, db, world, spy):
    application = screened(db, world)
    spy.clear()
    response = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    assert response.status_code == 200
    body = response.json()
    assert body["identical_blind_text"] is True
    assert body["identical_result"] is True
    assert body["original_blind_text"] == body["swapped_blind_text"]
    assert "[NAME]" in body["swapped_blind_text"]
    assert [call.feature for call in spy] == ["cv_mask"]  # one masking, and the assessment came from the cache


def test_the_swap_really_changes_the_identity_and_flips_the_gender(client, db, world, spy):
    application = screened(db, world)
    spy.clear()
    client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    sent = spy[0].prompt
    assert "Canaryname" not in sent and "Zebrawski" not in sent
    assert fairness.WOMAN.name in sent
    assert "Ms." in sent and "She" in sent
    assert "Mr." not in sent and "He " not in sent


def test_the_gender_flips_the_other_way_for_a_woman():
    swapped = fairness.swap_identity(
        "Mai Lan\nShe is great. Ms. Lan shipped it.\n", {"names": ["Mai Lan", "Lan"], "gender_terms": ["She", "Ms."]},
    )
    assert fairness.MAN.name in swapped
    assert "He is great" in swapped and "Mr." in swapped
    assert "Mai Lan" not in swapped


def test_a_gender_label_guides_the_flip_and_its_value_is_masked():
    swapped = fairness.swap_identity("Mai Lan\nGender: Female\n", {"names": ["Mai Lan"], "gender_terms": []})
    assert fairness.MAN.name in swapped
    assert "Gender: [GENDER]" in swapped


def test_a_label_word_used_elsewhere_is_left_alone():
    swapped = fairness.swap_identity(
        "An Le\nGiới tính: Nam\nWorked in Việt Nam for Nam Corp.\n", {"names": ["An Le"], "gender_terms": []},
    )
    assert fairness.WOMAN.name in swapped
    assert "Việt Nam" in swapped and "Nam Corp" in swapped


def test_a_name_inside_an_email_or_url_does_not_break_their_masking():
    swapped = fairness.swap_identity(
        "Zebrawski\nzebrawski@example.test https://example.test/zebrawski\n", {"names": ["Zebrawski"], "gender_terms": []},
    )
    assert swapped.splitlines()[1] == "[EMAIL] [URL]"


def test_a_second_assess_of_the_swapped_cv_makes_no_ai_call_because_the_cache_hits(client, db, world, spy):
    application = screened(db, world)
    body = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr()).json()
    db.rollback()
    twin = application_row(db, world, "#A2", candidate_user_id=world.other_id, cv_text_blind=body["swapped_blind_text"],
                           cv_blind_hash=application.cv_blind_hash)
    spy.clear()
    result = screening.assess(db, twin)
    assert result.cache_hit is True
    assert spy == []


def test_a_masker_that_misses_the_swapped_name_is_reported_honestly(client, db, world, spy):
    application = screened(db, world, responder=misses_the_swapped_name)
    original = application.cv_text_blind
    spy.clear()
    response = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    assert response.status_code == 200
    body = response.json()
    assert body["identical_blind_text"] is False
    assert body["identical_result"] is False
    assert body["original_blind_text"] == original
    assert fairness.WOMAN.name in body["swapped_blind_text"]
    assert [call.feature for call in spy] == ["cv_mask"]  # a differing text is not sent to the assessment


def test_differing_texts_write_an_audit_row_with_no_personal_content(client, db, world):
    application = screened(db, world, responder=misses_the_swapped_name)
    client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    db.rollback()
    row = db.query(AuditLog).filter_by(action="fairness_check", target_id=application.id).one()
    assert row.payload == {"identical_blind_text": False, "identical_result": False}
    assert row.actor_user_id == world.hr_id
    assert row.company_id == world.company_id
    assert row.ai_model


def test_fairness_never_overwrites_the_application(client, db, world):
    application = screened(db, world, responder=misses_the_swapped_name)
    application_id = application.id
    columns = [column.name for column in Application.__table__.columns]
    before = {name: getattr(application, name) for name in columns}
    results = sorted((row.id, row.status, row.quote) for row in db.query(RequirementResult).filter_by(application_id=application_id))
    claims = sorted((row.id, row.text) for row in db.query(CvClaim).filter_by(application_id=application_id))
    db.rollback()
    client.post(url(world, "fairness-check"), json={"application_id": application_id}, headers=hr())
    db.rollback()
    db.expire_all()
    application = db.get(Application, application_id)
    assert {name: getattr(application, name) for name in columns} == before
    assert sorted((row.id, row.status, row.quote) for row in db.query(RequirementResult).filter_by(application_id=application_id)) == results
    assert sorted((row.id, row.text) for row in db.query(CvClaim).filter_by(application_id=application_id)) == claims


def test_identical_blind_text_with_no_cached_row_is_still_the_same_result_by_construction(db, world):
    application = screened(db, world)
    from app.database.sql_models import ScreeningCache

    db.query(ScreeningCache).delete()
    db.commit()
    result = fairness.check(db, application)
    assert result.identical_blind_text is True
    assert result.identical_result is True


@pytest.mark.parametrize("same_payload", [True, False])
def test_different_blind_texts_compare_their_cached_results(db, world, same_payload):
    from app.ai.config import get_config
    from app.database.sql_models import ScreeningCache

    application = screened(db, world, responder=misses_the_swapped_name)
    cached = db.query(ScreeningCache).filter_by(blind_hash=application.cv_blind_hash).one()
    swapped_hash = identity.mask(
        fairness.swap_identity(RAW, fairness.found_terms(RAW, application.cv_text_blind)), company_id=world.company_id,
    ).blind_hash
    db.add(ScreeningCache(blind_hash=swapped_hash, job_id=world.job_id, job_version=application.job_version,
                          prompt_version=screening.PROMPT_VERSION, model=get_config().slot("bulk").model,
                          result=cached.result if same_payload else {"requirements": [], "claims": []}))
    db.commit()
    result = fairness.check(db, application)
    assert result.identical_blind_text is False
    assert result.identical_result is same_payload


def test_an_anonymized_application_gets_404_and_no_ai_call(client, db, world, spy):
    application = screened(db, world)
    retention.anonymize_application(db, application)
    spy.clear()
    response = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    assert response.status_code == 404
    assert spy == []


def test_an_application_with_no_cv_text_gets_409(client, db, world):
    application = application_row(db, world, stage="cv_failed")
    response = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    assert response.status_code == 409


def test_a_cv_with_no_identity_found_gets_409_not_a_hollow_pass(client, db, world, spy):
    """With nothing swapped, the two texts match trivially, and reporting that as a pass would be false."""
    fake.register("cv_mask", lambda *_: masker([], []))
    masked = identity.mask("Built a FastAPI service.", company_id=world.company_id)
    application = application_row(db, world, cv_text_raw="Built a FastAPI service.", cv_text_blind=masked.blind_text,
                                  cv_blind_hash=masked.blind_hash)
    spy.clear()
    response = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    assert response.status_code == 409
    assert spy == []


def test_a_label_as_the_only_identity_gets_409_because_its_value_was_masked_either_way(client, db, world, spy):
    fake.register("cv_mask", lambda *_: masker([], []))
    raw = "Gender: Male\nBuilt a FastAPI service."
    masked = identity.mask(raw, company_id=world.company_id)
    application = application_row(db, world, cv_text_raw=raw, cv_text_blind=masked.blind_text, cv_blind_hash=masked.blind_hash)
    spy.clear()
    response = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    assert response.status_code == 409
    assert spy == []


def test_blind_text_that_does_not_line_up_with_the_cv_gets_409(client, db, world):
    application = application_row(db, world, cv_text_raw=RAW, cv_text_blind="[NAME] wrote something else", cv_blind_hash="x")
    response = client.post(url(world, "fairness-check"), json={"application_id": application.id}, headers=hr())
    assert response.status_code == 409


def test_another_companys_application_gets_404(client, db, world):
    rival = application_row(db, world, company_id=world.rival_id, job_id=world.rival_job_id, cv_text_raw=RAW, cv_text_blind="b")
    response = client.post(url(world, "fairness-check"), json={"application_id": rival.id}, headers=hr())
    assert response.status_code == 404


def test_terms_are_recovered_from_the_blind_text_with_no_ai_call(spy):
    blind = "[NAME]\nEmail: [EMAIL]\n[GENDER] [NAME] built a FastAPI service. [GENDER] used Docker for 2 years."
    terms = fairness.found_terms(RAW, blind)
    assert terms["names"] == ["Canaryname Zebrawski", "Zebrawski"]
    assert terms["gender_terms"] == ["Mr.", "He"]
    assert spy == []


# 5. Withdrawing a consent


def consent_row(db, world, **columns):
    row = Consent(user_id=world.candidate_id, company_id=world.company_id, purpose="recording_screening",
                  text_version="v1", **columns)
    db.add(row)
    db.commit()
    return row


def test_the_owner_withdraws_a_consent(client, db, world):
    consent = consent_row(db, world)
    response = client.post(f"/api/me/consents/{consent.id}/withdraw", headers=auth_header(CANDIDATE))
    assert response.status_code == 200
    assert response.json()["withdrawn_at"]
    db.rollback()
    db.expire_all()
    assert db.get(Consent, consent.id).withdrawn_at is not None
    row = db.query(AuditLog).filter_by(action="consent_withdrawn", target_type="consent", target_id=consent.id).one()
    assert row.company_id == world.company_id
    assert CANDIDATE not in json.dumps(row.payload)


def test_another_users_consent_gets_404_and_stays(client, db, world):
    consent = consent_row(db, world)
    assert client.post(f"/api/me/consents/{consent.id}/withdraw", headers=auth_header(OTHER)).status_code == 404
    db.rollback()
    db.expire_all()
    assert db.get(Consent, consent.id).withdrawn_at is None
    assert db.query(AuditLog).filter_by(action="consent_withdrawn").count() == 0


def test_a_missing_consent_gets_the_same_404(client, world):
    response = client.post("/api/me/consents/999999/withdraw", headers=auth_header(CANDIDATE))
    assert response.status_code == 404


def test_withdrawing_twice_keeps_the_first_date_and_one_audit_row(client, db, world):
    earlier = utcnow().replace(microsecond=0) - timedelta(days=2)
    consent = consent_row(db, world, withdrawn_at=earlier)
    assert client.post(f"/api/me/consents/{consent.id}/withdraw", headers=auth_header(CANDIDATE)).status_code == 200
    db.rollback()
    db.expire_all()
    assert db.get(Consent, consent.id).withdrawn_at.replace(tzinfo=None) == earlier
    assert db.query(AuditLog).filter_by(action="consent_withdrawn").count() == 0


def test_withdrawing_needs_a_login(client, db, world):
    consent = consent_row(db, world)
    assert client.post(f"/api/me/consents/{consent.id}/withdraw").status_code == 401
