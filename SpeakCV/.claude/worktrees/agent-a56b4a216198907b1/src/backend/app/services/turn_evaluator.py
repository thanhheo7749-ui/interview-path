import re
from typing import Dict


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", (text or "").lower())


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, round(value, 2)))


STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with",
    "is", "are", "was", "were", "i", "we", "you", "it", "my", "our"
}


TECHNICAL_DEPTH_WORDS = {
    "because", "implemented", "designed", "optimized", "measured", "scaled",
    "latency", "performance", "tradeoff", "tradeoffs", "architecture", "database",
    "api", "apis", "cache", "caching", "auth", "testing", "deployment"
}


COMMUNICATION_FILLERS = {"um", "uh", "like", "youknow", "basically"}


def evaluate_turn(answer_text: str, target_topic: str) -> Dict[str, float]:
    answer_tokens = _tokenize(answer_text)
    topic_tokens = [token for token in _tokenize(target_topic) if token not in STOP_WORDS]

    if not answer_tokens:
        return {"correctness": 0.0, "depth": 0.0, "communication": 0.0}

    answer_token_set = set(answer_tokens)
    topic_overlap = sum(1 for token in set(topic_tokens) if token in answer_token_set)
    overlap_ratio = topic_overlap / max(len(set(topic_tokens)), 1)

    technical_hits = sum(1 for token in answer_tokens if token in TECHNICAL_DEPTH_WORDS)
    sentence_count = max(1, len(re.findall(r"[.!?]", answer_text)) or 1)
    word_count = len(answer_tokens)
    unique_ratio = len(answer_token_set) / max(word_count, 1)
    filler_hits = sum(1 for token in answer_tokens if token in COMMUNICATION_FILLERS)

    correctness = _clamp(0.2 + (overlap_ratio * 0.8))

    depth = _clamp(
        (min(word_count, 30) / 30) * 0.65
        + min(technical_hits, 4) * 0.12
        + min(sentence_count, 3) * 0.05
    )

    communication = _clamp(
        0.28
        + min(word_count, 25) / 25 * 0.3
        + unique_ratio * 0.22
        - min(filler_hits, 3) * 0.08
    )

    return {
        "correctness": correctness,
        "depth": depth,
        "communication": communication,
    }


def build_turn_analysis(answer_text: str, target_topic: str, analysis: Dict[str, str]) -> Dict[str, object]:
    turn_evaluation = evaluate_turn(answer_text, target_topic)
    merged_analysis: Dict[str, object] = {
        **analysis,
        "turn_evaluation": turn_evaluation,
    }

    if turn_evaluation["depth"] <= 0.4:
        merged_analysis["prompt_hint"] = (
            "Ask for one concrete example, technical detail, or measurable result to deepen the answer."
        )

    return merged_analysis


def extract_last_ai_question(chat_history: list) -> str:
    for item in reversed(chat_history or []):
        if isinstance(item, dict) and item.get("role") == "assistant":
            return str(item.get("content", "")).strip()
    return ""


def resolve_turn_target_topic(chat_history: list, fallback_topic: str) -> str:
    last_question = extract_last_ai_question(chat_history)
    return last_question or fallback_topic


__all__ = [
    "build_turn_analysis",
    "evaluate_turn",
    "extract_last_ai_question",
    "resolve_turn_target_topic",
]
