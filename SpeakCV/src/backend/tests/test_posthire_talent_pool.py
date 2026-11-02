"""The talent pool: its own consent, a retained masked CV that lasts only while the entry is valid, and re-assessment."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.ai import gateway
from app.ai.config import get_config
from app.ai.providers import fake
from app.ai.types import AIProviderError
from app.database.sql_models import (
    AIUsageLog, Application, AuditLog, Consent, CvClaim, Job, JobRequirement, Notification, RequirementResult,
    ScreeningCache, TalentPoolEntry, User, VoiceSession, VoiceTurn,
)
from app.hiring import consents, cv_processing, retention
from app.hiring import fake_demo as hiring_fake_demo
from app.posthire import talent_pool
from tests.helpers import auth_header, make_user
from tests.helpers_board import CANDIDATE_EMAIL, CANDIDATE_NAME, CV_RAW, make_application, make_world

STRONG_CV = "[NAME]\nBuilt a FastAPI service used by 3 teams.\nUsed Docker in production."
WEAK_CV = "[NAME]\nPlanned weddings and catered banquets across the region."


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def fakes(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path / "recordings"))
    hiring_fake_demo.install()


@pytest.fixture
def world(db):
    world = make_world(db)
    new_job = Job(company_id=world["company"].id, title="Platform", slug="platform", status="published", version=1,
                  description="Run FastAPI services with Docker in production.", interview_languages=["en"])
    db.add(new_job)
    db.commit()
    db.add_all([
        JobRequirement(company_id=new_job.company_id, job_id=new_job.id, text="FastAPI experience", must_have=True, position=0),
        JobRequirement(company_id=new_job.company_id, job_id=new_job.id, text="Docker in production", must_have=True, position=1),
    ])
    db.commit()
    world["new_job"] = new_job
    return world


_numbers = iter(range(1, 100000))


def rejected(db, job, blind=STRONG_CV, **columns):
    application = make_application(db, job, alias=f"#A{next(_numbers)}", hr_decision="rejected",
                                   hr_decided_at=utcnow(), **columns)
    application.cv_text_blind = blind
    application.cv_blind_hash = hashlib.sha256(blind.encode()).hexdigest()
    db.commit()
    return application


def owner(db, application):
    return db.get(User, application.candidate_user_id)


def headers_of(db, application):
    return auth_header(owner(db, application).email)


def join(db, application):
    user = owner(db, application)
    talent_pool.give_consent(db, application, user, consents.VERSION, "en")
    return talent_pool.opt_in(db, application, user)


def url_matches(world, job=None):
    return f"/api/companies/{world['company'].id}/jobs/{(job or world['new_job']).id}/talent-matches"


def url_invite(world, entry_id, company=None):
    return f"/api/companies/{(company or world['company']).id}/talent-pool/{entry_id}/invite"


def reload(db, row):
    db.expire_all()
    return db.get(type(row), row.id)


def elsewhere_application(db, world, candidate_user_id=None):
    application = make_application(db, world["other_job"], alias="#A1", hr_decision="rejected", hr_decided_at=utcnow())
    application.cv_text_blind = STRONG_CV
    if candidate_user_id is not None:
        application.candidate_user_id = candidate_user_id
    db.commit()
    return application


def _outage(*args, **kwargs):
    raise AIProviderError("down")


# Opting in


@pytest.mark.parametrize("language,months,purpose", [("en", "12 months", "future jobs"), ("vi", "12 tháng", "công việc")])
def test_consent_text_states_the_period_and_the_purpose_in_each_language(language, months, purpose):
    assert "talent_pool" in consents.PURPOSES
    text = consents.current_text("talent_pool", language).text
    assert months in text
    assert purpose in text


def test_the_consent_text_is_served(client, db, world):
    application = rejected(db, world["job"])
    response = client.get("/api/consents/talent_pool?language=vi", headers=headers_of(db, application))
    assert response.status_code == 200
    assert "12 tháng" in response.json()["text"]


@pytest.mark.parametrize("body", [{}, {"consent_version": "1999-01-01"}])
def test_opting_in_without_the_current_consent_gets_422_and_writes_nothing(client, db, world, body):
    application = rejected(db, world["job"])
    response = client.post(f"/api/applications/{application.id}/talent-pool", json=body, headers=headers_of(db, application))
    assert response.status_code == 422
    assert db.query(TalentPoolEntry).count() == 0
    assert db.query(Consent).filter_by(purpose="talent_pool").count() == 0


def test_the_service_refuses_with_no_consent_at_all(db, world):
    application = rejected(db, world["job"])
    with pytest.raises(talent_pool.ConsentRequired):
        talent_pool.opt_in(db, application, owner(db, application))
    assert db.query(TalentPoolEntry).count() == 0


def test_the_service_refuses_a_consent_to_an_older_text(db, world):
    application = rejected(db, world["job"])
    consents.record(db, application.candidate_user_id, application.company_id, application.id, "talent_pool", "1999-01-01")
    db.commit()
    with pytest.raises(talent_pool.ConsentRequired):
        talent_pool.opt_in(db, application, owner(db, application))


def test_another_purposes_consent_is_not_enough(db, world):
    application = rejected(db, world["job"])
    consents.record(db, application.candidate_user_id, application.company_id, application.id, "cv_processing", consents.VERSION)
    db.commit()
    with pytest.raises(talent_pool.ConsentRequired):
        talent_pool.opt_in(db, application, owner(db, application))


def test_opting_in_keeps_the_blind_cv_for_twelve_months(client, db, world):
    application = rejected(db, world["job"])
    response = client.post(f"/api/applications/{application.id}/talent-pool",
                           json={"consent_version": consents.VERSION, "consent_language": "vi"},
                           headers=headers_of(db, application))
    assert response.status_code == 200
    body = response.json()
    entry = db.get(TalentPoolEntry, body["id"])
    assert body["status"] == "active"
    assert entry.retained_cv_text == STRONG_CV
    assert CV_RAW not in entry.retained_cv_text
    assert entry.embedding is not None and entry.embedding_model == get_config().slot("embedding").model
    assert 364 <= (entry.expires_at - utcnow()).days <= 366
    consent = db.get(Consent, entry.consent_id)
    assert (consent.purpose, consent.text_version, consent.language) == ("talent_pool", consents.VERSION, "vi")
    assert consent.application_id == application.id and consent.company_id == application.company_id


def test_opting_in_never_returns_the_text(client, db, world):
    application = rejected(db, world["job"])
    response = client.post(f"/api/applications/{application.id}/talent-pool", json={"consent_version": consents.VERSION},
                           headers=headers_of(db, application))
    assert "FastAPI" not in response.text and "retained" not in response.text


def test_another_users_application_gets_404(client, db, world):
    application = rejected(db, world["job"])
    stranger = make_user(db, "stranger@example.test")
    response = client.post(f"/api/applications/{application.id}/talent-pool", json={"consent_version": consents.VERSION},
                           headers=auth_header(stranger.email))
    assert response.status_code == 404
    assert db.query(Consent).filter_by(purpose="talent_pool").count() == 0


def test_a_simulated_application_cannot_join(client, db, world):
    application = rejected(db, world["job"], is_simulated=True)
    response = client.post(f"/api/applications/{application.id}/talent-pool", json={"consent_version": consents.VERSION},
                           headers=headers_of(db, application))
    assert response.status_code == 404


@pytest.mark.parametrize("columns", [
    {"hr_decision": "pending", "hr_decided_at": None}, {"hr_decision": "approved"}, {"stage": "invited"},
])
def test_only_a_rejected_candidate_who_can_see_it_may_join(client, db, world, columns):
    application = rejected(db, world["job"])
    for name, value in columns.items():
        setattr(application, name, value)
    db.commit()
    response = client.post(f"/api/applications/{application.id}/talent-pool", json={"consent_version": consents.VERSION},
                           headers=headers_of(db, application))
    assert response.status_code == 409
    assert db.query(TalentPoolEntry).count() == 0
    assert db.query(Consent).filter_by(purpose="talent_pool").count() == 0


def test_opting_in_twice_changes_nothing(client, db, world):
    application = rejected(db, world["job"])
    url = f"/api/applications/{application.id}/talent-pool"
    first = client.post(url, json={"consent_version": consents.VERSION}, headers=headers_of(db, application)).json()
    second = client.post(url, json={"consent_version": consents.VERSION}, headers=headers_of(db, application)).json()
    assert second["id"] == first["id"] and second["expires_at"] == first["expires_at"]
    assert db.query(TalentPoolEntry).count() == 1
    assert db.query(Consent).filter_by(purpose="talent_pool").count() == 1


def test_joining_again_after_leaving_updates_the_one_row_with_a_new_consent(db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    entry_id, first_consent = entry.id, entry.consent_id
    talent_pool.leave(db, entry_id, owner(db, application))

    again = join(db, application)
    assert again.id == entry_id
    assert db.query(TalentPoolEntry).count() == 1
    assert again.status == "active" and again.retained_cv_text == STRONG_CV and again.embedding is not None
    assert again.consent_id != first_consent
    assert db.get(Consent, first_consent).withdrawn_at is not None


def test_joining_again_after_expiry_needs_a_new_consent(db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    entry.expires_at = utcnow() - timedelta(days=1)
    db.commit()
    talent_pool.expire(db)
    with pytest.raises(talent_pool.ConsentRequired):
        talent_pool.opt_in(db, application, owner(db, application))
    again = join(db, application)
    assert again.status == "active" and again.retained_cv_text == STRONG_CV
    assert again.expires_at > utcnow() + timedelta(days=300)
    assert db.query(TalentPoolEntry).count() == 1


def test_an_embedding_outage_does_not_stop_opting_in_and_matching_fills_it_later(db, world, monkeypatch):
    application = rejected(db, world["job"])
    real_embed = gateway.embed
    monkeypatch.setattr(gateway, "embed", _outage)
    entry = join(db, application)
    assert entry.status == "active" and entry.embedding is None

    monkeypatch.setattr(gateway, "embed", real_embed)
    assert [match.entry_id for match in talent_pool.matches(db, world["company"].id, world["new_job"].id)] == [entry.id]
    assert reload(db, entry).embedding is not None


def test_a_candidate_lists_their_own_entries_only(client, db, world):
    application = rejected(db, world["job"])
    other = rejected(db, world["job"])
    entry = join(db, application)
    join(db, other)
    body = client.get("/api/me/talent-pool", headers=headers_of(db, application)).json()
    assert [row["id"] for row in body] == [entry.id]
    assert body[0]["job_title"] == "Backend" and body[0]["company_name"] == "Acme"
    assert body[0]["status"] == "active" and body[0]["consent_id"] == entry.consent_id
    assert "retained_cv_text" not in body[0] and "embedding" not in body[0]


# Retention: the application follows Block 3, and the masked copy follows the entry


def with_a_recording(db, application):
    session = VoiceSession(company_id=application.company_id, purpose="screening", application_id=application.id,
                           owner_user_id=application.candidate_user_id, language="en", status="completed")
    db.add(session)
    db.commit()
    turn = VoiceTurn(session_id=session.id, position=0, question_text="q", question_source="must_have",
                     transcript="my spoken answer", transcript_status="done", audio_path="a/0.webm")
    db.add(turn)
    db.commit()
    return turn


def anonymized_by_retention(db, application):
    application.hr_decided_at = utcnow() - timedelta(days=4000)
    db.commit()
    assert retention.run(db) >= 1
    db.expire_all()


def test_retention_takes_audio_and_transcripts_and_the_entry_keeps_the_masked_cv(db, world):
    application = rejected(db, world["job"])
    turn = with_a_recording(db, application)
    entry = join(db, application)
    assert retention.has_extension(db, application) is False

    anonymized_by_retention(db, application)
    application = db.get(Application, application.id)
    assert application.anonymized_at is not None
    assert application.cv_text_blind is None and application.candidate_user_id is None
    assert db.get(VoiceTurn, turn.id).transcript is None and db.get(VoiceTurn, turn.id).audio_path is None
    entry = db.get(TalentPoolEntry, entry.id)
    assert entry.status == "active" and entry.retained_cv_text == STRONG_CV


def test_the_candidate_can_still_withdraw_after_their_application_is_anonymized(client, db, world):
    application = rejected(db, world["job"])
    headers = headers_of(db, application)
    entry = join(db, application)
    entry_id, consent_id = entry.id, entry.consent_id
    anonymized_by_retention(db, application)

    mine = client.get("/api/me/consents", headers=headers).json()
    assert [row["id"] for row in mine if row["purpose"] == "talent_pool"] == [consent_id]

    response = client.post(f"/api/me/consents/{consent_id}/withdraw", headers=headers)
    assert response.status_code == 200
    assert response.json()["purpose"] == "talent_pool"
    db.expire_all()
    # The entry was the last link between this person and the anonymized application, so it goes too.
    assert db.get(TalentPoolEntry, entry_id) is None
    consent = db.get(Consent, consent_id)
    assert consent.withdrawn_at is not None and consent.user_id is None
    audit = db.query(AuditLog).filter_by(action="consent_withdrawn", target_id=consent_id).one()
    assert audit.actor_user_id is None


def test_the_candidate_can_still_leave_after_their_application_is_anonymized(client, db, world):
    application = rejected(db, world["job"])
    headers = headers_of(db, application)
    entry = join(db, application)
    entry_id = entry.id
    anonymized_by_retention(db, application)
    response = client.post(f"/api/talent-pool/{entry_id}/leave", headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "left"
    db.expire_all()
    assert db.get(TalentPoolEntry, entry_id) is None


def test_withdrawing_the_consent_ends_the_entry_and_deletes_the_cv_at_once(client, db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    response = client.post(f"/api/me/consents/{entry.consent_id}/withdraw", headers=headers_of(db, application))
    assert response.status_code == 200
    entry = reload(db, entry)
    assert entry.status == "left"
    assert entry.retained_cv_text is None and entry.embedding is None and entry.embedding_model is None


def test_withdrawing_through_the_consents_module_does_the_same(db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    consents.withdraw(db, entry.consent_id, application.candidate_user_id)
    db.commit()
    entry = reload(db, entry)
    assert entry.status == "left" and entry.retained_cv_text is None


def test_withdrawing_another_consent_does_not_touch_the_entry(client, db, world):
    application = rejected(db, world["job"])
    other = consents.record(db, application.candidate_user_id, application.company_id, application.id, "cv_processing", consents.VERSION)
    db.commit()
    entry = join(db, application)
    assert client.post(f"/api/me/consents/{other.id}/withdraw", headers=headers_of(db, application)).status_code == 200
    entry = reload(db, entry)
    assert entry.status == "active" and entry.retained_cv_text == STRONG_CV


def test_the_candidates_own_delete_also_ends_the_entry(client, db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    entry_id, consent_id = entry.id, entry.consent_id
    response = client.delete(f"/api/me/applications/{application.id}", headers=headers_of(db, application))
    assert response.status_code == 204
    db.expire_all()
    assert db.get(TalentPoolEntry, entry_id) is None
    consent = db.get(Consent, consent_id)
    assert consent.withdrawn_at is not None and consent.user_id is None


def test_anonymizing_after_the_entry_ended_leaves_no_link_to_the_person(db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    entry_id = entry.id
    talent_pool.leave(db, entry_id, owner(db, application))
    anonymized_by_retention(db, application)
    assert db.get(TalentPoolEntry, entry_id) is None


def test_anonymizing_when_the_entry_is_past_its_date_ends_it(db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    entry_id, consent_id = entry.id, entry.consent_id
    entry.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    anonymized_by_retention(db, application)
    assert db.get(TalentPoolEntry, entry_id) is None
    assert db.get(Consent, consent_id).user_id is None


def test_a_person_at_two_companies_withdraws_from_one_only(client, db, world):
    application = rejected(db, world["job"])
    elsewhere = elsewhere_application(db, world, application.candidate_user_id)
    entry, other_entry = join(db, application), join(db, elsewhere)
    assert other_entry.company_id != entry.company_id

    response = client.post(f"/api/me/consents/{entry.consent_id}/withdraw", headers=headers_of(db, application))
    assert response.status_code == 200
    assert reload(db, entry).status == "left"
    other_entry = reload(db, other_entry)
    assert other_entry.status == "active" and other_entry.retained_cv_text == STRONG_CV
    assert db.get(Consent, other_entry.consent_id).withdrawn_at is None


def test_anonymizing_at_one_company_leaves_the_entry_at_the_other(db, world):
    application = rejected(db, world["job"])
    elsewhere = elsewhere_application(db, world, application.candidate_user_id)
    other_entry = join(db, elsewhere)
    application.hr_decided_at = utcnow() - timedelta(days=4000)
    db.commit()
    retention.anonymize_application(db, application, trigger=retention.TRIGGER_CANDIDATE)
    other_entry = reload(db, other_entry)
    assert other_entry.status == "active" and other_entry.retained_cv_text == STRONG_CV
    assert db.get(Consent, other_entry.consent_id).user_id == elsewhere.candidate_user_id


def test_two_entries_of_one_person_at_one_company_end_separately(db, world):
    first = rejected(db, world["job"])
    second = rejected(db, world["new_job"])
    second.candidate_user_id = first.candidate_user_id
    db.commit()
    entry_one, entry_two = join(db, first), join(db, second)
    talent_pool.leave(db, entry_one.id, owner(db, first))
    assert reload(db, entry_one).status == "left"
    assert reload(db, entry_two).status == "active"


# Matching


def test_matches_rank_by_cosine_reassess_and_show_no_identity(client, db, world):
    strong = rejected(db, world["job"])
    weak = rejected(db, world["job"], blind=WEAK_CV)
    strong_entry, weak_entry = join(db, strong), join(db, weak)
    response = client.get(url_matches(world), headers=world["people"]["hr"]["headers"])
    assert response.status_code == 200
    rows = response.json()
    assert [row["entry_id"] for row in rows] == [strong_entry.id, weak_entry.id]
    assert rows[0]["similarity"] > rows[1]["similarity"]
    assert rows[0]["alias"] == strong.alias and rows[1]["alias"] == weak.alias
    assert rows[0]["strength"] == "strong" and rows[1]["strength"] == "weak"
    assert rows[0]["must_haves_met"] == 2 and rows[0]["must_haves_total"] == 2
    assert {item["status"] for item in rows[0]["requirements"]} == {"met"}
    assert rows[1]["must_haves_met"] == 0
    for item in rows[0]["requirements"]:
        assert item["quote"] in STRONG_CV

    for secret in (CANDIDATE_NAME, CANDIDATE_EMAIL, CV_RAW, "candidate_user_id", "retained_cv_text", "cv_text"):
        assert secret not in response.text
    assert "weddings" not in response.text  # the masked CV itself is not sent, only verified quotes


def test_top_k_limits_what_is_assessed(db, world):
    for _ in range(3):
        join(db, rejected(db, world["job"], blind=f"[NAME]\nFastAPI and Docker in production, {next(_numbers)}."))
    assert len(talent_pool.matches(db, world["company"].id, world["new_job"].id, top_k=2)) == 2
    assert db.query(AIUsageLog).filter_by(feature="cv_assess").count() == 2


def test_an_empty_pool_makes_no_ai_call(db, world):
    assert talent_pool.matches(db, world["company"].id, world["new_job"].id) == []
    assert db.query(AIUsageLog).count() == 0


def test_a_job_that_cannot_be_embedded_gets_503(client, db, world, monkeypatch):
    join(db, rejected(db, world["job"]))
    monkeypatch.setattr(gateway, "embed", _outage)
    assert client.get(url_matches(world), headers=world["people"]["hr"]["headers"]).status_code == 503


def test_top_k_is_bounded_by_the_route(client, db, world):
    assert client.get(url_matches(world) + "?top_k=5000", headers=world["people"]["hr"]["headers"]).status_code == 422


def test_matching_writes_no_evidence_for_any_application(db, world):
    join(db, rejected(db, world["job"]))
    talent_pool.matches(db, world["company"].id, world["new_job"].id)
    assert db.query(RequirementResult).count() == 0
    assert db.query(CvClaim).count() == 0
    assert db.query(Application).count() == 1


def test_a_failed_assessment_keeps_the_match_marked_unassessed(db, world, monkeypatch):
    join(db, rejected(db, world["job"]))
    monkeypatch.setattr(gateway, "generate_structured", _outage)
    match = talent_pool.matches(db, world["company"].id, world["new_job"].id)[0]
    assert match.strength == "unassessed" and match.requirements == ()


def test_a_quote_the_cv_does_not_hold_counts_for_nothing(db, world):
    requirement_ids = [row.id for row in db.query(JobRequirement).filter_by(job_id=world["new_job"].id)]
    fake.register("cv_assess", lambda _s, _m, _schema: json.dumps({
        "requirements": [{"requirement_id": item, "status": "met", "quote": "not in the cv at all"} for item in requirement_ids],
        "claims": [],
    }))
    join(db, rejected(db, world["job"]))
    match = talent_pool.matches(db, world["company"].id, world["new_job"].id)[0]
    assert match.must_haves_met == 0 and match.strength == "weak"


def test_an_entry_embedded_with_another_model_is_embedded_again(db, world):
    entry = join(db, rejected(db, world["job"]))
    entry.embedding_model = "an-older-model"
    entry.embedding = b"\x00\x00\x80\x3f"
    db.commit()
    assert [m.entry_id for m in talent_pool.matches(db, world["company"].id, world["new_job"].id)] == [entry.id]
    assert reload(db, entry).embedding_model == get_config().slot("embedding").model


@pytest.mark.parametrize("end", ["left", "expired_not_swept", "swept", "withdrawn_only"])
def test_an_entry_no_longer_valid_is_never_matched(db, world, end):
    application = rejected(db, world["job"])
    entry = join(db, application)
    if end == "left":
        talent_pool.leave(db, entry.id, owner(db, application))
    elif end == "expired_not_swept":
        entry.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    elif end == "swept":
        entry.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        talent_pool.expire(db)
    else:  # defensive: a consent marked withdrawn by anything other than consents.withdraw
        db.get(Consent, entry.consent_id).withdrawn_at = utcnow()
        db.commit()
    assert talent_pool.matches(db, world["company"].id, world["new_job"].id) == []


def test_simulated_rows_are_never_matched(db, world):
    application = rejected(db, world["job"])
    join(db, application)
    application.is_simulated = True
    db.commit()
    assert talent_pool.matches(db, world["company"].id, world["new_job"].id) == []


def test_another_companys_entries_are_never_matched(db, world):
    join(db, elsewhere_application(db, world))
    assert talent_pool.matches(db, world["company"].id, world["new_job"].id) == []


def test_someone_who_recently_applied_to_the_job_is_left_out(db, world):
    application = rejected(db, world["job"])
    join(db, application)
    db.add(Application(company_id=world["company"].id, job_id=world["new_job"].id, job_version=1, alias="#A9000",
                       candidate_user_id=application.candidate_user_id, stage="invited"))
    db.commit()
    assert talent_pool.matches(db, world["company"].id, world["new_job"].id) == []


def test_the_job_someone_was_just_rejected_from_is_left_out(db, world):
    join(db, rejected(db, world["job"]))
    assert talent_pool.matches(db, world["company"].id, world["job"].id) == []


def test_the_same_job_stays_left_out_after_the_source_is_anonymized(db, world):
    application = rejected(db, world["job"])
    join(db, application)
    anonymized_by_retention(db, application)
    assert talent_pool.matches(db, world["company"].id, world["job"].id) == []


def test_one_person_with_two_entries_is_listed_once(db, world):
    first = rejected(db, world["job"])
    other_job = Job(company_id=world["company"].id, title="Other", slug="other-role", status="published", version=1,
                    interview_languages=["en"])
    db.add(other_job)
    db.commit()
    second = rejected(db, other_job)
    second.candidate_user_id = first.candidate_user_id
    db.commit()
    join(db, first)
    join(db, second)
    assert len(talent_pool.matches(db, world["company"].id, world["new_job"].id)) == 1


def test_a_job_of_another_company_gets_404(client, db, world):
    response = client.get(url_matches(world, world["other_job"]), headers=world["people"]["hr"]["headers"])
    assert response.status_code == 404


def test_matches_need_hr_of_this_company(client, db, world):
    assert client.get(url_matches(world), headers=world["people"]["emp"]["headers"]).status_code == 403
    assert client.get(url_matches(world), headers=world["people"]["hr2"]["headers"]).status_code == 403
    assert client.get(url_matches(world)).status_code == 401


def test_leaving_removes_the_match_results_no_application_uses(db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    talent_pool.matches(db, world["company"].id, world["new_job"].id)
    assert db.query(ScreeningCache).count() == 1
    application.cv_blind_hash = None  # as when the application itself has gone
    db.commit()
    talent_pool.leave(db, entry.id, owner(db, application))
    assert db.query(ScreeningCache).count() == 0


def test_a_leave_during_the_ai_call_discards_the_result(db, world):
    application = rejected(db, world["job"])
    entry = join(db, application)
    entry_id, user = entry.id, owner(db, application)
    application.cv_blind_hash = None
    db.commit()

    def leaves_while_assessing(_system, _messages, _schema):
        talent_pool.leave(db, entry_id, user)
        return json.dumps({"requirements": [], "claims": []})

    fake.register("cv_assess", leaves_while_assessing)
    assert talent_pool.matches(db, world["company"].id, world["new_job"].id) == []
    assert db.query(ScreeningCache).count() == 0


# Inviting


def invite_by_route(client, world, entry_id, job=None, headers=None, company=None):
    return client.post(url_invite(world, entry_id, company), json={"job_id": (job or world["new_job"]).id},
                       headers=headers or world["people"]["hr"]["headers"])


def test_invite_creates_a_new_application_and_earlier_evidence_is_not_reused(client, db, world):
    source = rejected(db, world["job"], hidden_text_detected=True)
    db.add(RequirementResult(application_id=source.id, requirement_id=world["requirements"][0].id, source="interview",
                             status="met", quote="a quote from an earlier interview"))
    db.add(CvClaim(application_id=source.id, text="an earlier claim", quote="earlier"))
    db.commit()
    entry = join(db, source)
    response = invite_by_route(client, world, entry.id)
    assert response.status_code == 201
    body = response.json()
    assert body["alias"] != source.alias
    assert "candidate_user_id" not in body and "FastAPI" not in response.text

    db.expire_all()
    application = db.get(Application, body["id"])
    assert application.source_channel == "talent_pool"
    assert application.job_id == world["new_job"].id
    assert application.candidate_user_id == source.candidate_user_id
    assert application.stage == "invited"  # the background job ran
    assert application.cv_status == "meets"
    assert application.cv_text_blind == STRONG_CV and application.cv_text_raw is None
    assert application.cv_file_path is None
    assert application.hidden_text_detected is True  # HR's warning follows the text
    assert application.hr_decision == "pending"
    assert db.query(VoiceSession).filter_by(application_id=application.id).count() == 0
    results = db.query(RequirementResult).filter_by(application_id=application.id).all()
    assert {row.source for row in results} == {"cv"}
    assert "a quote from an earlier interview" not in {row.quote for row in results}
    assert db.query(CvClaim).filter_by(application_id=application.id, text="an earlier claim").count() == 0
    # No masking call: the retained text was already masked.
    assert db.query(AIUsageLog).filter_by(feature="cv_mask").count() == 0


def test_the_candidate_is_notified_and_the_hr_action_is_audited(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    body = invite_by_route(client, world, entry.id).json()
    rows = db.query(Notification).filter_by(user_id=source.candidate_user_id, application_id=body["id"]).all()
    assert [row.kind for row in rows] == ["invited_from_pool"]
    assert "Platform" in rows[0].subject + rows[0].body
    audit = db.query(AuditLog).filter_by(action="talent_pool_invited", target_id=body["id"]).one()
    assert audit.actor_user_id == world["people"]["hr"]["id"]
    assert CANDIDATE_NAME not in json.dumps(audit.payload) and "FastAPI" not in json.dumps(audit.payload)


def test_the_invited_application_holds_no_consent_it_was_not_given(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    body = invite_by_route(client, world, entry.id).json()
    assert db.query(Consent).filter_by(application_id=body["id"]).count() == 0


@pytest.mark.parametrize("end", ["left", "swept", "expired_not_swept"])
def test_an_ended_entry_gets_409(client, db, world, end):
    source = rejected(db, world["job"])
    entry = join(db, source)
    if end == "left":
        talent_pool.leave(db, entry.id, owner(db, source))
    else:
        entry.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        if end == "swept":
            talent_pool.expire(db)
    assert invite_by_route(client, world, entry.id).status_code == 409
    assert db.query(Application).filter_by(source_channel="talent_pool").count() == 0


def test_another_companys_entry_gets_404(client, db, world):
    entry = join(db, elsewhere_application(db, world))
    assert invite_by_route(client, world, entry.id).status_code == 404
    assert db.query(Application).filter_by(source_channel="talent_pool").count() == 0


def test_a_job_of_another_company_cannot_be_the_target(client, db, world):
    entry = join(db, rejected(db, world["job"]))
    assert invite_by_route(client, world, entry.id, job=world["other_job"]).status_code == 404


def test_hr_of_another_company_cannot_invite(client, db, world):
    entry = join(db, rejected(db, world["job"]))
    assert invite_by_route(client, world, entry.id, headers=world["people"]["hr2"]["headers"]).status_code == 403
    # Through their own company the same entry does not exist.
    response = invite_by_route(client, world, entry.id, job=world["other_job"], headers=world["people"]["hr2"]["headers"],
                               company=world["other"])
    assert response.status_code == 404


def test_a_closed_job_gets_409(client, db, world):
    entry = join(db, rejected(db, world["job"]))
    world["new_job"].status = "closed"
    db.commit()
    assert invite_by_route(client, world, entry.id).status_code == 409


def test_inviting_twice_to_one_job_gets_409(client, db, world):
    entry = join(db, rejected(db, world["job"]))
    assert invite_by_route(client, world, entry.id).status_code == 201
    assert invite_by_route(client, world, entry.id).status_code == 409
    assert db.query(Application).filter_by(source_channel="talent_pool").count() == 1


def test_inviting_to_the_job_of_the_source_within_the_period_gets_409(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    entry_id = entry.id
    anonymized_by_retention(db, source)
    # Anonymizing removed the application's link to the person, and the source itself still counts.
    source_row = db.get(Application, source.id)
    source_row.created_at = utcnow() - timedelta(days=1)
    db.commit()
    assert invite_by_route(client, world, entry_id, job=world["job"]).status_code == 409


def test_a_simulated_entry_cannot_be_invited(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    source.is_simulated = True
    db.commit()
    assert invite_by_route(client, world, entry.id).status_code == 404


def test_an_anonymized_source_can_still_be_invited_from_the_retained_copy(client, db, world):
    source = rejected(db, world["job"])
    candidate_id = source.candidate_user_id
    entry = join(db, source)
    entry_id = entry.id
    anonymized_by_retention(db, source)
    response = invite_by_route(client, world, entry_id)
    assert response.status_code == 201
    db.expire_all()
    application = db.get(Application, response.json()["id"])
    assert application.candidate_user_id == candidate_id and application.cv_text_blind == STRONG_CV


def test_an_ai_failure_on_the_new_application_lets_the_candidate_retry(db, world, monkeypatch):
    entry = join(db, rejected(db, world["job"]))
    application = talent_pool.invite(db, entry, world["new_job"], world["people"]["hr"]["id"])
    monkeypatch.setattr(gateway, "generate_structured", _outage)
    cv_processing.run_from_blind_text(application.id, STRONG_CV)
    application = reload(db, application)
    assert application.stage == "cv_failed" and application.processing_error == cv_processing.TRY_AGAIN


def test_the_job_runs_once(db, world):
    entry = join(db, rejected(db, world["job"]))
    application = talent_pool.invite(db, entry, world["new_job"], world["people"]["hr"]["id"])
    cv_processing.run_from_blind_text(application.id, STRONG_CV)
    assert reload(db, application).stage == "invited"
    cv_processing.run_from_blind_text(application.id, "another text entirely")
    application = reload(db, application)
    assert application.stage == "invited" and application.cv_text_blind == STRONG_CV


# An invitation the candidate has not acted on holds a copy of the same CV, so it goes with the entry


def test_leaving_withdraws_an_invitation_not_yet_started(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    invited = invite_by_route(client, world, entry.id).json()["id"]
    assert client.post(f"/api/talent-pool/{entry.id}/leave", headers=headers_of(db, source)).status_code == 200
    db.expire_all()
    application = db.get(Application, invited)
    assert application.anonymized_at is not None
    assert application.cv_text_blind is None and application.candidate_user_id is None
    assert db.query(Notification).filter_by(application_id=invited).count() == 0


def test_withdrawing_the_consent_stops_a_cv_job_still_waiting(db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    application = talent_pool.invite(db, entry, world["new_job"], world["people"]["hr"]["id"])
    application_id = application.id
    consents.withdraw(db, entry.consent_id, source.candidate_user_id)
    db.commit()
    cv_processing.run_from_blind_text(application_id, STRONG_CV)
    application = reload(db, application)
    assert application.anonymized_at is not None and application.cv_text_blind is None


def test_a_withdrawal_during_the_assessment_cannot_write_the_text_back(db, world):
    source = rejected(db, world["job"])
    source.cv_blind_hash = None  # only the invited application holds the hash, as when the source has gone
    db.commit()
    entry = join(db, source)
    consent_id, user_id = entry.consent_id, source.candidate_user_id
    application = talent_pool.invite(db, entry, world["new_job"], world["people"]["hr"]["id"])
    application_id = application.id

    def withdraws_while_assessing(_system, _messages, _schema):
        consents.withdraw(db, consent_id, user_id)
        db.commit()
        return json.dumps({"requirements": [], "claims": []})

    fake.register("cv_assess", withdraws_while_assessing)
    cv_processing.run_from_blind_text(application_id, STRONG_CV)
    application = reload(db, application)
    assert application.anonymized_at is not None and application.cv_text_blind is None
    assert db.query(ScreeningCache).count() == 0


def test_leaving_keeps_an_application_the_candidate_has_already_started(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    invited = invite_by_route(client, world, entry.id).json()["id"]
    db.add(VoiceSession(company_id=source.company_id, purpose="screening", application_id=invited,
                        owner_user_id=source.candidate_user_id, language="en", status="in_progress"))
    db.commit()
    client.post(f"/api/talent-pool/{entry.id}/leave", headers=headers_of(db, source))
    db.expire_all()
    application = db.get(Application, invited)
    assert application.anonymized_at is None and application.cv_text_blind == STRONG_CV


def test_leaving_keeps_an_application_with_a_different_cv(db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    other_cv = rejected(db, world["new_job"], blind="[NAME]\nA different CV.", source_channel="talent_pool")
    other_cv.candidate_user_id = source.candidate_user_id
    other_cv.hr_decision = "pending"
    other_cv.stage = "invited"
    db.commit()
    talent_pool.leave(db, entry.id, owner(db, source))
    assert reload(db, other_cv).anonymized_at is None


def test_expiry_keeps_an_invitation_already_made(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    invited = invite_by_route(client, world, entry.id).json()["id"]
    entry.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    talent_pool.expire(db)
    db.expire_all()
    assert db.get(Application, invited).anonymized_at is None


# Leaving


def test_leaving_deletes_the_cv_withdraws_the_consent_and_is_idempotent(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    headers = headers_of(db, source)
    first = client.post(f"/api/talent-pool/{entry.id}/leave", headers=headers)
    assert first.status_code == 200 and first.json() == {"id": entry.id, "status": "left"}
    entry = reload(db, entry)
    assert entry.status == "left"
    assert entry.retained_cv_text is None and entry.embedding is None and entry.embedding_model is None
    consent = db.get(Consent, entry.consent_id)
    withdrawn_at = consent.withdrawn_at
    assert withdrawn_at is not None
    assert db.query(AuditLog).filter_by(action="consent_withdrawn", target_id=consent.id).count() == 1

    second = client.post(f"/api/talent-pool/{entry.id}/leave", headers=headers)
    assert second.status_code == 200 and second.json() == {"id": entry.id, "status": "left"}
    assert reload(db, consent).withdrawn_at == withdrawn_at
    assert db.query(AuditLog).filter_by(action="consent_withdrawn", target_id=consent.id).count() == 1


def test_leaving_when_the_consent_was_already_marked_withdrawn_still_deletes_the_cv(db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    db.get(Consent, entry.consent_id).withdrawn_at = utcnow()
    db.commit()
    assert talent_pool.leave(db, entry.id, owner(db, source)) == "left"
    assert reload(db, entry).retained_cv_text is None


def test_another_user_gets_404_and_nothing_changes(client, db, world):
    entry = join(db, rejected(db, world["job"]))
    stranger = make_user(db, "stranger@example.test")
    assert client.post(f"/api/talent-pool/{entry.id}/leave", headers=auth_header(stranger.email)).status_code == 404
    entry = reload(db, entry)
    assert entry.status == "active" and entry.retained_cv_text == STRONG_CV


def test_leaving_an_expired_entry_keeps_its_status_and_withdraws_the_consent(client, db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    entry.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    talent_pool.expire(db)
    response = client.post(f"/api/talent-pool/{entry.id}/leave", headers=headers_of(db, source))
    assert response.status_code == 200 and response.json()["status"] == "expired"
    assert db.get(Consent, reload(db, entry).consent_id).withdrawn_at is not None


# Expiry


def test_expire_deletes_the_text_after_the_date_and_not_before(db, world):
    due = join(db, rejected(db, world["job"]))
    not_due = join(db, rejected(db, world["job"]))
    due.expires_at = utcnow() - timedelta(days=1)
    not_due.expires_at = utcnow() + timedelta(days=1)
    db.commit()

    assert talent_pool.expire(db) == 1
    due, not_due = reload(db, due), reload(db, not_due)
    assert due.status == "expired"
    assert due.retained_cv_text is None and due.embedding is None and due.embedding_model is None
    assert not_due.status == "active" and not_due.retained_cv_text == STRONG_CV
    assert talent_pool.expire(db) == 0


def test_expire_takes_a_time(db, world):
    entry = join(db, rejected(db, world["job"]))
    assert talent_pool.expire(db, now=utcnow() + timedelta(days=200)) == 0
    assert talent_pool.expire(db, now=utcnow() + timedelta(days=400)) == 1
    assert reload(db, entry).status == "expired"


def test_expiry_after_anonymizing_removes_the_copy_and_the_last_link(db, world):
    source = rejected(db, world["job"])
    entry = join(db, source)
    entry_id, consent_id = entry.id, entry.consent_id
    anonymized_by_retention(db, source)
    assert talent_pool.expire(db, now=utcnow() + timedelta(days=400)) == 1
    db.expire_all()
    assert db.get(TalentPoolEntry, entry_id) is None
    assert db.get(Consent, consent_id).user_id is None


def test_one_failing_entry_does_not_stop_the_others(db, world, monkeypatch):
    first, second = join(db, rejected(db, world["job"])), join(db, rejected(db, world["job"]))
    first.expires_at = second.expires_at = utcnow() - timedelta(days=1)
    db.commit()
    first_id = first.id
    real_end = talent_pool._end

    def fails_once(session, entry, *args, **kwargs):
        if entry.id == first_id:
            raise RuntimeError("no")
        return real_end(session, entry, *args, **kwargs)

    monkeypatch.setattr(talent_pool, "_end", fails_once)
    assert talent_pool.expire(db) == 1
    monkeypatch.setattr(talent_pool, "_end", real_end)
    assert talent_pool.expire(db) == 1


def test_the_daily_pass_expires_entries(db, world):
    entry = join(db, rejected(db, world["job"]))
    entry.expires_at = utcnow() - timedelta(days=1)
    db.commit()
    retention._daily_pass()
    assert reload(db, entry).status == "expired"


# Beside the re-apply guard and consent withdrawal (Block 3 final review fixes)


def _in_the_pool_with_a_session(db, world):
    application = rejected(db, world["job"])
    db.add(VoiceSession(company_id=application.company_id, purpose="screening", application_id=application.id,
                        owner_user_id=application.candidate_user_id, language="en", status="completed"))
    db.commit()
    user_id = application.candidate_user_id
    join(db, application)
    return application.id, user_id


def test_retention_keeps_a_valid_entry_and_also_leaves_the_guard(db, world):
    from app.database.sql_models import ReapplyGuard
    from app.hiring import reapply_guard

    application_id, user_id = _in_the_pool_with_a_session(db, world)
    job_id = world["job"].id
    retention.anonymize_application(db, db.get(Application, application_id))
    db.rollback()
    entry = db.query(TalentPoolEntry).filter_by(source_application_id=application_id).one()
    assert entry.status == "active" and entry.retained_cv_text
    consent = db.get(Consent, entry.consent_id)
    assert consent.user_id == user_id and consent.withdrawn_at is None
    assert db.query(ReapplyGuard).count() == 1
    assert reapply_guard.blocked_until(db, user_id, job_id) is not None


def test_a_guard_stops_an_invitation_to_that_job_and_only_that_job(client, db, world):
    from app.hiring import applications as hiring_applications
    from app.hiring import reapply_guard

    application_id, user_id = _in_the_pool_with_a_session(db, world)
    other = make_application(db, world["job"], alias=f"#A{next(_numbers)}")
    other_user = other.candidate_user_id
    assert other_user != user_id
    reapply_guard.remember(db, user_id, world["new_job"].id, utcnow() - timedelta(days=1))
    db.commit()
    with pytest.raises(hiring_applications.AlreadyApplied):
        hiring_applications.check_reapply(db, user_id, world["new_job"].id)
    assert talent_pool._candidate_rows(db, world["company"].id, world["new_job"].id, utcnow()) == []
    other_job = Job(company_id=world["company"].id, title="Third", slug="third", status="published", version=1, interview_languages=["en"])
    db.add(other_job)
    db.commit()
    assert len(talent_pool._candidate_rows(db, world["company"].id, other_job.id, utcnow())) == 1


def test_withdrawing_the_pool_consent_after_anonymizing_goes_through_the_route_and_names_nobody(client, db, world):
    application_id, user_id = _in_the_pool_with_a_session(db, world)
    email = db.get(User, user_id).email
    retention.anonymize_application(db, db.get(Application, application_id))
    db.rollback()
    consent_id = db.query(TalentPoolEntry).filter_by(source_application_id=application_id).one().consent_id
    response = client.post(f"/api/me/consents/{consent_id}/withdraw", headers=auth_header(email))
    assert response.status_code == 200, response.text
    db.rollback()
    db.expire_all()
    assert db.query(TalentPoolEntry).filter_by(source_application_id=application_id).count() == 0
    consent = db.get(Consent, consent_id)
    assert consent.withdrawn_at is not None and consent.user_id is None
    row = db.query(AuditLog).filter_by(action="consent_withdrawn", target_id=consent_id).one()
    assert row.actor_user_id is None


def test_a_withdrawal_that_retracts_an_invitation_commits_both_in_one_transaction(client, db, world):
    """anonymize_application shares the caller's transaction here: its rollback must not undo the withdrawal."""
    application = rejected(db, world["job"])
    email = owner(db, application).email
    entry = join(db, application)
    consent_id, entry_id = entry.consent_id, entry.id
    invited = talent_pool.invite(db, entry, world["new_job"], world["people"]["hr"]["id"])
    invited_id = invited.id
    db.query(Application).filter_by(id=invited_id).update({"cv_blind_hash": application.cv_blind_hash})
    db.commit()
    response = client.post(f"/api/me/consents/{consent_id}/withdraw", headers=auth_header(email))
    assert response.status_code == 200, response.text
    db.rollback()
    db.expire_all()
    assert db.get(Consent, consent_id).withdrawn_at is not None
    assert db.get(TalentPoolEntry, entry_id).status == "left"
    assert db.get(Application, invited_id).anonymized_at is not None


def test_commit_false_keeps_what_the_caller_has_pending(db, world):
    application = rejected(db, world["job"])
    application_id = application.id
    db.add(AuditLog(company_id=application.company_id, action="callers_own_work", target_type="application", target_id=application_id))
    assert retention.anonymize_application(db, application, commit=False) is True
    db.rollback()
    assert db.query(AuditLog).filter_by(action="callers_own_work").count() == 0  # nothing was committed for the caller
    assert db.get(Application, application_id).anonymized_at is None


def test_deleting_the_source_erases_questions_once_the_invitation_it_retracts_is_gone(client, db, world):
    from app.database.sql_models import AssistantQuestion

    application = rejected(db, world["job"])
    application_id, user_id = application.id, application.candidate_user_id
    email = owner(db, application).email
    entry = join(db, application)
    invited = talent_pool.invite(db, entry, world["new_job"], world["people"]["hr"]["id"])
    db.query(Application).filter_by(id=invited.id).update({"cv_blind_hash": application.cv_blind_hash})
    question = AssistantQuestion(company_id=world["company"].id, user_id=user_id, audience="candidate", question="Is there leave?",
                                 language="en", answered=False)
    db.add(question)
    db.commit()
    question_id = question.id
    assert client.delete(f"/api/me/applications/{application_id}", headers=auth_header(email)).status_code == 204
    db.rollback()
    db.expire_all()
    row = db.get(AssistantQuestion, question_id)
    assert row.user_id is None and row.question == ""

