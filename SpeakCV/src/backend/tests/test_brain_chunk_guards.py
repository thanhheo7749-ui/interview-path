"""A chunk is only as open as the nodes extracted from it, and it speaks for those nodes in a conflict."""
import json
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from app.ai import gateway
from app.ai.providers import fake
from app.brain import audience as aud
from app.brain import contradiction, copilot, ingestion, retriever, review
from app.brain.chunking import chunk_pages
from app.brain.ingestion import chunks_sharing_quote
from app.brain.text import shares_span
from app.database.sql_models import Company, KbChunk, KbDocument, KbNode, KbNodeSource
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
    a = world.node("Annual leave in the handbook", "Figure from the handbook.", "internal", document=handbook, chunk_text=TWELVE)
    b = world.node("Annual leave in the policy", "Figure from the policy.", "internal", document=policy, chunk_text=FIFTEEN)
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


# A quote that straddles two chunks: the next chunk starts inside it, so it says the tail of what HR classed as hidden.

STRADDLING_CANARY = "CANARYTAIL77"
STRADDLING_QUOTE = (
    "The salary band for this backend engineering role, as agreed by the compensation committee last quarter for "
    f"the coming year and reviewed by the board of directors, is 30 to 40 million VND {STRADDLING_CANARY} per month."
)
STRADDLING_QUESTION = "What is the salary band for the backend role?"


def straddling_document(db, company):
    """Hard-window chunks, cut so that one holds the whole quote and the next one starts inside it, before the canary."""
    before = ("Our backend team builds services for customers and partners across the region every day. " * 14)[:1120]
    after = "Applicants should send a short letter about their distributed systems work and salary band questions. " * 12
    data = f"{before} {STRADDLING_QUOTE} {after}"
    pieces = chunk_pages([(None, data)])
    holders = [piece for piece in pieces if STRADDLING_QUOTE in piece.text]
    tails = [piece for piece in pieces if STRADDLING_CANARY in piece.text and STRADDLING_QUOTE not in piece.text]
    assert len(holders) == 1 and len(tails) == 1  # otherwise this document no longer tests a straddling quote
    note = {"ref": "Backend salary band", "type": "private_note", "title": "Backend salary band",
            "body": "Pay is discussed at the offer.", "quote": STRADDLING_QUOTE, "fact_kind": "none", "fact_value": "",
            "fact_unit": "", "scope_text": "", "effective_date": ""}
    for piece in pieces:
        fake.enqueue("kb_extract", json.dumps({"nodes": [note] if piece is holders[0] else [], "edges": []}))
    document = ingestion.create_document(
        db, company.id, None, title="Job advert", data=data.encode(), suffix=".md", visibility="public",
        department_id=None, language="en", effective_date=None,
    )
    job = ingestion.start_job(db, document.id)
    ingestion.run_job(job.id)
    db.expire_all()
    return db.query(KbNode).filter_by(title="Backend salary band").one(), db.get(KbDocument, document.id)


@pytest.fixture
def acme(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    fake.reset()
    row = Company(slug="acme", name="Acme")
    db.add(row)
    db.commit()
    return row


def candidate_sees(db, company_id, question):
    """Everything a candidate's question can reach: the prompt, the response and the retrieved context."""
    fake.register("copilot_answer", lambda *_: json.dumps({"can_answer": False, "answer": "", "citation_ids": []}))
    response = copilot.ask(db, aud.candidate(company_id), question, None)
    retrieved = retriever.search(db, aud.candidate(company_id), question, top_k=100, char_budget=10 ** 6)
    return " ".join([prompt_text(), json.dumps(asdict(response), default=str), *[i.text for i in retrieved.items]])


@pytest.mark.parametrize("decision", ["accept", "reject"])
def test_the_tail_of_a_straddling_quote_reaches_no_candidate(db, acme, decision):
    node, document = straddling_document(db, acme)
    assert node.visibility == "confidential"
    if decision == "accept":
        review.publish_node(db, node, None)
    else:
        node.status = "rejected"
    document.status = "published"
    db.commit()
    assert STRADDLING_CANARY not in candidate_sees(db, acme.id, STRADDLING_QUESTION)
    assert any(STRADDLING_CANARY in text for (text,) in db.query(KbChunk.text))


def test_a_straddling_quote_links_both_chunks(db, acme):
    node, _ = straddling_document(db, acme)
    assert db.query(KbNodeSource).filter_by(node_id=node.id).count() == 2


@pytest.mark.parametrize("quote,source,shared", [
    ("the whole quote is here", "before the whole quote is here after", True),
    ("the salary band is 30 million", "30 million and more after it", True),  # the tail starts the chunk
    ("the salary band is 30 million", "text before it the salary band", True),  # the head ends the chunk
    ("a b the salary band is 30 million c d", "the salary band is 30 million", True),  # the chunk lies inside the quote
    ("the salary  band\nis 30 million", "band is 30 million and after", True),  # compared after normalising whitespace
    ("the salary band is 30 million", "nothing about it in here at all", False),
    ("the salary band is 30 million.", ". nothing here", False),  # one character is chance, not a span
    ("", "anything", False),
])
def test_shares_span(quote, source, shared):
    assert shares_span(quote, source) is shared


def test_a_chunk_far_from_the_quote_is_not_linked_by_a_chance_match_at_its_edge():
    quote = "Annual leave is 12 days per year."
    chunks = ["Annual leave is 12 days per year. Then more.", "year. A different section starts here.",
              "Filler that says nothing.", "year. This chunk is far from the quote."]
    assert chunks_sharing_quote(quote, chunks) == [0, 1]


# An edit corrects the fact, not the document: the chunk it came from still says the old value.


def decision(**fields):
    return SimpleNamespace(**{**dict(action="edit", node_id=None, into_node_id=None, document_id=None, title=None,
                                     body=None, visibility=None, fact_value=None, fact_unit=None, scope_text=None),
                              **fields})


def stated_fact(world, title, body, value, unit, document, chunk_text):
    node = world.node(title, body, "public", document=document, chunk_text=chunk_text)
    node.fact_kind, node.fact_value, node.fact_unit, node.scope_text = "number", value, unit, "all staff"
    world.db.commit()
    return node


def test_a_conflict_settled_by_an_edit_leaves_no_old_value_in_the_prompt(db, world):
    keep = stated_fact(world, "Annual leave days entitlement", "Annual leave is 17 days.", "17", "days",
                       world.document("Handbook 2026", "public"), "Annual leave entitlement is 17 days CANARY17 per year.")
    edited = stated_fact(world, "Annual leave days entitlement", "Annual leave is 19 days.", "19", "days",
                         world.document("Old memo", "public"), "Annual leave entitlement is 19 days CANARY19 per year.")
    world.open_conflict(keep, edited)

    review.apply_decisions(db, world.company_id, world.hr_id, [decision(node_id=edited.id, fact_value="17")])
    db.commit()
    db.refresh(world.conflict)
    assert world.conflict.resolution == contradiction.EDIT_RESOLVED

    seen = candidate_sees(db, world.company_id, "How many days of annual leave entitlement?")
    assert "CANARY19" not in seen
    assert "19 days" not in seen
    assert "CANARY17" in seen  # the side nobody edited still speaks from its chunk


def test_a_corrected_published_value_leaves_no_old_value_in_the_prompt(db, world):
    edited = stated_fact(world, "Probation length policy", "Probation is 6 months.", "6", "months",
                         world.document("Handbook", "public"), "Probation length policy: probation lasts 6 months CANARY6.")

    review.apply_decisions(db, world.company_id, world.hr_id, [decision(node_id=edited.id, fact_value="2")])
    db.commit()

    seen = candidate_sees(db, world.company_id, "What is the probation length policy?")
    assert "CANARY6" not in seen
    assert "6 months" not in seen
    assert "2 months" in seen or "2\n" in seen or "2 " in seen
    assert db.query(KbNodeSource).filter_by(node_id=edited.id).one().stale is True


@pytest.mark.parametrize("field,value", [("fact_unit", "weeks"), ("scope_text", "contractors")])
def test_every_claim_field_marks_the_sources_stale(db, world, field, value):
    edited = stated_fact(world, "Probation length policy", "Probation applies widely.", "6", "months",
                         world.document("Handbook", "public"), "Probation lasts 6 months CANARY6.")
    review.apply_decisions(db, world.company_id, world.hr_id, [decision(node_id=edited.id, **{field: value})])
    db.commit()
    assert db.query(KbNodeSource).filter_by(node_id=edited.id).one().stale is True


def test_a_wording_edit_keeps_the_chunk(db, world):
    edited = stated_fact(world, "Probation length policy", "Probation is 6 months.", "6", "months",
                         world.document("Handbook", "public"), "Probation lasts 6 months CANARY6.")
    review.apply_decisions(db, world.company_id, world.hr_id, [decision(node_id=edited.id, body="Six months it is, 6.")])
    db.commit()
    assert db.query(KbNodeSource).filter_by(node_id=edited.id).one().stale is False
    assert "CANARY6" in candidate_sees(db, world.company_id, "What is the probation length policy?")


def test_a_non_fact_with_no_claim_is_not_marked_stale(db, world):
    edited = world.node("A plain note", "Words.", "public", type="policy", document=world.document("Handbook", "public"))
    review.apply_decisions(db, world.company_id, world.hr_id, [decision(node_id=edited.id, body="Other words.")])
    db.commit()
    assert db.query(KbNodeSource).filter_by(node_id=edited.id).one().stale is False


@pytest.mark.parametrize("kind", ["candidate", "employee", "manager", "hr"])
def test_a_stale_link_withholds_the_chunk_from_every_audience(db, world, kind):
    node = world.node("Probation length policy", "Probation is 6 months.", "public",
                      document=world.document("Handbook", "public"), chunk_text="Probation lasts 6 months CANARY6.")
    db.query(KbNodeSource).filter_by(node_id=node.id).update({"stale": True})
    db.commit()
    bundle = retriever.search(db, aud.Audience(world.company_id, kind), "What is the probation length policy?",
                              top_k=100, char_budget=10 ** 6)
    assert not any("CANARY6" in item.text for item in bundle.items)


def test_a_body_edited_with_the_value_is_kept_as_written(db, world):
    edited = stated_fact(world, "Probation length policy", "Probation is 6 months.", "6", "months",
                         world.document("Handbook", "public"), "Probation lasts 6 months CANARY6.")
    review.apply_decisions(db, world.company_id, world.hr_id,
                           [decision(node_id=edited.id, fact_value="2", body="Probation is 2 months now.")])
    db.commit()
    db.refresh(edited)
    assert edited.body == "Probation is 2 months now."


def test_a_body_that_does_not_state_the_old_claim_survives_the_edit(db, world):
    edited = stated_fact(world, "Probation length policy", "Probation follows the handbook.", "6", "months",
                         world.document("Handbook", "public"), "Probation lasts 6 months CANARY6.")
    review.apply_decisions(db, world.company_id, world.hr_id, [decision(node_id=edited.id, fact_value="2")])
    db.commit()
    db.refresh(edited)
    assert edited.body == "Probation follows the handbook."


def test_the_conflict_check_is_not_shown_the_old_quote_of_an_edited_fact(db, world):
    edited = stated_fact(world, "Probation length policy", "", "6", "months",
                         world.document("Handbook", "public"), "Probation lasts 6 months CANARY6.")
    db.query(KbNodeSource).filter_by(node_id=edited.id).update({"stale": True, "quote": "lasts 6 months QUOTECANARY"})
    db.commit()
    assert "QUOTECANARY" not in contradiction._fact_block(db, edited)


def test_merging_a_stale_link_onto_the_same_chunk_keeps_it_stale(db, world):
    document = world.document("Handbook", "public")
    stale = world.node("Leave days", "Words.", "public", status="draft", document=document, chunk_text="Leave CANARY.")
    link = db.query(KbNodeSource).filter_by(node_id=stale.id).one()
    target = world.node("Leave days total", "Words.", "public")
    db.add(KbNodeSource(node_id=target.id, chunk_id=link.chunk_id, quote=link.quote))
    link.stale = True
    db.commit()
    review.apply_decisions(db, world.company_id, world.hr_id,
                           [decision(action="merge", node_id=stale.id, into_node_id=target.id)])
    db.commit()
    assert db.query(KbNodeSource).filter_by(node_id=target.id).one().stale is True


# F2: a merge moves a chunk that says another value onto this fact.


def merge_world(world, value, target_value, target_kind="number"):
    document = world.document("Handbook", "public")
    moved = stated_fact(world, "Leave days total", "Words.", value, "days", document, "Leave is CANARYMOVED days a year.")
    moved.status = "draft"
    target = stated_fact(world, "Annual leave days", "Annual leave.", target_value, "days",
                         world.document("Policy", "public"), "Annual leave days are set here.")
    target.fact_kind = target_kind
    world.db.commit()
    return moved, target


def merge(world, moved, target):
    review.apply_decisions(world.db, world.company_id, world.hr_id,
                           [decision(action="merge", node_id=moved.id, into_node_id=target.id)])
    world.db.commit()


def moved_links(db, target):
    return {row.quote: row.stale for row in db.query(KbNodeSource).filter_by(node_id=target.id).all()}


def test_merging_into_another_value_marks_the_moved_source_stale_and_keeps_its_chunk_out(db, world):
    moved, target = merge_world(world, "19", "17")
    links_before = db.query(KbNodeSource).filter_by(node_id=target.id).count()
    merge(world, moved, target)
    rows = db.query(KbNodeSource).filter_by(node_id=target.id).order_by(KbNodeSource.id).all()
    assert len(rows) == links_before + 1
    assert sorted(row.stale for row in rows) == [False, True]
    assert "CANARYMOVED" not in candidate_sees(db, world.company_id, "How many leave days total a year?")


def test_merging_into_the_same_value_keeps_the_chunk(db, world):
    moved, target = merge_world(world, "17", "17")
    merge(world, moved, target)
    assert not any(row.stale for row in db.query(KbNodeSource).filter_by(node_id=target.id))
    assert "CANARYMOVED" in candidate_sees(db, world.company_id, "How many leave days total a year?")


def test_merging_a_non_fact_marks_nothing_stale(db, world):
    document = world.document("Handbook", "public")
    moved = world.node("Words one", "Words.", "public", type="policy", status="draft", document=document)
    target = world.node("Words two", "Words.", "public", type="policy", document=document)
    merge(world, moved, target)
    assert not any(row.stale for row in db.query(KbNodeSource).filter_by(node_id=target.id))


# F6: HR is told when a body is cleared, and an unchanged body sent back counts as untouched.


def test_a_body_sent_back_unchanged_is_still_cleared_when_it_states_the_old_value(db, world):
    edited = stated_fact(world, "Probation length policy", "Probation is 6 months.", "6", "months",
                         world.document("Handbook", "public"), "Probation lasts 6 months CANARY6.")
    review.apply_decisions(db, world.company_id, world.hr_id,
                           [decision(node_id=edited.id, fact_value="2", body="Probation is 6 months.")])
    db.commit()
    db.refresh(edited)
    assert edited.body == ""
