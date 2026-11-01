import pytest

from app.ai.config import load_config
from app.ai.types import AIConfigError


def _all_fake(monkeypatch):
    for slot in ("REASONING", "BULK", "EMBEDDING", "STT", "TTS"):
        monkeypatch.setenv(f"AI_{slot}_PROVIDER", "fake")
    monkeypatch.setenv("APP_ENV", "test")


def test_all_fake_is_valid_outside_production(monkeypatch):
    _all_fake(monkeypatch)
    config = load_config()
    assert config.slot("reasoning").provider == "fake"
    assert config.slot("embedding").dim == 64


def test_production_refuses_a_fake_slot(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(AIConfigError, match="AI_REASONING_PROVIDER"):
        load_config()


def test_missing_key_names_the_variable(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_BULK_PROVIDER", "openai")
    monkeypatch.setenv("AI_BULK_MODEL", "some-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AIConfigError, match="OPENAI_API_KEY"):
        load_config()


def test_missing_model_names_the_variable(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_BULK_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("AI_BULK_MODEL", raising=False)
    with pytest.raises(AIConfigError, match="AI_BULK_MODEL"):
        load_config()


def test_vendor_that_cannot_serve_a_slot_is_refused(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_EMBEDDING_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_EMBEDDING_MODEL", "x")
    monkeypatch.setenv("AI_EMBEDDING_DIM", "8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    with pytest.raises(AIConfigError, match="AI_EMBEDDING_PROVIDER"):
        load_config()


def test_unknown_provider_is_refused(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_STT_PROVIDER", "nonsense")
    with pytest.raises(AIConfigError, match="AI_STT_PROVIDER"):
        load_config()


def test_embedding_dim_is_required_for_a_real_vendor(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("AI_EMBEDDING_MODEL", "m")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("AI_EMBEDDING_DIM", raising=False)
    with pytest.raises(AIConfigError, match="AI_EMBEDDING_DIM"):
        load_config()


def _all_openai_in_production(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    for slot in ("REASONING", "BULK", "EMBEDDING", "STT", "TTS"):
        monkeypatch.setenv(f"AI_{slot}_PROVIDER", "openai")
        monkeypatch.setenv(f"AI_{slot}_MODEL", "m")
    monkeypatch.setenv("AI_EMBEDDING_DIM", "8")
    monkeypatch.setenv("OPENAI_API_KEY", "made-up")


@pytest.mark.parametrize("value", ["", "  ", "https://api.openai.com/v1/"])
def test_blank_or_official_openai_url_does_not_warn(monkeypatch, caplog, value):
    _all_openai_in_production(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", value)
    load_config()
    assert "OPENAI_BASE_URL" not in caplog.text


def test_custom_openai_url_warns_in_production(monkeypatch, caplog):
    _all_openai_in_production(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example.com/v1")
    load_config()
    assert "OPENAI_BASE_URL" in caplog.text
