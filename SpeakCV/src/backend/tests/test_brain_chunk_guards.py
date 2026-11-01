"""A chunk is only as open as the nodes extracted from it, and it speaks for those nodes in a conflict."""
import json
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from app.ai import gateway
from app.ai.providers import fake
from app.brain import audience as aud
from app.brain import contradiction, copilot, retriever
from app.database.sql_models import KbChunk, KbNodeSource
from tests.helpers import auth_header
from tests.test_brain_copilot import World, answer_json, prompt_text

PUBLIC_DOC_CANARY = "CANARY-PUBLIC-JD-SALARY-4417"
SALARY_QUESTION = "What is the salary band?"


@pytest.fixture(autouse=True)
def _empty_vector_cache():
    retriever.clear_vector_cache()
    yield
    retriever.clear_vector_cache()


@pytest.fixture
def world(db):
    return World(db)


@pytest.fixture
def api(client, world):
    return SimpleNamespace(client=client, public="/api/public/companies/acme/ask")


def plant_salary_chunk(world, node_status="published", node_visibility="confidential", department_id=None,
                       document_visibility="public"):
    """A document says the band out loud, and extraction turned that sentence into a node of its own."""
    document = world.document("Job Advert", document_visibility)
    return world.node("Backend pay note", "Pay discussed at offer.", node_visibility, type="private_note",
                      status=node_status, document=document, department_id=department_id,
                      chunk_text=f"The salary band is 30 to 40 million. {PUBLIC_DOC_CANARY}")


def assert_salary_chunk_hidden(response):
    assert PUBLIC_DOC_CANARY not in fake.last_system()
    assert PUBLIC_DOC_CANARY not in " ".join(m["content"] for m in fake.last_messages())
    assert PUBLIC_DOC_CANARY not in json.dumps(asdict(response), default=str)


def everything(db, audience):
    bundle = retriever.search(db, audience, SALARY_QUESTION, top_k=100, char_budget=10 ** 6)
    return " ".join(item.text for item in bundle.items)


# C1


@pytest.mark.parametrize("kind", ["candidate", "employee"])
@pytest.mark.parametrize("status,visibility", [("published", "confidential"), ("rejected", "confidential"),
                                               ("rejected", "public"), ("superseded", "public"),
                                               ("draft", "confidential")])
def test_public_chunk_stays_out_when_its_node_is_hidden_or_withdrawn(db, world, kind, status, visibility):
    plant_salary_chunk(world, status, visibility)
    audience = aud.Audience(world.company_id, kind)
    response = copilot.ask(db, audience, SALARY_QUESTION, None)
    assert "<context>" in prompt_text()  # the model was called, so this checks a real prompt
    assert_salary_chunk_hidden(response)
    assert PUBLIC_DOC_CANARY not in everything(db, audience)


def test_employee_does_not_get_an_internal_chunk_behind_a_confidential_node(db, world):
    plant_salary_chunk(world, document_visibility="internal")
    assert PUBLIC_DOC_CANARY not in everything(db, world.employee_audience)


def test_control_a_public_chunk_whose_node_is_also_public_reaches_the_candidate(db, world):
    plant_salary_chunk(world, "published", "public")
    fake.enqueue("copilot_answer", answer_json(world.public_leave_ref))
    copilot.ask(db, aud.candidate(world.company_id), SALARY_QUESTION, None)
    assert PUBLIC_DOC_CANARY in prompt_text()


def test_control_a_draft_public_node_does_not_hide_its_chunk(db, world):
    plant_salary_chunk(world, "draft", "public")
    assert PUBLIC_DOC_CANARY in everything(db, aud.candidate(world.company_id))


def test_a_chunk_with_no_nodes_at_all_keeps_its_documents_layer(db, world):
    document = world.document("Job Advert", "public")
    text = f"The salary band is open. {PUBLIC_DOC_CANARY}"
    db.add(KbChunk(company_id=world.company_id, document_id=document.id, position=0, text=text,
                   **world._vector_fields(text, world.company_id)))
    db.commit()
    assert PUBLIC_DOC_CANARY in everything(db, aud.candidate(world.company_id))


def test_hr_still_sees_a_chunk_sourcing_a_confidential_node(db, world):
    plant_salary_chunk(world)
    assert PUBLIC_DOC_CANARY in everything(db, world.hr_audience)


@pytest.mark.parametrize("status", ["rejected", "superseded"])
def test_a_withdrawn_node_hides_its_chunk_from_hr_too(db, world, status):
    plant_salary_chunk(world, status)
    assert PUBLIC_DOC_CANARY not in everything(db, world.hr_audience)


def test_one_hidden_node_hides_a_chunk_that_also_sources_a_public_node(db, world):
    node = plant_salary_chunk(world, "published", "public")
    chunk_id = db.query(KbNodeSource.chunk_id).filter_by(node_id=node.id).scalar()
    note = world.node("Pay note", "Pay.", "confidential", type="private_note")
    db.add(KbNodeSource(node_id=note.id, chunk_id=chunk_id, quote="quote"))
    db.commit()
    assert PUBLIC_DOC_CANARY not in everything(db, aud.candidate(world.company_id))


def test_manager_reads_a_chunk_behind_a_confidential_node_only_in_their_subtree(db, world):
    plant_salary_chunk(world, department_id=world.eng_id)
    assert PUBLIC_DOC_CANARY in everything(db, world.manager_audience)


def test_manager_outside_the_department_does_not_read_the_chunk(db, world):
    plant_salary_chunk(world, department_id=world.sales_id)
    assert PUBLIC_DOC_CANARY not in everything(db, world.manager_audience)


def test_manager_does_not_read_a_chunk_behind_a_company_wide_confidential_node(db, world):
    # department_id NULL makes the layer test NULL in SQL, and NOT NULL is not true. It must still exclude the chunk.
    plant_salary_chunk(world, department_id=None)
    assert PUBLIC_DOC_CANARY not in everything(db, world.manager_audience)


def test_rejecting_a_node_hides_its_chunk_at_once_with_the_vector_cache_warm(db, world):
    node = plant_salary_chunk(world, "published", "public")
    candidate = aud.candidate(world.company_id)
    assert PUBLIC_DOC_CANARY in everything(db, candidate)
    node.status = "rejected"
    db.commit()
    assert PUBLIC_DOC_CANARY not in everything(db, candidate)


def test_public_route_does_not_leak_the_chunk_through_http(db, api, world):
    plant_salary_chunk(world)
    response = api.client.post(api.public, headers=auth_header("hr@example.test"), json={"question": SALARY_QUESTION})
    assert response.status_code == 200
    assert PUBLIC_DOC_CANARY not in response.text and PUBLIC_DOC_CANARY not in prompt_text()


# C2


LEAVE_QUESTION = "How many days of annual leave do we get?"
TWELVE = "How many days of annual leave do we get? Twelve: annual leave is 12 days."
FIFTEEN = "How many days of annual leave do we get? Fifteen: annual leave is 15 days."
PORTAL = "How many days of annual leave do we get? Ask for them in the leave portal."


@pytest.fixture
def leave(db, world):
    """Two facts disagree, and their source chunks say so in words closer to the question than the nodes are."""
    world.make_empty()
    handbook = world.document("Internal Handbook", "internal")
    policy = world.document("Leave Policy", "internal")
    guide = world.document("Portal Guide", "internal")
    a = world.node("Entitlement in the handbook", "Handbook entitlement figure.", "internal", document=handbook, chunk_text=TWELVE)
    b = world.node("Entitlement in the policy", "Policy entitlement figure.", "internal", document=policy, chunk_text=FIFTEEN)
    portal = world.node("Portal note", "Requests go through the portal.", "internal", document=guide, chunk_text=PORTAL)
    conflict = world.open_conflict(a, b)
    chunk_of = {node.id: db.query(KbNodeSource.chunk_id).filter_by(node_id=node.id).scalar() for node in (a, b, portal)}
    return SimpleNamespace(a=a, b=b, portal=portal, conflict=conflict, ref_a=f"n{a.id}", ref_b=f"n{b.id}",
                           chunk_a=f"c{chunk_of[a.id]}", chunk_b=f"c{chunk_of[b.id]}", chunk_portal=f"c{chunk_of[portal.id]}")


def _force_order(monkeypatch, first_refs):
    real = retriever.search

    def reordered(*args, **kwargs):
        bundle = real(*args, **kwargs)
        first = [item for ref in first_refs for item in bundle.items if item.ref == ref]
        rest = [item for item in bundle.items if item.ref not in first_refs]
        return replace(bundle, items=(*first, *rest))

    monkeypatch.setattr(copilot.retriever, "search", reordered)


@pytest.fixture
def spy_reasoning(monkeypatch):
    spy = SimpleNamespace(calls=0)
    real = gateway.generate_structured

    def counting(*args, **kwargs):
        spy.calls += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(copilot.gateway, "generate_structured", counting)
    return spy


def test_after_hr_keeps_15_days_no_12_days_reaches_the_prompt(db, world, leave):
    contradiction.resolve(db, leave.conflict, "b", world.hr_id)
    fake.enqueue("copilot_answer", answer_json(leave.chunk_b, answer="15 days."))
    response = copilot.ask(db, world.employee_audience, LEAVE_QUESTION, world.employee_id)
    assert response.state == "answered" and response.answer == "15 days."
    assert "12 days" in TWELVE and "12 days" not in prompt_text()
    assert "15 days" in prompt_text()


def test_chunks_ranked_above_both_facts_still_give_the_conflict_state_and_no_model_call(db, world, leave, spy_reasoning):
    items = retriever.search(db, world.employee_audience, LEAVE_QUESTION).items
    refs = [item.ref for item in items]
    assert {leave.chunk_a, leave.chunk_b, leave.chunk_portal} == set(refs[:3])  # the trap is real: no fact node is on top
    response = copilot.ask(db, world.employee_audience, LEAVE_QUESTION, world.employee_id)
    assert response.state == "conflict"
    assert spy_reasoning.calls == 0
    assert fake.last_messages() == []
    assert "12" not in response.answer and "15" not in response.answer
    assert {c.title for c in response.citations} == {"Internal Handbook", "Leave Policy"}


def test_a_conflicted_chunk_below_the_top_three_is_withheld_from_the_prompt(db, world, leave, monkeypatch):
    first = [leave.chunk_portal, f"n{leave.portal.id}"]
    filler = world.node("Annual leave days note", "How many days of annual leave do we get is a common question.", "internal",
                        document=world.document("FAQ", "internal"), chunk_text="Unrelated section.")
    _force_order(monkeypatch, [*first, f"n{filler.id}"])
    fake.enqueue("copilot_answer", answer_json(leave.chunk_portal, answer="Use the portal."))
    response = copilot.ask(db, world.employee_audience, LEAVE_QUESTION, world.employee_id)
    assert response.state == "answered"
    prompt = fake.last_messages()[0]["content"]
    assert PORTAL in prompt
    for value in ("12 days", "15 days"):
        assert value not in prompt


def test_citing_a_withheld_conflicted_chunk_fails_verification(db, world, leave, monkeypatch):
    filler = world.node("Annual leave days note", "How many days of annual leave do we get is a common question.", "internal",
                        document=world.document("FAQ", "internal"), chunk_text="Unrelated section.")
    _force_order(monkeypatch, [leave.chunk_portal, f"n{leave.portal.id}", f"n{filler.id}"])
    for _ in range(2):
        fake.enqueue("copilot_answer", answer_json(leave.chunk_a, answer="12 days."))
    assert copilot.ask(db, world.employee_audience, LEAVE_QUESTION, world.employee_id).state == "not_found"


def test_visible_conflicts_maps_a_chunk_to_the_conflict_of_its_node(db, world, leave):
    found = retriever.visible_conflicts(db, world.employee_audience, {leave.chunk_a, leave.chunk_portal})
    assert set(found) == {leave.chunk_a}
    assert {c.title for c in found[leave.chunk_a]} == {"Internal Handbook", "Leave Policy"}


def test_conflicted_refs_name_the_chunks_in_the_bundle(db, world, leave):
    bundle = retriever.search(db, world.employee_audience, LEAVE_QUESTION)
    assert {leave.chunk_a, leave.chunk_b} <= bundle.conflicted_refs
    assert leave.chunk_portal not in bundle.conflicted_refs


def test_a_conflict_with_a_hidden_side_does_not_withhold_the_visible_chunk(db, world, leave):
    leave.conflict.status = "dismissed"
    hidden_doc = world.document("Secret Pay", "confidential")
    hidden = world.node("Hidden entitlement", "CANARY-HIDDEN-LEAVE-1212", "confidential", document=hidden_doc)
    world.open_conflict(leave.a, hidden)
    fake.enqueue("copilot_answer", answer_json(leave.chunk_a, answer="12 days."))
    response = copilot.ask(db, world.employee_audience, LEAVE_QUESTION, world.employee_id)
    assert response.state == "answered"
    assert "12 days" in prompt_text()
    assert "CANARY-HIDDEN-LEAVE-1212" not in prompt_text() + json.dumps(asdict(response), default=str)
    assert "Secret Pay" not in json.dumps(asdict(response), default=str)


@pytest.mark.parametrize("status", ["dismissed", "resolved"])
def test_a_conflict_no_longer_open_does_not_hold_back_the_chunks(db, world, leave, status):
    leave.conflict.status = status
    db.commit()
    fake.enqueue("copilot_answer", answer_json(leave.chunk_a, answer="12 days."))
    assert copilot.ask(db, world.employee_audience, LEAVE_QUESTION, world.employee_id).state == "answered"
