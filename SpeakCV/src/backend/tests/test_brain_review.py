import pytest

from app.brain import review, vectors
from app.database.sql_models import (
    Company, CompanyMember, Department, KbChunk, KbConflict, KbDocument, KbEdge, KbNode, KbNodeSource,
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
    assert first["sources"] == [{"quote": "12 days", "page": 3, "document_title": "Handbook"}]
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
        {"action": "reject", "node_id": published.id},
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
    assert node == {"id": str(graph.pub.id), "layer": "public", "type": "fact", "title": "Public fact"}
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
