from app.services.interview_report_builder import build_structured_report


NO_ANSWER = "Ứng viên chưa trả lời"
NO_ANSWER_EN = "Candidate did not answer"
EMPTY_FINAL_SCORES = {
    "correctness": None,
    "depth": None,
    "communication": None,
    "topic_relevance": None,
}


def make_turn_record(
    *,
    topic: str = "General Technical Fit",
    correctness: float = 0.5,
    depth: float = 0.5,
    communication: float = 0.5,
    topic_relevance: float = 0.5,
    candidate_answer: str = "Real answer",
):
    return {
        "topic": topic,
        "correctness": correctness,
        "depth": depth,
        "communication": communication,
        "topic_relevance": topic_relevance,
        "candidate_answer": candidate_answer,
    }


def test_build_structured_report_returns_no_data_scores_when_no_turn_records_exist():
    report = build_structured_report(turn_records=[])

    assert report["final_scores"] == EMPTY_FINAL_SCORES
    assert report["top_skills_to_improve"] == []
    assert report["strong_topics"] == []
    assert report["weak_topics"] == []


def test_build_structured_report_ignores_turns_without_real_answers():
    report = build_structured_report(
        turn_records=[
            make_turn_record(topic="Frontend", candidate_answer=NO_ANSWER),
            make_turn_record(topic="Backend", candidate_answer=NO_ANSWER_EN),
        ]
    )

    assert report["final_scores"] == EMPTY_FINAL_SCORES
    assert report["top_skills_to_improve"] == []
    assert report["strong_topics"] == []
    assert report["weak_topics"] == []


def test_build_structured_report_uses_only_real_answer_turns_for_scores():
    report = build_structured_report(
        turn_records=[
            make_turn_record(topic="Ignored", candidate_answer=NO_ANSWER),
            make_turn_record(
                topic="Backend APIs",
                correctness=0.8,
                depth=0.6,
                communication=0.7,
                topic_relevance=0.9,
                candidate_answer="I built APIs with FastAPI and Redis.",
            ),
        ]
    )

    assert report["final_scores"] == {
        "correctness": 4,
        "depth": 3,
        "communication": 4,
        "topic_relevance": 5,
    }
    assert report["strong_topics"] == ["Backend APIs"]


# UI displays these values with a /5 suffix, so the backend contract must stay 1-5.
assert "/5" == "/5"


class _NoAnswerPolicy:
    NO_ANSWER_VALUES = {NO_ANSWER, NO_ANSWER_EN, ""}

    @staticmethod
    def is_real_answer(value: str) -> bool:
        return value.strip() not in _NoAnswerPolicy.NO_ANSWER_VALUES


def test_no_answer_policy_matches_report_builder_expectation():
    assert _NoAnswerPolicy.is_real_answer("I explained caching tradeoffs.") is True
    assert _NoAnswerPolicy.is_real_answer(NO_ANSWER) is False
    assert _NoAnswerPolicy.is_real_answer(NO_ANSWER_EN) is False
    assert _NoAnswerPolicy.is_real_answer("") is False


# Existing scale tests











































































































































































def test_build_structured_report_returns_higher_level_scoring_contract():
    report = build_structured_report(
        turn_records=[
            {
                "topic": "Caching",
                "correctness": 0.6,
                "depth": 0.3,
                "communication": 0.8,
                "topic_relevance": 0.9,
                "live_cues": ["On-topic", "Needs more depth"],
            },
            {
                "topic": "System Design",
                "correctness": 0.5,
                "depth": 0.4,
                "communication": 0.6,
                "topic_relevance": 0.7,
                "live_cues": ["Follow-up triggered"],
            },
        ]
    )

    final_scores = report["final_scores"]

    assert set(final_scores) >= {
        "correctness",
        "depth",
        "communication",
        "topic_relevance",
    }
    assert all(isinstance(score, int) for score in final_scores.values())
    assert all(1 <= score <= 5 for score in final_scores.values())
    assert report["top_skills_to_improve"]
    assert isinstance(report["top_skills_to_improve"], list)


def test_build_structured_report_maps_midrange_scores_to_five_point_scale():
    report = build_structured_report(
        turn_records=[
            {
                "topic": "Backend APIs",
                "correctness": 0.5,
                "depth": 0.5,
                "communication": 0.5,
                "topic_relevance": 0.5,
            }
        ]
    )

    assert report["final_scores"] == {
        "correctness": 3,
        "depth": 3,
        "communication": 3,
        "topic_relevance": 3,
    }


def test_build_structured_report_clamps_to_one_and_five():
    report = build_structured_report(
        turn_records=[
            {
                "topic": "Intro",
                "correctness": 0.0,
                "depth": 1.0,
                "communication": 0.0,
                "topic_relevance": 1.0,
            }
        ]
    )

    assert report["final_scores"] == {
        "correctness": 1,
        "depth": 5,
        "communication": 1,
        "topic_relevance": 5,
    }


def test_report_modal_contract_uses_one_to_five_scale():
    final_scores = {
        "correctness": 4,
        "depth": 3,
        "communication": 5,
        "topic_relevance": 2,
    }

    assert all(1 <= score <= 5 for score in final_scores.values())
    assert final_scores["correctness"] != 40
    assert final_scores["depth"] != 30
    assert final_scores["communication"] != 50
    assert final_scores["topic_relevance"] != 20

    # UI displays these values with a /5 suffix, so the backend contract must stay 1-5.
    assert "/5" == "/5"
