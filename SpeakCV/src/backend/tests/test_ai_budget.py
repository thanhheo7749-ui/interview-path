"""The per-company daily AI budget, enforced in the gateway before any vendor call."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.ai import gateway
from app.ai.providers import fake
from app.ai.types import AIError, BudgetExceeded
from app.core import settings
from app.database.sql_models import AIUsageLog

USER = [{"role": "user", "content": "hello"}]


class Answer(BaseModel):
    answer: str


@pytest.fixture(autouse=True)
def _no_budget_override(monkeypatch):
    fake.reset()
    monkeypatch.delenv("AI_COMPANY_DAILY_BUDGET_USD", raising=False)


def _spend(db, company_id, cost, days_ago=0):
    created = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    db.add(AIUsageLog(company_id=company_id, feature="earlier", slot="bulk", provider="fake", model="fake", success=True,
                      estimated_cost_usd=cost, created_at=created))
    db.commit()


def test_a_company_over_its_daily_budget_is_refused_before_the_vendor_call_and_it_is_logged(db, monkeypatch):
    _spend(db, 7, 25.0)
    calls = []
    monkeypatch.setattr(fake.FakeProvider, "generate_text", lambda self, **kw: calls.append(kw))
    with pytest.raises(BudgetExceeded) as caught:
        gateway.generate_text("reasoning", "sys", USER, 100, "unit_test", company_id=7)
    assert isinstance(caught.value, AIError) and calls == []
    row = db.query(AIUsageLog).filter_by(feature="unit_test").one()
    assert (row.company_id, row.success, row.error_type) == (7, False, "BudgetExceeded")


def test_every_gateway_entry_point_checks_the_budget(db):
    _spend(db, 7, 30.0)
    for call in (
        lambda: gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test", 7),
        lambda: gateway.embed(["x"], "query", "unit_test", 7),
        lambda: gateway.transcribe(b"x", "audio/webm", ["en"], "unit_test", 7),
        lambda: gateway.synthesize("x", "en", None, "unit_test", 7),
    ):
        with pytest.raises(BudgetExceeded):
            call()


def test_spend_below_the_budget_other_companies_older_days_and_unpriced_calls_do_not_count(db):
    _spend(db, 7, 24.0)
    _spend(db, 8, 100.0)
    _spend(db, 7, 100.0, days_ago=2)
    _spend(db, 7, None)
    assert gateway.generate_text("reasoning", "sys", USER, 100, "unit_test", company_id=7).text


def test_a_call_without_a_company_is_never_limited(db):
    _spend(db, None, 500.0)
    assert gateway.generate_text("reasoning", "sys", USER, 100, "unit_test").text


def test_the_budget_comes_from_settings_and_defaults_to_25(db, monkeypatch):
    assert settings.ai_company_daily_budget_usd() == 25.0
    _spend(db, 7, 10.0)
    assert gateway.generate_text("reasoning", "sys", USER, 100, "unit_test", company_id=7).text
    monkeypatch.setenv("AI_COMPANY_DAILY_BUDGET_USD", "10")
    with pytest.raises(BudgetExceeded):
        gateway.generate_text("reasoning", "sys", USER, 100, "unit_test", company_id=7)


@pytest.mark.parametrize("bad", ["abc", "-1", "0", "nan"])
def test_a_bad_budget_value_is_refused(monkeypatch, bad):
    monkeypatch.setenv("AI_COMPANY_DAILY_BUDGET_USD", bad)
    with pytest.raises(settings.ConfigError):
        settings.ai_company_daily_budget_usd()


def test_a_budget_refusal_shows_hr_a_clear_message_with_a_code(app):
    @app.get("/__budget_probe")
    def probe():
        raise BudgetExceeded("limit")

    with TestClient(app) as client:
        response = client.get("/__budget_probe")
    assert response.status_code == 429
    assert response.json()["code"] == "ai_budget_exceeded" and "daily" in response.json()["detail"]
