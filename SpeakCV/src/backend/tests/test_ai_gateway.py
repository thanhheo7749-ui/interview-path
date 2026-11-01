import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.ai import gateway
from app.ai.providers import fake
from app.ai.types import AIOutputError, AIProviderError
from app.database.sql_models import AIUsageLog


class Answer(BaseModel):
    answer: str


USER = [{"role": "user", "content": "hello"}]


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


def test_generate_text_returns_text_and_logs_usage(db):
    result = gateway.generate_text("reasoning", "sys", USER, 100, "unit_test", company_id=7)
    assert result.provider == "fake"
    assert "hello" in result.text
    row = db.query(AIUsageLog).one()
    assert (row.feature, row.slot, row.company_id, row.success) == ("unit_test", "reasoning", 7, True)
    assert row.input_tokens > 0


def test_structured_retries_once_with_the_validation_error(db):
    fake.enqueue("unit_test", "not json")
    fake.enqueue("unit_test", '{"answer": "ok"}')
    result = gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test")
    assert result.value == Answer(answer="ok")
    assert db.query(AIUsageLog).count() == 2
    assert fake.last_messages()[-1]["role"] == "user"
    assert "validation" in fake.last_messages()[-1]["content"].lower()


def test_structured_second_failure_raises_output_error():
    fake.enqueue("unit_test", "bad")
    fake.enqueue("unit_test", "still bad")
    with pytest.raises(AIOutputError):
        gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test")


def test_structured_default_output_matches_schema():
    assert gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test").value.answer


def test_vendor_failure_becomes_provider_error_and_is_logged(db, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("socket closed")

    monkeypatch.setattr(fake.FakeProvider, "generate_text", lambda self, **kw: boom(**kw))
    with pytest.raises(AIProviderError):
        gateway.generate_text("reasoning", "sys", USER, 100, "unit_test")
    row = db.query(AIUsageLog).one()
    assert row.success is False
    assert row.error_type == "RuntimeError"


def test_embed_is_deterministic_and_reports_model_and_dimension():
    first = gateway.embed(["xin chào thế giới", "other"], "document", "unit_test")
    second = gateway.embed(["xin chào thế giới", "other"], "query", "unit_test")
    assert first.vectors == second.vectors
    assert first.dimension == 64 == len(first.vectors[0])
    assert first.model == "fake"


def test_fake_embedding_ranks_shared_words_higher():
    vectors = gateway.embed(["annual leave policy", "annual leave days", "kubernetes cluster"], "document", "unit_test").vectors
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    assert dot(vectors[0], vectors[1]) > dot(vectors[0], vectors[2])


def test_transcribe_returns_utf8_audio_bytes_as_text():
    result = gateway.transcribe("xin chào".encode(), "audio/webm", ["vi"], "unit_test")
    assert result.text == "xin chào"
    assert result.language == "vi"


def test_synthesize_returns_audio():
    result = gateway.synthesize("hello", "en", None, "unit_test")
    assert result.audio and result.mime_type == "audio/mpeg"


def test_usage_log_failure_does_not_break_the_call(monkeypatch):
    from app.ai import usage

    def broken_session():
        raise RuntimeError("database down")

    monkeypatch.setattr(usage, "SessionLocal", broken_session)
    assert gateway.generate_text("reasoning", "sys", USER, 100, "unit_test").text


def test_cost_is_estimated_from_pricing():
    from app.ai.types import Usage
    from app.ai.usage import estimate_cost

    assert estimate_cost("claude-opus-5-5", Usage(input_tokens=1_000_000, output_tokens=1_000_000)) == pytest.approx(24.0)
    assert estimate_cost("unknown-model", Usage(input_tokens=5)) is None


def test_ai_errors_map_to_http_status(app):
    @app.get("/_boom503")
    def boom503():
        raise AIProviderError("down")

    @app.get("/_boom502")
    def boom502():
        raise AIOutputError("bad")

    client = TestClient(app)
    assert client.get("/_boom503").status_code == 503
    assert client.get("/_boom502").status_code == 502
