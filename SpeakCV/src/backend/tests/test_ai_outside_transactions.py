"""No AI call runs while the calling session holds uncommitted writes.

Every test runs on a file database, like the e2e backend. A probe wrapped around the provider writes through a second
connection with no busy timeout at the moment of each vendor call: if the caller holds a write, the probe is refused at
once. On MySQL the same mistake would hold row locks for the length of a real vendor call.
"""
import sqlite3
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.ai import gateway
from app.ai.providers import fake
from app.ai.types import AIProviderError
from app.brain import fake_demo, ingestion, seed
from app.database.database import Base, SessionLocal, engine
from app.database.sql_models import (
    AIUsageLog, Application, AuditLog, ChannelContent, Company, CompanyMember, Job, JobChannelLink, JobDraft,
    JobDraftMessage, JobRequirement, KbChunk, KbDocument, KbNode, RejectionFeedback, RequirementResult, User,
)
from app.hiring import consents, cv_processing
from app.hiring import fake_demo as hiring_fake_demo
from app.main import create_app
from app.posthire import feedback, talent_pool
from tests import helpers_board
from tests.helpers import auth_header
from tests.helpers_board import make_application, make_session
from tests.helpers_board import make_world as make_board_world
from tests.helpers_jd import ai_line, assistant_json, line, make_draft, make_world
from tests.test_brain_ingestion import TEXT, TWO_CHUNKS, extraction, fact, real_extract
from tests.test_brain_review import World as ReviewWorld

HR = auth_header("hr@acme.test")
MANAGER = auth_header("mgr@acme.test")
LANGUAGES = ["en"]


class Probe:
    def __init__(self, path):
        self.path = path
        self.calls = Counter()
        self.refused = []
        self.first_usage_id = 0

    def try_write(self):
        feature = fake._current_feature["value"]
        self.calls[feature] += 1
        connection = sqlite3.connect(self.path, timeout=0)
        try:
            connection.execute("INSERT INTO probe_writes (feature) VALUES (?)", (feature,))
            connection.commit()
        except sqlite3.OperationalError as error:
            self.refused.append((feature, str(error)))
        finally:
            connection.close()

    def start(self):
        """Forget the set-up: only what happens from here on counts."""
        self.calls.clear()
        self.refused.clear()
        session = SessionLocal()
        try:
            self.first_usage_id = max((row[0] for row in session.query(AIUsageLog.id)), default=0)
        finally:
            session.close()

    def assert_clean(self, *features):
        assert self.refused == []
        assert set(features) <= set(self.calls), f"expected AI calls for {features}, saw {dict(self.calls)}"
        session = SessionLocal()
        try:
            rows = session.query(AIUsageLog.feature).filter(AIUsageLog.id > self.first_usage_id).all()
        finally:
            session.close()
        assert Counter(row[0] for row in rows) == self.calls


class _ProbingProvider:
    def __init__(self, inner, probe):
        self._inner, self._probe = inner, probe

    def __getattr__(self, name):
        method = getattr(self._inner, name)

        def call(**kwargs):
            self._probe.try_write()
            return method(**kwargs)

        return call


@pytest.fixture(autouse=True)
def probe(tmp_path, monkeypatch):
    path = tmp_path / "guard.db"
    file_engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(file_engine)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE probe_writes (id INTEGER PRIMARY KEY, feature TEXT)")
    connection.commit()
    connection.close()
    SessionLocal.configure(bind=file_engine)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    watcher = Probe(path)
    real_provider = gateway.get_provider
    monkeypatch.setattr(gateway, "get_provider", lambda name: _ProbingProvider(real_provider(name), watcher))
    fake_demo.install()
    yield watcher
    SessionLocal.configure(bind=engine)
    file_engine.dispose()


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def api(probe):
    with TestClient(create_app()) as client:
        yield client


def _url(world, tail):
    return f"/api/companies/{world.company.id}{tail}"


def _lines(world):
    return [
        line("l1", [world.role.id], en="We build the APIs of our hiring platform", vi="Xay dung API", ko="API"),
        line("l2", [world.python.id], en="You have 3 years of Python experience", vi="3 nam Python", ko="Python 3",
             is_requirement=True, must_have=True),
    ]


def _approved(api, db, world):
    draft = make_draft(db, world.company.id, _lines(world), world.request.id)
    assert api.post(_url(world, f"/job-drafts/{draft.id}/submit"), headers=HR).status_code == 200
    assert api.post(_url(world, f"/job-drafts/{draft.id}/approve"), headers=MANAGER).status_code == 200
    return draft


def _flag_single_language(text):
    """The classifier flags a requirement line, which lint reads in three languages and the job in one."""
    def answer(_system, messages, _schema):
        statement = messages[-1]["content"].removeprefix("<statement>\n").removesuffix("\n</statement>")
        flagged = statement == text
        return ('{"flagged": %s, "category": "age", "reason": "flagged"}' % ("true" if flagged else "false"))
    return answer


# --- jobs ------------------------------------------------------------------------------------------------------------

def test_job_create(api, world, probe):
    probe.start()
    response = api.post(_url(world, "/jobs"), headers=HR, json={
        "title": "Backend", "description": "Build APIs", "interview_languages": LANGUAGES,
        "requirements": [{"text": "Three years of Python"}, {"text": "Knows containers"}],
    })
    assert response.status_code == 201, response.text
    assert len(response.json()["requirements"]) == 2
    probe.assert_clean("discrimination_check")


def test_job_patch(api, world, probe):
    created = api.post(_url(world, "/jobs"), headers=HR, json={
        "title": "Backend", "description": "Build APIs", "interview_languages": LANGUAGES,
        "requirements": [{"text": "Three years of Python"}],
    }).json()
    probe.start()
    response = api.patch(_url(world, f"/jobs/{created['id']}"), headers=HR, json={
        "title": "Backend 2", "department_id": world.eng.id,
        "requirements": [{"text": "Three years of Python"}, {"text": "Knows containers"}],
    })
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Backend 2"
    assert response.json()["version"] == 2
    probe.assert_clean("discrimination_check")


def test_a_rejected_requirement_on_create_leaves_nothing_behind(api, db, world, probe):
    probe.start()
    response = api.post(_url(world, "/jobs"), headers=HR, json={
        "title": "Backend", "interview_languages": LANGUAGES,
        "requirements": [{"text": "Three years of Python"}, {"text": "Must be male"}],
    })
    assert response.status_code == 422
    db.rollback()
    assert db.query(Job).count() == 0
    assert db.query(JobRequirement).count() == 0
    assert db.query(AuditLog).filter_by(action="job.create").count() == 0
    probe.assert_clean("discrimination_check")


def test_a_rejected_requirement_on_patch_changes_nothing(api, db, world, probe):
    created = api.post(_url(world, "/jobs"), headers=HR, json={
        "title": "Backend", "interview_languages": LANGUAGES, "requirements": [{"text": "Three years of Python"}],
    }).json()
    probe.start()
    response = api.patch(_url(world, f"/jobs/{created['id']}"), headers=HR, json={
        "title": "Changed", "department_id": world.eng.id, "requirements": [{"text": "Must be male"}],
    })
    assert response.status_code == 422
    db.rollback()
    job = db.get(Job, created["id"])
    assert (job.title, job.department_id, job.version) == ("Backend", None, 1)
    assert [row.text for row in db.query(JobRequirement).filter_by(active=True)] == ["Three years of Python"]
    probe.assert_clean()


def test_a_requirement_that_lost_its_check_during_the_call_is_refused(api, db, world, probe):
    """Unchanged rows are not checked again. If another request removes one during the AI call, it would come back here
    as a new row that no check has seen, so the request is refused and changes nothing."""
    created = api.post(_url(world, "/jobs"), headers=HR, json={
        "title": "Backend", "interview_languages": LANGUAGES, "requirements": [{"text": "Three years of Python"}],
    }).json()

    def remove_it_from_elsewhere(_system, _messages, _schema):
        other = SessionLocal()
        other.query(JobRequirement).filter_by(job_id=created["id"]).update({"active": False})
        other.commit()
        other.close()
        return '{"flagged": false, "category": "age", "reason": ""}'

    fake.register("discrimination_check", remove_it_from_elsewhere)
    response = api.patch(_url(world, f"/jobs/{created['id']}"), headers=HR, json={
        "title": "Changed", "requirements": [{"text": "Three years of Python"}, {"text": "Knows containers"}],
    })
    assert response.status_code == 409
    db.rollback()
    job = db.get(Job, created["id"])
    assert (job.title, job.version) == ("Backend", 1)
    assert db.query(JobRequirement).filter_by(job_id=job.id, active=True).count() == 0


# --- knowledge review ------------------------------------------------------------------------------------------------

@pytest.fixture
def review_world(db):
    return ReviewWorld(db)


def _decide(client, world, items):
    return client.post(world.url("review/decide"), json={"items": items}, headers=world.hr)


def test_review_decide_with_an_edit(api, review_world, probe):
    node = review_world.node("Python", type="requirement")
    other = review_world.node("Docker", type="skill")
    probe.start()
    response = _decide(api, review_world, [
        {"action": "reject", "node_id": other.id},
        {"action": "edit", "node_id": node.id, "title": "Python 3", "body": "Three years of Python"},
        {"action": "accept", "node_id": node.id},
    ])
    assert response.status_code == 200, response.text
    probe.assert_clean("discrimination_check", "kb_embed")
    node = review_world.reload(node)
    assert (node.status, node.title) == ("published", "Python 3")
    assert node.embedding_model is not None and node.embedding != review_world.reload(other).embedding


def test_two_edits_of_one_node_are_checked_on_the_text_each_one_leaves(api, review_world, probe):
    node = review_world.node("Python", type="requirement")
    probe.start()
    response = _decide(api, review_world, [
        {"action": "edit", "node_id": node.id, "title": "Python 3"},
        {"action": "edit", "node_id": node.id, "body": "Three years"},
    ])
    assert response.status_code == 200, response.text
    assert probe.calls["discrimination_check"] == 2
    assert probe.calls["kb_embed"] == 1
    probe.assert_clean()
    assert review_world.reload(node).body == "Three years"


def test_a_review_409_from_the_guard_changes_nothing(api, review_world, probe):
    other = review_world.node("Docker", type="skill")
    node = review_world.node("Python", type="requirement")
    probe.start()
    response = _decide(api, review_world, [
        {"action": "accept", "node_id": other.id},
        {"action": "accept", "node_id": node.id, "body": "Must be male"},
    ])
    assert response.status_code == 409
    node, other = review_world.reload(node), review_world.reload(other)
    assert (node.status, node.body, node.guard_category) == ("draft", "Python body", None)
    assert other.status == "draft"
    assert probe.calls["kb_embed"] == 0  # a request the guard refuses pays for no embedding
    probe.assert_clean()


def test_a_node_that_changed_during_the_call_is_refused(api, review_world, probe):
    node = review_world.node("Python", type="requirement")
    node_id = node.id

    def change_it_from_elsewhere(_system, _messages, _schema):
        other = SessionLocal()
        other.get(KbNode, node_id).body = "Changed by someone else"
        other.commit()
        other.close()
        return '{"flagged": false, "category": "age", "reason": ""}'

    fake.register("discrimination_check", change_it_from_elsewhere)
    response = _decide(api, review_world, [{"action": "accept", "node_id": node_id, "title": "Python 3"}])
    assert response.status_code == 409
    node = review_world.reload(node)
    assert (node.status, node.title, node.body) == ("draft", "Python", "Changed by someone else")


# --- JD Studio -------------------------------------------------------------------------------------------------------

def test_publish_from_jd_studio(api, db, world, probe):
    draft = _approved(api, db, world)
    probe.start()
    response = api.post(_url(world, f"/job-drafts/{draft.id}/publish"), headers=HR)
    assert response.status_code == 200, response.text
    assert response.json()["job"]["status"] == "published"
    probe.assert_clean("discrimination_check", "lint_embed")


def test_republish_onto_an_existing_job(api, db, world, probe):
    draft = _approved(api, db, world)
    assert api.post(_url(world, f"/job-drafts/{draft.id}/publish"), headers=HR).status_code == 200
    lines = _lines(world) + [line("l3", [world.docker.id], en="You ship containers", vi="Docker", ko="Docker",
                                  is_requirement=True)]
    db.expire_all()
    stored = db.get(JobDraft, draft.id)
    stored.lines, stored.status = lines, "approved"
    db.commit()
    probe.start()
    response = api.post(_url(world, f"/job-drafts/{draft.id}/publish"), headers=HR)
    assert response.status_code == 200, response.text
    assert response.json()["job"]["version"] == 2
    probe.assert_clean("discrimination_check")


def test_a_publish_refused_by_the_guard_leaves_no_job(api, db, world, probe):
    draft = _approved(api, db, world)
    fake.register("discrimination_check", _flag_single_language("You have 3 years of Python experience"))
    probe.start()
    response = api.post(_url(world, f"/job-drafts/{draft.id}/publish"), headers=HR)
    assert response.status_code == 422, response.text
    db.expire_all()
    assert db.query(Job).count() == 0
    stored = db.get(JobDraft, draft.id)
    assert (stored.status, stored.job_id) == ("approved", None)
    probe.assert_clean("discrimination_check")


def test_publish_to_a_closed_job_asks_no_ai_about_requirements(api, db, world, probe):
    draft = _approved(api, db, world)
    job = Job(company_id=world.company.id, title="Old", description="", status="closed", version=1,
              interview_languages=["en"])
    db.add(job)
    db.flush()
    db.get(JobDraft, draft.id).job_id = job.id
    db.commit()
    seen = []
    fake.register("discrimination_check", lambda _system, messages, _schema: (
        seen.append(messages[-1]["content"]) or '{"flagged": false, "category": "age", "reason": ""}'))
    response = api.post(_url(world, f"/job-drafts/{draft.id}/publish"), headers=HR)
    assert response.status_code == 409
    assert "<statement>\nYou have 3 years of Python experience\n</statement>" not in seen


def test_lint_run(api, db, world, probe):
    draft = make_draft(db, world.company.id, _lines(world), world.request.id)
    probe.start()
    response = api.post(_url(world, f"/job-drafts/{draft.id}/lint"), headers=HR)
    assert response.status_code == 200, response.text
    probe.assert_clean("discrimination_check", "lint_embed")


def test_draft_generate(api, world, probe):
    probe.start()
    response = api.post(_url(world, f"/hiring-requests/{world.request.id}/drafts"), headers=HR)
    assert response.status_code == 200, response.text
    assert response.json()["lines"]
    assert "lint" in response.json()
    probe.assert_clean("jd_generate", "discrimination_check", "lint_embed")


def test_draft_assistant(api, db, world, probe):
    draft = make_draft(db, world.company.id, _lines(world), world.request.id)
    fake.enqueue("jd_assistant", assistant_json(
        [ai_line("l1", [world.role.id], en="We build the APIs", vi="API", ko="API")], summary="Shorter"))
    probe.start()
    response = api.post(_url(world, f"/job-drafts/{draft.id}/assistant"), headers=HR, json={"message": "Shorter"})
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    probe.assert_clean("jd_assistant", "discrimination_check", "lint_embed")
    db.expire_all()
    assert db.query(JobDraftMessage).filter_by(job_draft_id=draft.id).count() == 2


def test_draft_edit(api, db, world, probe):
    draft = make_draft(db, world.company.id, _lines(world), world.request.id)
    probe.start()
    response = api.patch(_url(world, f"/job-drafts/{draft.id}"), headers=HR, json={
        "lines": [{"id": "l1", "text": {"en": "We build services"}}],
    })
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    probe.assert_clean("discrimination_check", "lint_embed")


def test_draft_line_confirm(api, db, world, probe):
    fake.enqueue("jd_assistant", assistant_json(
        [ai_line("l1", [world.role.id], en="We build the APIs", vi="API", ko="API")],
        proposals=[{"en": "Salary is high", "vi": "Luong cao", "ko": "Pay", "reason": "No source"}]))
    draft = make_draft(db, world.company.id, _lines(world), world.request.id)
    proposal = api.post(_url(world, f"/job-drafts/{draft.id}/assistant"), headers=HR,
                        json={"message": "Add pay"}).json()["needs_confirmation"][0]
    probe.start()
    response = api.post(_url(world, f"/job-drafts/{draft.id}/lines/{proposal['id']}/confirm"), headers=HR)
    assert response.status_code == 200, response.text
    assert [item["text"]["en"] for item in response.json()["lines"]][-1] == "Salary is high"
    assert response.json()["proposals"] == []
    probe.assert_clean("discrimination_check", "lint_embed")


def test_an_edit_refused_by_validation_runs_no_lint(api, db, world, probe):
    draft = make_draft(db, world.company.id, _lines(world), world.request.id)
    probe.start()
    response = api.patch(_url(world, f"/job-drafts/{draft.id}"), headers=HR, json={
        "lines": [{"id": "l1", "source_node_ids": [world.note.id]}],
    })
    assert response.status_code == 422
    assert probe.calls == Counter()


def test_channel_generate(api, db, world, probe):
    draft = _approved(api, db, world)
    assert api.post(_url(world, f"/job-drafts/{draft.id}/publish"), headers=HR).status_code == 200
    probe.start()
    response = api.post(_url(world, f"/job-drafts/{draft.id}/channels/generate"), headers=HR)
    assert response.status_code == 200, response.text
    assert response.json()["channels"]
    probe.assert_clean("channel_content")


def test_channel_commentary(api, db, world, probe):
    job = Job(company_id=world.company.id, title="Backend", slug="backend-ch", status="published", version=1,
              interview_languages=["en"])
    db.add(job)
    db.commit()
    db.add(Application(company_id=world.company.id, job_id=job.id, job_version=1, alias="#C1",
                       source_channel="linkedin", stage="ready_for_hr", cv_status="meets", hr_decision="approved"))
    db.commit()
    probe.start()
    response = api.post(_url(world, f"/jobs/{job.id}/channels/commentary"), headers=HR, json={})
    assert response.status_code == 200, response.text
    assert response.json()["observations"]
    probe.assert_clean("channel_commentary")


def test_channel_generate_saves_nothing_when_the_ai_fails(api, db, world, monkeypatch):
    draft = _approved(api, db, world)
    assert api.post(_url(world, f"/job-drafts/{draft.id}/publish"), headers=HR).status_code == 200
    db.expire_all()
    job_id = db.get(JobDraft, draft.id).job_id

    def boom(_system, _messages, _schema):
        raise RuntimeError("down")

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        fake.register("channel_content", boom)  # after the start-up, which installs the demo responders
        response = client.post(_url(world, f"/job-drafts/{draft.id}/channels/generate"), headers=HR)
    assert response.status_code >= 500
    db.expire_all()
    assert db.query(ChannelContent).count() == 0
    assert db.query(JobChannelLink).filter_by(job_id=job_id).count() == 0


# --- rejection feedback ----------------------------------------------------------------------------------------------

def _interviewed_application(db):
    board = make_board_world(db)
    application = make_application(db, board["job"], cv_status="not_met")
    make_session(db, application, [(1, "Q", "I built a FastAPI service used by three teams", None)])
    db.add(RequirementResult(application_id=application.id, requirement_id=board["requirements"][0].id,
                             source="interview", status="evidence", quote="I built a FastAPI service"))
    db.commit()
    return board, application.id


def test_rejecting_drafts_feedback_in_the_background(api, db, probe):
    board, application_id = _interviewed_application(db)
    path = f"/api/companies/{board['company'].id}/applications/{application_id}/decision"
    headers = board["people"]["hr"]["headers"]
    probe.start()
    response = api.post(path, headers=headers, json={"decision": "rejected"})
    assert response.status_code == 200, response.text
    probe.assert_clean("rejection_feedback")
    db.rollback()
    assert db.query(RejectionFeedback).filter_by(application_id=application_id).one().status == "draft"


def test_hr_drafting_feedback_holds_no_write(api, db, probe):
    board, application_id = _interviewed_application(db)
    application = db.get(Application, application_id)
    application.hr_decision = "rejected"
    db.commit()
    path = f"/api/companies/{board['company'].id}/applications/{application_id}/feedback/draft"
    headers = board["people"]["hr"]["headers"]
    probe.start()
    response = api.post(path, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "ai"
    probe.assert_clean("rejection_feedback")


def test_a_refused_feedback_draft_retries_holding_no_write(db, probe):
    _, application_id = _interviewed_application(db)
    application = db.get(Application, application_id)
    application.hr_decision = "rejected"
    db.commit()
    fake_demo.install()
    fake.enqueue("rejection_feedback", '{"went_well": [], "to_build": [], "learning_ids": [], "message": "not_met"}')
    probe.start()
    feedback.create_draft_for(application_id)
    assert probe.calls["rejection_feedback"] == 2
    probe.assert_clean("rejection_feedback")


# --- ingestion -------------------------------------------------------------------------------------------------------

def _requirement(title, quote):
    return {"ref": title, "type": "requirement", "title": title, "body": quote, "quote": quote, "fact_kind": "none",
            "fact_value": "", "fact_unit": "", "scope_text": "", "effective_date": ""}


@pytest.fixture
def company(db):
    row = Company(slug="acme", name="Acme")
    db.add(row)
    db.commit()
    return row


def _document(db, company, data):
    return ingestion.create_document(
        db, company.id, None, title="Handbook", data=data, suffix=".md", visibility="internal", department_id=None,
        language="en", effective_date=None,
    )


def test_ingestion(db, company, probe):
    fake.enqueue("kb_extract", extraction([
        fact("Annual leave", "12 days of annual leave"), _requirement("Speak up", "we speak up early"),
    ]))
    document = _document(db, company, TEXT.encode())
    job = ingestion.start_job(db, document.id)
    probe.start()
    ingestion.run_job(job.id)
    db.expire_all()
    assert db.get(KbDocument, document.id).status == "review"
    node = db.query(KbNode).filter_by(title="Speak up").one()
    assert node.embedding is not None
    probe.assert_clean("kb_extract", "kb_embed", "discrimination_check")


def test_ingestion_retry_of_failed_chunks(db, company, probe, monkeypatch):
    def outage(chunk_text, *args):
        if "12 days of annual leave" not in chunk_text or "extra leave" in chunk_text:
            raise AIProviderError("down")
        fake.enqueue("kb_extract", extraction([fact("Annual leave", "12 days of annual leave")]))
        return real_extract(chunk_text, *args)

    with monkeypatch.context() as patch:
        patch.setattr(ingestion, "extract_chunk", outage)
        document = _document(db, company, TWO_CHUNKS.encode())
        job = ingestion.start_job(db, document.id)
        ingestion.run_job(job.id)
    db.expire_all()
    job = db.get(type(job), job.id)
    assert job.failed_chunk_ids

    def back_up(chunk_text, *args):
        if "extra leave" in chunk_text:
            fake.enqueue("kb_extract", extraction([
                fact("Extra leave", "receive 15 days of extra leave", "15"),
                _requirement("Extra leave rule", "receive 15 days of extra leave"),
            ]))
        else:
            fake.enqueue("kb_extract", extraction())
        return real_extract(chunk_text, *args)

    monkeypatch.setattr(ingestion, "extract_chunk", back_up)
    job_id = job.id
    ingestion.start_failed_retry(db, job)
    probe.start()
    ingestion.run_failed_retry(job_id)
    db.expire_all()
    probe.assert_clean("kb_extract", "kb_embed", "discrimination_check")
    assert db.get(type(job), job_id).failed_chunk_ids == []
    for title in ("Extra leave", "Extra leave rule"):
        node = db.query(KbNode).filter_by(title=title).one()
        assert node.embedding is not None and node.status == "draft"
    assert db.query(KbChunk).filter_by(document_id=document.id).count() > 0


def test_ingestion_retry_keeps_a_flag_on_the_new_node(db, company, probe, monkeypatch):
    def outage(chunk_text, *args):
        raise AIProviderError("down")

    with monkeypatch.context() as patch:
        patch.setattr(ingestion, "extract_chunk", outage)
        job = ingestion.start_job(db, _document(db, company, TEXT.encode()).id)
        ingestion.run_job(job.id)
    db.expire_all()
    job = db.get(type(job), job.id)
    job_id = job.id
    fake.enqueue("kb_extract", extraction([_requirement("Speak up", "we speak up early")]))
    fake.register("discrimination_check", lambda *_: '{"flagged": true, "category": "age", "reason": "flagged"}')
    ingestion.start_failed_retry(db, job)
    ingestion.run_failed_retry(job_id)
    db.expire_all()
    assert probe.refused == []
    node = db.query(KbNode).filter_by(title="Speak up").one()
    assert (node.guard_category, node.guard_reason) == ("age", "flagged")


def test_seeding_a_sample_company(db, probe):
    probe.start()
    seed.seed_samples(auto_approve=True, only="sori-labs")
    db.expire_all()
    assert db.query(Job).filter_by(status="published").count() == 1
    assert db.query(CompanyMember).count() > 0
    probe.assert_clean("kb_embed", "discrimination_check")


def test_onboarding_plan_is_built_outside_a_transaction(api, db, probe):
    from tests.test_posthire_onboarding import build, create_url

    hire = build(db)
    probe.start()
    response = api.post(create_url(hire), headers=HR)
    assert response.status_code == 200, response.text
    probe.assert_clean("onboarding_plan")
    assert db.query(AuditLog).filter_by(action="onboarding.created").count() == 1


# The talent pool


def _pool_world(db):
    hiring_fake_demo.install()
    world = helpers_board.make_world(db)
    application = helpers_board.make_application(db, world["job"], alias="#A1", hr_decision="rejected")
    application.cv_text_blind = helpers_board.CV_BLIND
    target = Job(company_id=world["company"].id, title="Platform", slug="platform", status="published", version=1,
                 interview_languages=["en"])
    db.add(target)
    db.commit()
    db.add(JobRequirement(company_id=target.company_id, job_id=target.id, text="FastAPI", must_have=True, position=0))
    db.commit()
    return application, target, world


def _join_pool(db, application):
    user = db.get(User, application.candidate_user_id)
    talent_pool.give_consent(db, application, user, consents.VERSION)
    return talent_pool.opt_in(db, application, user)


def test_talent_pool_opt_in(db, probe):
    application, _, _ = _pool_world(db)
    probe.start()
    entry = _join_pool(db, application)
    assert entry.embedding is not None
    probe.assert_clean("talent_pool_embed")


def test_talent_pool_matches(db, probe):
    application, target, world = _pool_world(db)
    entry = _join_pool(db, application)
    entry.embedding = None  # so matching embeds it as well
    db.commit()
    probe.start()
    assert len(talent_pool.matches(db, world["company"].id, target.id)) == 1
    probe.assert_clean("talent_pool_query", "talent_pool_embed", "cv_assess")


def test_talent_pool_invitation_job(db, probe):
    application, target, world = _pool_world(db)
    entry = _join_pool(db, application)
    invited = talent_pool.invite(db, entry, target, world["people"]["hr"]["id"])
    invited_id = invited.id
    probe.start()
    cv_processing.run_from_blind_text(invited_id, helpers_board.CV_BLIND)
    db.expire_all()
    assert db.get(type(invited), invited_id).stage == "invited"
    probe.assert_clean("cv_assess")
