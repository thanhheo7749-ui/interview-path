from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest

from app.ai import gateway
from app.ai.config import get_config
from app.brain import audience as aud
from app.brain import retriever, vectors
from app.cli import main
from app.database.sql_models import (
    Company,
    Department,
    KbChunk,
    KbConflict,
    KbDocument,
    KbEdge,
    KbNode,
    KbNodeSource,
)

CANARY = "CANARY-SALARY-BAND-9931"
CHUNK_CANARY = "CANARY-SALARY-CHUNK-7741"
NOT_SHARED = retriever.Citation("Company document (not shared)", None, None, False)


@pytest.fixture(autouse=True)
def _empty_vector_cache():
    # Each test rebuilds the database, so ids and kb_version repeat between tests.
    retriever.clear_vector_cache()
    yield
    retriever.clear_vector_cache()


class Builder:
    def __init__(self, db, company_id):
        self.db = db
        self.company_id = company_id

    def _vector_fields(self, text):
        result = gateway.embed([text], "document", "test_setup", self.company_id)
        return {"embedding": vectors.encode(result.vectors[0]), "embedding_model": result.model,
                "embedding_dim": result.dimension}

    def node(self, title, body="", type="fact", visibility="public", status="published", department_id=None,
             company_id=None, embedded=True):
        company_id = company_id or self.company_id
        fields = self._vector_fields(f"{title}\n{body}") if embedded else {}
        row = KbNode(company_id=company_id, department_id=department_id, type=type, title=title, body=body,
                     language="en", visibility=visibility, status=status, **fields)
        self.db.add(row)
        self.db.commit()
        return row

    def document(self, title, visibility="internal", status="published", department_id=None, company_id=None,
                 effective_date=None):
        row = KbDocument(company_id=company_id or self.company_id, department_id=department_id, title=title,
                         language="en", visibility=visibility, status=status, effective_date=effective_date)
        self.db.add(row)
        self.db.commit()
        return row

    def chunk(self, document, text, page=None, position=0):
        row = KbChunk(company_id=document.company_id, document_id=document.id, position=position, page=page,
                      text=text, **self._vector_fields(text))
        self.db.add(row)
        self.db.commit()
        return row

    def edge(self, source, target, relation, must_have=None, status="published", company_id=None):
        row = KbEdge(company_id=company_id or self.company_id, source_node_id=source.id, target_node_id=target.id,
                     relation=relation, must_have=must_have, status=status)
        self.db.add(row)
        self.db.commit()
        return row

    def source(self, node, chunk, quote="quote"):
        row = KbNodeSource(node_id=node.id, chunk_id=chunk.id, quote=quote)
        self.db.add(row)
        self.db.commit()
        return row


@pytest.fixture
def world(db):
    company = Company(slug="acme", name="Acme")
    other = Company(slug="other", name="Other")
    db.add_all([company, other])
    db.commit()
    eng = Department(company_id=company.id, name="Engineering")
    sales = Department(company_id=company.id, name="Sales")
    db.add_all([eng, sales])
    db.commit()
    backend = Department(company_id=company.id, parent_id=eng.id, name="Backend")
    db.add(backend)
    db.commit()

    b = Builder(db, company.id)

    company_node = b.node("Acme", type="company")
    department_node = b.node("Engineering", type="department", department_id=eng.id)
    b.edge(department_node, company_node, "part_of")

    role = b.node("Backend Developer", "Backend Developer role", type="role")
    b.edge(department_node, role, "has_role")
    python = b.node("Python experience", "Writes Python daily", type="requirement")
    docker = b.node("Docker", "Builds containers", type="skill")
    b.edge(role, docker, "requires", must_have=False)
    b.edge(role, python, "requires", must_have=True)

    value = b.node("Speak up early", "Tell the team about risks", type="value")
    behavior = b.node("Raises risks in standup", "Says it out loud", type="behavior")
    b.edge(department_node, value, "holds")
    b.edge(value, behavior, "shown_by")
    b.edge(role, behavior, "expects")

    company_value = b.node("Company value", "Held by the whole company", type="value", visibility="internal")
    b.edge(company_node, company_value, "holds")

    note = b.node("Pay note", f"salary band {CANARY}", type="private_note", visibility="confidential",
                  department_id=eng.id)
    b.edge(role, note, "has_note")

    internal_role = b.node("Internal Only Role", "Not advertised", type="role", visibility="internal")

    handbook = b.document("Internal Handbook", effective_date=date(2026, 1, 15))
    handbook_chunk = b.chunk(handbook, "Speak up early when a risk appears at work.", page=3)
    b.source(value, handbook_chunk)

    pay_document = b.document("Pay Bands", visibility="confidential", department_id=sales.id)
    pay_chunk = b.chunk(pay_document, f"salary band table {CHUNK_CANARY}", page=9)

    draft = b.node("Draft thing", "draft unreviewed DRAFT-TEXT", status="draft")
    b.edge(role, draft, "requires")
    review_document = b.document("Review Doc", visibility="public", status="review")
    b.chunk(review_document, "draft unreviewed REVIEW-DOC-TEXT")
    b.node("Old thing", "draft unreviewed SUPERSEDED-TEXT", status="superseded")
    rejected = b.node("Rejected thing", "draft unreviewed REJECTED-TEXT", status="rejected")

    other_b = Builder(db, other.id)
    other_node = other_b.node("Elsewhere", "only in the other company OTHER-COMPANY-ONLY")
    other_document = other_b.document("Other Handbook", visibility="public", effective_date=date(2020, 2, 2))
    other_chunk = other_b.chunk(other_document, "only in the other company OTHER-COMPANY-ONLY chunk")
    b.edge(role, other_node, "requires")

    leave_a = b.node("Annual leave days", "Annual leave is 12 days", visibility="internal")
    leave_b = b.node("Annual leave allowance", "Annual leave is 15 days", visibility="internal")
    db.add(KbConflict(company_id=company.id, node_a_id=leave_a.id, node_b_id=leave_b.id, status="open"))
    db.commit()

    b.node("연차 휴가", "연차 휴가는 15일입니다", visibility="internal", type="policy")
    b.node("Chính sách nghỉ phép", "Nhân viên được nghỉ phép 12 ngày", visibility="internal", type="policy")
    b.node("Travel policy", "policy " * 60, visibility="internal", type="policy")
    b.node("Expense policy", "policy " * 60, visibility="internal", type="policy")

    return SimpleNamespace(
        b=b,
        company_id=company.id,
        other_company_id=other.id,
        eng_id=eng.id,
        sales_id=sales.id,
        backend_id=backend.id,
        hr_audience=aud.Audience(company.id, "hr"),
        employee_audience=aud.Audience(company.id, "employee"),
        role_id=role.id,
        role=role,
        internal_role_id=internal_role.id,
        note_id=note.id,
        python=python,
        draft=draft,
        rejected=rejected,
        department_node=department_node,
        company_node=company_node,
        value=value,
        handbook=handbook,
        handbook_chunk=handbook_chunk,
        pay_document=pay_document,
        pay_chunk=pay_chunk,
        other_node=other_node,
        other_chunk=other_chunk,
        conflicted_ref=f"n{leave_a.id}",
    )


def joined(bundle):
    return " ".join(item.text for item in bundle.items)


# Permission filtering


def test_candidate_search_never_returns_confidential_text(db, world):
    bundle = retriever.search(db, aud.candidate(world.company_id), "salary band")
    assert CANARY not in " ".join(item.text for item in bundle.items)


def test_hr_search_finds_confidential_text(db, world):
    bundle = retriever.search(db, world.hr_audience, "salary band")
    assert CANARY in " ".join(item.text for item in bundle.items)


def test_search_never_crosses_companies(db, world):
    bundle = retriever.search(db, world.hr_audience, "only in the other company")
    assert "OTHER-COMPANY-ONLY" not in " ".join(item.text for item in bundle.items)


def test_draft_nodes_and_unpublished_document_chunks_are_never_returned(db, world):
    bundle = retriever.search(db, world.hr_audience, "draft unreviewed")
    assert "DRAFT-TEXT" not in " ".join(item.text for item in bundle.items)
    assert "REVIEW-DOC-TEXT" not in " ".join(item.text for item in bundle.items)


def test_superseded_and_rejected_nodes_are_never_returned(db, world):
    text = joined(retriever.search(db, world.hr_audience, "draft unreviewed", top_k=50, char_budget=100000))
    assert "SUPERSEDED-TEXT" not in text
    assert "REJECTED-TEXT" not in text


def test_employee_gets_internal_but_no_confidential_nodes_or_chunks(db, world):
    text = joined(retriever.search(db, world.employee_audience, "salary band annual leave", top_k=50, char_budget=100000))
    assert "Annual leave" in text
    assert CANARY not in text
    assert CHUNK_CANARY not in text


def test_candidate_gets_no_internal_chunks_or_nodes(db, world):
    text = joined(retriever.search(db, aud.candidate(world.company_id), "annual leave speak up risk", top_k=50, char_budget=100000))
    assert "Annual leave" not in text
    assert "risk appears at work" not in text


def test_manager_reads_confidential_only_inside_their_subtree(db, world):
    eng_manager = aud.simulated(db, world.company_id, "manager", world.eng_id)
    sales_manager = aud.simulated(db, world.company_id, "manager", world.sales_id)
    query = "salary band"

    eng_text = joined(retriever.search(db, eng_manager, query, top_k=50, char_budget=100000))
    sales_text = joined(retriever.search(db, sales_manager, query, top_k=50, char_budget=100000))

    assert CANARY in eng_text and CHUNK_CANARY not in eng_text
    assert CHUNK_CANARY in sales_text and CANARY not in sales_text


def test_manager_without_a_department_gets_no_confidential_text(db, world):
    text = joined(retriever.search(db, aud.Audience(world.company_id, "manager"), "salary band", top_k=50, char_budget=100000))
    assert CANARY not in text
    assert CHUNK_CANARY not in text


def test_a_chunk_whose_row_names_another_company_is_not_returned(db, world):
    hostile = world.b.document("Acme doc", visibility="public")
    row = world.b.chunk(hostile, "misfiled MISFILED-CHUNK-TEXT")
    row.company_id = world.other_company_id
    db.commit()
    assert "MISFILED-CHUNK-TEXT" not in joined(retriever.search(db, world.hr_audience, "misfiled"))


# The cache


def test_a_wider_audience_filling_the_cache_does_not_widen_a_narrower_one(db, world):
    candidate = aud.candidate(world.company_id)
    assert CANARY in joined(retriever.search(db, world.hr_audience, "salary band", top_k=50, char_budget=100000))
    text = joined(retriever.search(db, candidate, "salary band", top_k=50, char_budget=100000))
    assert CANARY not in text
    assert CHUNK_CANARY not in text


def test_a_narrower_audience_filling_the_cache_does_not_narrow_a_wider_one(db, world):
    retriever.search(db, aud.candidate(world.company_id), "salary band")
    assert CANARY in joined(retriever.search(db, world.hr_audience, "salary band"))


def test_a_cached_vector_for_a_hidden_row_is_never_selected(db, world):
    model = get_config().slot("embedding").model
    version = db.get(Company, world.company_id).kb_version
    query_vector = np.asarray(gateway.embed(["salary band"], "query", "test_setup", world.company_id).vectors[0], dtype="<f4")
    retriever._vector_cache[(world.company_id, model, version, "node")] = {world.note_id: query_vector}
    retriever._vector_cache[(world.company_id, model, version, "chunk")] = {world.pay_chunk.id: query_vector}

    text = joined(retriever.search(db, aud.candidate(world.company_id), "salary band", top_k=50, char_budget=100000))

    assert CANARY not in text
    assert CHUNK_CANARY not in text


def test_the_cache_holds_only_id_to_vector_and_no_text(db, world):
    retriever.search(db, world.hr_audience, "salary band")
    assert {key[3] for key in retriever._vector_cache} == {"node", "chunk"}
    for key, entries in retriever._vector_cache.items():
        assert key[:2] == (world.company_id, get_config().slot("embedding").model)
        assert entries
        for row_id, vector in entries.items():
            assert isinstance(row_id, int)
            assert isinstance(vector, np.ndarray)
            assert vector.dtype.kind == "f"


def test_nodes_and_chunks_with_the_same_id_do_not_share_a_cached_vector(db, world):
    # Ids of the two tables overlap in this world, so a shared map would give a chunk a node's vector.
    assert world.handbook_chunk.id == 1 and db.get(KbNode, 1) is not None
    retriever.search(db, world.hr_audience, "risk")
    model = get_config().slot("embedding").model
    version = db.get(Company, world.company_id).kb_version
    node_vector = retriever._vector_cache[(world.company_id, model, version, "node")][1]
    chunk_vector = retriever._vector_cache[(world.company_id, model, version, "chunk")][1]
    assert node_vector.tobytes() != chunk_vector.tobytes()


def test_a_version_change_drops_that_companys_older_cache_entries_only(db, world):
    retriever.search(db, world.hr_audience, "policy")
    retriever.search(db, aud.Audience(world.other_company_id, "hr"), "other")
    old_version = db.get(Company, world.company_id).kb_version
    db.get(Company, world.company_id).kb_version = old_version + 1
    db.commit()

    retriever.search(db, world.hr_audience, "policy")

    versions = {key[2] for key in retriever._vector_cache if key[0] == world.company_id}
    assert versions == {old_version + 1}
    assert any(key[0] == world.other_company_id for key in retriever._vector_cache)


def test_a_new_kb_version_reads_new_vectors(db, world):
    candidate = aud.candidate(world.company_id)
    retriever.search(db, candidate, "completely new wording")
    role = db.get(KbNode, world.role_id)
    new_vector = gateway.embed(["completely new wording"], "document", "test_setup", world.company_id).vectors[0]
    role.embedding = vectors.encode(new_vector)
    db.get(Company, world.company_id).kb_version += 1
    db.commit()

    bundle = retriever.search(db, candidate, "completely new wording", top_k=1)

    assert bundle.items[0].ref == f"n{world.role_id}"


# Citations


def test_public_node_from_an_internal_document_hides_its_source_from_candidates(db, world):
    item = next(i for i in retriever.search(db, aud.candidate(world.company_id), "speak up early").items if i.ref.startswith("n"))
    assert item.citations == (retriever.Citation("Company document (not shared)", None, None, False),)


def test_the_same_node_shows_its_source_to_employees(db, world):
    item = next(i for i in retriever.search(db, world.employee_audience, "speak up early").items if i.ref.startswith("n"))
    assert item.citations[0].title == "Internal Handbook"
    assert item.citations[0].shared is True


def test_a_shared_citation_carries_page_and_effective_date(db, world):
    item = _item(retriever.search(db, world.employee_audience, "speak up early"), f"n{world.value.id}")
    assert item.citations == (retriever.Citation("Internal Handbook", 3, date(2026, 1, 15), True),)


def test_a_chunk_cites_its_own_document(db, world):
    bundle = retriever.search(db, world.employee_audience, "speak up early")
    item = _item(bundle, f"c{world.handbook_chunk.id}")
    assert item.kind == "chunk"
    assert item.node_type is None
    assert item.citations == (retriever.Citation("Internal Handbook", 3, date(2026, 1, 15), True),)


def test_a_node_without_sources_has_no_citations(db, world):
    item = _item(retriever.search(db, aud.candidate(world.company_id), "backend developer role"), f"n{world.role_id}")
    assert item.kind == "node"
    assert item.node_type == "role"
    assert item.citations == ()


def test_a_source_in_an_unpublished_document_still_cites_when_its_layer_allows(db, world):
    # document_filter requires status == published, so reusing it here would hide this source.
    retired = world.b.document("Retired Handbook", status="superseded", effective_date=date(2024, 5, 1))
    chunk = world.b.chunk(retired, "Retired wording", page=2)
    node = world.b.node("Quiet rule", "quiet rule text", visibility="internal")
    world.b.source(node, chunk)

    item = _item(retriever.search(db, world.employee_audience, "quiet rule"), f"n{node.id}")

    assert item.citations == (retriever.Citation("Retired Handbook", 2, date(2024, 5, 1), True),)
    assert "Retired wording" not in joined(retriever.search(db, world.employee_audience, "retired wording", top_k=50, char_budget=100000))


def test_an_unpublished_document_above_the_audience_layer_stays_hidden(db, world):
    # Ignoring status must not also mean ignoring the layer.
    retired = world.b.document("Retired Secret Plan", visibility="confidential", status="superseded")
    chunk = world.b.chunk(retired, "Retired wording", page=2)
    node = world.b.node("Quiet rule", "quiet rule text", visibility="internal")
    world.b.source(node, chunk)

    item = _item(retriever.search(db, world.employee_audience, "quiet rule"), f"n{node.id}")

    assert item.citations == (NOT_SHARED,)


def test_a_manager_sees_a_confidential_source_only_inside_their_subtree(db, world):
    node = world.b.node("Quiet rule", "quiet rule text", visibility="internal")
    world.b.source(node, world.pay_chunk)
    sales = aud.simulated(db, world.company_id, "manager", world.sales_id)
    eng = aud.simulated(db, world.company_id, "manager", world.eng_id)

    assert _item(retriever.search(db, sales, "quiet rule"), f"n{node.id}").citations[0].title == "Pay Bands"
    assert _item(retriever.search(db, eng, "quiet rule"), f"n{node.id}").citations == (NOT_SHARED,)


def test_a_source_in_another_companys_document_never_shows_its_title(db, world):
    node = world.b.node("Quiet rule", "quiet rule text")
    world.b.source(node, world.other_chunk)

    item = _item(retriever.search(db, world.hr_audience, "quiet rule"), f"n{node.id}")

    assert item.citations == (NOT_SHARED,)


def test_hidden_sources_collapse_to_one_citation_and_shared_ones_remain(db, world):
    second_secret = world.b.document("Second Secret", visibility="confidential")
    open_document = world.b.document("Open Guide", visibility="public")
    node = world.b.node("Quiet rule", "quiet rule text")
    world.b.source(node, world.pay_chunk)
    world.b.source(node, world.b.chunk(second_secret, "secret words", page=1))
    world.b.source(node, world.b.chunk(open_document, "guide words", page=4))
    world.b.source(node, world.b.chunk(open_document, "guide words again", page=4, position=1))

    item = _item(retriever.search(db, aud.candidate(world.company_id), "quiet rule"), f"n{node.id}")

    assert set(item.citations) == {NOT_SHARED, retriever.Citation("Open Guide", 4, None, True)}
    assert len(item.citations) == 2


def _item(bundle, ref):
    return next(item for item in bundle.items if item.ref == ref)


# Expansion


def test_edge_expansion_does_not_cross_into_invisible_nodes(db, world):
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role")
    assert CANARY not in " ".join(item.text for item in bundle.items)
    assert any("Backend Developer" in item.text for item in bundle.items)


def test_expansion_adds_a_visible_neighbour(db, world):
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role")
    assert any("Python experience" in item.text for item in bundle.items)


def test_expansion_reaches_neighbours_outside_top_k_with_decayed_scores(db, world):
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role", top_k=1)
    seed = bundle.items[0]
    assert seed.ref == f"n{world.role_id}"
    assert _item(bundle, f"n{world.python.id}").score == pytest.approx(seed.score * 0.5)
    assert _item(bundle, f"n{world.company_node.id}").score == pytest.approx(seed.score * 0.25)


def test_expansion_stops_after_two_hops(db, world):
    far = world.b.node("Far away", "three hops out")
    world.b.edge(far, world.company_node, "applies_to")
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role", top_k=1, char_budget=100000)
    assert f"n{far.id}" not in {item.ref for item in bundle.items}


def test_expansion_crosses_no_invisible_node_even_as_a_stepping_stone(db, world):
    hidden_hop = world.b.node("Hidden hop", "secret middle", visibility="confidential")
    beyond = world.b.node("Beyond the hop", "reachable only through a secret")
    world.b.edge(world.role, hidden_hop, "applies_to")
    world.b.edge(hidden_hop, beyond, "applies_to")

    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role", top_k=1, char_budget=100000)

    assert f"n{beyond.id}" not in {item.ref for item in bundle.items}


def test_expansion_ignores_edges_that_are_not_published(db, world):
    neighbour = world.b.node("Pending neighbour", "linked by a draft edge")
    world.b.edge(world.role, neighbour, "applies_to", status="draft")
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role", top_k=1, char_budget=100000)
    assert f"n{neighbour.id}" not in {item.ref for item in bundle.items}


def test_expansion_does_not_reach_draft_rejected_or_foreign_nodes(db, world):
    world.b.edge(world.role, world.rejected, "applies_to")
    refs = {item.ref for item in retriever.search(db, world.hr_audience, "backend developer role", top_k=1, char_budget=100000).items}
    assert f"n{world.draft.id}" not in refs
    assert f"n{world.rejected.id}" not in refs
    assert f"n{world.other_node.id}" not in refs


# Vectors and models


def test_vectors_from_another_model_are_refused_with_a_clear_error(db, world):
    db.query(KbNode).update({KbNode.embedding_model: "old-model"})
    db.query(KbChunk).update({KbChunk.embedding_model: "old-model"})
    db.commit()
    with pytest.raises(retriever.NoEmbeddingsError, match="make reembed"):
        retriever.search(db, world.hr_audience, "anything")


def test_rows_of_another_model_are_not_compared_when_others_match(db, world):
    db.query(KbNode).filter(KbNode.id == world.role_id).update({KbNode.embedding_model: "old-model"})
    db.commit()
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role", top_k=50, char_budget=100000)
    model = get_config().slot("embedding").model
    version = db.get(Company, world.company_id).kb_version
    assert world.role_id not in retriever._vector_cache[(world.company_id, model, version, "node")]
    # The role has no comparable vector, so it can arrive only as a neighbour with a decayed score.
    assert bundle.items[0].ref != f"n{world.role_id}"


def test_rows_that_were_never_embedded_ask_the_operator_to_reembed(db):
    company = Company(slug="fresh", name="Fresh")
    db.add(company)
    db.commit()
    Builder(db, company.id).node("Fresh", type="company", embedded=False)
    with pytest.raises(retriever.NoEmbeddingsError, match="make reembed"):
        retriever.search(db, aud.Audience(company.id, "hr"), "anything")


def test_an_unembedded_node_is_still_reachable_as_a_neighbour(db, world):
    plain = world.b.node("Plain neighbour", "no vector here", embedded=False)
    world.b.edge(world.role, plain, "applies_to")
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role", top_k=1, char_budget=100000)
    assert f"n{plain.id}" in {item.ref for item in bundle.items}


def test_vectors_of_another_dimension_are_refused(db, world):
    db.query(KbNode).update({KbNode.embedding: vectors.encode([1.0, 0.0, 0.0])})
    db.query(KbChunk).update({KbChunk.embedding: vectors.encode([1.0, 0.0, 0.0])})
    db.commit()
    with pytest.raises(retriever.NoEmbeddingsError, match="make reembed"):
        retriever.search(db, world.hr_audience, "anything")


def test_a_company_with_no_rows_returns_an_empty_bundle(db):
    company = Company(slug="empty", name="Empty")
    db.add(company)
    db.commit()
    assert retriever.search(db, aud.Audience(company.id, "hr"), "anything") == retriever.ContextBundle((), 0.0, frozenset())


def test_a_candidate_with_nothing_visible_gets_an_empty_bundle_not_an_error(db, world):
    db.query(KbNode).filter(KbNode.company_id == world.company_id).update({KbNode.visibility: "internal"})
    db.query(KbDocument).filter(KbDocument.company_id == world.company_id).update({KbDocument.visibility: "internal"})
    db.commit()
    assert retriever.search(db, aud.candidate(world.company_id), "anything").items == ()


def test_the_query_is_embedded_as_a_query_for_the_company(db, world, monkeypatch):
    calls = []
    real = gateway.embed

    def spy(texts, kind, feature, company_id=None):
        calls.append((texts, kind, feature, company_id))
        return real(texts, kind, feature, company_id)

    monkeypatch.setattr(gateway, "embed", spy)
    retriever.search(db, world.hr_audience, "policy")
    assert calls == [(["policy"], "query", "kb_query_embed", world.company_id)]


def test_a_supplied_query_vector_skips_the_embed_call(db, world, monkeypatch):
    query_vector = gateway.embed(["backend developer role"], "query", "test_setup", world.company_id).vectors[0]

    def refuse(*args, **kwargs):
        raise AssertionError("search must not embed when given a vector")

    monkeypatch.setattr(gateway, "embed", refuse)
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role", query_vector=query_vector)
    assert bundle.items[0].ref == f"n{world.role_id}"


# Scoring and assembly


def test_weights_are_the_specified_constants():
    assert retriever.VECTOR_WEIGHT == 0.7
    assert retriever.KEYWORD_WEIGHT == 0.3


def test_keyword_search_works_for_korean_and_vietnamese(db, world):
    assert any("연차 휴가" in i.text for i in retriever.search(db, world.hr_audience, "연차 휴가 일수").items)
    assert any("nghỉ phép" in i.text for i in retriever.search(db, world.hr_audience, "nghỉ phép").items)


def test_character_budget_is_respected(db, world):
    bundle = retriever.search(db, world.hr_audience, "policy", char_budget=100)
    assert sum(len(item.text) for item in bundle.items) <= 100 or len(bundle.items) == 1


def test_the_first_item_is_kept_and_truncated_to_the_budget(db, world):
    bundle = retriever.search(db, world.hr_audience, "travel policy", char_budget=20)
    assert len(bundle.items) == 1
    assert len(bundle.items[0].text) == 20


def test_items_are_sorted_and_best_score_is_the_top_score(db, world):
    bundle = retriever.search(db, world.hr_audience, "annual leave days", char_budget=100000)
    scores = [item.score for item in bundle.items]
    assert scores == sorted(scores, reverse=True)
    assert bundle.best_score == scores[0]
    assert all(isinstance(score, float) for score in scores)


def test_open_conflict_is_flagged_and_resolved_conflict_is_not(db, world):
    bundle = retriever.search(db, world.hr_audience, "annual leave days")
    assert world.conflicted_ref in bundle.conflicted_refs
    db.query(KbConflict).update({KbConflict.status: "resolved"})
    db.commit()
    assert retriever.search(db, world.hr_audience, "annual leave days").conflicted_refs == frozenset()


def test_conflicted_refs_name_only_nodes_in_the_bundle(db, world):
    bundle = retriever.search(db, aud.candidate(world.company_id), "backend developer role")
    assert bundle.conflicted_refs == frozenset()

    bundle = retriever.search(db, world.hr_audience, "annual leave days", char_budget=1)
    assert len(bundle.items) == 1
    assert bundle.conflicted_refs <= {bundle.items[0].ref}


# Role profile


def test_role_profile_walks_the_graph(db, world):
    profile = retriever.role_profile(db, aud.candidate(world.company_id), world.role_id)
    assert profile.title == "Backend Developer"
    assert [(r.title, r.must_have) for r in profile.requirements] == [("Python experience", True), ("Docker", False)]
    assert {v.title for v in profile.values} == {"Speak up early"}
    assert {b.title for b in profile.behaviors} == {"Raises risks in standup"}


def test_role_profile_excludes_confidential_notes_for_candidates(db, world):
    profile = retriever.role_profile(db, aud.candidate(world.company_id), world.role_id)
    assert CANARY not in str(profile)


def test_role_profile_for_an_invisible_role_is_none(db, world):
    assert retriever.role_profile(db, aud.candidate(world.company_id), world.internal_role_id) is None


def test_role_profile_includes_values_held_by_the_company(db, world):
    profile = retriever.role_profile(db, world.hr_audience, world.role_id)
    assert "Company value" in {v.title for v in profile.values}


def test_role_profile_is_none_for_absent_foreign_or_non_role_nodes(db, world):
    assert retriever.role_profile(db, world.hr_audience, 999999) is None
    assert retriever.role_profile(db, world.hr_audience, world.other_node.id) is None
    assert retriever.role_profile(db, world.hr_audience, world.python.id) is None


def test_role_profile_keeps_fields_for_later_blocks(db, world):
    profile = retriever.role_profile(db, world.hr_audience, world.role_id)
    assert profile.role_node_id == world.role_id
    assert profile.body == "Backend Developer role"
    assert profile.department_id is None
    python = profile.requirements[0]
    assert python == retriever.RoleRequirement(world.python.id, "requirement", "Python experience",
                                               "Writes Python daily", True, "public")
    assert profile.requirements[1].type == "skill"
    item = next(v for v in profile.values if v.title == "Speak up early")
    assert item == retriever.ProfileItem(world.value.id, "value", "Speak up early", "Tell the team about risks")


def test_role_profile_hides_a_confidential_requirement_from_candidates(db, world):
    secret = world.b.node("Secret dealbreaker", "SECRET-REQUIREMENT", type="requirement", visibility="confidential")
    world.b.edge(world.role, secret, "requires", must_have=True)

    candidate_profile = retriever.role_profile(db, aud.candidate(world.company_id), world.role_id)
    hr_profile = retriever.role_profile(db, world.hr_audience, world.role_id)

    assert "SECRET-REQUIREMENT" not in str(candidate_profile)
    assert "Secret dealbreaker" in {r.title for r in hr_profile.requirements}


def test_role_profile_ignores_draft_edges_and_draft_nodes(db, world):
    pending = world.b.node("Pending skill", "", type="skill")
    world.b.edge(world.role, pending, "requires", must_have=True, status="draft")
    titles = {r.title for r in retriever.role_profile(db, world.hr_audience, world.role_id).requirements}
    assert "Pending skill" not in titles
    assert "Draft thing" not in titles
    assert "Elsewhere" not in titles


def test_role_profile_does_not_walk_through_a_hidden_department(db, world):
    db.get(KbNode, world.department_node.id).visibility = "internal"
    db.commit()
    profile = retriever.role_profile(db, aud.candidate(world.company_id), world.role_id)
    assert {v.title for v in profile.values} == set()
    assert {b.title for b in profile.behaviors} == {"Raises risks in standup"}


def test_role_profile_survives_a_part_of_cycle(db, world):
    world.b.edge(world.company_node, world.department_node, "part_of")
    assert retriever.role_profile(db, world.hr_audience, world.role_id) is not None


def test_role_profile_needs_no_embeddings(db, world):
    db.query(KbNode).update({KbNode.embedding: None, KbNode.embedding_model: None})
    db.commit()
    assert retriever.role_profile(db, world.hr_audience, world.role_id).title == "Backend Developer"


# Visible graph


def test_visible_graph_for_a_candidate_has_only_visible_nodes_and_edges(db, world):
    nodes, edges = retriever.visible_graph(db, aud.candidate(world.company_id))
    ids = {node.id for node in nodes}

    assert world.role_id in ids
    assert world.note_id not in ids
    assert world.internal_role_id not in ids
    assert world.draft.id not in ids
    assert world.other_node.id not in ids
    assert edges
    for edge in edges:
        assert edge.source_node_id in ids and edge.target_node_id in ids
        assert edge.status == "published"
    assert world.note_id not in {edge.target_node_id for edge in edges}


def test_visible_graph_for_hr_includes_the_note_but_no_draft_or_foreign_edge(db, world):
    world.b.edge(world.role, world.python, "applies_to", status="draft")
    nodes, edges = retriever.visible_graph(db, world.hr_audience)
    ids = {node.id for node in nodes}

    assert world.note_id in ids
    assert world.note_id in {edge.target_node_id for edge in edges}
    assert world.other_node.id not in {edge.target_node_id for edge in edges}
    assert world.draft.id not in {edge.target_node_id for edge in edges}
    assert all(edge.status == "published" for edge in edges)


def test_visible_graph_excludes_an_edge_filed_under_another_company(db, world):
    edge = world.b.edge(world.role, world.python, "applies_to", company_id=world.other_company_id)
    _, edges = retriever.visible_graph(db, world.hr_audience)
    assert edge.id not in {row.id for row in edges}


# reembed


def test_reembed_makes_search_work_again_after_a_model_change(db, world):
    db.query(KbNode).update({KbNode.embedding_model: "old-model"})
    db.query(KbChunk).update({KbChunk.embedding_model: "old-model"})
    db.commit()
    with pytest.raises(retriever.NoEmbeddingsError):
        retriever.search(db, world.hr_audience, "annual leave days")

    assert main(["reembed"]) == 0

    db.expire_all()
    assert world.conflicted_ref in retriever.search(db, world.hr_audience, "annual leave days").conflicted_refs


def test_reembed_covers_chunks_and_non_rejected_nodes_and_increments_version(db, world):
    before = db.get(Company, world.company_id).kb_version
    db.query(KbNode).update({KbNode.embedding_model: "old-model"})
    db.query(KbChunk).update({KbChunk.embedding_model: "old-model"})
    db.commit()

    assert main(["reembed"]) == 0

    db.expire_all()
    model = get_config().slot("embedding").model
    assert db.get(Company, world.company_id).kb_version == before + 1
    assert {row.embedding_model for row in db.query(KbChunk).all()} == {model}
    for row in db.query(KbNode).all():
        assert row.embedding_model == ("old-model" if row.status == "rejected" else model)
    node = db.get(KbNode, world.role_id)
    assert node.embedding_dim == get_config().slot("embedding").dim
    expected = gateway.embed([f"{node.title}\n{node.body}"], "document", "test_setup", world.company_id).vectors[0]
    assert node.embedding == vectors.encode(expected)


def test_reembed_can_be_limited_to_one_company(db, world):
    db.query(KbNode).update({KbNode.embedding_model: "old-model"})
    db.commit()
    before_other = db.get(Company, world.other_company_id).kb_version

    assert main(["reembed", "--company", "acme"]) == 0

    db.expire_all()
    assert db.get(KbNode, world.role_id).embedding_model == get_config().slot("embedding").model
    assert db.get(KbNode, world.other_node.id).embedding_model == "old-model"
    assert db.get(Company, world.other_company_id).kb_version == before_other


def test_reembed_rejects_an_unknown_company(db, world, capsys):
    assert main(["reembed", "--company", "nope"]) != 0
    assert "nope" in capsys.readouterr().err


def test_reembed_sends_batches_of_64_as_documents(db, world, monkeypatch):
    for index in range(70):
        world.b.node(f"Extra {index}", "body", embedded=False)
    calls = []
    real = gateway.embed

    def spy(texts, kind, feature, company_id=None):
        calls.append((len(texts), kind))
        return real(texts, kind, feature, company_id)

    monkeypatch.setattr(gateway, "embed", spy)
    assert main(["reembed", "--company", "acme"]) == 0
    assert calls
    assert max(size for size, _ in calls) == 64
    assert {kind for _, kind in calls} == {"document"}


def test_a_failed_reembed_changes_nothing(db, world, monkeypatch):
    before = db.get(Company, world.company_id).kb_version
    db.query(KbNode).update({KbNode.embedding_model: "old-model"})
    db.commit()
    real = gateway.embed
    seen = []

    def fail_second(texts, kind, feature, company_id=None):
        seen.append(1)
        if len(seen) > 1:
            raise RuntimeError("provider down")
        return real(texts, kind, feature, company_id)

    monkeypatch.setattr(gateway, "embed", fail_second)
    with pytest.raises(RuntimeError):
        main(["reembed", "--company", "acme"])

    db.expire_all()
    assert db.get(KbNode, world.role_id).embedding_model == "old-model"
    assert db.get(Company, world.company_id).kb_version == before
