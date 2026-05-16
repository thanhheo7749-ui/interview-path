from statistics import mean
from typing import Any


DEFAULT_TOPIC = "General Technical Fit"
DEFAULT_IMPROVEMENT = "Communication clarity"
NO_ANSWER_VALUES = {"Ứng viên chưa trả lời", "Candidate did not answer", ""}
EMPTY_FINAL_SCORES = {
    "correctness": None,
    "depth": None,
    "communication": None,
    "topic_relevance": None,
}


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def _to_five_point(score: float) -> int:
    scaled = _clamp_score(score) * 5
    rounded = int(scaled + 0.5)
    return max(1, min(5, rounded))


def _to_report_score(score: float) -> int:
    return _to_five_point(score)


def _has_real_answer(turn: dict[str, Any]) -> bool:
    candidate_answer = str(turn.get("candidate_answer") or "").strip()
    return candidate_answer not in NO_ANSWER_VALUES


def _metric_average(turn_records: list[dict[str, Any]], key: str) -> float:
    scores = [float(turn.get(key, 0.0)) for turn in turn_records]
    return mean(scores) if scores else 0.0


def _unique_topics(turn_records: list[dict[str, Any]], predicate) -> list[str]:
    topics: list[str] = []
    for turn in turn_records:
        topic = str(turn.get("topic") or DEFAULT_TOPIC)
        if predicate(turn) and topic not in topics:
            topics.append(topic)
    return topics


def build_structured_report(turn_records: list[dict[str, Any]]) -> dict[str, Any]:
    answered_turns = [turn for turn in turn_records if _has_real_answer(turn)]
    if not answered_turns:
        return {
            "final_scores": EMPTY_FINAL_SCORES,
            "top_skills_to_improve": [],
            "strong_topics": [],
            "weak_topics": [],
        }

    final_scores = {
        "correctness": _to_report_score(_metric_average(answered_turns, "correctness")),
        "depth": _to_report_score(_metric_average(answered_turns, "depth")),
        "communication": _to_report_score(_metric_average(answered_turns, "communication")),
        "topic_relevance": _to_report_score(_metric_average(answered_turns, "topic_relevance")),
    }

    weak_topics = _unique_topics(
        answered_turns,
        lambda turn: float(turn.get("depth", 0.0)) <= 0.4
        or float(turn.get("correctness", 0.0)) <= 0.5,
    )
    strong_topics = _unique_topics(
        answered_turns,
        lambda turn: float(turn.get("correctness", 0.0)) >= 0.7
        and float(turn.get("communication", 0.0)) >= 0.6,
    )

    top_skills_to_improve = weak_topics[:]
    while len(top_skills_to_improve) < 3:
        if DEFAULT_IMPROVEMENT not in top_skills_to_improve:
            top_skills_to_improve.append(DEFAULT_IMPROVEMENT)
        else:
            top_skills_to_improve.append(DEFAULT_TOPIC)
        top_skills_to_improve = list(dict.fromkeys(top_skills_to_improve))

    return {
        "final_scores": final_scores,
        "top_skills_to_improve": top_skills_to_improve[:3],
        "strong_topics": strong_topics[:3],
        "weak_topics": weak_topics[:3],
    }
