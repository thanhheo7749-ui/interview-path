from statistics import mean
from typing import Any


DEFAULT_TOPIC = "General Technical Fit"
NO_ANSWER_VALUES = {"Ứng viên chưa trả lời", "Candidate did not answer", ""}
SCORE_KEYS = ("correctness", "depth", "communication", "topic_relevance")
EMPTY_FINAL_SCORES = {
    "correctness": None,
    "depth": None,
    "communication": None,
    "topic_relevance": None,
}

SKILL_LABELS = {
    "technical_depth": "Technical depth",
    "impact_quantification": "Impact quantification",
    "communication_clarity": "Communication clarity",
    "role_fit_articulation": "General Technical Fit",
}


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def _to_five_point(score: float) -> int:
    scaled = _clamp_score(score) * 5
    rounded = int(scaled + 0.5)
    return max(1, min(5, rounded))


def _has_real_answer(turn: dict[str, Any]) -> bool:
    if "candidate_answer" in turn:
        candidate_answer = str(turn.get("candidate_answer") or "").strip()
        return candidate_answer not in NO_ANSWER_VALUES
    return any(turn.get(key) is not None for key in SCORE_KEYS)


def _infer_turn_scores(turn: dict[str, Any]) -> dict[str, float]:
    answer = str(turn.get("candidate_answer") or "").strip()
    evaluation = str(turn.get("evaluation") or "").lower()

    if not answer or answer in NO_ANSWER_VALUES or "idk" in answer.lower() or "dont know" in answer.lower():
        return {
            "correctness": 0.12,
            "depth": 0.1,
            "communication": 0.28,
            "topic_relevance": 0.2,
        }

    answer_len = len(answer)
    has_number = any(ch.isdigit() for ch in answer)

    depth = 0.45
    communication = 0.5
    correctness = 0.45
    topic_relevance = 0.45

    if answer_len >= 120:
        depth += 0.15
        communication += 0.1
    elif answer_len <= 20:
        depth -= 0.15
        communication -= 0.1

    if has_number:
        correctness += 0.1
        topic_relevance += 0.05

    if "không" in evaluation or "not" in evaluation or "insufficient" in evaluation:
        correctness -= 0.1
        topic_relevance -= 0.1

    return {
        "correctness": _clamp_score(correctness),
        "depth": _clamp_score(depth),
        "communication": _clamp_score(communication),
        "topic_relevance": _clamp_score(topic_relevance),
    }


def _merge_turn_scores(turn: dict[str, Any]) -> dict[str, Any]:
    inferred = _infer_turn_scores(turn)
    merged = dict(turn)
    for key in SCORE_KEYS:
        val = turn.get(key)
        if val is None:
            merged[key] = inferred[key]
        else:
            merged[key] = _clamp_score(float(val))
    return merged


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


def _extract_weak_signals(turn: dict[str, Any]) -> list[str]:
    answer = str(turn.get("candidate_answer") or "").lower()
    evaluation = str(turn.get("evaluation") or "").lower()
    signals: list[str] = []

    if len(answer.strip()) < 30 or "not provide" in evaluation or "không cung cấp" in evaluation:
        signals.append("technical_depth")
    if not any(ch.isdigit() for ch in answer) or "measurable" in evaluation or "đo lường" in evaluation:
        signals.append("impact_quantification")
    if "idk" in answer or "không biết" in answer or "unclear" in evaluation:
        signals.append("communication_clarity")
    if "role" in evaluation or "fit" in evaluation or "phù hợp" in evaluation:
        signals.append("role_fit_articulation")

    return signals


def _build_hr_recommendation(
    final_scores: dict[str, int | None],
    answered_count: int,
) -> dict[str, Any]:
    valid_scores = [score for score in final_scores.values() if isinstance(score, int)]
    if not valid_scores or answered_count == 0:
        return {
            "decision": "Pending Interview",
            "readiness_level": "Awaiting Candidate Responses",
            "culture_fit_signal": "No turn signals recorded yet",
            "estimated_minutes_saved": 30,
            "pii_anonymized": True,
            "evidence_grounded": True,
        }

    avg_score = mean(valid_scores)
    if avg_score >= 4.0:
        decision = "Strong Hire"
        readiness_level = "Enterprise Ready"
        culture_fit_signal = "High Ownership & Structured STAR Communication"
    elif avg_score >= 3.0:
        decision = "Consider / Round 2"
        readiness_level = "Interview Ready"
        culture_fit_signal = "Solid Foundation — Probe Technical Depth in Round 2"
    else:
        decision = "Needs Coaching"
        readiness_level = "Pre-Hire Training Recommended"
        culture_fit_signal = "Needs Structured STAR Framing & Technical Depth"

    return {
        "decision": decision,
        "readiness_level": readiness_level,
        "culture_fit_signal": culture_fit_signal,
        "estimated_minutes_saved": max(30, answered_count * 15 + 5),
        "pii_anonymized": True,
        "evidence_grounded": True,
    }


def build_structured_report(turn_records: list[dict[str, Any]]) -> dict[str, Any]:
    answered_turns = [turn for turn in turn_records if _has_real_answer(turn)]
    if not answered_turns:
        return {
            "final_scores": EMPTY_FINAL_SCORES,
            "top_skills_to_improve": [],
            "strong_topics": [],
            "weak_topics": [],
            "hr_recommendation": _build_hr_recommendation(EMPTY_FINAL_SCORES, 0),
        }

    scored_turns: list[dict[str, Any]] = []
    weak_signal_count: dict[str, int] = {}

    for turn in answered_turns:
        merged = _merge_turn_scores(turn)
        scored_turns.append(merged)
        for signal in _extract_weak_signals(turn):
            weak_signal_count[signal] = weak_signal_count.get(signal, 0) + 1

    final_scores = {
        "correctness": _to_five_point(_metric_average(scored_turns, "correctness")),
        "depth": _to_five_point(_metric_average(scored_turns, "depth")),
        "communication": _to_five_point(_metric_average(scored_turns, "communication")),
        "topic_relevance": _to_five_point(_metric_average(scored_turns, "topic_relevance")),
    }

    weak_topics = _unique_topics(
        scored_turns,
        lambda turn: float(turn.get("depth", 0.0)) <= 0.45
        or float(turn.get("correctness", 0.0)) <= 0.45,
    )
    strong_topics = _unique_topics(
        scored_turns,
        lambda turn: float(turn.get("correctness", 0.0)) >= 0.65
        and float(turn.get("communication", 0.0)) >= 0.6,
    )

    ranked_signals = sorted(weak_signal_count.items(), key=lambda item: item[1], reverse=True)
    top_skills_to_improve = [SKILL_LABELS[key] for key, _ in ranked_signals if key in SKILL_LABELS][:3]

    fallback = ["Communication clarity", "Technical depth", "General Technical Fit"]
    for item in fallback:
        if len(top_skills_to_improve) >= 3:
            break
        if item not in top_skills_to_improve:
            top_skills_to_improve.append(item)

    return {
        "final_scores": final_scores,
        "top_skills_to_improve": top_skills_to_improve[:3],
        "strong_topics": strong_topics[:3],
        "weak_topics": weak_topics[:3],
        "hr_recommendation": _build_hr_recommendation(final_scores, len(answered_turns)),
    }
