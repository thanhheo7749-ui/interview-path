import logging

import pytest

from app.ai.providers import get_provider
from app.ai.types import AIConfigError
from app.core.settings import ConfigError
from app.main import create_app


def test_wildcard_origin_is_refused(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.test,*")
    with pytest.raises(ConfigError, match="ALLOWED_ORIGINS"):
        create_app()


@pytest.mark.parametrize("value", ["0", "-1", "ten", "1.5", ""])
def test_bad_upload_limit_is_refused(monkeypatch, value):
    monkeypatch.setenv("MAX_UPLOAD_MB", value)
    with pytest.raises(ConfigError, match="MAX_UPLOAD_MB"):
        create_app()


def test_unset_upload_limit_uses_the_default(monkeypatch):
    monkeypatch.delenv("MAX_UPLOAD_MB")
    create_app()


def test_blank_origins_log_a_warning(monkeypatch, caplog):
    monkeypatch.setenv("ALLOWED_ORIGINS", " ")
    with caplog.at_level(logging.WARNING):
        create_app()
    assert "ALLOWED_ORIGINS" in caplog.text


def test_configured_origins_do_not_warn(caplog):
    with caplog.at_level(logging.WARNING):
        create_app()
    assert "ALLOWED_ORIGINS" not in caplog.text


@pytest.fixture
def anthropic_bulk_slot(monkeypatch):
    monkeypatch.setenv("AI_BULK_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_BULK_MODEL", "claude-haiku-5-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "made-up-key")
    get_provider.cache_clear()
    yield
    get_provider.cache_clear()


def test_bad_provider_setting_fails_at_startup(monkeypatch, anthropic_bulk_slot):
    monkeypatch.setenv("ANTHROPIC_EFFORT", "enormous")
    with pytest.raises(AIConfigError, match="ANTHROPIC_EFFORT"):
        create_app()


def test_missing_sdk_fails_at_startup(monkeypatch, anthropic_bulk_slot):
    from app import main

    def missing(_name):
        raise ImportError("no module named anthropic")

    monkeypatch.setattr(main, "get_provider", missing)
    with pytest.raises(ImportError):
        create_app()


def test_fake_provider_is_not_instantiated_at_startup(monkeypatch):
    from app import main

    seen = []
    monkeypatch.setattr(main, "get_provider", seen.append)
    create_app()
    assert seen == []


def test_configured_real_provider_is_instantiated_once(monkeypatch, anthropic_bulk_slot):
    from app import main

    seen = []
    monkeypatch.setattr(main, "get_provider", seen.append)
    monkeypatch.setenv("AI_REASONING_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_REASONING_MODEL", "claude-haiku-5-5")
    create_app()
    assert seen == ["anthropic"]
