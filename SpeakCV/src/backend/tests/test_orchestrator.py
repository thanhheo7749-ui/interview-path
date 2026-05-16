from app.services.orchestrator import build_interview_result


def test_build_interview_result_wraps_content_analysis_and_trace():
    result = build_interview_result(
        ai_text="Next question?",
        analysis={"turn_evaluation": {"correctness": "partial"}},
        usage={"provider": "gemini"},
        trace_id="trace-123",
    )

    assert result["content"] == "Next question?"
    assert result["analysis"]["turn_evaluation"]["correctness"] == "partial"
    assert result["usage"]["provider"] == "gemini"
    assert result["trace_id"] == "trace-123"


def test_interview_result_contains_turn_evaluation_and_signals():
    result = build_interview_result(
        ai_text="Tell me about your API design choices.",
        analysis={
            "transcript": {"transcript_confidence": 0.9, "low_quality_flag": False},
            "speaking_signals": {"clarity_score": 0.88, "speaking_signal": "clear"},
            "turn_evaluation": {"correctness": 0.6, "depth": 0.7, "communication": 0.8},
            "interview_context": {"target_topics": ["System Design"]},
            "next_topic": "System Design",
        },
        usage={"provider": "gemini", "model": "gpt-4o-mini", "latency_ms": 123},
        trace_id="trace-456",
    )

    assert result["analysis"]["transcript"]["transcript_confidence"] == 0.9
    assert result["analysis"]["speaking_signals"]["clarity_score"] == 0.88
    assert result["analysis"]["turn_evaluation"]["depth"] == 0.7
    assert result["analysis"]["interview_context"]["target_topics"] == ["System Design"]
    assert result["analysis"]["next_topic"] == "System Design"
    assert result["usage"]["model"] == "gpt-4o-mini"


def test_interview_result_contains_planner_fields():
    result = build_interview_result(
        ai_text="Next question",
        analysis={
            "turn_evaluation": {
                "correctness": 0.6,
                "depth": 0.5,
                "communication": 0.7,
                "topic_relevance": 0.8,
            },
            "planner_decision": {
                "why_selected": "gap_in_jd",
                "topic_state": "probing",
                "next_topic": "Caching",
                "followup_mode": "deep_dive",
            },
            "live_cues": ["On-topic", "Needs more depth"],
        },
        usage={},
        trace_id="trace-123",
    )

    planner_decision = result["analysis"]["planner_decision"]

    assert set(planner_decision) >= {
        "why_selected",
        "topic_state",
        "next_topic",
        "followup_mode",
    }
    assert planner_decision["next_topic"] == "Caching"
    assert planner_decision["followup_mode"] == "deep_dive"
