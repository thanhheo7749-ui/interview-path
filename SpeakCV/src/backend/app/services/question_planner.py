from typing import Any


SHALLOW_DEPTH_THRESHOLD = 0.4
STRONG_CORRECTNESS_THRESHOLD = 0.75
DEFAULT_TOPIC = "General Technical Fit"


def _next_priority_topic(priority_topics: list[str], planner_state: dict[str, str]) -> str:
    for topic in priority_topics:
        if planner_state.get(topic, "unasked") != "completed":
            return topic
    return priority_topics[0] if priority_topics else DEFAULT_TOPIC


def plan_next_question(
    planner_seed: dict[str, Any],
    planner_state: dict[str, str],
    previous_turn: dict[str, Any],
    transcript: dict[str, Any],
) -> dict[str, Any]:
    priority_topics = planner_seed.get("priority_topics", [])
    next_topic = _next_priority_topic(priority_topics, planner_state)
    current_state = planner_state.get(next_topic, "probing")
    turn_eval = previous_turn.get("turn_evaluation", {})

    if transcript.get("low_quality_flag"):
        return {
            "next_topic": next_topic,
            "followup_mode": "clarify",
            "why_selected": "clarify_low_quality_transcript",
            "topic_state": current_state,
            "question_strategy": "clarify",
        }

    if turn_eval.get("depth", 0.0) <= SHALLOW_DEPTH_THRESHOLD:
        return {
            "next_topic": next_topic,
            "followup_mode": "deep_dive",
            "why_selected": "previous_answer_shallow",
            "topic_state": current_state,
            "question_strategy": "deep_dive",
        }

    if turn_eval.get("correctness", 0.0) >= STRONG_CORRECTNESS_THRESHOLD:
        return {
            "next_topic": next_topic,
            "followup_mode": "stretch",
            "why_selected": "strong_performance_raise_difficulty",
            "topic_state": "strong",
            "question_strategy": "stretch",
        }

    return {
        "next_topic": next_topic,
        "followup_mode": "probe",
        "why_selected": "gap_in_jd",
        "topic_state": current_state,
        "question_strategy": "opening",
    }


__all__ = ["plan_next_question"]
