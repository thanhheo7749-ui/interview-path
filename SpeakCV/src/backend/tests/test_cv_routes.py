import asyncio
import inspect

import pytest
from fastapi.testclient import TestClient

from app import ai_service
from app.ai.providers import fake
from app.database.sql_models import AIUsageLog, User
from app.main import create_app
from app.routers import admin, cv, interview
from app.routers.profile import get_current_user
from tests.helpers import iter_routes, route_path

PDF = ("resume.pdf", b"%PDF-fake", "application/pdf")
SECRET_TEXT = "secret-internal-detail"


@pytest.fixture
def api():
    app = create_app(legacy_b2c=True)
    app.dependency_overrides[get_current_user] = lambda: User(id=1, email="a@example.test", role="user", credits=10)
    return TestClient(app)


@pytest.fixture
def readable_cv(monkeypatch):
    async def extract(_file):
        return "Candidate CV text"

    monkeypatch.setattr(cv, "extract_text_from_cv", extract)


def _fail_provider(monkeypatch):
    def boom(self, **kwargs):
        raise RuntimeError(SECRET_TEXT)

    monkeypatch.setattr(fake.FakeProvider, "generate_text", boom)


def test_review_returns_the_full_report_as_plain_text(api, readable_cv):
    fake.enqueue("legacy", "## Report")
    response = api.post("/api/review-cv", files={"file": PDF}, data={"jd_text": "JD"})
    assert response.status_code == 200
    assert response.text == "## Report"
    assert response.headers["content-type"].startswith("text/plain")


def test_review_ai_failure_is_a_real_error_status(api, readable_cv, monkeypatch):
    _fail_provider(monkeypatch)
    response = api.post("/api/review-cv", files={"file": PDF})
    assert response.status_code == 503
    assert SECRET_TEXT not in response.text


def test_review_of_an_empty_cv_is_rejected(api, monkeypatch):
    async def extract(_file):
        return ""

    monkeypatch.setattr(cv, "extract_text_from_cv", extract)
    assert api.post("/api/review-cv", files={"file": PDF}).status_code == 400


def test_stream_helper_is_gone():
    assert not hasattr(ai_service, "call_ai_chat_stream")


def test_makeover_with_unparseable_ai_output_is_502(api, readable_cv):
    fake.enqueue("legacy", "this is not json")
    response = api.post("/api/cv/upload-makeover", files={"file": PDF})
    assert response.status_code == 502
    assert "this is not json" not in response.text


@pytest.mark.parametrize("output", ["this is not json", "[1, 2]"])
def test_tailor_with_unparseable_ai_output_is_502(api, output):
    fake.enqueue("legacy", output)
    response = api.post("/api/cv/tailor", json={"master_cv_json": {}, "jd_text": "Engineer"})
    assert response.status_code == 502


def test_generate_cv_unexpected_error_is_500_without_exception_text(api, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError(SECRET_TEXT)

    monkeypatch.setattr(cv, "call_ai_chat", boom)
    response = api.post("/api/generate-cv", json={"user_info": "x", "position": "p", "company": "c"})
    assert response.status_code == 500
    assert SECRET_TEXT not in response.text
    assert "content" not in response.json()


@pytest.mark.parametrize(
    "call",
    [
        lambda api: api.post("/api/cv/upload-makeover", files={"file": PDF}),
        lambda api: api.post("/api/cv/tailor", json={"master_cv_json": {}, "jd_text": "Engineer"}),
    ],
)
def test_other_cv_routes_do_not_return_exception_text(api, readable_cv, monkeypatch, call):
    def boom(**kwargs):
        raise RuntimeError(SECRET_TEXT)

    monkeypatch.setattr(cv, "call_ai_chat", boom)
    response = call(api)
    assert response.status_code == 500
    assert SECRET_TEXT not in response.text


def test_default_output_budget_fits_a_long_cv():
    assert ai_service.DEFAULT_MAX_OUTPUT_TOKENS == 8000


def test_default_budget_reaches_the_gateway(monkeypatch):
    seen = {}
    real = ai_service.gateway.generate_text

    def spy(slot, system, messages, max_output_tokens, feature, company_id=None):
        seen["max"] = max_output_tokens
        return real(slot, system, messages, max_output_tokens, feature, company_id)

    monkeypatch.setattr(ai_service.gateway, "generate_text", spy)
    ai_service.call_ai_chat([{"role": "user", "content": "x"}])
    assert seen["max"] == 8000


# Routes that call the gateway and have nothing to await, so FastAPI must run them in the threadpool.
SYNC_AI_ROUTES = [
    ("/api/generate-cv", cv.generate_cv),
    ("/api/cv/tailor", cv.tailor_cv),
    ("/api/chat", interview.chat),
    ("/api/hint", interview.get_hint),
    ("/api/end-interview", interview.end_interview),
    ("/api/admin/ai-brain/ingestion/jobs", admin.ai_brain_start_job),
]


@pytest.mark.parametrize("path,endpoint", SYNC_AI_ROUTES)
def test_ai_routes_without_awaits_are_plain_functions(path, endpoint):
    assert not inspect.iscoroutinefunction(endpoint), f"{path} would block the event loop"
    mounted = {route_path(r) for r in iter_routes(create_app(legacy_b2c=True))}
    assert path in mounted


def _record_loop(seen, result):
    def spy(*args, **kwargs):
        try:
            asyncio.get_running_loop()
            seen["on_event_loop"] = True
        except RuntimeError:
            seen["on_event_loop"] = False
        return result

    return spy


def test_review_calls_ai_off_the_event_loop(api, readable_cv, monkeypatch):
    seen = {}
    monkeypatch.setattr(cv, "call_ai_chat", _record_loop(seen, "report"))
    assert api.post("/api/review-cv", files={"file": PDF}).status_code == 200
    assert seen == {"on_event_loop": False}


def test_makeover_calls_ai_off_the_event_loop(api, readable_cv, monkeypatch):
    seen = {}
    monkeypatch.setattr(cv, "call_ai_chat", _record_loop(seen, '{"full_name": "A"}'))
    assert api.post("/api/cv/upload-makeover", files={"file": PDF}).status_code == 200
    assert seen == {"on_event_loop": False}


def test_transcribe_calls_ai_off_the_event_loop(api, monkeypatch):
    seen = {}
    transcript = type("T", (), {"text": "a clear enough answer"})()
    monkeypatch.setattr(interview.gateway, "transcribe", _record_loop(seen, transcript))
    response = api.post("/api/transcribe", files={"file": ("a.webm", b"abc", "audio/webm")}, data={"lang": "vi"})
    assert response.status_code == 200
    assert seen == {"on_event_loop": False}


def test_review_usage_is_logged_once(api, readable_cv, db):
    assert api.post("/api/review-cv", files={"file": PDF}).status_code == 200
    assert db.query(AIUsageLog).count() == 1
