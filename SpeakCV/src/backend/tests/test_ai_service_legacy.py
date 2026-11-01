from app.ai.providers import fake
from app.ai_service import call_ai_chat, call_ai_chat_stream, call_ai_chat_with_meta
from app.database.sql_models import AIUsageLog


def test_system_messages_move_to_the_system_argument_and_usage_is_logged(db):
    text = call_ai_chat(
        [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hello"}],
        slot="reasoning",
    )
    assert "hello" in text
    assert all(m["role"] != "system" for m in fake.last_messages())
    row = db.query(AIUsageLog).one()
    assert (row.slot, row.feature) == ("reasoning", "legacy")


def test_with_meta_keeps_its_shape():
    meta = call_ai_chat_with_meta([{"role": "user", "content": "hi"}])
    assert set(meta) == {"content", "provider", "model", "latency_ms"}
    assert meta["provider"] == "fake"


def test_stream_yields_the_whole_text():
    chunks = list(call_ai_chat_stream([{"role": "user", "content": "hi"}]))
    assert len(chunks) == 1 and "hi" in chunks[0]


def test_json_response_format_is_requested_in_the_system_prompt(monkeypatch):
    seen = {}
    from app import ai_service

    real = ai_service.gateway.generate_text

    def spy(slot, system, messages, max_output_tokens, feature, company_id=None):
        seen["system"] = system
        return real(slot, system, messages, max_output_tokens, feature, company_id)

    monkeypatch.setattr(ai_service.gateway, "generate_text", spy)
    call_ai_chat([{"role": "user", "content": "x"}], response_format={"type": "json_object"})
    assert "JSON" in seen["system"]
