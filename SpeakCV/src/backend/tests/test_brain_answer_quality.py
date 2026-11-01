"""What Copilot reads and when it answers: fact text, relevance, citations and the gap list."""
import json
from types import SimpleNamespace

import pytest

from app.ai import gateway
from app.ai.providers import fake
from app.brain import copilot, retriever
from tests.test_brain_copilot import World, answer_json


@pytest.fixture
def world(db):
    return World(db)


@pytest.fixture
def spy_reasoning(monkeypatch):
    spy = SimpleNamespace(calls=0)
    real = gateway.generate_structured

    def counting(*args, **kwargs):
        spy.calls += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(copilot.gateway, "generate_structured", counting)
    return spy


# I2: a fact's value, unit and scope are part of its text


def _fact(**fields):
    return SimpleNamespace(**{"title": "Annual leave", "body": "", "fact_value": None, "fact_unit": None,
                              "scope_text": None, **fields})


def test_node_text_of_a_plain_node_is_title_and_body():
    assert retriever.node_text(_fact(body="Leave rules.")) == "Annual leave\nLeave rules."
    assert retriever.node_text(_fact()) == "Annual leave"


def test_node_text_of_a_fact_adds_value_unit_and_scope():
    text = retriever.node_text(_fact(body="Leave rules.", fact_value="15", fact_unit="days", scope_text="all staff"))
    assert text == "Annual leave\nLeave rules.\n15 days\nall staff"


def test_node_text_skips_empty_fact_fields():
    assert retriever.node_text(_fact(fact_value="15", fact_unit="", scope_text="")) == "Annual leave\n15"


def test_editing_a_facts_value_changes_what_the_model_reads(db, world):
    world.leave.fact_kind, world.leave.fact_value, world.leave.fact_unit = "number", "27", "working days"
    world.leave.scope_text = "field engineers"
    db.commit()
    fake.enqueue("copilot_answer", answer_json(world.leave_ref))
    copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    prompt = fake.last_messages()[0]["content"]
    assert "27 working days" in prompt and "field engineers" in prompt


def test_keyword_scoring_sees_the_value_and_scope(db, world):
    question = "annual leave for zanzibar contractors"
    before = retriever.search(db, world.employee_audience, question)
    score_before = next(item.score for item in before.items if item.ref == world.leave_ref)
    world.leave.fact_kind, world.leave.fact_value, world.leave.scope_text = "number", "27", "zanzibar contractors"
    db.commit()
    after = retriever.search(db, world.employee_audience, question)
    assert next(item.score for item in after.items if item.ref == world.leave_ref) > score_before
