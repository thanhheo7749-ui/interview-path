from app.services.question_planner import plan_next_question


def test_plan_next_question_returns_deep_dive_followup_for_shallow_previous_answer():
    decision = plan_next_question(
        planner_seed={"priority_topics": ["Caching", "System Design"]},
        planner_state={"Caching": "probing"},
        previous_turn={
            "turn_evaluation": {
                "correctness": 0.6,
                "depth": 0.3,
                "communication": 0.7,
                "topic_relevance": 0.8,
            }
        },
        transcript={"low_quality_flag": False},
    )

    assert decision["next_topic"] == "Caching"
    assert decision["followup_mode"] == "deep_dive"
    assert decision["why_selected"] == "previous_answer_shallow"
