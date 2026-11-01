"""A chunk is only as open as the nodes extracted from it, and it speaks for those nodes in a conflict."""
import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from app.ai.providers import fake
from app.brain import audience as aud
from app.brain import copilot, retriever
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
