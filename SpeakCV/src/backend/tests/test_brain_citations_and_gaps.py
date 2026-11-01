"""What the gap list counts, what an answer may cite, and who may ask."""
from types import SimpleNamespace

import pytest

from app.ai import gateway
from app.ai.providers import fake
from app.brain import copilot, gaps, retriever
from app.database.sql_models import AssistantQuestion, KbEdge, KbNode
from tests.helpers import auth_header, make_user
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


# I13: a question that hit a conflict waits on HR's decision, not on a new document


def test_a_conflict_question_is_logged_with_its_state_and_left_out_of_the_gap_list(db, world):
    world.open_conflict_on_leave()
    response = copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    assert response.state == "conflict"
    row = db.get(AssistantQuestion, response.question_id)
    assert row.state == "conflict" and row.answered is False
    assert gaps.list_gaps(db, world.company_id) == []


def test_a_not_found_question_and_an_old_row_with_no_state_stay_in_the_gap_list(db, world):
    for question, state in (("Is there a sailing club?", "not_found"), ("Is there a chess club?", None),
                            ("Which side is right?", "conflict"), ("Why did it break?", "failed")):
        db.add(AssistantQuestion(company_id=world.company_id, audience="employee", question=question, language="en",
                                 answered=False, state=state, resolved=False))
    db.commit()
    samples = {group.sample_question for group in gaps.list_gaps(db, world.company_id)}
    assert samples == {"Is there a sailing club?", "Is there a chess club?"}


# I14: every answer returned has a citation someone can follow


def _sourceless(db, world):
    """Hop expansion brings in nodes like this one, which no document stands behind."""
    return world.node("Annual leave days at Acme", "Annual leave is 99 days.", "internal")


def test_citing_only_a_sourceless_node_retries_then_is_not_found(db, world, spy_reasoning):
    node = _sourceless(db, world)
    for _ in range(3):
        fake.enqueue("copilot_answer", answer_json(f"n{node.id}", answer="UNCITED"))
    response = copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    assert spy_reasoning.calls == 2
    assert response.state == "not_found" and "UNCITED" not in response.answer and response.citations == []
    assert db.get(AssistantQuestion, response.question_id).answered is False


def test_a_retry_after_citing_a_sourceless_node_can_still_answer(db, world):
    node = _sourceless(db, world)
    fake.enqueue("copilot_answer", answer_json(f"n{node.id}"))
    fake.enqueue("copilot_answer", answer_json(world.leave_ref))
    response = copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    assert response.state == "answered" and response.citations
    retry = fake.last_messages()[-1]["content"]
    assert world.leave_ref in retry and f"n{node.id}" not in retry


def test_a_sourceless_node_next_to_a_sourced_one_still_fails_the_check(db, world, spy_reasoning):
    node = _sourceless(db, world)
    for _ in range(2):
        fake.enqueue("copilot_answer", answer_json(world.leave_ref, f"n{node.id}"))
    assert copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id).state == "not_found"
    assert spy_reasoning.calls == 2


def test_a_sourceless_node_stays_readable_in_the_prompt_but_is_not_offered_for_citing(db, world):
    node = _sourceless(db, world)
    fake.enqueue("copilot_answer", answer_json(world.leave_ref))
    copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    prompt = fake.last_messages()[0]["content"]
    assert f"[n{node.id}] Annual leave days at Acme" in prompt
    citable = prompt.split("</context>")[1].split("<question>")[0]
    assert world.leave_ref in citable and f"n{node.id}" not in citable


def test_with_nothing_citable_the_model_is_not_called(db, world, spy_reasoning):
    world.make_empty()
    world.node("Annual leave days", "Annual leave is 12 days.", "internal")
    response = copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    assert response.state == "not_found" and spy_reasoning.calls == 0


def test_a_hop_neighbour_with_no_source_cannot_be_the_citation_of_an_answer(db, world):
    company_node = KbNode(company_id=world.company_id, type="company", title="Acme", body="", language="en",
                          visibility="public", status="published")
    db.add(company_node)
    db.commit()
    db.add(KbEdge(company_id=world.company_id, source_node_id=world.leave.id, target_node_id=company_node.id,
                  relation="applies_to", status="published"))
    db.commit()
    question = "How many days of annual leave?"
    assert f"n{company_node.id}" in {item.ref for item in retriever.search(db, world.employee_audience, question).items}
    for _ in range(2):
        fake.enqueue("copilot_answer", answer_json(f"n{company_node.id}", answer="UNCITED"))
    response = copilot.ask(db, world.employee_audience, question, world.employee_id)
    assert response.state == "not_found"


# A flagged user changes their password before asking anything


def test_public_ask_refuses_a_user_who_must_change_their_password(db, client, world):
    user = make_user(db, "flagged@example.test")
    user.must_change_password = True
    db.commit()
    response = client.post("/api/public/companies/acme/ask", headers=auth_header("flagged@example.test"),
                           json={"question": "How many days of annual leave?"})
    assert response.status_code == 403
    assert response.json()["detail"] == "password_change_required"
    assert db.query(AssistantQuestion).count() == 0


def test_public_ask_refuses_a_flagged_user_before_saying_whether_the_slug_exists(db, client, world):
    user = make_user(db, "flagged@example.test")
    user.must_change_password = True
    db.commit()
    response = client.post("/api/public/companies/nope/ask", headers=auth_header("flagged@example.test"),
                           json={"question": "How many days of annual leave?"})
    assert response.status_code == 403
