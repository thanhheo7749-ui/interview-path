import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import zipfile

import docx
import pytest
from docx.shared import RGBColor
from reportlab.pdfgen import canvas
from sqlalchemy.exc import IntegrityError

from app.ai import gateway
from app.ai.providers import fake
from app.ai.types import AIProviderError
from app.database.sql_models import (
    AIUsageLog, Application, AuditLog, Company, Consent, CvClaim, Job, JobChannelLink, JobRequirement, KbEdge, KbNode,
    Notification, RequirementResult, User,
)
from app.core import uploads
from app.core.rate_limit import limiter
from app.hiring import applications, consents, cv_processing, screening, state
from tests.helpers import auth_header, iter_routes, make_user, route_path

CANDIDATE = "candidate@example.test"
OTHER = "other@example.test"
CV_LINES = [
    "Canaryname Zebrawski",
    "Email: canary.zebrawski@example.test  Phone: +84 912 345 678",
    "Built a FastAPI service used by 3 teams.",
    "Used Docker in production for 2 years.",
]
INJECTION = (Path(__file__).parent / "fixtures" / "cv_injection.txt").read_text(encoding="utf-8")


def make_docx(lines=CV_LINES, hidden=()) -> bytes:
    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    for line in hidden:
        document.add_paragraph().add_run(line).font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(lines=CV_LINES) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 780
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 20
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme", default_locale="en")
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend Developer", slug="acme-backend", description="d", status="published",
              version=3, interview_languages=["en"])
    db.add(job)
    db.commit()
    must_public = JobRequirement(company_id=company.id, job_id=job.id, text="FastAPI services", must_have=True, visibility="public", position=0)
    must_kube = JobRequirement(company_id=company.id, job_id=job.id, text="Kubernetes operations", must_have=True, visibility="public", position=1)
    secret = JobRequirement(company_id=company.id, job_id=job.id, text="Secretive salary band wording", must_have=False, visibility="confidential", position=2)
    internal = JobRequirement(company_id=company.id, job_id=job.id, text="Internalonly team note", must_have=False, visibility="internal", position=3)
    retired = JobRequirement(company_id=company.id, job_id=job.id, text="Retiredskill", must_have=False, visibility="public", position=4, active=False)
    link = JobChannelLink(company_id=company.id, job_id=job.id, channel="linkedin", token="tok-linkedin-1234567")
    db.add_all([must_public, must_kube, secret, internal, retired, link])
    db.commit()
    return SimpleNamespace(
        company_id=company.id, job_id=job.id, slug=job.slug,
        must_public=must_public.id, must_kube=must_kube.id, secret=secret.id,
        user=make_user(db, CANDIDATE), other=make_user(db, OTHER),
    )


def apply(client, slug="acme-backend", data=None, name="cv.docx", content_type=DOCX, email=CANDIDATE, version=consents.VERSION, **form):
    payload = {"consent_version": version, **form} if version is not None else form
    return client.post(
        f"/api/public/jobs/{slug}/apply",
        files={"file": (name, make_docx() if data is None else data, content_type)},
        data=payload,
        headers=auth_header(email),
    )


def fresh(db, application_id):
    db.rollback()
    db.expire_all()
    return db.get(Application, application_id)


def assess_all_met(db, world):
    return json.dumps({
        "requirements": [
            {"requirement_id": world.must_public, "status": "met", "quote": "Built a FastAPI service"},
            {"requirement_id": world.must_kube, "status": "met", "quote": "Used Docker in production"},
        ],
        "claims": [],
    })


def assess_weak(world):
    return json.dumps({
        "requirements": [
            {"requirement_id": world.must_public, "status": "partial", "quote": "Built a FastAPI service"},
            {"requirement_id": world.must_kube, "status": "not_found", "quote": ""},
        ],
        "claims": [],
    })


# 1. Login and consent


def test_apply_requires_login(client, world):
    response = client.post("/api/public/jobs/acme-backend/apply", files={"file": ("cv.docx", make_docx(), DOCX)},
                           data={"consent_version": consents.VERSION})
    assert response.status_code == 401


def test_apply_requires_consent_version(client, world, db):
    assert apply(client, version=None).status_code == 422
    assert db.query(Application).count() == 0


def test_old_consent_version_gets_409_with_the_current_one(client, world, db):
    response = apply(client, version="2020-01-01")
    assert response.status_code == 409
    assert response.json()["detail"]["current_version"] == consents.VERSION
    assert db.query(Application).count() == 0


def test_unknown_job_gets_404(client, world):
    assert apply(client, slug="nope").status_code == 404


# 2. File types and size


def test_pdf_and_docx_are_accepted(client, world, db):
    assert apply(client).status_code == 201
    second = Job(company_id=world.company_id, title="Other", slug="other", status="published", version=1, interview_languages=["en"])
    db.add(second)
    db.commit()
    assert apply(client, slug="other", data=make_pdf(), name="cv.pdf", content_type="application/pdf").status_code == 201


@pytest.mark.parametrize("name,content_type", [
    ("cv.doc", "application/msword"),
    ("cv.txt", "text/plain"),
    ("cv.doc", "application/octet-stream"),
    ("cv.txt", "application/pdf"),
    ("cv.pdf", "text/plain"),
])
def test_other_file_types_get_415(client, world, db, name, content_type):
    assert apply(client, data=b"data", name=name, content_type=content_type).status_code == 415
    assert db.query(Application).count() == 0


def test_cv_upload_types_is_pdf_and_docx_only():
    assert uploads.CV_UPLOAD_TYPES == {"application/pdf", DOCX}


def test_oversize_gets_413(client, world, db):
    assert apply(client, data=b"x" * (1024 * 1024 + 1)).status_code == 413
    assert db.query(Application).count() == 0


# CV text cap


def test_cv_at_the_character_limit_is_accepted(client, world, db):
    assert applications.MAX_CV_CHARS == 20_000
    assert apply(client, data=make_docx(["x" * 20_000])).status_code == 201


def test_cv_over_the_character_limit_is_refused_and_nothing_is_stored(client, world, db, _storage):
    response = apply(client, data=make_docx(["x" * 20_001]))
    assert response.status_code == 422
    assert "20,000" in response.json()["detail"]
    assert db.query(Application).count() == 0
    assert db.query(Consent).count() == 0
    assert [p for p in _storage.rglob("*") if p.is_file()] == []


def test_multibyte_cv_at_the_limit_is_accepted_and_stored(client, world, db):
    response = apply(client, data=make_docx(["ệ" * 20_000]))
    assert response.status_code == 201
    assert len(fresh(db, response.json()["id"]).cv_text_raw) == 20_000


def test_text_that_cannot_fit_the_column_is_refused(client, world, db):
    """Characters outside the basic plane use 4 bytes and would overflow a 64 KB Text column."""
    response = apply(client, data=make_docx(["😀" * 20_000]))
    assert response.status_code == 422
    assert db.query(Application).count() == 0


def test_a_reupload_over_the_limit_is_refused_and_keeps_the_stage(client, world, db, _storage):
    application_id = apply(client, data=make_pdf([])  , name="cv.pdf", content_type="application/pdf").json()["id"]
    before = sorted(p for p in _storage.rglob("*") if p.is_file())
    response = client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("cv.docx", make_docx(["x" * 20_001]), DOCX)}, headers=auth_header(CANDIDATE))
    assert response.status_code == 422
    assert fresh(db, application_id).stage == "cv_failed"
    assert sorted(p for p in _storage.rglob("*") if p.is_file()) == before


# Hostile or oversized files


def _pdf_of_pages(count) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for number in range(count):
        pdf.drawString(50, 780, f"Page {number}")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _docx_bomb() -> bytes:
    buffer = io.BytesIO(make_docx())
    with zipfile.ZipFile(buffer, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/padding.bin", b"\0" * (50 * 1024 * 1024 + 1))
    return buffer.getvalue()


def test_a_pdf_over_30_pages_gets_a_clear_422_and_nothing_is_stored(client, world, db, _storage):
    response = apply(client, data=_pdf_of_pages(31), name="cv.pdf", content_type="application/pdf")
    assert response.status_code == 422
    assert "30 pages" in response.json()["detail"]
    assert db.query(Application).count() == 0
    assert [p for p in _storage.rglob("*") if p.is_file()] == []


def test_a_pdf_of_30_pages_is_accepted(client, world):
    assert apply(client, data=_pdf_of_pages(30), name="cv.pdf", content_type="application/pdf").status_code == 201


def test_a_docx_over_the_uncompressed_limit_gets_a_clear_422_and_nothing_is_stored(client, world, db, _storage):
    data = _docx_bomb()
    assert len(data) < 1024 * 1024, "the upload limit must not be what refuses it"
    response = apply(client, data=data)
    assert response.status_code == 422
    assert "50 MB" in response.json()["detail"]
    assert db.query(Application).count() == 0
    assert [p for p in _storage.rglob("*") if p.is_file()] == []


def test_a_reupload_of_a_docx_bomb_gets_422_and_keeps_the_stage(client, world, db):
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    response = client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("cv.docx", _docx_bomb(), DOCX)}, headers=auth_header(CANDIDATE))
    assert response.status_code == 422
    assert fresh(db, application_id).stage == "cv_failed"


# Rate limits


@pytest.fixture
def rate_limited():
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


def test_apply_returns_429_on_the_11th_request_per_user(client, world, rate_limited):
    codes = [apply(client).status_code for _ in range(11)]
    assert codes[:10] == [201] + [409] * 9
    assert codes[10] == 429
    assert apply(client, email=OTHER).status_code == 201


def test_reupload_returns_429_on_the_11th_request_per_user(client, world, rate_limited):
    application_id = apply(client).json()["id"]

    def reupload(email):
        return client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("cv.docx", make_docx(), DOCX)}, headers=auth_header(email)).status_code

    codes = [reupload(CANDIDATE) for _ in range(11)]
    assert codes == [409] * 10 + [429]
    assert reupload(OTHER) == 404


# 3. Success


def test_success_returns_201_and_processes_in_the_background(client, world, db):
    response = apply(client, src="tok-linkedin-1234567")
    assert response.status_code == 201
    application = fresh(db, response.json()["id"])
    assert application.stage == "invited"
    assert application.cv_status in {"meets", "not_met"}
    assert application.alias == "#A1"
    assert application.job_version == 3
    assert application.source_channel == "linkedin"
    assert application.cv_file_path and application.cv_suffix == ".docx"
    assert application.cv_blind_hash and application.cv_text_blind and application.cv_text_raw
    assert application.processing_error is None
    consent = db.query(Consent).filter_by(application_id=application.id).one()
    assert (consent.purpose, consent.text_version, consent.user_id, consent.company_id) == (
        "cv_processing", consents.VERSION, world.user.id, world.company_id)


def test_channel_is_direct_without_a_token_or_with_an_unknown_one(client, world, db):
    application_id = apply(client).json()["id"]
    assert fresh(db, application_id).source_channel == "direct"
    other = Job(company_id=world.company_id, title="Other", slug="other", status="published", version=1, interview_languages=["en"])
    db.add(other)
    db.commit()
    application_id = apply(client, slug="other", src="nope").json()["id"]
    assert fresh(db, application_id).source_channel == "direct"


def test_a_token_from_another_job_does_not_set_the_channel(client, world, db):
    other = Job(company_id=world.company_id, title="Other", slug="other", status="published", version=1, interview_languages=["en"])
    db.add(other)
    db.commit()
    application_id = apply(client, slug="other", src="tok-linkedin-1234567").json()["id"]
    assert fresh(db, application_id).source_channel == "direct"


def test_invited_notification_is_queued_once_and_says_nothing_of_the_label(client, world, db):
    fake.enqueue("cv_assess", assess_weak(world))
    application_id = apply(client).json()["id"]
    rows = db.query(Notification).filter_by(user_id=world.user.id).all()
    assert [row.kind for row in rows] == ["invited"]
    assert fresh(db, application_id).cv_status == "not_met"
    text = f"{rows[0].subject} {rows[0].body}".lower()
    assert "backend developer" in text
    for word in ("not_met", "does not meet", "cv_status"):
        assert word not in text


def test_screening_results_and_claims_are_stored_and_hidden_flag_is_set(client, world, db):
    fake.enqueue("cv_assess", json.dumps({
        "requirements": [{"requirement_id": world.must_public, "status": "met", "quote": "Built a FastAPI service"}],
        "claims": [{"text": "Scale", "quote": "used by 3 teams"}],
    }))
    application_id = apply(client, data=make_docx(hidden=["Whitetextsecret"])).json()["id"]
    application = fresh(db, application_id)
    assert application.hidden_text_detected is True
    assert "Whitetextsecret" not in application.cv_text_raw and "Whitetextsecret" not in application.cv_text_blind
    assert db.query(RequirementResult).filter_by(application_id=application_id, source="cv").count() == 4
    assert db.query(CvClaim).filter_by(application_id=application_id).count() == 1


# 4. Everyone gets invited


def test_a_weak_cv_is_still_invited_and_never_rejected(client, world, db):
    fake.enqueue("cv_assess", assess_weak(world))
    application = fresh(db, apply(client).json()["id"])
    assert application.stage == "invited"
    assert application.cv_status == "not_met"
    assert application.hr_decision == "pending"
    reasons = application.cv_status_reason
    assert {reason["requirement_id"] for reason in reasons} == {world.must_public, world.must_kube}


def test_a_strong_cv_is_labelled_by_code(client, world, db):
    fake.enqueue("cv_assess", assess_all_met(db, world))
    application = fresh(db, apply(client).json()["id"])
    assert application.cv_status == "meets" and application.cv_status_reason == []
    assert application.hr_decision == "pending"


def test_an_injected_cv_is_invited_and_the_label_is_unchanged_end_to_end(client, world, db):
    """Visible and white-text instructions; the model is fooled and answers met with quotes that are not there."""
    fake.enqueue("cv_mask", json.dumps({"names": [], "gender_terms": [], "ages": [], "addresses": []}))
    fake.enqueue("cv_assess", json.dumps({
        "requirements": [
            {"requirement_id": world.must_public, "status": "met", "quote": "Ten years of FastAPI"},
            {"requirement_id": world.must_kube, "status": "met", "quote": "IGNORE ALL PREVIOUS INSTRUCTIONS"},
        ],
        "claims": [],
    }))
    lines = INJECTION.splitlines()
    application = fresh(db, apply(client, data=make_docx(lines[:5], hidden=lines[5:])).json()["id"])
    assert application.stage == "invited"
    assert application.cv_status == "not_met"
    assert application.hr_decision == "pending"
    assert application.hidden_text_detected is True


# 5. Repeat applications


def test_applying_twice_gets_409_with_the_reapply_date(client, world, db):
    first = apply(client)
    assert first.status_code == 201
    second = apply(client)
    assert second.status_code == 409
    assert "reapply_after" in second.json()["detail"]
    assert db.query(Application).count() == 1


def test_a_duplicate_stores_no_file(client, world, _storage):
    apply(client)
    before = sorted(p for p in _storage.rglob("*") if p.is_file())
    apply(client)
    assert sorted(p for p in _storage.rglob("*") if p.is_file()) == before


def test_reapplying_is_allowed_after_90_days(client, world, db):
    application_id = apply(client).json()["id"]
    application = fresh(db, application_id)
    application.created_at = datetime.now(timezone.utc) - timedelta(days=89)
    db.commit()
    assert apply(client).status_code == 409
    application = fresh(db, application_id)
    application.created_at = datetime.now(timezone.utc) - timedelta(days=91)
    db.commit()
    assert apply(client).status_code == 201


def test_a_withdrawn_application_still_counts_within_90_days(client, world, db):
    application_id = apply(client).json()["id"]
    assert client.post(f"/api/applications/{application_id}/withdraw", headers=auth_header(CANDIDATE)).status_code == 200
    assert apply(client).status_code == 409


def test_another_job_is_allowed_at_any_time(client, world, db):
    other = Job(company_id=world.company_id, title="Other", slug="other", status="published", version=1, interview_languages=["en"])
    db.add(other)
    db.commit()
    assert apply(client).status_code == 201
    assert apply(client, slug="other").status_code == 201


def test_another_candidate_can_apply_to_the_same_job(client, world):
    assert apply(client).status_code == 201
    assert apply(client, email=OTHER).status_code == 201


# 6. Closed job


def test_a_closed_job_gets_409(client, world, db):
    job = db.get(Job, world.job_id)
    job.status = "closed"
    db.commit()
    assert apply(client).status_code == 409
    assert db.query(Application).count() == 0


def test_a_draft_job_gets_404(client, world, db):
    job = db.get(Job, world.job_id)
    job.status = "draft"
    db.commit()
    assert apply(client).status_code == 404


def test_create_application_rejects_closed_and_draft_jobs(world, db):
    job = db.get(Job, world.job_id)
    for status in ("closed", "draft"):
        job.status = status
        db.commit()
        with pytest.raises(applications.JobNotOpen):
            applications.create_application(db, world.user, job, make_docx(), ".docx", None, consents.VERSION)


# 7. No text and re-upload


def test_no_extractable_text_fails_with_its_message_and_reupload_restarts(client, world, db, _storage):
    response = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf")
    assert response.status_code == 201
    application_id = response.json()["id"]
    application = fresh(db, application_id)
    assert application.stage == "cv_failed"
    assert "no extractable text" in application.processing_error
    old_path = application.cv_file_path
    assert application.cv_status is None

    response = client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("new.docx", make_docx(), DOCX)}, headers=auth_header(CANDIDATE))
    assert response.status_code == 200
    application = fresh(db, application_id)
    assert application.stage == "invited"
    assert application.processing_error is None
    assert application.cv_suffix == ".docx"
    assert application.cv_status in {"meets", "not_met"}
    assert application.cv_file_path != old_path
    assert not (_storage / old_path).exists()
    assert (_storage / application.cv_file_path).exists()


def test_a_corrupt_file_fails_without_a_crash(client, world, db):
    application_id = apply(client, data=b"%PDF-not", name="cv.pdf", content_type="application/pdf").json()["id"]
    application = fresh(db, application_id)
    assert application.stage == "cv_failed" and application.processing_error


def test_failed_status_is_visible_to_the_candidate_with_its_fixed_message(client, world):
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    body = client.get(f"/api/applications/{application_id}", headers=auth_header(CANDIDATE)).json()
    assert body["status"] == "cv_unreadable"
    assert "no extractable text" in body["processing_error"]


def test_reupload_from_another_stage_gets_409(client, world):
    application_id = apply(client).json()["id"]
    response = client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("new.docx", make_docx(), DOCX)}, headers=auth_header(CANDIDATE))
    assert response.status_code == 409


def test_reupload_refuses_other_file_types(client, world, db):
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    response = client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("new.doc", b"x", "application/msword")}, headers=auth_header(CANDIDATE))
    assert response.status_code == 415
    assert fresh(db, application_id).stage == "cv_failed"


def test_reprocessing_replaces_screening_rows_after_a_retry(client, world, db, monkeypatch):
    """A retry must not double rows, and must clear the earlier error and label."""
    application_id = apply(client).json()["id"]
    application = fresh(db, application_id)
    application.stage = "cv_failed"
    application.processing_error = "earlier"
    db.commit()
    count = db.query(RequirementResult).filter_by(application_id=application_id, source="cv").count()
    cv_processing.run(application_id)
    application = fresh(db, application_id)
    assert application.stage == "invited" and application.processing_error is None
    assert db.query(RequirementResult).filter_by(application_id=application_id, source="cv").count() == count


# 8. AI down, and the raw CV


def _ai_down(_system, _messages, _schema):
    raise AIProviderError("down")


def test_ai_down_during_masking_fails_and_no_assessment_runs(client, world, db):
    fake.register("cv_mask", _ai_down)
    assess_calls = []
    fake.register("cv_assess", lambda *_: assess_calls.append(1) or "{}")
    application = fresh(db, apply(client).json()["id"])
    assert application.stage == "cv_failed"
    assert application.processing_error == "We could not process your CV right now. Please try again."
    assert application.cv_status is None and application.cv_text_blind is None and application.cv_text_raw is None
    assert assess_calls == []
    assert db.query(AIUsageLog).filter_by(feature="cv_assess").count() == 0


def test_ai_down_during_assessment_fails_with_the_same_message_and_keeps_no_rows(client, world, db):
    fake.register("cv_assess", _ai_down)
    application = fresh(db, apply(client).json()["id"])
    assert application.stage == "cv_failed"
    assert application.processing_error == "We could not process your CV right now. Please try again."
    assert application.cv_status is None
    assert db.query(RequirementResult).filter_by(application_id=application.id).count() == 0


def test_ai_garbage_during_masking_fails_safely(client, world, db):
    fake.enqueue("cv_mask", "not json")
    fake.enqueue("cv_mask", "still not json")
    assess_calls = []
    fake.register("cv_assess", lambda *_: assess_calls.append(1) or "{}")
    application = fresh(db, apply(client).json()["id"])
    assert application.stage == "cv_failed" and assess_calls == []


def test_an_unexpected_error_fails_with_a_generic_message(client, world, db, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("Canaryname Zebrawski secret")

    monkeypatch.setattr(cv_processing.identity, "mask", boom)
    application = fresh(db, apply(client).json()["id"])
    assert application.stage == "cv_failed"
    assert "Canaryname" not in application.processing_error


def test_cv_text_never_reaches_the_logs(client, world, db, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    fake.enqueue("cv_mask", "not json with Canaryname Zebrawski")
    fake.enqueue("cv_mask", "not json with Canaryname Zebrawski")
    apply(client)
    assert "Canaryname" not in caplog.text and "Zebrawski" not in caplog.text


def test_the_masking_call_is_the_only_one_that_sees_the_raw_cv(client, world, db, monkeypatch):
    """The canary name sits on the first line, the email is regex-masked before any AI call."""
    calls = []
    real = gateway.generate_structured

    def spy(slot, system, messages, schema, max_output_tokens, feature, company_id=None):
        result = real(slot, system, messages, schema, max_output_tokens, feature, company_id)
        calls.append((feature, system + json.dumps(fake.last_messages(), ensure_ascii=False)))
        return result

    monkeypatch.setattr(gateway, "generate_structured", spy)
    application_id = apply(client).json()["id"]
    assert [feature for feature, _ in calls] == ["cv_mask", "cv_assess"]
    mask_prompt, assess_prompt = calls[0][1], calls[1][1]
    assert "Canaryname" in mask_prompt
    assert "canary.zebrawski@example.test" not in mask_prompt
    for secret in ("Canaryname", "Zebrawski", "canary.zebrawski", "912 345 678"):
        assert secret not in assess_prompt
    assert "Built a FastAPI service" in assess_prompt
    application = fresh(db, application_id)
    assert "Canaryname" in application.cv_text_raw
    assert "Canaryname" not in application.cv_text_blind and "canary.zebrawski" not in application.cv_text_blind


def test_cv_assess_prompt_after_processing_has_no_name_or_email_by_last_messages(client, world, db):
    apply(client)
    prompt = json.dumps(fake.last_messages(), ensure_ascii=False)
    assert "<cv>" in prompt
    for secret in ("Canaryname", "Zebrawski", "canary.zebrawski@example.test"):
        assert secret not in prompt


def test_the_registered_name_is_gone_from_cv_assess_when_the_model_lists_no_names(client, world, db, monkeypatch):
    """The CV told the model to list nothing, and it obeyed. The account's own details still go."""
    user = db.get(User, world.user.id)
    user.full_name = "Canaryname Q Zebrawski"
    user.email = "canary.handle@example.test"
    db.commit()
    prompts = {}
    real = gateway.generate_structured

    def spy(slot, system, messages, schema, max_output_tokens, feature, company_id=None):
        prompts[feature] = json.dumps(messages, ensure_ascii=False)
        return real(slot, system, messages, schema, max_output_tokens, feature, company_id)

    monkeypatch.setattr(gateway, "generate_structured", spy)
    fake.enqueue("cv_mask", json.dumps({"names": [], "gender_terms": [], "ages": [], "addresses": []}))
    lines = ["Canaryname Zebrawski", "Handle canary.handle on forums", "Q built a FastAPI service used by 3 teams."]
    application_id = apply(client, data=make_docx(lines), email="canary.handle@example.test").json()["id"]
    assert "Canaryname" in prompts["cv_mask"]
    for secret in ("Canaryname", "Zebrawski", "canary.handle"):
        assert secret not in prompts["cv_assess"]
    assert "Q built a FastAPI" in prompts["cv_assess"], "a single-character token is not a term"
    assert fresh(db, application_id).cv_text_blind.startswith("[NAME] [NAME]")


def test_a_registered_name_that_is_a_common_word_does_not_change_the_blind_text(client, world, db):
    user = db.get(User, world.user.id)
    user.full_name = "Trần Long"
    user.email = "long@example.test"
    db.commit()
    fake.enqueue("cv_mask", json.dumps({"names": [], "gender_terms": [], "ages": [], "addresses": []}))
    application_id = apply(client, data=make_docx(["Long ran a long-running job"]), email="long@example.test").json()["id"]
    assert fresh(db, application_id).cv_text_blind == "[NAME] ran a long-running job"


def test_identity_only_differences_give_exactly_the_same_result_end_to_end(client, world, db):
    """Same CV, different person: the second application is answered from the cache."""
    second_lines = ["Otherperson Quillfeather", "Email: quill@example.test  Phone: 0987 654 321", *CV_LINES[2:]]
    one = fresh(db, apply(client).json()["id"]).id
    assess_count = db.query(AIUsageLog).filter_by(feature="cv_assess").count()
    two = fresh(db, apply(client, data=make_docx(second_lines), email=OTHER).json()["id"]).id
    assert db.query(AIUsageLog).filter_by(feature="cv_assess").count() == assess_count
    first, second = fresh(db, one), fresh(db, two)
    assert first.cv_blind_hash == second.cv_blind_hash
    assert first.cv_status == second.cv_status and first.cv_status_reason == second.cv_status_reason


# 9. Ownership


@pytest.mark.parametrize("method,path", [
    ("get", "/api/applications/{id}"),
    ("get", "/api/applications/{id}/fit"),
    ("post", "/api/applications/{id}/withdraw"),
    ("post", "/api/applications/{id}/decline-recording"),
])
def test_another_users_application_is_404_and_looks_like_a_missing_one(client, world, db, method, path):
    application_id = apply(client).json()["id"]
    foreign = getattr(client, method)(path.format(id=application_id), headers=auth_header(OTHER))
    missing = getattr(client, method)(path.format(id=999999), headers=auth_header(OTHER))
    assert foreign.status_code == 404 and missing.status_code == 404
    assert foreign.json() == missing.json()
    assert fresh(db, application_id).stage == "invited"


def test_another_users_reupload_is_404_and_changes_nothing(client, world, db):
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    path = fresh(db, application_id).cv_file_path
    response = client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("new.docx", make_docx(), DOCX)}, headers=auth_header(OTHER))
    assert response.status_code == 404
    application = fresh(db, application_id)
    assert application.stage == "cv_failed" and application.cv_file_path == path


def test_my_applications_lists_only_mine(client, world):
    mine = apply(client).json()["id"]
    theirs = apply(client, email=OTHER).json()["id"]
    body = client.get("/api/me/applications", headers=auth_header(CANDIDATE)).json()
    assert [item["id"] for item in body] == [mine]
    assert theirs not in [item["id"] for item in body]
    assert body[0]["company_slug"] == "acme"


@pytest.mark.parametrize("method,path", [
    ("get", "/api/me/applications"),
    ("get", "/api/applications/1"),
    ("get", "/api/applications/1/fit"),
    ("post", "/api/applications/1/withdraw"),
    ("post", "/api/applications/1/reupload"),
    ("post", "/api/applications/1/decline-recording"),
    ("get", "/api/consents/cv_processing"),
])
def test_candidate_routes_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


# 10. Candidates never see the label


@pytest.mark.parametrize("assessment", ["weak", "strong"])
def test_candidate_responses_never_contain_the_label_or_cv_text(client, world, db, assessment):
    fake.enqueue("cv_assess", assess_weak(world) if assessment == "weak" else assess_all_met(db, world))
    created = apply(client)
    application_id = created.json()["id"]
    application = fresh(db, application_id)
    assert application.cv_status == ("not_met" if assessment == "weak" else "meets")
    headers = auth_header(CANDIDATE)
    responses = [
        created,
        client.get("/api/me/applications", headers=headers),
        client.get(f"/api/applications/{application_id}", headers=headers),
        client.get(f"/api/applications/{application_id}/fit", headers=headers),
    ]
    forbidden = ["cv_status", "not_met", "cv_status_reason", "does not meet", "\"meets\"", "cv_text", "blind", "hidden_text",
                 "[NAME]", "[EMAIL]", "Canaryname", "canary.zebrawski", "Built a FastAPI service", "hr_decision"]
    for response in responses:
        assert response.status_code in (200, 201)
        for word in forbidden:
            assert word not in response.text, f"{word} in {response.request.url}"


def test_application_response_holds_exactly_the_agreed_fields(client, world):
    application_id = apply(client).json()["id"]
    body = client.get(f"/api/applications/{application_id}", headers=auth_header(CANDIDATE)).json()
    assert set(body) == {"id", "alias", "status", "job_title", "company_name", "company_slug", "is_sample", "created_at",
                         "withdraw_reason", "processing_error", "interview_languages", "decision", "failure_reason", "email_enabled", "contact_email", "feedback", "reapply_after", "interview_window"}
    assert body["alias"] == "#A1" and body["job_title"] == "Backend Developer" and body["company_name"] == "Acme"
    assert body["company_slug"] == "acme" and body["interview_languages"] == ["en"]
    assert body["is_sample"] is False and body["status"] == "invited"


@pytest.mark.parametrize("stage,friendly", [
    ("submitted", "reading_cv"), ("cv_processing", "reading_cv"), ("cv_failed", "cv_unreadable"), ("invited", "invited"),
    ("session_in_progress", "interview_in_progress"), ("session_completed", "with_hr"), ("analyzing", "with_hr"),
    ("declined_recording", "with_hr"), ("ready_for_hr", "with_hr"), ("withdrawn", "withdrawn"),
])
def test_every_stage_has_a_friendly_status(client, world, db, stage, friendly):
    application_id = apply(client).json()["id"]
    application = fresh(db, application_id)
    application.stage = stage
    db.commit()
    body = client.get(f"/api/applications/{application_id}", headers=auth_header(CANDIDATE)).json()
    assert body["status"] == friendly


def test_every_state_machine_stage_is_mapped():
    from app.routers.applications import FRIENDLY_STATUS

    assert set(FRIENDLY_STATUS) == set(state.STAGES)


# 11. Fit Compass


def _culture_graph(db, world):
    def node(title, type_, visibility="public", status="published"):
        row = KbNode(company_id=world.company_id, type=type_, title=title, body=f"{title} body", language="en", visibility=visibility, status=status)
        db.add(row)
        db.flush()
        return row.id

    def edge(source, target, relation, must_have=None):
        db.add(KbEdge(company_id=world.company_id, source_node_id=source, target_node_id=target, relation=relation, must_have=must_have, status="published"))

    role = node("Backend Developer", "role")
    department = node("Engineering", "department")
    value = node("Ownership", "value")
    behavior = node("Tells the team early", "behavior")
    hidden_value = node("Confidentialvalue", "value", visibility="confidential")
    hidden_behavior = node("Internalbehavior", "behavior", visibility="internal")
    edge(department, role, "has_role")
    edge(department, value, "holds")
    edge(department, hidden_value, "holds")
    edge(role, behavior, "expects")
    edge(role, hidden_behavior, "expects")
    job = db.get(Job, world.job_id)
    job.role_node_id = role
    db.commit()


def test_fit_lists_only_public_active_requirements_with_friendly_words(client, world, db):
    fake.enqueue("cv_assess", json.dumps({
        "requirements": [
            {"requirement_id": world.must_public, "status": "met", "quote": "Built a FastAPI service"},
            {"requirement_id": world.must_kube, "status": "not_found", "quote": ""},
            {"requirement_id": world.secret, "status": "met", "quote": "Used Docker"},
        ],
        "claims": [],
    }))
    application_id = apply(client).json()["id"]
    response = client.get(f"/api/applications/{application_id}/fit", headers=auth_header(CANDIDATE))
    assert response.status_code == 200
    assert {item["text"]: item["fit"] for item in response.json()["requirements"]} == {
        "FastAPI services": "matches", "Kubernetes operations": "not_seen",
    }
    for absent in ("Secretive", "Internalonly", "Retiredskill", "must_have", "quote"):
        assert absent not in response.text


def test_fit_shows_partly(client, world, db):
    fake.enqueue("cv_assess", assess_weak(world))
    application_id = apply(client).json()["id"]
    response = client.get(f"/api/applications/{application_id}/fit", headers=auth_header(CANDIDATE))
    assert {item["text"]: item["fit"] for item in response.json()["requirements"]}["FastAPI services"] == "partly"


def test_fit_shows_team_style_from_public_nodes_only(client, world, db):
    _culture_graph(db, world)
    application_id = apply(client).json()["id"]
    response = client.get(f"/api/applications/{application_id}/fit", headers=auth_header(CANDIDATE))
    style = {item["title"]: item["type"] for item in response.json()["team_style"]}
    assert style == {"Ownership": "value", "Tells the team early": "behavior"}
    assert "Confidentialvalue" not in response.text and "Internalbehavior" not in response.text


def test_fit_without_a_role_uses_the_public_values_of_the_company(client, world, db):
    _culture_graph(db, world)
    job = db.get(Job, world.job_id)
    job.role_node_id = None
    db.commit()
    application_id = apply(client).json()["id"]
    response = client.get(f"/api/applications/{application_id}/fit", headers=auth_header(CANDIDATE))
    assert {item["title"] for item in response.json()["team_style"]} == {"Ownership", "Tells the team early"}
    assert "Confidentialvalue" not in response.text


def test_fit_before_the_cv_is_read_gets_409(client, world):
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    assert client.get(f"/api/applications/{application_id}/fit", headers=auth_header(CANDIDATE)).status_code == 409


# 12. Withdraw


def test_withdraw_from_invited_keeps_the_reason(client, world, db):
    application_id = apply(client).json()["id"]
    response = client.post(f"/api/applications/{application_id}/withdraw", json={"reason": "Took another job"}, headers=auth_header(CANDIDATE))
    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    assert response.json()["withdraw_reason"] == "Took another job"
    application = fresh(db, application_id)
    assert application.stage == "withdrawn" and application.withdraw_reason == "Took another job"
    audit = db.query(AuditLog).filter_by(action="application_withdrawn", target_id=application_id).one()
    assert "Took another job" not in json.dumps(audit.payload)


def test_withdraw_needs_no_reason(client, world, db):
    application_id = apply(client).json()["id"]
    assert client.post(f"/api/applications/{application_id}/withdraw", headers=auth_header(CANDIDATE)).status_code == 200
    application = fresh(db, application_id)
    assert application.stage == "withdrawn" and application.withdraw_reason is None


def test_withdraw_from_another_stage_gets_409(client, world, db):
    application_id = apply(client).json()["id"]
    fresh(db, application_id).stage = "ready_for_hr"
    db.commit()
    assert client.post(f"/api/applications/{application_id}/withdraw", json={"reason": "x"}, headers=auth_header(CANDIDATE)).status_code == 409
    application = fresh(db, application_id)
    assert application.stage == "ready_for_hr" and application.withdraw_reason is None


def test_withdraw_while_the_cv_could_not_be_processed(client, world, db):
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    assert fresh(db, application_id).stage == "cv_failed"
    assert client.post(f"/api/applications/{application_id}/withdraw", json={"reason": "x"}, headers=auth_header(CANDIDATE)).status_code == 200
    application = fresh(db, application_id)
    assert application.stage == "withdrawn" and application.withdraw_reason == "x"


def test_withdraw_reason_has_a_length_limit(client, world):
    application_id = apply(client).json()["id"]
    response = client.post(f"/api/applications/{application_id}/withdraw", json={"reason": "x" * 2001}, headers=auth_header(CANDIDATE))
    assert response.status_code == 422


# 13. Decline recording


def test_decline_recording_moves_to_ready_for_hr_with_no_ai_and_the_label_unchanged(client, world, db):
    fake.enqueue("cv_assess", assess_weak(world))
    application_id = apply(client).json()["id"]
    before = fresh(db, application_id).cv_status
    calls = db.query(AIUsageLog).count()
    response = client.post(f"/api/applications/{application_id}/decline-recording", headers=auth_header(CANDIDATE))
    assert response.status_code == 200
    application = fresh(db, application_id)
    assert application.stage == "ready_for_hr"
    assert application.cv_status == before == "not_met"
    assert application.hr_decision == "pending"
    assert db.query(AIUsageLog).count() == calls
    assert db.query(AuditLog).filter_by(action="recording_declined", target_id=application_id).count() == 1


def test_decline_recording_from_another_stage_gets_409(client, world):
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    assert client.post(f"/api/applications/{application_id}/decline-recording", headers=auth_header(CANDIDATE)).status_code == 409


# 14. Aliases


def test_applications_in_a_company_get_different_aliases(client, world, db):
    one = apply(client).json()["id"]
    two = apply(client, email=OTHER).json()["id"]
    assert fresh(db, one).alias == "#A1" and fresh(db, two).alias == "#A2"


def test_next_alias_uses_the_highest_number_not_string_order(db, world):
    db.add_all([
        Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias=alias, stage="invited")
        for alias in ("#A2", "#A10", "#A9")
    ])
    db.commit()
    assert applications.next_alias(db, world.company_id) == "#A11"


def test_aliases_are_per_company(db, world):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    db.add(Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias="#A7", stage="invited"))
    db.commit()
    assert applications.next_alias(db, other.id) == "#A1"


def test_a_concurrent_alias_collision_retries_with_a_new_alias(world, db, monkeypatch, _storage):
    """Both writers read the same highest number: the unique constraint stops one, and it tries again."""
    db.add(Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias="#A1", stage="invited"))
    db.commit()
    real = applications.next_alias
    answers = iter(["#A1", "#A1"])
    monkeypatch.setattr(applications, "next_alias", lambda session, company_id: next(answers, None) or real(session, company_id))
    job = db.get(Job, world.job_id)
    created = applications.create_application(db, world.user, job, make_docx(), ".docx", None, consents.VERSION)
    assert created.alias == "#A2"
    assert db.query(Consent).filter_by(application_id=created.id).count() == 1
    assert len([p for p in _storage.rglob("*") if p.is_file()]) == 1


def test_giving_up_on_aliases_stores_nothing(world, db, monkeypatch, _storage):
    db.add(Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias="#A1", stage="invited"))
    db.commit()
    monkeypatch.setattr(applications, "next_alias", lambda session, company_id: "#A1")
    job = db.get(Job, world.job_id)
    with pytest.raises(IntegrityError):
        applications.create_application(db, world.user, job, make_docx(), ".docx", None, consents.VERSION)
    assert db.query(Application).count() == 1
    assert [p for p in _storage.rglob("*") if p.is_file()] == []


# Processing: claims, restart, concurrency


def test_run_for_a_missing_application_does_nothing():
    assert cv_processing.run(999999) is None


def test_run_does_not_restart_an_application_that_moved_on(client, world, db):
    """A second background task for the same application must not reprocess it, or mark it failed."""
    application_id = apply(client).json()["id"]
    calls = db.query(AIUsageLog).count()
    cv_processing.run(application_id)
    application = fresh(db, application_id)
    assert application.stage == "invited" and application.processing_error is None
    assert db.query(AIUsageLog).count() == calls


def test_a_stage_changed_during_processing_does_not_crash_the_job(client, world, db, monkeypatch):
    """Startup marked the job failed while it was still running: the job gives way."""
    application_id = apply(client, data=make_pdf([]), name="cv.pdf", content_type="application/pdf").json()["id"]
    real = cv_processing.identity.mask

    def mask(raw_text, **kwargs):
        result = real(raw_text, **kwargs)
        cv_processing.fail_interrupted()
        return result

    monkeypatch.setattr(cv_processing.identity, "mask", mask)
    response = client.post(f"/api/applications/{application_id}/reupload",
                           files={"file": ("new.docx", make_docx(), DOCX)}, headers=auth_header(CANDIDATE))
    assert response.status_code == 200
    application = fresh(db, application_id)
    assert application.stage == "cv_failed" and application.cv_status is None


def test_startup_marks_stuck_applications_failed_so_the_candidate_can_retry(world, db):
    stuck = Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias="#A1", stage="cv_processing")
    orphan = Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias="#A2", stage="submitted")
    fine = Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias="#A3", stage="invited")
    db.add_all([stuck, orphan, fine])
    db.commit()
    assert cv_processing.fail_interrupted() == 2
    db.expire_all()
    assert stuck.stage == "cv_failed" and stuck.processing_error
    assert orphan.stage == "cv_failed" and orphan.processing_error
    assert fine.stage == "invited" and fine.processing_error is None


def test_the_startup_step_runs_in_the_app_lifespan(app, world, db):
    from fastapi.testclient import TestClient

    db.add(Application(company_id=world.company_id, job_id=world.job_id, job_version=1, alias="#A1", stage="cv_processing"))
    db.commit()
    with TestClient(app):
        pass
    db.expire_all()
    assert db.query(Application).filter_by(alias="#A1").one().stage == "cv_failed"


# Consent text


def test_consent_text_route_returns_the_current_text_and_version(client, world):
    response = client.get("/api/consents/cv_processing?language=vi", headers=auth_header(CANDIDATE))
    assert response.status_code == 200
    assert response.json()["version"] == consents.VERSION
    assert response.json()["text"] == consents.current_text("cv_processing", "vi").text


def test_consent_text_uses_the_company_retention(client, world, db):
    company = db.get(Company, world.company_id)
    company.retention_days = 45
    db.commit()
    response = client.get(f"/api/consents/recording_screening?company_id={world.company_id}", headers=auth_header(CANDIDATE))
    assert "45" in response.json()["text"]


def test_consent_text_unknown_purpose_or_company_gets_404(client, world):
    assert client.get("/api/consents/marketing", headers=auth_header(CANDIDATE)).status_code == 404
    assert client.get("/api/consents/cv_processing?company_id=999999", headers=auth_header(CANDIDATE)).status_code == 404


# Fake responders


def test_the_demo_responders_are_installed_with_the_app(client, world, db):
    application = fresh(db, apply(client).json()["id"])
    assert "[NAME]" in application.cv_text_blind
    assert db.query(RequirementResult).filter_by(application_id=application.id, requirement_id=world.must_public).one().status == "met"
    assert db.query(RequirementResult).filter_by(application_id=application.id, requirement_id=world.must_kube).one().status == "not_found"
    claims = [claim.quote for claim in db.query(CvClaim).filter_by(application_id=application.id)]
    assert "Built a FastAPI service used by 3 teams." in claims


def test_the_queue_wins_over_the_demo_responder(client, world, db):
    fake.enqueue("cv_assess", assess_all_met(db, world))
    assert fresh(db, apply(client).json()["id"]).cv_status == "meets"


# Routes


def test_the_candidate_routes_exist():
    from app.main import create_app

    paths = {route_path(route) for route in iter_routes(create_app())}
    assert {
        "/api/public/jobs/{slug}/apply", "/api/me/applications", "/api/applications/{application_id}",
        "/api/applications/{application_id}/fit", "/api/applications/{application_id}/withdraw",
        "/api/applications/{application_id}/reupload", "/api/applications/{application_id}/decline-recording",
        "/api/consents/{purpose}",
    } <= paths


def test_no_code_in_this_task_writes_a_decision():
    root = Path(__file__).resolve().parents[1] / "app"
    for name in ("hiring/applications.py", "hiring/cv_processing.py", "hiring/screening.py", "routers/applications.py", "hiring/identity.py"):
        assert "hr_decision" not in (root / name).read_text(encoding="utf-8"), name


def test_only_the_masking_module_reads_raw_text_before_it_is_stored():
    root = Path(__file__).resolve().parents[1] / "app"
    assert "cv_text_raw" not in (root / "hiring/screening.py").read_text(encoding="utf-8")
    assert "cv_text_raw" not in (root / "hiring/fake_demo.py").read_text(encoding="utf-8")


# Deleting does not reset the limit (I-11)


def _with_session(db, application_id):
    from app.database.sql_models import VoiceSession

    application = db.get(Application, application_id)
    db.add(VoiceSession(company_id=application.company_id, purpose="screening", application_id=application_id,
                        owner_user_id=application.candidate_user_id, language="en", status="completed"))
    db.commit()


def test_deleting_after_a_session_does_not_reset_the_limit(client, world, db):
    first = apply(client).json()["id"]
    _with_session(db, first)
    assert client.delete(f"/api/me/applications/{first}", headers=auth_header(CANDIDATE)).status_code == 204
    again = apply(client)
    assert again.status_code == 409
    assert again.json()["detail"]["reapply_after"]


def test_deleting_before_any_session_or_decision_leaves_the_job_open(client, world, db):
    first = apply(client).json()["id"]
    db.rollback()
    assert client.delete(f"/api/me/applications/{first}", headers=auth_header(CANDIDATE)).status_code == 204
    assert apply(client).status_code == 201
