import pytest

from app.brain import gaps, vectors
from app.database.sql_models import AssistantQuestion, Company, CompanyMember
from tests.helpers import auth_header, make_user

NEAR_A = [1.0, 0.0, 0.0, 0.0]
NEAR_A2 = [0.9, 0.3, 0.0, 0.0]  # cosine with NEAR_A is about 0.95
JUST_BELOW = [0.79, 0.613, 0.0, 0.0]  # cosine with NEAR_A is about 0.79
JUST_ABOVE = [0.81, 0.586, 0.0, 0.0]  # cosine with NEAR_A is about 0.81
FAR = [0.0, 0.0, 1.0, 0.0]


@pytest.fixture
def company(db):
    row = Company(slug="acme", name="Acme")
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def other_company(db):
    row = Company(slug="other", name="Other")
    db.add(row)
    db.commit()
    return row


def ask(db, company, text, vector=NEAR_A, model="fake", answered=False, resolved=False):
    row = AssistantQuestion(
        company_id=company.id, audience="employee", question=text, language="en", answered=answered,
        embedding=vectors.encode(vector) if vector is not None else None,
        embedding_model=model if vector is not None else None, resolved=resolved,
    )
    db.add(row)
    db.commit()
    return row


def test_similar_questions_group_with_a_sample_and_a_count(db, company):
    first = ask(db, company, "How many days of leave?")
    ask(db, company, "Annual leave days?", NEAR_A2)
    groups = gaps.list_gaps(db, company.id)
    assert len(groups) == 1
    assert groups[0].group_id == first.id
    assert groups[0].sample_question == "How many days of leave?"
    assert groups[0].count == 2


def test_clustering_threshold_is_cosine_080(db, company):
    seed = ask(db, company, "seed")
    above = ask(db, company, "above", JUST_ABOVE)
    below = ask(db, company, "below", JUST_BELOW)
    groups = {group.group_id: group for group in gaps.list_gaps(db, company.id)}
    assert groups[seed.id].question_ids == (seed.id, above.id)
    assert groups[below.id].question_ids == (below.id,)


def test_a_question_joins_the_first_matching_seed(db, company):
    a = ask(db, company, "a", NEAR_A)
    b = ask(db, company, "b", JUST_BELOW)  # under the threshold against a, so it seeds its own group
    both = ask(db, company, "both", [0.95, 0.312, 0.0, 0.0])  # over the threshold against both seeds
    groups = {group.group_id: group.question_ids for group in gaps.list_gaps(db, company.id)}
    assert groups[a.id] == (a.id, both.id)
    assert groups[b.id] == (b.id,)


def test_groups_are_sorted_by_count_largest_first(db, company):
    lone = ask(db, company, "lone", FAR)
    big = ask(db, company, "big")
    ask(db, company, "big 2")
    ask(db, company, "big 3")
    assert [group.group_id for group in gaps.list_gaps(db, company.id)] == [big.id, lone.id]


def test_answered_and_resolved_questions_are_excluded(db, company):
    ask(db, company, "answered", answered=True)
    ask(db, company, "resolved", resolved=True)
    assert gaps.list_gaps(db, company.id) == []


def test_resolve_marks_the_whole_group_and_it_disappears(db, company):
    seed = ask(db, company, "seed")
    member = ask(db, company, "member", NEAR_A2)
    other = ask(db, company, "other", FAR)
    assert gaps.resolve_group(db, company.id, seed.id) == 2
    db.expire_all()
    assert db.get(AssistantQuestion, seed.id).resolved is True
    assert db.get(AssistantQuestion, member.id).resolved is True
    assert db.get(AssistantQuestion, other.id).resolved is False
    assert [group.group_id for group in gaps.list_gaps(db, company.id)] == [other.id]


def test_resolve_of_a_non_seed_member_or_unknown_id_changes_nothing(db, company):
    ask(db, company, "seed")
    member = ask(db, company, "member", NEAR_A2)
    assert gaps.resolve_group(db, company.id, member.id) == 0
    assert gaps.resolve_group(db, company.id, 999999) == 0
    assert gaps.list_gaps(db, company.id)[0].count == 2


def test_companies_never_mix(db, company, other_company):
    ask(db, company, "ours")
    theirs = ask(db, other_company, "theirs")
    assert [group.sample_question for group in gaps.list_gaps(db, company.id)] == ["ours"]
    assert gaps.resolve_group(db, company.id, theirs.id) == 0
    db.expire_all()
    assert db.get(AssistantQuestion, theirs.id).resolved is False


def test_questions_from_another_model_are_singletons_and_not_compared(db, company):
    ours = ask(db, company, "current model")
    ask(db, company, "current model 2", NEAR_A2)
    old_a = ask(db, company, "old model a", model="old-model")
    old_b = ask(db, company, "old model b", model="old-model")
    groups = {group.group_id: group.question_ids for group in gaps.list_gaps(db, company.id)}
    assert len(groups[ours.id]) == 2
    assert groups[old_a.id] == (old_a.id,)
    assert groups[old_b.id] == (old_b.id,)


def test_questions_with_no_embedding_or_a_wrong_length_vector_are_singletons(db, company):
    ask(db, company, "seed")
    none = ask(db, company, "no embedding", None)
    short = ask(db, company, "short vector", [1.0, 0.0])
    groups = {group.group_id: group.question_ids for group in gaps.list_gaps(db, company.id)}
    assert groups[none.id] == (none.id,)
    assert groups[short.id] == (short.id,)


# API


@pytest.fixture
def members(db, company, other_company):
    for email, target, role in [("hr@example.test", company, "hr"), ("employee@example.test", company, "employee"),
                                ("manager@example.test", company, "manager"), ("hr-other@example.test", other_company, "hr")]:
        user = make_user(db, email)
        db.add(CompanyMember(company_id=target.id, user_id=user.id, role=role))
    db.commit()


def test_gap_list_route(db, client, company, members):
    seed = ask(db, company, "seed")
    ask(db, company, "member", NEAR_A2)
    response = client.get(f"/api/companies/{company.id}/kb/gaps", headers=auth_header("hr@example.test"))
    assert response.status_code == 200
    assert response.json() == [{"group_id": seed.id, "sample_question": "seed", "count": 2}]


def test_resolve_route_and_the_group_disappears(db, client, company, members):
    seed = ask(db, company, "seed")
    headers = auth_header("hr@example.test")
    response = client.post(f"/api/companies/{company.id}/kb/gaps/{seed.id}/resolve", headers=headers)
    assert response.status_code == 200 and response.json() == {"resolved": 1}
    assert client.get(f"/api/companies/{company.id}/kb/gaps", headers=headers).json() == []


def test_a_group_from_another_company_is_404(db, client, company, other_company, members):
    theirs = ask(db, other_company, "theirs")
    response = client.post(f"/api/companies/{company.id}/kb/gaps/{theirs.id}/resolve", headers=auth_header("hr@example.test"))
    assert response.status_code == 404
    db.expire_all()
    assert db.get(AssistantQuestion, theirs.id).resolved is False


@pytest.mark.parametrize("email", ["employee@example.test", "manager@example.test", "hr-other@example.test"])
def test_gap_routes_are_hr_only(db, client, company, members, email):
    seed = ask(db, company, "seed")
    headers = auth_header(email)
    assert client.get(f"/api/companies/{company.id}/kb/gaps", headers=headers).status_code == 403
    assert client.post(f"/api/companies/{company.id}/kb/gaps/{seed.id}/resolve", headers=headers).status_code == 403


def test_gap_list_does_not_expose_who_asked(db, client, company, members):
    member = db.query(CompanyMember).filter_by(company_id=company.id, role="employee").one()
    row = ask(db, company, "seed")
    row.user_id = member.user_id
    db.commit()
    body = client.get(f"/api/companies/{company.id}/kb/gaps", headers=auth_header("hr@example.test")).json()
    assert set(body[0]) == {"group_id", "sample_question", "count"}
