import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.ai.providers import fake
from app.ai.types import AIError
from app.brain import audience as aud
from app.brain import retriever, review, vectors
from app.database.sql_models import (
    Company, CompanyMember, Department, KbChunk, KbConflict, KbDocument, KbEdge, KbIngestionJob, KbNode, KbNodeSource,
)
from tests.helpers import auth_header, make_user

VEC = vectors.encode([1.0, 0.0, 0.0, 0.0])
OTHER_VEC = vectors.encode([0.0, 1.0, 0.0, 0.0])


class World:
    def __init__(self, db):
        self.db = db
        self.company = Company(slug="acme", name="Acme")
        self.other = Company(slug="other", name="Other")
        db.add_all([self.company, self.other])
        db.commit()
        self.hr_user = make_user(db, "hr@example.test")
        self.manager_user = make_user(db, "mgr@example.test")
        self.employee_user = make_user(db, "emp@example.test")
        for user, role in ((self.hr_user, "hr"), (self.manager_user, "manager"), (self.employee_user, "employee")):
            db.add(CompanyMember(company_id=self.company.id, user_id=user.id, role=role))
        db.commit()
        self.hr = auth_header("hr@example.test")
        self.doc = self.document("Handbook")
        self.chunk = KbChunk(company_id=self.company.id, document_id=self.doc.id, position=0, page=3, text="t")
        db.add(self.chunk)
        db.commit()

    def document(self, title, status="review", company=None):
        row = KbDocument(company_id=(company or self.company).id, title=title, language="en", visibility="internal",
                         status=status)
        self.db.add(row)
        self.db.commit()
        return row

    def node(self, title, type="fact", status="draft", visibility="internal", vec=VEC, company=None, doc=True,
             quote="quote"):
        row = KbNode(company_id=(company or self.company).id, type=type, title=title, body=f"{title} body",
                     language="en", visibility=visibility, status=status, embedding=vec,
                     embedding_model="fake", embedding_dim=4)
        self.db.add(row)
        self.db.commit()
        if doc:
            self.db.add(KbNodeSource(node_id=row.id, chunk_id=self.chunk.id, quote=quote))
            self.db.commit()
        return row

    def edge(self, a, b, relation="applies_to", status="draft"):
        row = KbEdge(company_id=self.company.id, source_node_id=a.id, target_node_id=b.id, relation=relation,
                     status=status)
        self.db.add(row)
        self.db.commit()
        return row

    def url(self, tail, company=None):
        return f"/api/companies/{(company or self.company).id}/kb/{tail}"

    def reload(self, row):
        self.db.expire_all()
        return self.db.get(type(row), row.id)


@pytest.fixture
def w(db):
    return World(db)


def decide(client, w, items, headers=None):
    return client.post(w.url("review/decide"), json={"items": items}, headers=headers or w.hr)


def version(w):
    w.db.expire_all()
    return w.db.get(Company, w.company.id).kb_version


def test_review_lists_drafts_with_sources_edges_and_merge_proposals(client, w):
    a = w.node("Annual leave", quote="12 days")
    b = w.node("Leave policy", vec=VEC, status="published")
    c = w.node("Holiday", vec=OTHER_VEC)
    w.node("Published only", type="policy", status="published")
    w.edge(a, c, "requires")
    body = client.get(w.url(f"review?document_id={w.doc.id}"), headers=w.hr).json()
    assert {n["id"] for n in body["nodes"]} == {a.id, c.id}
    first = next(n for n in body["nodes"] if n["id"] == a.id)
    assert (first["type"], first["title"], first["body"], first["visibility"]) == (
        "fact", "Annual leave", "Annual leave body", "internal")
    assert first["sources"] == [{"quote": "12 days", "page": 3, "document_title": "Handbook", "effective_date": None}]
    assert "embedding" not in first
    [edge] = body["edges"]
    assert (edge["source_title"], edge["target_title"], edge["relation"]) == ("Annual leave", "Holiday", "requires")
    [proposal] = body["merge_proposals"]
    assert proposal["node_id"] == a.id and proposal["into_node_id"] == b.id
    assert proposal["cosine"] >= 0.90 and proposal["into_title"] == "Leave policy"


def test_merge_proposal_needs_same_type_and_different_title(client, w):
    w.node("Annual leave")
    w.node("annual  LEAVE", status="published")
    w.node("Other type", type="policy", status="published")
    assert client.get(w.url("review"), headers=w.hr).json()["merge_proposals"] == []


def test_review_without_document_lists_all_company_drafts_only(client, w):
    mine = w.node("Mine")
    w.node("Theirs", company=w.other)
    ids = {n["id"] for n in client.get(w.url("review"), headers=w.hr).json()["nodes"]}
    assert ids == {mine.id}


def test_accept_publishes_stamps_and_bumps_version(client, w):
    node = w.node("Leave")
    before = version(w)
    response = decide(client, w, [{"action": "accept", "node_id": node.id}])
    assert response.status_code == 200
    node = w.reload(node)
    assert (node.status, node.approved_by) == ("published", w.hr_user.id) and node.approved_at is not None
    assert version(w) == before + 1


def test_version_bumps_once_per_request(client, w):
    nodes = [w.node("A"), w.node("B"), w.node("C")]
    before = version(w)
    decide(client, w, [{"action": "accept", "node_id": n.id} for n in nodes])
    assert version(w) == before + 1


def test_edit_then_accept_changes_fields_and_recomputes_embedding(client, w):
    node = w.node("Leave")
    old = node.embedding
    items = [{"action": "accept", "node_id": node.id, "title": "Annual leave", "body": "20 days off",
              "fact_value": "20", "fact_unit": "days", "scope_text": "everyone", "visibility": "public"}]
    assert decide(client, w, items).status_code == 200
    node = w.reload(node)
    assert (node.title, node.body, node.fact_value, node.fact_unit, node.scope_text, node.visibility) == (
        "Annual leave", "20 days off", "20", "days", "everyone", "public")
    assert node.status == "published" and node.embedding != old and node.embedding_model == "fake"


def test_reject_dismisses_open_conflicts(client, w):
    a, b = w.node("A", status="published"), w.node("B")
    conflict = KbConflict(company_id=w.company.id, node_a_id=a.id, node_b_id=b.id, status="open")
    w.db.add(conflict)
    w.db.commit()
    decide(client, w, [{"action": "reject", "node_id": b.id}])
    assert w.reload(b).status == "rejected"
    conflict = w.reload(conflict)
    assert (conflict.status, conflict.resolution) == ("dismissed", "node_rejected")


def test_layer_change_alone_keeps_draft(client, w):
    node = w.node("Leave")
    assert decide(client, w, [{"action": "edit", "node_id": node.id, "visibility": "public"}]).status_code == 200
    node = w.reload(node)
    assert (node.status, node.visibility, node.approved_at) == ("draft", "public", None)


def test_invalid_visibility_is_422(client, w):
    node = w.node("Leave")
    assert decide(client, w, [{"action": "edit", "node_id": node.id, "visibility": "secret"}]).status_code == 422


def test_bulk_with_unknown_node_changes_nothing(client, w):
    good = w.node("Good")
    foreign = w.node("Foreign", company=w.other)
    before = version(w)
    for bad in (999999, foreign.id):
        response = decide(client, w, [{"action": "accept", "node_id": good.id}, {"action": "reject", "node_id": bad}])
        assert response.status_code == 404
    assert w.reload(good).status == "draft" and version(w) == before


def test_bulk_failure_after_earlier_items_rolls_back(client, w):
    a, b = w.node("A"), w.node("B")
    published = w.node("P", status="published")
    response = decide(client, w, [
        {"action": "accept", "node_id": a.id, "title": "Renamed"},
        {"action": "accept", "node_id": published.id},
        {"action": "accept", "node_id": b.id},
    ])
    assert response.status_code == 409
    assert (w.reload(a).status, w.reload(a).title) == ("draft", "A")


def test_merge_moves_sources_and_edges_and_rejects_source(client, w):
    a = w.node("Annual leave dup", quote="q-a")
    b = w.node("Annual leave", quote="q-b")
    c = w.node("Dept", "department", "published")
    edge = w.edge(a, c)
    response = decide(client, w, [{"action": "merge", "node_id": a.id, "into_node_id": b.id}])
    assert response.status_code == 200
    assert w.reload(a).status == "rejected"
    quotes = {s.quote for s in w.db.query(KbNodeSource).filter_by(node_id=b.id)}
    assert quotes == {"q-a", "q-b"}
    assert w.db.query(KbNodeSource).filter_by(node_id=a.id).count() == 0
    assert w.reload(edge).source_node_id == b.id


def test_merge_drops_edge_that_would_duplicate_or_loop(client, w):
    a, b, c = w.node("A"), w.node("B"), w.node("C", status="published")
    w.edge(a, c)
    w.edge(b, c)
    w.edge(a, b)
    decide(client, w, [{"action": "merge", "node_id": a.id, "into_node_id": b.id}])
    w.db.expire_all()
    pairs = [(e.source_node_id, e.target_node_id) for e in w.db.query(KbEdge)]
    assert pairs == [(b.id, c.id)]


def test_merge_into_other_type_is_422(client, w):
    a, other_type = w.node("A"), w.node("B", type="policy")
    response = decide(client, w, [{"action": "merge", "node_id": a.id, "into_node_id": other_type.id}])
    assert response.status_code == 422
    assert w.reload(a).status == "draft"


def test_merge_into_other_company_or_inactive_or_self_is_refused(client, w):
    a = w.node("A")
    foreign = w.node("F", company=w.other)
    rejected = w.node("R", status="rejected")
    assert decide(client, w, [{"action": "merge", "node_id": a.id, "into_node_id": foreign.id}]).status_code in (404, 422)
    assert decide(client, w, [{"action": "merge", "node_id": a.id, "into_node_id": rejected.id}]).status_code == 422
    assert decide(client, w, [{"action": "merge", "node_id": a.id, "into_node_id": a.id}]).status_code == 422
    assert w.reload(a).status == "draft"


def test_edge_published_when_both_ends_published(client, w):
    a, b = w.node("A"), w.node("B")
    edge = w.edge(a, b)
    decide(client, w, [{"action": "accept", "node_id": a.id}])
    assert w.reload(edge).status == "draft"
    decide(client, w, [{"action": "accept", "node_id": b.id}])
    assert w.reload(edge).status == "published"


def test_accepting_node_publishes_edge_to_already_published_node(client, w):
    org = w.node("Dept", "department", "published", "public")
    node = w.node("Policy", "policy")
    edge = w.edge(node, org)
    decide(client, w, [{"action": "accept", "node_id": node.id}])
    assert w.reload(edge).status == "published"


def test_edge_with_rejected_end_is_rejected(client, w):
    a, b = w.node("A"), w.node("B")
    edge = w.edge(a, b)
    decide(client, w, [{"action": "accept", "node_id": a.id}, {"action": "reject", "node_id": b.id}])
    assert w.reload(edge).status == "rejected"


def test_document_published_when_no_drafts_remain(client, w):
    a, b = w.node("A"), w.node("B")
    decide(client, w, [{"action": "accept", "node_id": a.id}])
    assert w.reload(w.doc).status == "review"
    decide(client, w, [{"action": "accept", "node_id": b.id}])
    assert w.reload(w.doc).status == "published"


def test_document_published_when_all_rejected(client, w):
    a = w.node("A")
    decide(client, w, [{"action": "reject", "node_id": a.id}])
    assert w.reload(w.doc).status == "published"


def test_publish_document_without_nodes(client, w):
    empty = w.document("Empty")
    assert decide(client, w, [{"action": "publish_document", "document_id": empty.id}]).status_code == 200
    assert w.reload(empty).status == "published"


def test_publish_document_errors(client, w):
    w.node("Pending")
    foreign = w.document("Foreign", company=w.other)
    assert decide(client, w, [{"action": "publish_document", "document_id": foreign.id}]).status_code == 404
    assert decide(client, w, [{"action": "publish_document", "document_id": w.doc.id}]).status_code == 409


def test_action_shape_is_validated(client, w):
    node = w.node("A")
    assert decide(client, w, [{"action": "explode", "node_id": node.id}]).status_code == 422
    assert decide(client, w, [{"action": "accept"}]).status_code == 422
    assert decide(client, w, [{"action": "merge", "node_id": node.id}]).status_code == 422
    assert decide(client, w, []).status_code == 422


def test_company_nodes_are_not_review_items(client, w):
    w.node("Acme", "company", "published", "public", doc=False)
    assert client.get(w.url("review"), headers=w.hr).json()["nodes"] == []


def test_only_hr_can_use_review_and_graph(client, db, w):
    other_hr = make_user(db, "other-hr@example.test")
    db.add(CompanyMember(company_id=w.other.id, user_id=other_hr.id, role="hr"))
    db.commit()
    node = w.node("A")
    calls = [("get", "review", None), ("post", "review/decide", {"items": [{"action": "accept", "node_id": node.id}]}),
             ("get", "graph", None)]
    for email in ("mgr@example.test", "emp@example.test", "other-hr@example.test", None):
        headers = auth_header(email) if email else {}
        for method, tail, payload in calls:
            response = client.request(method, w.url(tail), json=payload, headers=headers)
            assert response.status_code in (401, 403), (email, tail, response.status_code)
    assert w.reload(node).status == "draft"


def test_enumeration_gives_same_answer_for_missing_and_foreign_nodes(client, w):
    foreign = w.node("F", company=w.other)
    codes = {decide(client, w, [{"action": "accept", "node_id": i}]).status_code for i in (foreign.id, 987654)}
    assert codes == {404}


@pytest.fixture
def graph(w):
    w.company_node = w.node("Acme", "company", "published", "public", doc=False)
    w.pub = w.node("Public fact", status="published", visibility="public")
    w.internal = w.node("Internal fact", status="published", visibility="internal")
    w.draft = w.node("Draft", status="draft", visibility="public")
    w.edge(w.pub, w.company_node, status="published")
    w.edge(w.internal, w.pub, "requires", status="published")
    w.edge(w.draft, w.pub, status="draft")
    return w


def get_graph(client, w, query="", headers=None):
    return client.get(w.url(f"graph{query}"), headers=headers or w.hr)


def test_graph_hr_sees_all_published(client, graph):
    body = get_graph(client, graph).json()
    assert {n["title"] for n in body["nodes"]} == {"Acme", "Public fact", "Internal fact"}
    assert len(body["links"]) == 2


def test_graph_shape(client, graph):
    body = get_graph(client, graph).json()
    node = next(n for n in body["nodes"] if n["title"] == "Public fact")
    assert node == {
        "id": str(graph.pub.id), "layer": "public", "type": "fact", "title": "Public fact", "body": "Public fact body",
    }
    link = next(item for item in body["links"] if item["relation"] == "requires")
    assert link == {"source": str(graph.internal.id), "target": str(graph.pub.id), "relation": "requires"}


def test_graph_candidate_view_hides_non_public_and_their_edges(client, graph):
    body = get_graph(client, graph, "?view_as=candidate").json()
    assert {n["title"] for n in body["nodes"]} == {"Acme", "Public fact"}
    ids = {n["id"] for n in body["nodes"]}
    assert all(item["source"] in ids and item["target"] in ids for item in body["links"])
    assert len(body["links"]) == 1


def test_graph_view_as_root_is_422(client, graph):
    assert get_graph(client, graph, "?view_as=root").status_code == 422


def test_graph_manager_with_foreign_department_is_422(client, db, graph):
    foreign = Department(company_id=graph.other.id, name="Foreign")
    db.add(foreign)
    db.commit()
    assert get_graph(client, graph, f"?view_as=manager&department_id={foreign.id}").status_code == 422


def test_graph_manager_view_with_own_department(client, db, graph):
    dept = Department(company_id=graph.company.id, name="Eng")
    db.add(dept)
    db.commit()
    assert get_graph(client, graph, f"?view_as=manager&department_id={dept.id}").status_code == 200


def test_auto_approve_requires_sample_company(db, w):
    w.node("A")
    with pytest.raises(PermissionError):
        review.auto_approve_document(db, w.doc.id, w.hr_user.id)
    assert w.reload(w.doc).status == "review"


def test_auto_approve_publishes_everything_for_sample_company(db, w):
    db.get(Company, w.company.id).is_sample = True
    db.commit()
    a, b = w.node("A"), w.node("B")
    edge = w.edge(a, b)
    review.auto_approve_document(db, w.doc.id, w.hr_user.id)
    assert {w.reload(a).status, w.reload(b).status} == {"published"}
    assert w.reload(edge).status == "published" and w.reload(w.doc).status == "published"
    assert w.reload(a).approved_by == w.hr_user.id


def test_finish_document_if_decided_only_acts_on_review_documents(db, w):
    w.node("A")
    assert review.finish_document_if_decided(db, w.doc.id) is False
    failed = w.document("Failed", status="failed")
    assert review.finish_document_if_decided(db, failed.id) is False
    assert w.reload(failed).status == "failed"


# Editing a fact and contradictions

AGREE = json.dumps({"same_topic": True, "same_scope": True, "same_value": False})


def fact(w, title, value, status="draft"):
    row = w.node(title, status=status)
    row.fact_kind, row.fact_value, row.fact_unit = "number", value, "days"
    w.db.commit()
    return row


def conflict_between(w, a, b, status="open", resolution=None):
    row = KbConflict(company_id=w.company.id, node_a_id=a.id, node_b_id=b.id, status=status, resolution=resolution)
    w.db.add(row)
    w.db.commit()
    return row


def set_version(w, value=5):
    w.company.kb_version = value
    w.db.commit()
    return value


def version(w):
    return w.reload(w.company).kb_version


def decide_ok(client, w, *items):
    response = client.post(w.url("review/decide"), json={"items": list(items)}, headers=w.hr)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def steady_vectors(monkeypatch):
    """Keeps an edited fact close to the others: the fake embedding is hash noise, a real one would barely move."""
    monkeypatch.setattr(review.gateway, "embed", lambda texts, *_a, **_k: SimpleNamespace(
        vectors=[[1.0, 0.0, 0.0, 0.0] for _ in texts], model="fake", dimension=4,
    ))


@pytest.fixture
def spy_check(monkeypatch):
    calls = []
    monkeypatch.setattr(review.contradiction, "check_new_facts", lambda *a, **k: calls.append(a[2]) or 0)
    return calls


def test_an_edit_that_creates_a_disagreement_opens_a_conflict(client, w, steady_vectors):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "12")
    start = set_version(w)
    fake.enqueue("kb_conflict_check", AGREE)
    body = decide_ok(client, w, {"action": "accept", "node_id": new.id, "fact_value": "15"})
    assert body["warnings"] == []
    row = w.db.query(KbConflict).one()
    assert (row.status, row.node_a_id, row.node_b_id) == ("open", old.id, new.id)
    assert w.reload(new).status == "published"
    assert version(w) == start + 1


def test_opening_several_conflicts_still_moves_the_version_once(client, w, steady_vectors):
    fact(w, "Leave", "12", "published")
    fact(w, "Leave two", "13", "published")
    new = fact(w, "Leave policy", "12")
    start = set_version(w)
    fake.enqueue("kb_conflict_check", AGREE)
    fake.enqueue("kb_conflict_check", AGREE)
    decide_ok(client, w, {"action": "accept", "node_id": new.id, "fact_value": "15"})
    assert w.db.query(KbConflict).filter_by(status="open").count() == 2
    assert version(w) == start + 1


def test_an_edit_that_resolves_a_conflict_closes_it_with_a_note(client, w):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "15")
    row = conflict_between(w, old, new)
    start = set_version(w)
    body = decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "12.0"})
    row = w.reload(row)
    assert (row.status, row.resolution, row.resolved_by) == ("dismissed", "edit_resolved", w.hr_user.id)
    assert row.resolved_at is not None
    assert body["warnings"] == []
    assert fake.last_messages() == []
    assert version(w) == start + 1


def test_a_resolving_edit_on_either_side_closes_it(client, w):
    new, old = fact(w, "Leave policy", "15"), fact(w, "Leave", "12", "published")
    row = conflict_between(w, old, new)
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "12"})
    assert w.reload(row).status == "dismissed"
    other = conflict_between(w, new, fact(w, "Leave two", "15"))
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "15"})
    assert w.reload(other).status == "dismissed"


def test_an_edit_that_still_disagrees_keeps_the_one_conflict_and_asks_nothing(client, w):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "15")
    row = conflict_between(w, old, new)
    decide_ok(client, w, {"action": "accept", "node_id": new.id, "fact_value": "20"})
    assert w.reload(row).status == "open"
    assert w.db.query(KbConflict).count() == 1
    assert fake.last_messages() == []


def test_unparseable_values_are_not_treated_as_equal(client, w):
    old, new = fact(w, "Leave", "many", "published"), fact(w, "Leave policy", "15")
    row = conflict_between(w, old, new)
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "several"})
    assert w.reload(row).status == "open"


def test_a_conflict_the_edit_settled_can_open_again_when_values_part(client, w, steady_vectors):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "15")
    first = conflict_between(w, old, new)
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "12"})
    assert w.reload(first).status == "dismissed"
    fake.enqueue("kb_conflict_check", AGREE)
    decide_ok(client, w, {"action": "accept", "node_id": new.id, "fact_value": "20"})
    assert w.db.query(KbConflict).filter_by(status="open").count() == 1


def test_a_pair_hr_dismissed_as_different_scope_stays_closed_while_the_value_holds(client, w, steady_vectors):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "15")
    conflict_between(w, old, new, status="dismissed", resolution="different_scope")
    decide_ok(client, w, {"action": "accept", "node_id": new.id, "title": "Leave policy, renamed"})
    assert w.db.query(KbConflict).count() == 1
    assert fake.last_messages() == []


@pytest.mark.parametrize("field,value", [("fact_value", "20"), ("fact_unit", "weeks"), ("scope_text", "Hanoi only")])
def test_a_dismissal_does_not_hide_a_contradiction_after_a_change(client, w, steady_vectors, field, value):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "15")
    conflict_between(w, old, new, status="dismissed", resolution="different_scope")
    fake.enqueue("kb_conflict_check", AGREE)
    decide_ok(client, w, {"action": "edit", "node_id": new.id, field: value})
    assert w.db.query(KbConflict).filter_by(status="open").count() == 1
    assert w.db.query(KbConflict).filter_by(status="dismissed").count() == 1


def test_a_recheck_never_reopens_an_open_or_resolved_pair(client, w, steady_vectors):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "15")
    conflict_between(w, old, new)
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "20"})
    assert w.db.query(KbConflict).count() == 1
    assert fake.last_messages() == []


def test_ai_failure_keeps_the_edit_and_returns_a_warning(client, w, steady_vectors):
    fact(w, "Leave", "12", "published")
    new = fact(w, "Leave policy", "12")
    start = set_version(w)
    fake.enqueue("kb_conflict_check", "not json")
    fake.enqueue("kb_conflict_check", "still not json")
    body = decide_ok(client, w, {"action": "accept", "node_id": new.id, "fact_value": "15"})
    assert body["ok"] is True
    assert len(body["warnings"]) == 1
    node = w.reload(new)
    assert (node.status, node.fact_value) == ("published", "15")
    assert w.db.query(KbConflict).count() == 0
    assert version(w) == start + 1


def test_ai_failure_on_one_node_still_checks_the_next(client, w, monkeypatch):
    first, second = fact(w, "One", "1"), fact(w, "Two", "2")
    checked = []

    def check(_db, _company_id, node_ids, **_):
        checked.extend(node_ids)
        if node_ids == [first.id]:
            raise AIError("no answer")
        return 0

    monkeypatch.setattr(review.contradiction, "check_new_facts", check)
    body = decide_ok(
        client, w, {"action": "accept", "node_id": first.id, "fact_value": "5"},
        {"action": "accept", "node_id": second.id, "fact_value": "6"},
    )
    assert checked == [first.id, second.id]
    assert len(body["warnings"]) == 1
    assert w.reload(second).status == "published"


def test_an_edit_that_changes_nothing_does_not_call_the_ai(client, w, spy_check):
    fact(w, "Leave", "12", "published")
    new = fact(w, "Leave policy", "15")
    decide_ok(client, w, {
        "action": "accept", "node_id": new.id, "fact_value": "15", "fact_unit": "days",
        "title": "Leave policy", "body": "Leave policy body",
    })
    assert spy_check == []


def test_a_plain_accept_does_not_call_the_ai(client, w, spy_check):
    new = fact(w, "Leave policy", "15")
    decide_ok(client, w, {"action": "accept", "node_id": new.id})
    assert spy_check == []


@pytest.mark.parametrize("field,value", [
    ("fact_value", "20"), ("fact_unit", "weeks"), ("title", "New title"), ("body", "New body"),
    ("scope_text", "Hanoi office"),
])
@pytest.mark.parametrize("action,status", [("accept", "draft"), ("edit", "draft"), ("edit", "published")])
def test_each_fact_field_triggers_the_check_at_any_status(client, w, spy_check, field, value, action, status):
    new = fact(w, "Leave policy", "15", status)
    decide_ok(client, w, {"action": action, "node_id": new.id, field: value})
    assert spy_check == [[new.id]]


def test_a_layer_change_does_not_trigger_the_check(client, w, spy_check):
    new = fact(w, "Leave policy", "15")
    decide_ok(client, w, {"action": "accept", "node_id": new.id, "visibility": "public"})
    assert spy_check == []


@pytest.mark.parametrize("field,value", [("fact_value", "20"), ("fact_unit", "weeks"), ("scope_text", "Hanoi office")])
def test_an_edit_to_a_fact_field_embeds_the_new_text(client, w, field, value):
    new = fact(w, "Leave policy", "15")
    before = new.embedding
    decide_ok(client, w, {"action": "edit", "node_id": new.id, field: value})
    assert w.reload(new).embedding != before


def test_editing_a_facts_value_changes_its_stored_embedding_under_the_fake_provider(client, w):
    new = fact(w, "Leave policy", "15")
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "title": "Leave rule"})
    before = w.reload(new).embedding
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "20"})
    assert w.reload(new).embedding != before


def test_re_embedding_goes_through_the_retrievers_node_text(client, w, monkeypatch):
    new = fact(w, "Leave policy", "15")
    seen = []
    real = review.gateway.embed
    monkeypatch.setattr(review.gateway, "embed", lambda texts, *a, **k: seen.extend(texts) or real(texts, *a, **k))
    monkeypatch.setattr(retriever, "node_text", lambda node: f"TEXT OF {node.id}", raising=False)
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "20"})
    assert f"TEXT OF {new.id}" in seen


def test_a_node_without_a_fact_kind_is_not_checked(client, w, spy_check):
    new = w.node("Plain")
    decide_ok(client, w, {"action": "accept", "node_id": new.id, "title": "Plainer"})
    assert spy_check == []


def test_a_draft_edit_is_rechecked_and_moves_the_version_once(client, w, spy_check):
    new = fact(w, "Leave policy", "15")
    start = set_version(w)
    decide_ok(client, w, {"action": "edit", "node_id": new.id, "fact_value": "20"})
    assert spy_check == [[new.id]]
    assert version(w) == start + 1


def test_edit_then_accept_in_one_request_is_rechecked_once(client, w, spy_check):
    new = fact(w, "Leave policy", "15")
    start = set_version(w)
    decide_ok(
        client, w, {"action": "edit", "node_id": new.id, "fact_value": "20"},
        {"action": "accept", "node_id": new.id, "fact_unit": "weeks"},
    )
    assert spy_check == [[new.id]]
    assert version(w) == start + 1


def test_edit_then_reject_in_one_request_is_not_rechecked(client, w, spy_check):
    new = fact(w, "Leave policy", "15")
    decide_ok(
        client, w, {"action": "edit", "node_id": new.id, "fact_value": "20"},
        {"action": "reject", "node_id": new.id},
    )
    assert spy_check == []


def test_a_bad_item_undoes_the_closing_and_runs_no_check(client, w, spy_check):
    old, new = fact(w, "Leave", "12", "published"), fact(w, "Leave policy", "15")
    row = conflict_between(w, old, new)
    response = client.post(w.url("review/decide"), headers=w.hr, json={"items": [
        {"action": "accept", "node_id": new.id, "fact_value": "12"},
        {"action": "reject", "node_id": 999999},
    ]})
    assert response.status_code == 404
    assert w.reload(row).status == "open"
    assert w.reload(new).fact_value == "15"
    assert spy_check == []


# Published knowledge can be corrected and retracted

def candidate_titles(w):
    w.db.commit()
    nodes, _ = retriever.visible_graph(w.db, aud.candidate(w.company.id))
    return {n.title for n in nodes}


def test_a_wrong_layer_publish_can_be_corrected_and_the_candidate_stops_seeing_it(client, w):
    node = w.node("Salary band", type="private_note", visibility="public", status="published")
    assert "Salary band" in candidate_titles(w)
    start = set_version(w)
    decide_ok(client, w, {"action": "edit", "node_id": node.id, "visibility": "confidential"})
    node = w.reload(node)
    assert (node.status, node.visibility) == ("published", "confidential")
    assert "Salary band" not in candidate_titles(w)
    assert version(w) == start + 1


def test_rejecting_a_published_node_unpublishes_it(client, w):
    node = w.node("Wrong", status="published", visibility="public")
    other = w.node("Other", status="published", visibility="public")
    third = w.node("Third")
    published_edge, draft_edge = w.edge(node, other, status="published"), w.edge(third, node)
    conflict = conflict_between(w, node, other)
    start = set_version(w)
    decide_ok(client, w, {"action": "reject", "node_id": node.id})
    assert w.reload(node).status == "rejected"
    assert "Wrong" not in candidate_titles(w)
    row = w.reload(conflict)
    assert (row.status, row.resolution) == ("dismissed", "node_rejected")
    assert w.reload(published_edge).status == "rejected" and w.reload(draft_edge).status == "rejected"
    assert version(w) == start + 1


@pytest.mark.parametrize("action,status,extra", [
    ("accept", "published", {}), ("accept", "rejected", {}), ("edit", "rejected", {"title": "x"}),
    ("edit", "superseded", {"title": "x"}), ("reject", "rejected", {}), ("reject", "superseded", {}),
])
def test_what_review_still_refuses(client, w, action, status, extra):
    node = w.node("Done", status=status)
    assert decide(client, w, [{"action": action, "node_id": node.id, **extra}]).status_code == 409


def test_a_published_node_cannot_be_merged_away(client, w):
    published, target = w.node("Published", status="published"), w.node("Target")
    response = decide(client, w, [{"action": "merge", "node_id": published.id, "into_node_id": target.id}])
    assert response.status_code == 409


def test_edit_body_longer_than_15000_characters_is_422(client, w):
    node = w.node("Long")
    assert decide(client, w, [{"action": "edit", "node_id": node.id, "body": "x" * 15001}]).status_code == 422
    assert decide(client, w, [{"action": "edit", "node_id": node.id, "body": "x" * 15000}]).status_code == 200


def test_version_moves_by_atomic_update_and_keeps_a_concurrent_bump(client, w, monkeypatch):
    node = w.node("Leave")
    start = set_version(w)
    real = review._embed_nodes

    def bump_from_elsewhere(db, company_id, nodes):
        db.execute(text("UPDATE companies SET kb_version = kb_version + 1 WHERE id = :id"), {"id": company_id})
        real(db, company_id, nodes)

    monkeypatch.setattr(review, "_embed_nodes", bump_from_elsewhere)
    decide_ok(client, w, {"action": "accept", "node_id": node.id, "title": "New title"})
    assert version(w) == start + 2


def test_auto_approve_moves_the_version_once(db, w):
    db.get(Company, w.company.id).is_sample = True
    db.commit()
    w.node("A"), w.node("B")
    start = set_version(w)
    review.auto_approve_document(db, w.doc.id, w.hr_user.id)
    assert version(w) == start + 1


# Unpublishing a document

@pytest.fixture
def two_documents(w):
    w.second = w.document("Second", status="published")
    w.second_chunk = KbChunk(company_id=w.company.id, document_id=w.second.id, position=0, page=1, text="s")
    w.db.add(w.second_chunk)
    w.doc.status = "published"
    w.db.commit()
    w.sole = w.node("Sole", status="published", visibility="public", quote="sole quote")
    w.sole_draft = w.node("Sole draft", quote="draft quote")
    w.shared = w.node("Shared", status="published", visibility="public", quote="first quote")
    w.db.add(KbNodeSource(node_id=w.shared.id, chunk_id=w.second_chunk.id, quote="second quote"))
    w.db.commit()
    return w


def unpublish(client, w, document_id=None, headers=None):
    return client.post(w.url(f"documents/{document_id or w.doc.id}/unpublish"), headers=headers or w.hr)


def test_unpublish_withdraws_the_document_and_its_sole_source_nodes(client, two_documents):
    w = two_documents
    other = w.node("Elsewhere", status="published", doc=False)
    conflict = conflict_between(w, w.sole, other)
    edge = w.edge(w.sole, other, status="published")
    start = set_version(w)
    response = unpublish(client, w)
    assert response.status_code == 200
    body = response.json()
    assert body["document"]["status"] == "withdrawn"
    assert (body["rejected_nodes"], body["kept_nodes"]) == (2, 1)
    assert w.reload(w.doc).status == "withdrawn"
    assert (w.reload(w.sole).status, w.reload(w.sole_draft).status) == ("rejected", "rejected")
    assert w.reload(w.shared).status == "published"
    row = w.reload(conflict)
    assert (row.status, row.resolution) == ("dismissed", "node_rejected")
    assert w.reload(edge).status == "rejected"
    assert version(w) == start + 1


def test_unpublish_removes_chunks_from_retrieval_and_sole_nodes_from_the_candidate(client, two_documents):
    w = two_documents
    hr = aud.simulated(w.db, w.company.id, "hr", None)
    assert w.chunk.id in {row.id for row in retriever._allowed_chunks(w.db, hr)}
    assert "Sole" in candidate_titles(w)
    assert unpublish(client, w).status_code == 200
    w.db.commit()
    assert w.chunk.id not in {row.id for row in retriever._allowed_chunks(w.db, hr)}
    assert w.second_chunk.id in {row.id for row in retriever._allowed_chunks(w.db, hr)}
    titles = candidate_titles(w)
    assert "Sole" not in titles and "Shared" in titles


def test_a_kept_node_stops_citing_the_withdrawn_document(client, two_documents):
    w = two_documents
    assert unpublish(client, w).status_code == 200
    w.db.expire_all()
    assert [s.quote for s in w.db.query(KbNodeSource).filter_by(node_id=w.shared.id)] == ["second quote"]


def test_withdrawing_each_source_in_turn_finally_rejects_the_node(client, two_documents):
    w = two_documents
    assert unpublish(client, w).status_code == 200
    assert w.reload(w.shared).status == "published"
    assert unpublish(client, w, w.second.id).status_code == 200
    assert w.reload(w.shared).status == "rejected"


@pytest.mark.parametrize("status", ["processing", "failed", "withdrawn"])
def test_only_a_reviewed_or_published_document_can_be_unpublished(client, w, status):
    w.doc.status = status
    w.db.commit()
    assert unpublish(client, w).status_code == 409
    assert w.reload(w.doc).status == status


def test_a_document_in_review_can_be_unpublished(client, w):
    draft = w.node("Draft")
    assert unpublish(client, w).status_code == 200
    assert w.reload(draft).status == "rejected"


def test_a_document_with_a_running_job_cannot_be_unpublished(client, w):
    w.doc.status = "published"
    w.db.add(KbIngestionJob(document_id=w.doc.id, status="running"))
    w.db.commit()
    assert unpublish(client, w).status_code == 409


def test_unpublish_permissions(client, w):
    foreign = w.document("Foreign", company=w.other)
    assert unpublish(client, w, foreign.id).status_code == 404
    assert unpublish(client, w, 999999).status_code == 404
    assert unpublish(client, w, headers=auth_header("emp@example.test")).status_code == 403
    assert unpublish(client, w, headers=auth_header("mgr@example.test")).status_code == 403
    assert w.reload(w.doc).status == "review"


def test_a_withdrawn_document_cannot_be_retried(client, w):
    w.doc.status = "withdrawn"
    job = KbIngestionJob(document_id=w.doc.id, status="failed", failed_chunk_ids=[w.chunk.id])
    w.db.add(job)
    w.db.commit()
    assert client.post(w.url(f"jobs/{job.id}/retry"), headers=w.hr).status_code == 409
    assert client.post(w.url(f"jobs/{job.id}/retry-failed"), headers=w.hr).status_code == 409
    assert w.db.query(KbChunk).filter_by(document_id=w.doc.id).count() == 1


# Resolving conflicts

def facts_abc(w, status="draft"):
    a, b, c = fact(w, "A", "12", status), fact(w, "B", "15", status), fact(w, "C", "20", status)
    return a, b, c, conflict_between(w, a, b), conflict_between(w, a, c), conflict_between(w, b, c)


def resolve(client, w, row, action):
    return client.post(w.url(f"conflicts/{row.id}/resolve"), json={"action": action}, headers=w.hr)


def test_superseding_a_node_closes_its_other_conflicts(client, w):
    a, b, c, ab, ac, bc = facts_abc(w)
    assert resolve(client, w, ab, "a").status_code == 200
    assert w.reload(b).status == "superseded"
    row = w.reload(bc)
    assert (row.status, row.resolution) == ("dismissed", "node_superseded")
    assert row.resolved_at is not None
    assert w.reload(ac).status == "open"
    # The Radar's list no longer offers a choice that would leave no live value.
    listed = client.get(w.url("conflicts"), headers=w.hr).json()
    assert [item["id"] for item in listed] == [ac.id]
    assert resolve(client, w, ac, "b").status_code == 200
    assert {w.reload(a).status, w.reload(c).status} == {"superseded", "draft"}


def test_resolve_is_409_when_a_side_is_not_live(client, w):
    a, b = fact(w, "A", "12"), fact(w, "B", "15")
    for status in ("superseded", "rejected"):
        b = w.reload(b)
        b.status = status
        w.db.commit()
        row = conflict_between(w, a, b)
        for action in ("a", "b", "different_scope"):
            assert resolve(client, w, row, action).status_code == 409
        assert w.reload(row).status == "open"
        assert w.reload(a).status == "draft"


def test_resolve_settles_edges_and_finishes_the_document(client, w):
    org = w.node("Acme", "company", "published", "public", doc=False)
    keep, lose = fact(w, "Keep", "12", "published"), fact(w, "Lose", "15")
    keep_edge, lose_edge = w.edge(keep, org), w.edge(lose, org)
    published_edge = w.edge(lose, keep, status="published")
    row = conflict_between(w, keep, lose)
    start = set_version(w)
    assert resolve(client, w, row, "a").status_code == 200
    assert w.reload(lose_edge).status == "rejected" and w.reload(published_edge).status == "rejected"
    assert w.reload(keep_edge).status == "published"
    assert w.reload(w.doc).status == "published"
    assert version(w) == start + 1


def test_resolve_leaves_the_document_in_review_while_a_draft_remains(client, w):
    keep, lose, _other = fact(w, "Keep", "12"), fact(w, "Lose", "15"), fact(w, "Other", "20")
    assert resolve(client, w, conflict_between(w, keep, lose), "a").status_code == 200
    assert w.reload(w.doc).status == "review"


def test_conflicts_list_each_sides_sources(client, db, w):
    doc = w.document("Leave policy")
    doc.effective_date = date(2026, 3, 1)
    chunk = KbChunk(company_id=w.company.id, document_id=doc.id, position=0, page=7, text="t")
    db.add(chunk)
    db.commit()
    a, b = fact(w, "A", "12"), fact(w, "B", "15")
    db.add(KbNodeSource(node_id=b.id, chunk_id=chunk.id, quote="15 days"))
    db.commit()
    conflict_between(w, a, b)
    [item] = client.get(w.url("conflicts"), headers=w.hr).json()
    assert item["node_a"]["sources"] == [
        {"quote": "quote", "page": 3, "document_title": "Handbook", "effective_date": None}
    ]
    assert {"quote": "15 days", "page": 7, "document_title": "Leave policy", "effective_date": "2026-03-01"} in item["node_b"]["sources"]
    assert "embedding" not in item["node_a"]


def test_graph_returns_body_and_no_embeddings(client, graph):
    body = get_graph(client, graph).json()
    node = next(n for n in body["nodes"] if n["title"] == "Internal fact")
    assert node["body"] == "Internal fact body"
    assert not any("embedding" in key for key in node)


def test_graph_body_stays_within_the_audience(client, graph):
    body = get_graph(client, graph, "?view_as=candidate").json()
    assert all("Internal fact" not in n["body"] for n in body["nodes"])
