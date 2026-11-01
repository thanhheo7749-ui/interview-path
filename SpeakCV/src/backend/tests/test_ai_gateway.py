import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.ai import gateway
from app.ai.providers import fake
from app.ai.types import AIConfigError, AIOutputError, AIProviderError, Usage
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


def test_failed_validation_is_logged_as_a_failure_with_its_usage(db):
    fake.enqueue("unit_test", "not json")
    fake.enqueue("unit_test", '{"answer": "ok"}')
    gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test")
    first, second = db.query(AIUsageLog).order_by(AIUsageLog.id).all()
    assert (first.success, first.error_type) == (False, "ValidationError")
    assert first.input_tokens > 0 and first.output_tokens > 0
    assert (second.success, second.error_type) == (True, None)


def test_two_failed_validations_write_two_failure_rows_only(db):
    fake.enqueue("unit_test", "bad")
    fake.enqueue("unit_test", "still bad")
    with pytest.raises(AIOutputError):
        gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test")
    rows = db.query(AIUsageLog).all()
    assert [(r.success, r.error_type) for r in rows] == [(False, "ValidationError")] * 2


def test_output_error_usage_is_logged(db, monkeypatch):
    def refused(self, **kwargs):
        raise AIOutputError("refused", usage=Usage(input_tokens=40, output_tokens=3))

    monkeypatch.setattr(fake.FakeProvider, "generate_text", refused)
    with pytest.raises(AIOutputError):
        gateway.generate_text("reasoning", "sys", USER, 100, "unit_test")
    row = db.query(AIUsageLog).one()
    assert (row.success, row.error_type, row.input_tokens, row.output_tokens) == (False, "AIOutputError", 40, 3)


def test_output_error_without_usage_logs_zero_tokens(db, monkeypatch):
    def empty(self, **kwargs):
        raise AIOutputError("empty")

    monkeypatch.setattr(fake.FakeProvider, "generate_text", empty)
    with pytest.raises(AIOutputError):
        gateway.generate_text("reasoning", "sys", USER, 100, "unit_test")
    assert db.query(AIUsageLog).one().input_tokens == 0


@pytest.mark.parametrize("error", [ImportError("no sdk"), KeyError("KEY"), AIConfigError("bad effort")])
def test_provider_construction_failure_is_a_provider_error_with_a_usage_row(db, monkeypatch, error):
    def broken(_name):
        raise error

    monkeypatch.setattr(gateway, "get_provider", broken)
    with pytest.raises(AIProviderError):
        gateway.generate_text("reasoning", "sys", USER, 100, "unit_test")
    row = db.query(AIUsageLog).one()
    assert (row.success, row.error_type) == (False, type(error).__name__)


def _with_prices(monkeypatch, **models):
    from app.ai import usage

    monkeypatch.setattr(usage, "_prices", lambda: models)


def test_cost_covers_audio_and_characters_when_priced(monkeypatch):
    from app.ai.usage import estimate_cost

    _with_prices(monkeypatch, m={"input_per_1m": 1.0, "output_per_1m": 2.0, "per_audio_second": 0.5, "per_1k_characters": 3.0})
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000, audio_seconds=2.0, characters=2000)
    assert estimate_cost("m", usage) == pytest.approx(1.0 + 2.0 + 1.0 + 6.0)


@pytest.mark.parametrize("usage", [Usage(input_tokens=10, audio_seconds=1.0), Usage(input_tokens=10, characters=5)])
def test_cost_is_unknown_rather_than_partial(monkeypatch, usage):
    from app.ai.usage import estimate_cost

    _with_prices(monkeypatch, m={"input_per_1m": 1.0, "output_per_1m": 2.0})
    assert estimate_cost("m", usage) is None


def test_token_only_model_still_gets_a_cost(monkeypatch):
    from app.ai.usage import estimate_cost

    _with_prices(monkeypatch, m={"input_per_1m": 1.0, "output_per_1m": 2.0})
    assert estimate_cost("m", Usage(input_tokens=1_000_000)) == pytest.approx(1.0)


def test_fake_speech_costs_zero_rather_than_unknown():
    from app.ai.usage import estimate_cost

    assert estimate_cost("fake", Usage(characters=100, audio_seconds=1.0)) == 0


def test_pricing_file_lists_what_still_needs_a_price():
    from app.ai.usage import PRICING_PATH

    text = PRICING_PATH.read_text(encoding="utf-8")
    assert all(name in text for name in ("gpt-transcribe", "TTS", "Voyage"))


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
