from app.services.turn_evaluator import (
    build_turn_analysis,
    evaluate_turn,
    extract_last_ai_question,
    resolve_turn_target_topic,
)


PROMPT_HINT = "Ask for one concrete example, technical detail, or measurable result to deepen the answer."


def test_evaluate_turn_scores_strong_relevant_answer():
    result = evaluate_turn(
        "I used Python and FastAPI to build REST APIs, added Redis caching, and improved response time by 40 percent.",
        "Python FastAPI backend APIs",
    )

    assert result["correctness"] >= 0.7
    assert result["depth"] >= 0.7
    assert result["communication"] >= 0.7


def test_evaluate_turn_marks_shallow_short_answer():
    result = evaluate_turn("Python.", "Python backend development")

    assert result["depth"] <= 0.4
    assert result["communication"] <= 0.6


def test_evaluate_turn_marks_off_topic_answer_lower_correctness():
    result = evaluate_turn(
        "I enjoy team lunches and office events more than coding tasks.",
        "database indexing and query optimization",
    )

    assert result["correctness"] <= 0.4


def test_build_turn_analysis_adds_prompt_hint_for_shallow_depth():
    analysis = {"intent": "answering", "confidence_level": "Confident"}

    result = build_turn_analysis("I used Python.", "Python backend development", analysis)

    assert result["turn_evaluation"]["depth"] <= 0.4
    assert result["prompt_hint"] == PROMPT_HINT
    assert result["intent"] == "answering"
    assert result["confidence_level"] == "Confident"


def test_build_turn_analysis_skips_prompt_hint_when_depth_is_not_shallow():
    result = build_turn_analysis(
        "I built Python APIs with FastAPI, handled auth, and optimized SQL queries for lower latency.",
        "Python backend development",
        {"intent": "answering", "confidence_level": "Confident"},
    )

    assert result["turn_evaluation"]["depth"] >= 0.5
    assert "prompt_hint" not in result


def test_extract_last_ai_question_returns_latest_assistant_message():
    chat_history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Tell me about your API caching approach."},
        {"role": "user", "content": "I used Redis."},
    ]

    assert extract_last_ai_question(chat_history) == "Tell me about your API caching approach."


def test_resolve_turn_target_topic_falls_back_when_no_assistant_question_exists():
    chat_history = [{"role": "user", "content": "I used Redis."}]

    assert resolve_turn_target_topic(chat_history, "backend caching") == "backend caching"


def test_resolve_turn_target_topic_prefers_latest_assistant_question():
    chat_history = [
        {"role": "assistant", "content": "What tradeoffs did you consider?"},
        {"role": "user", "content": "Latency vs complexity."},
    ]

    assert resolve_turn_target_topic(chat_history, "backend caching") == "What tradeoffs did you consider?"


def test_build_turn_analysis_keeps_existing_analysis_fields_without_mutating_input():
    analysis = {"intent": "answering", "confidence_level": "Confident", "filler_count": 0}

    result = build_turn_analysis(
        "I built APIs with FastAPI and Redis caching.",
        "backend caching",
        analysis,
    )

    assert analysis == {"intent": "answering", "confidence_level": "Confident", "filler_count": 0}
    assert result is not analysis
    assert result["intent"] == "answering"
    assert result["confidence_level"] == "Confident"
    assert result["filler_count"] == 0
    assert {"correctness", "depth", "communication"}.issubset(result["turn_evaluation"])


def test_build_turn_analysis_returns_structured_data_only_for_empty_answer():
    result = build_turn_analysis(
        "",
        "backend caching",
        {"intent": "answering", "confidence_level": "Confident"},
    )

    assert set(result.keys()) == {"intent", "confidence_level", "turn_evaluation", "prompt_hint"}
    assert result["turn_evaluation"] == {
        "correctness": 0.0,
        "depth": 0.0,
        "communication": 0.0,
    }
    assert result["prompt_hint"] == PROMPT_HINT
    assert "TURN SIGNALS" not in str(result)
    assert "If the answer is shallow" not in str(result)
    assert "prompt_context" not in result
    assert "prompt_hint_rule" not in result
    assert "target_topic" not in result
    assert "chat_history" not in result
    assert "next_topic" not in result


def test_build_turn_analysis_returns_scores_without_prompt_formatting_for_stronger_answer():
    result = build_turn_analysis(
        "I designed APIs, measured latency, and improved cache hit rate with Redis.",
        "backend caching",
        {"intent": "answering", "confidence_level": "Confident"},
    )

    assert set(result.keys()) == {"intent", "confidence_level", "turn_evaluation"}
    assert result["turn_evaluation"]["depth"] > 0.4
    assert all(0.0 <= score <= 1.0 for score in result["turn_evaluation"].values())
    assert "prompt_hint" not in result
    assert "TURN SIGNALS" not in str(result)
    assert "If the answer is shallow" not in str(result)
    assert "prompt_context" not in result
    assert "prompt_hint_rule" not in result
    assert "target_topic" not in result
    assert "chat_history" not in result
    assert "next_topic" not in result


def test_build_turn_analysis_only_adds_small_hint_when_answer_is_shallow():
    result = build_turn_analysis(
        "Python.",
        "Python backend development",
        {"intent": "answering", "confidence_level": "Confident"},
    )

    assert set(result.keys()) == {"intent", "confidence_level", "turn_evaluation", "prompt_hint"}
    assert result["prompt_hint"] == PROMPT_HINT
    assert result["turn_evaluation"]["depth"] <= 0.4
    assert all(0.0 <= score <= 1.0 for score in result["turn_evaluation"].values())
    assert "TURN SIGNALS" not in str(result)
    assert "If the answer is shallow" not in str(result)
    assert "prompt_context" not in result
    assert "prompt_hint_rule" not in result
    assert "target_topic" not in result
    assert "chat_history" not in result
    assert "next_topic" not in result
