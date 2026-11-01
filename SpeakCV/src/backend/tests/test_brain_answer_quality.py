"""What Copilot reads and when it answers: fact text and relevance."""
from types import SimpleNamespace

import pytest
import yaml

from app.ai import gateway
from app.ai.providers import fake
from app.brain import copilot, retriever
from app.brain.text import content_tokens, keyword_coverage, tokenise
from app.database.sql_models import KbChunk, KbEdge, KbNode, KbNodeSource
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


# I9: relevance comes from raw signals, while the hybrid score only ranks


def test_stop_words_are_dropped_in_each_language():
    assert content_tokens(tokenise("What is the annual leave?")) == ["annual", "leave"]
    assert content_tokens(tokenise("Tôi được nghỉ phép bao nhiêu ngày?")) == ["nghỉ", "phép", "ngày"]
    assert "연차" in content_tokens(tokenise("연차는 며칠입니까?"))
    assert not {"입니", "니까"} & set(content_tokens(tokenise("연차는 며칠입니까?")))


def test_keyword_coverage_is_the_share_of_distinct_content_tokens_found():
    query = tokenise("What is the annual leave annual policy?")
    assert keyword_coverage(query, tokenise("Annual leave and the policy")) == 1.0
    assert keyword_coverage(query, tokenise("annual")) == pytest.approx(1 / 3)
    assert keyword_coverage(query, tokenise("the is what")) == 0.0


def test_keyword_coverage_of_a_query_with_only_stop_words_is_zero():
    assert keyword_coverage(tokenise("What is the"), tokenise("What is the")) == 0.0


def test_thresholds_are_provisional_and_live_in_the_yaml():
    source = copilot.THRESHOLDS_PATH.read_text(encoding="utf-8")
    assert "provisional" in source.lower()
    assert "min_cosine" in source and "min_keyword_coverage" in source
    assert copilot.min_keyword_coverage() == yaml.safe_load(source)["min_keyword_coverage"]
    assert copilot.threshold_for("some-new-embedding-model") == yaml.safe_load(source)["min_cosine"]["default"]


def test_scores_are_exposed_on_the_bundle(db, world):
    question = "How many days of annual leave?"
    bundle = retriever.search(db, world.employee_audience, question)
    item = next(item for item in bundle.items if item.ref == world.leave_ref)
    assert item.keyword_coverage > 0.5
    assert item.cosine > 0
    assert bundle.best_cosine == max(item.cosine for item in bundle.items)
    assert bundle.best_keyword_coverage == max(item.keyword_coverage for item in bundle.items)


def test_a_bundle_built_from_three_values_still_works():
    assert retriever.ContextBundle((), 0.0, frozenset()).best_cosine == 0.0
    item = retriever.ContextItem("n1", "node", "t", 0.0, None, ())
    assert item.cosine == 0.0 and item.keyword_coverage == 0.0


def test_a_hop_neighbour_with_no_vector_has_no_cosine(db, world):
    company_node = KbNode(company_id=world.company_id, type="company", title="Acme", body="", language="en",
                          visibility="public", status="published")
    db.add(company_node)
    db.commit()
    db.add(KbEdge(company_id=world.company_id, source_node_id=world.leave.id, target_node_id=company_node.id,
                  relation="applies_to", status="published"))
    db.commit()
    bundle = retriever.search(db, world.employee_audience, "How many days of annual leave?")
    item = next(item for item in bundle.items if item.ref == f"n{company_node.id}")
    assert item.cosine == 0.0


@pytest.mark.parametrize("question", ["What is the of and for?", "Is there a for the on my in?", "What is the weather on Mars for us?"])
def test_a_query_sharing_only_stop_words_is_not_found_with_no_model_call(db, world, spy_reasoning, question):
    response = copilot.ask(db, world.employee_audience, question, world.employee_id)
    assert response.state == "not_found"
    assert spy_reasoning.calls == 0


def _bundle_with(cosine=0.0, coverage=0.0, ref="n1", best_score=0.99):
    item = retriever.ContextItem(ref, "node", "Text", best_score, None, (retriever.NOT_SHARED,), cosine, coverage)
    return retriever.ContextBundle((item,), best_score, frozenset())


def _signals_at(monkeypatch, bundle):
    monkeypatch.setattr(copilot.retriever, "search", lambda *a, **k: bundle)
    monkeypatch.setattr(copilot, "threshold_for", lambda model: 0.4)
    monkeypatch.setattr(copilot, "min_keyword_coverage", lambda: 0.6)


@pytest.mark.parametrize("cosine,coverage,calls", [
    (0.4, 0.0, 1), (0.0, 0.6, 1), (0.39, 0.59, 0), (0.0, 0.0, 0),
])
def test_either_raw_signal_alone_is_enough_and_the_hybrid_score_does_not_count(db, world, monkeypatch, spy_reasoning, cosine, coverage, calls):
    _signals_at(monkeypatch, _bundle_with(cosine, coverage))
    copilot.ask(db, world.employee_audience, "anything", world.employee_id)
    assert spy_reasoning.calls == calls


def _only_leave_conflict_and_dress_code(world):
    world.make_empty()
    handbook = world.document("Handbook", "internal")
    a = world.node("Annual leave handbook", "Annual leave is 12 days.", "internal", document=handbook, chunk_text="Leave A.")
    b = world.node("Annual leave policy", "Annual leave is 15 days.", "internal", document=handbook, chunk_text="Leave B.")
    world.open_conflict(a, b)
    dress = world.node("Uniform rule", "Factory uniform with safety shoes.", "internal", document=handbook, chunk_text="Uniform.")
    return a, b, dress


def test_a_conflicted_fact_unrelated_to_the_question_does_not_trigger_the_template(db, world, spy_reasoning):
    a, b, dress = _only_leave_conflict_and_dress_code(world)
    fake.enqueue("copilot_answer", answer_json(f"n{dress.id}", answer="Uniform with safety shoes."))
    response = copilot.ask(db, world.employee_audience, "Which uniform rule applies, safety shoes?", world.employee_id)
    assert response.state == "answered"
    assert spy_reasoning.calls == 1
    prompt = fake.last_messages()[0]["content"]
    assert "12 days" not in prompt and "15 days" not in prompt  # still withheld, though it does not stop the answer


def test_a_chunk_on_two_topics_does_not_trigger_the_template_for_the_topic_not_asked_about(db, world, spy_reasoning):
    # Chunks run to 1,200 characters, so one that matches the question can also state a conflicted fact on another topic.
    a, b, dress = _only_leave_conflict_and_dress_code(world)
    shared = KbNodeSource(node_id=a.id, chunk_id=_chunk_saying(db, world, "Which uniform rule applies? Safety shoes. Also annual leave is 12 days.").id, quote="q")
    db.add(shared)
    db.commit()
    question = "Which uniform rule applies, safety shoes?"
    assert f"c{shared.chunk_id}" in {item.ref for item in retriever.search(db, world.employee_audience, question).items[:3]}
    fake.enqueue("copilot_answer", answer_json(f"n{dress.id}", answer="Uniform with safety shoes."))
    response = copilot.ask(db, world.employee_audience, question, world.employee_id)
    assert response.state == "answered"
    prompt = fake.last_messages()[0]["content"]
    assert "12 days" not in prompt  # it does not stop the answer, and its value is still not asserted


def test_a_chunk_stating_the_conflicted_fact_asked_about_triggers_the_template(db, world, spy_reasoning):
    a, b, _ = _only_leave_conflict_and_dress_code(world)
    db.add(KbNodeSource(node_id=a.id, chunk_id=_chunk_saying(db, world, "How many days of annual leave? 12 days.").id, quote="q"))
    db.commit()
    response = copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    assert response.state == "conflict"
    assert spy_reasoning.calls == 0


def _chunk_saying(db, world, text):
    document = world.document("Mixed Section", "internal")
    chunk = KbChunk(company_id=world.company_id, document_id=document.id, position=0, text=text,
                    **world._vector_fields(text, world.company_id))
    db.add(chunk)
    db.commit()
    return chunk


def test_a_conflicted_fact_related_to_the_question_still_triggers_the_template(db, world, spy_reasoning):
    _only_leave_conflict_and_dress_code(world)
    response = copilot.ask(db, world.employee_audience, "How many days of annual leave?", world.employee_id)
    assert response.state == "conflict"
    assert spy_reasoning.calls == 0
