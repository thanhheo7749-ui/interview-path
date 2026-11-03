"""Gap-to-Growth: a catalogue the company writes. AI picks IDs from it, and code resolves every title and link."""
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.ai.providers import fake
from app.brain import fake_demo
from app.database.sql_models import AuditLog, KbNode, LearningResource, RequirementResult
from app.main import create_app
from app.posthire import feedback, learning
from tests.helpers import auth_header
from tests.helpers_board import CANDIDATE_EMAIL, make_application, make_session, make_world

QUOTE = "I built a FastAPI service used by three teams"
GOOD_MESSAGE = "Thank you for talking with us about this role."
LINK = "https://learn.example.test/docker"


@pytest.fixture
def world(db):
    world = make_world(db)
    company_id = world["company"].id
    world["docker_node"] = KbNode(company_id=company_id, type="skill", title="Docker", body="x", language="en",
                                  visibility="public", status="published")
    world["k8s_node"] = KbNode(company_id=company_id, type="skill", title="Kubernetes", body="x", language="en",
                               visibility="public", status="published")
    world["private_node"] = KbNode(company_id=company_id, type="skill", title="Project Falcon", body="x", language="en",
                                   visibility="confidential", status="published")
    world["foreign_node"] = KbNode(company_id=world["other"].id, type="skill", title="Foreign", body="x", language="en",
                                   visibility="public", status="published")
    db.add_all([world["docker_node"], world["k8s_node"], world["private_node"], world["foreign_node"]])
    db.flush()
    world["requirements"][1].node_id = world["docker_node"].id
    world["requirements"][2].node_id = world["k8s_node"].id
    db.commit()
    return world


@pytest.fixture
def api():
    return TestClient(create_app())


def path(world, tail="/learning-resources"):
    return f"/api/companies/{world['company'].id}{tail}"


def hr(world):
    return world["people"]["hr"]["headers"]


def resource(db, world, node="docker_node", title="Docker Foundations", link=LINK, provider="Acme Academy", **extra):
    row = LearningResource(company_id=extra.pop("company_id", world["company"].id), skill_node_id=world[node].id,
                           title=title, url=link, provider=provider, language="en", **extra)
    db.add(row)
    db.commit()
    return row


def interviewed(db, world, language="en", gap_index=1):
    application = make_application(db, world["job"], "#A1", hr_decision="rejected",
                                   hr_decided_at=datetime.now(timezone.utc), cv_status="not_met")
    session, _ = make_session(db, application, [(1, "Q", QUOTE, None)])
    session.language = language
    db.add_all([
        RequirementResult(application_id=application.id, requirement_id=world["requirements"][0].id,
                          source="interview", status="evidence", quote=QUOTE),
        RequirementResult(application_id=application.id, requirement_id=world["requirements"][gap_index].id,
                          source="interview", status="none"),
    ])
    db.commit()
    return application


def output(world, learning_ids=(), message=GOOD_MESSAGE, gap_index=1):
    return json.dumps({
        "went_well": [{"ref": f"r{world['requirements'][0].id}", "text": "You explained your FastAPI work", "quote": QUOTE}],
        "to_build": [{"ref": f"r{world['requirements'][gap_index].id}", "text": "Practise it on a real project", "quote": ""}],
        "learning_ids": list(learning_ids),
        "message": message,
    })


def item(world, **extra):
    return {"skill_node_id": world["docker_node"].id, "title": "Docker Foundations", "url": LINK,
            "provider": "Acme Academy", "language": "en", **extra}


def post_csv(api, world, text):
    return api.post(path(world), headers=hr(world), files={"file": ("catalogue.csv", text.encode("utf-8"), "text/csv")})


# 1. The catalogue


def test_create_read_update_delete_through_json(db, world, api):
    created = api.post(path(world), headers=hr(world), json=item(world))
    assert created.status_code == 201, created.text
    assert created.json()["created"] == 1 and created.json()["updated"] == 0
    resource_id = created.json()["items"][0]["id"]
    listed = api.get(path(world), headers=hr(world)).json()
    assert [row["title"] for row in listed] == ["Docker Foundations"]
    assert listed[0]["skill_title"] == "Docker" and listed[0]["created_by"] == world["people"]["hr"]["id"]

    changed = api.patch(path(world, f"/learning-resources/{resource_id}"), headers=hr(world), json={"title": "Docker Basics"})
    assert changed.status_code == 200 and changed.json()["title"] == "Docker Basics"
    assert changed.json()["url"] == LINK

    assert api.delete(path(world, f"/learning-resources/{resource_id}"), headers=hr(world)).status_code == 204
    assert api.get(path(world), headers=hr(world)).json() == []
    assert db.query(AuditLog).filter_by(action="learning_resources_saved").count() == 1
    assert db.query(AuditLog).filter_by(action="learning_resource_updated").count() == 1
    assert db.query(AuditLog).filter_by(action="learning_resource_deleted").count() == 1


def test_a_json_list_is_one_batch(db, world, api):
    response = api.post(path(world), headers=hr(world), json=[item(world), item(world, url=LINK + "/2")])
    assert response.status_code == 201 and response.json()["created"] == 2
    bad = api.post(path(world), headers=hr(world), json=[item(world, url=LINK + "/3"), item(world, url="ftp://x.test")])
    assert bad.status_code == 422 and bad.json()["detail"]["row"] == 2
    db.rollback()
    assert db.query(LearningResource).count() == 2


def test_csv_import(db, world, api):
    node = world["docker_node"].id
    text = (f"﻿skill_node_id,title,url,provider,language\n{node},\"Docker, the basics\",{LINK},Acme,en\n"
            f"{node},Docker 2,{LINK}/2,,vi\n")
    response = post_csv(api, world, text)
    assert response.status_code == 201, response.text
    assert response.json()["created"] == 2
    rows = db.query(LearningResource).order_by(LearningResource.id).all()
    assert [(row.title, row.provider, row.language) for row in rows] == [("Docker, the basics", "Acme", "en"), ("Docker 2", "", "vi")]
    assert rows[0].created_by == world["people"]["hr"]["id"]


def test_a_raw_csv_body_also_works(db, world, api):
    text = f"skill_node_id,title,url\n{world['docker_node'].id},Docker,{LINK}\n"
    response = api.post(path(world), headers={**hr(world), "Content-Type": "text/csv"}, content=text.encode())
    assert response.status_code == 201, response.text


def test_importing_the_same_row_again_updates_it(db, world, api):
    node = world["docker_node"].id
    post_csv(api, world, f"skill_node_id,title,url\n{node},Docker,{LINK}\n")
    response = post_csv(api, world, f"skill_node_id,title,url\n{node},Docker renamed,{LINK}\n")
    assert response.status_code == 201 and response.json() | {"items": []} == {"created": 0, "updated": 1, "items": []}
    assert db.query(LearningResource).one().title == "Docker renamed"


@pytest.mark.parametrize("text, row", [
    ("skill_node_id,title\n1,Docker\n", 0),
    ("skill_node_id,title,url\n{node},Docker,javascript:alert(1)\n", 1),
    ("skill_node_id,title,url\n{node},Docker,ftp://x.test/a\n", 1),
    ("skill_node_id,title,url\nabc,Docker,https://x.test\n", 1),
    ("skill_node_id,title,url\n{node},,https://x.test\n", 1),
    ("skill_node_id,title,url\n{node},Docker,https://x.test\n{node},Good,nonsense\n", 2),
])
def test_csv_errors_name_the_row_and_save_nothing(db, world, api, text, row):
    response = post_csv(api, world, text.format(node=world["docker_node"].id))
    assert response.status_code == 422
    assert response.json()["detail"]["row"] == row
    db.rollback()
    assert db.query(LearningResource).count() == 0


def test_a_csv_that_is_not_utf8_or_is_too_long_is_refused(world, api):
    bad = api.post(path(world), headers=hr(world), files={"file": ("c.csv", "tiêu đề".encode("utf-16"), "text/csv")})
    assert bad.status_code == 422
    header = "skill_node_id,title,url\n"
    long = header + "".join(f"{world['docker_node'].id},T{i},{LINK}/{i}\n" for i in range(learning.MAX_ROWS + 1))
    assert post_csv(api, world, long).status_code == 422


def test_a_file_of_another_type_is_refused(world, api):
    response = api.post(path(world), headers=hr(world), files={"file": ("c.pdf", b"%PDF", "application/pdf")})
    assert response.status_code == 415


def test_a_body_that_is_not_json_is_refused(world, api):
    response = api.post(path(world), headers={**hr(world), "Content-Type": "application/json"}, content=b"{nope")
    assert response.status_code == 422
    assert api.post(path(world), headers=hr(world), json="just a string").status_code == 422


def test_the_skill_node_must_belong_to_the_company(db, world, api):
    response = api.post(path(world), headers=hr(world), json=item(world, skill_node_id=world["foreign_node"].id))
    assert response.status_code == 422
    assert api.post(path(world), headers=hr(world), json=item(world, skill_node_id=999_999)).status_code == 422
    row = resource(db, world)
    patched = api.patch(path(world, f"/learning-resources/{row.id}"), headers=hr(world),
                        json={"skill_node_id": world["foreign_node"].id})
    assert patched.status_code == 422


@pytest.mark.parametrize("link", [
    "javascript:alert(1)", "ftp://x.test/a", "data:text/html,hi", "//x.test/a", "x.test/a", "http://", "https:///a",
    "https://x.test/a b", "https://x.test/​a", 'https://x.test/"a', "https://x.test/" + "a" * 2000, "",
])
def test_only_http_and_https_links_are_accepted(world, api, link):
    assert api.post(path(world), headers=hr(world), json=item(world, url=link)).status_code == 422


@pytest.mark.parametrize("link", ["http://x.test", "https://x.test/a?b=1#c", "HTTPS://x.test/a_(b)"])
def test_good_links_are_accepted(world, api, link):
    assert api.post(path(world), headers=hr(world), json=item(world, url=link)).status_code == 201


@pytest.mark.parametrize("field, value", [
    ("title", ""), ("title", "   "), ("title", "x" * 501), ("title", 7), ("provider", "x" * 101), ("language", "x" * 11),
    ("language", "not a language"), ("skill_node_id", True), ("skill_node_id", None),
    ("title", "Docker at https://evil.example"), ("provider", "evil.example.com"),
])
def test_field_limits_are_checked_before_insert(world, api, field, value):
    assert api.post(path(world), headers=hr(world), json=item(world, **{field: value})).status_code == 422


def test_a_title_keeps_to_one_line(db, world, api):
    response = api.post(path(world), headers=hr(world), json=item(world, title="Docker\n- Evil  line"))
    assert response.status_code == 201
    assert response.json()["items"][0]["title"] == "Docker - Evil line"


def test_routes_are_hr_only_and_company_scoped(db, world, api):
    row = resource(db, world)
    employee = world["people"]["emp"]["headers"]
    foreign_hr = world["people"]["hr2"]["headers"]
    assert api.get(path(world), headers=employee).status_code == 403
    assert api.post(path(world), headers=employee, json=item(world)).status_code == 403
    tail = f"/learning-resources/{row.id}"
    assert api.patch(path(world, tail), headers=employee, json={"title": "x"}).status_code == 403
    assert api.delete(path(world, tail), headers=employee).status_code == 403
    foreign = f"/api/companies/{world['other'].id}"
    assert api.get(foreign + "/learning-resources", headers=foreign_hr).json() == []
    assert api.patch(foreign + tail, headers=foreign_hr, json={"title": "x"}).status_code == 404
    assert api.delete(foreign + tail, headers=foreign_hr).status_code == 404
    db.expire_all()
    assert db.get(LearningResource, row.id).title == "Docker Foundations"


# 2. suggest


def test_suggest_returns_only_rows_for_the_skills_asked_about(db, world):
    docker = resource(db, world)
    resource(db, world, node="k8s_node", title="K8s", link=LINK + "/k8s")
    company_id = world["company"].id
    assert [row.id for row in learning.suggest(db, company_id, [world["docker_node"].id])] == [docker.id]
    assert learning.suggest(db, company_id, [world["private_node"].id]) == []
    assert learning.suggest(db, company_id, []) == []


def test_suggest_never_crosses_companies(db, world):
    resource(db, world, node="foreign_node", company_id=world["other"].id)
    assert learning.suggest(db, world["company"].id, [world["foreign_node"].id]) == []


# 3. AI picks IDs and code resolves them


def test_the_prompt_receives_ids_and_code_resolves_title_and_url(db, world, api):
    row = resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id]))
    draft = feedback.draft(db, application, None)
    prompt = fake.last_messages()[-1]["content"]
    assert f"- id={row.id}: Docker Foundations" in prompt and LINK not in prompt
    assert "Docker Foundations" in draft.draft and LINK in draft.draft and "Suggested learning" in draft.draft
    assert feedback.guard(draft.draft, application) == []

    reply = api.post(f"/api/companies/{world['company'].id}/feedback/approve", headers=hr(world),
                     json={"items": [{"application_id": application.id, "version": read_version(api, world, application.id)}]})
    assert reply.status_code == 200, reply.text
    body = api.get(f"/api/applications/{application.id}/feedback", headers=auth_header(CANDIDATE_EMAIL)).json()
    assert body["learning"] == [{"id": row.id, "title": "Docker Foundations", "url": LINK, "provider": "Acme Academy",
                                 "language": "en"}]
    assert LINK not in body["message"] and "Suggested learning" not in body["message"]
    assert GOOD_MESSAGE in body["message"]


def test_unknown_ids_are_dropped_and_the_rest_of_the_draft_stands(db, world):
    row = resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id, 999_999, row.id]))
    draft = feedback.draft(db, application, None)
    assert draft.draft.count(LINK) == 1
    assert "999999" not in draft.draft and GOOD_MESSAGE in draft.draft


def test_only_unknown_ids_means_no_learning_section(db, world):
    resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [999_999]))
    draft = feedback.draft(db, application, None)
    assert "Suggested learning" not in draft.draft and LINK not in draft.draft


def test_a_real_id_for_another_skill_or_company_is_dropped(db, world):
    other_skill = resource(db, world, node="k8s_node", title="K8s Course", link=LINK + "/k8s")
    foreign = resource(db, world, node="foreign_node", company_id=world["other"].id, title="Foreign", link=LINK + "/foreign")
    resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [other_skill.id, foreign.id]))
    draft = feedback.draft(db, application, None)
    assert "K8s Course" not in draft.draft and "Foreign" not in draft.draft and LINK not in draft.draft


def test_a_gap_with_nothing_verified_for_it_offers_only_its_own_rows(db, world):
    resource(db, world, node="k8s_node", title="K8s", link=LINK + "/k8s")
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world))
    feedback.draft(db, application, None)
    assert "<learning>" not in fake.last_messages()[-1]["content"]


def test_a_catalogue_row_is_offered_for_a_gap_not_for_a_strength(db, world):
    world["requirements"][0].node_id = world["k8s_node"].id
    db.commit()
    resource(db, world, node="k8s_node", title="K8s", link=LINK + "/k8s")
    docker = resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [docker.id]))
    feedback.draft(db, application, None)
    prompt = fake.last_messages()[-1]["content"]
    assert f"id={docker.id}:" in prompt and "K8s" not in prompt


def test_a_confidential_skill_is_never_offered(db, world):
    world["requirements"][1].node_id = world["private_node"].id
    db.commit()
    row = resource(db, world, node="private_node", title="Falcon training", link=LINK + "/falcon")
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id]))
    draft = feedback.draft(db, application, None)
    assert "Falcon training" not in fake.last_messages()[-1]["content"] and "Falcon training" not in draft.draft


@pytest.mark.parametrize("title", ["Project Falcon deep dive", "For those who did not meet the bar"])
def test_a_catalogue_title_that_would_break_the_guard_is_not_offered(db, world, title):
    row = resource(db, world, title=title)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id]))
    draft = feedback.draft(db, application, None)
    assert title not in draft.draft and GOOD_MESSAGE in draft.draft


@pytest.mark.parametrize("message", [
    "See https://invented.example/docker to learn.",
    f"See {LINK}/invented to learn.",
    f"See {LINK} to learn, which is a real row but not the AI's to write.",
    "Try the Docker Mastery course on Udemy.",
    'Try "Docker Mastery" to learn.',
])
def test_an_invented_link_or_course_in_the_message_never_appears(db, world, message):
    row = resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id], message=message))
    fake.enqueue("rejection_feedback", output(world, [row.id], message=message))
    draft = feedback.draft(db, application, None)
    assert draft.draft == feedback.template("en", "Backend")
    for invented in ("invented", "Mastery", "Udemy"):
        assert invented not in draft.draft


def test_a_word_from_a_public_requirement_is_not_taken_for_an_invented_course(db, world):
    world["requirements"][2].text = "AWS certification"
    db.commit()
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, message="Earning an AWS certification would help here."))
    assert "AWS certification" in feedback.draft(db, application, None).draft


def test_hr_may_keep_a_catalogue_link_but_not_add_another(db, world, api):
    row = resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id]))
    feedback.draft(db, application, None)
    tail = f"/api/companies/{world['company'].id}/applications/{application.id}/feedback"
    assert api.patch(tail, headers=hr(world), json={"draft": f"Please see {LINK}."}).status_code == 200
    assert api.patch(tail, headers=hr(world), json={"draft": f"Please see {LINK}/other."}).status_code == 422
    assert api.patch(tail, headers=hr(world), json={"draft": f"Please see {LINK}.evil.example"}).status_code == 422
    assert api.patch(tail, headers=hr(world), json={"draft": "Please see https://other.example/x"}).status_code == 422
    assert api.patch(tail, headers=hr(world), json={"draft": "Please see https://other​.example/x"}).status_code == 422


def test_removing_a_line_removes_the_suggestion(db, world, api):
    row = resource(db, world)
    second = resource(db, world, title="Docker Two", link=LINK + "/two")
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id, second.id]))
    text = feedback.draft(db, application, None).draft
    kept = "\n".join(line for line in text.splitlines() if "Docker Two" not in line)
    tail = f"/api/companies/{world['company'].id}/applications/{application.id}/feedback"
    response = api.patch(tail, headers=hr(world), json={"draft": kept})
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["learning"]] == [row.id]


def test_a_catalogue_row_deleted_after_drafting_stops_the_send(db, world, api):
    row = resource(db, world)
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [row.id]))
    feedback.draft(db, application, None)
    db.delete(db.get(LearningResource, row.id))
    db.commit()
    reply = api.post(f"/api/companies/{world['company'].id}/feedback/approve", headers=hr(world),
                     json={"items": [{"application_id": application.id, "version": read_version(api, world, application.id)}]})
    assert reply.status_code == 422


def test_the_demo_responder_uses_catalogue_ids(db, world):
    fake_demo.install()
    row = resource(db, world)
    application = interviewed(db, world)
    draft = feedback.draft(db, application, None)
    assert LINK in draft.draft and row.title in draft.draft
    assert feedback.guard(draft.draft, application) == []


# 4. No catalogue, no section


def test_no_catalogue_means_no_learning_section(db, world):
    application = interviewed(db, world)
    fake.enqueue("rejection_feedback", output(world, [1, 2, 3]))
    draft = feedback.draft(db, application, None)
    assert "<learning>" not in fake.last_messages()[-1]["content"]
    assert "Suggested learning" not in draft.draft and "http" not in draft.draft


def test_the_learning_heading_follows_the_language(db, world):
    row = resource(db, world)
    application = interviewed(db, world, language="ko")
    fake.enqueue("rejection_feedback", output(world, [row.id], message="이야기를 나눠 주셔서 감사합니다."))
    assert "추천 학습" in feedback.draft(db, application, None).draft


def test_a_template_has_no_learning_section(db, world):
    resource(db, world)
    application = interviewed(db, world)

    def boom(_system, _messages, _schema):
        raise RuntimeError("down")

    fake.register("rejection_feedback", boom)
    draft = feedback.draft(db, application, None)
    assert LINK not in draft.draft


def read_version(api, world, application_id):
    reply = api.get(f"/api/companies/{world['company'].id}/applications/{application_id}/feedback", headers=hr(world))
    return reply.json()["version"]
