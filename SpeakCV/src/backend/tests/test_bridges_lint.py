import json

import numpy as np
import pytest

from app.ai import gateway
from app.ai.providers import fake
from app.brain import fake_demo, vectors
from app.bridges import jd_studio, lint
from tests.helpers_jd import line, make_draft, make_world


@pytest.fixture(autouse=True)
def _demo_responders():
    fake_demo.install()


@pytest.fixture
def world(db):
    return make_world(db)


def _checks(report, check):
    return [i for i in report.issues if i.check == check]


def test_discrimination_in_any_language_blocks_and_names_the_line(db, world):
    draft = make_draft(db, world.company.id, [
        line("l1", [world.role.id], en="We build APIs"),
        line("l2", [world.role.id], en="Fine", vi="Dưới 30 tuổi", ko="Fine"),
        line("l3", [world.role.id], en="Fine", vi="Fine", ko="남성 우대"),
    ])
    report = lint.run(db, draft)

    assert report.blocks_publish
    assert {i.line_id for i in _checks(report, "discrimination")} == {"l2", "l3"}
    assert all(i.severity == "block" for i in _checks(report, "discrimination"))
    assert draft.lint[0]["check"] == "discrimination"


def test_a_line_without_source_or_confirmation_blocks(db, world):
    confirmed = line("l2", [], en="Free lunch", hr_confirmed={"user_id": world.hr.id, "at": "2026-11-02T00:00:00Z"})
    draft = make_draft(db, world.company.id, [line("l1", [], en="Free lunch"), confirmed,
                                              line("l3", [987654], en="Gone")])
    report = lint.run(db, draft)

    assert report.blocks_publish
    assert {i.line_id for i in _checks(report, "no_source")} == {"l1", "l3"}


def test_a_line_citing_a_node_candidates_cannot_see_blocks(db, world):
    draft = make_draft(db, world.company.id, [line("l1", [world.note.id], en="Fine")])
    assert {i.line_id for i in _checks(lint.run(db, draft), "no_source")} == {"l1"}


def _near_duplicate_line(world, number="15"):
    return line("l1", [world.role.id], en=f"Employees get {number} days of annual leave", vi="Nghi phep", ko="Yeonca")


def test_a_line_that_conflicts_with_a_graph_fact_blocks_until_marked_different_scope(db, world):
    draft = make_draft(db, world.company.id, [_near_duplicate_line(world)])
    texts = [draft.lines[0]["text"]["en"], world.leave.title]
    first, second = (np.asarray(v) for v in gateway.embed(texts, "query", "t").vectors)
    assert float(first @ second) >= 0.80  # the fake embedding must make these neighbours

    fake.enqueue("lint_conflict_check", json.dumps({"same_topic": True}))
    report = lint.run(db, draft)
    conflicts = _checks(report, "conflict")
    assert report.blocks_publish and [(i.line_id, i.severity) for i in conflicts] == [("l1", "block")]
    assert conflicts[0].node_id == world.leave.id and world.leave.title not in conflicts[0].message

    edited = jd_studio.edit_lines(db, draft, [{"id": "l1", "conflict_dismissed": [world.leave.id]}], world.hr.id)
    assert edited.lines[0]["conflict_dismissed"] == [world.leave.id]
    fake.enqueue("lint_conflict_check", json.dumps({"same_topic": True}))
    assert not _checks(lint.run(db, edited), "conflict")


def test_the_same_value_or_another_topic_is_no_conflict(db, world):
    asked = []

    def always_same_topic(*_):
        asked.append(1)
        return json.dumps({"same_topic": True})

    same = make_draft(db, world.company.id, [_near_duplicate_line(world, "12")])
    fake.register("lint_conflict_check", always_same_topic)
    assert not _checks(lint.run(db, same), "conflict")
    assert asked == []  # the value matches, so code settles it without asking
    fake_demo.install()

    other_topic = make_draft(db, world.company.id, [_near_duplicate_line(world)])
    assert not _checks(lint.run(db, other_topic), "conflict")  # the demo model says not the same topic

    unit = make_draft(db, world.company.id, [_near_duplicate_line(world, "12").copy() | {
        "text": {"en": "Employees get 12 weeks of annual leave", "vi": "x", "ko": "y"}}])
    fake.enqueue("lint_conflict_check", json.dumps({"same_topic": True}))
    assert _checks(lint.run(db, unit), "conflict")  # the number matches but the unit does not


def test_seven_must_haves_warn_and_six_do_not(db, world):
    def lines(count):
        return [line(f"l{i}", [world.python.id], en=f"Skill {'abcdefg'[i]}", is_requirement=True, must_have=True)
                for i in range(count)]

    seven = lint.run(db, make_draft(db, world.company.id, lines(7)))
    assert [(i.check, i.severity) for i in seven.issues] == [("must_have_count", "warning")]
    assert not seven.blocks_publish
    assert lint.run(db, make_draft(db, world.company.id, lines(6))).issues == []


def test_a_clean_draft_does_not_block(db, world):
    draft = make_draft(db, world.company.id, [line("l1", [world.role.id], en="We build APIs")])
    report = lint.run(db, draft)
    assert report.issues == [] and report.blocks_publish is False and draft.lint == []


def test_classifier_failure_blocks_until_a_rerun_succeeds_or_hr_acknowledges(db, world):
    draft = make_draft(db, world.company.id, [line("l1", [world.role.id], en="We build APIs")])

    def boom(*_):
        raise RuntimeError("down")

    fake.register("discrimination_check", boom)
    report = lint.run(db, draft)
    assert report.blocks_publish and [(i.check, i.line_id) for i in report.issues] == [("unchecked", "l1")]

    fake_demo.install()  # the classifier is back
    assert not lint.run(db, draft).blocks_publish

    fake.register("discrimination_check", boom)
    assert lint.run(db, draft).blocks_publish
    acknowledged = lint.acknowledge_unchecked(db, draft, world.hr.id)
    report = lint.run(db, acknowledged)
    assert not report.blocks_publish
    assert [(i.check, i.severity) for i in report.issues] == [("unchecked", "warning")]
    assert acknowledged.lines[0]["unchecked_ack"]["user_id"] == world.hr.id

    # An edit voids the acknowledgement.
    edited = jd_studio.edit_lines(db, acknowledged, [{"id": "l1", "text": {"en": "We build things"}}], world.hr.id)
    assert edited.lint[0]["severity"] == "block"
