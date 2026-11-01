"""Compatibility layer for legacy routes. New code calls app.ai.gateway directly."""
from app.ai import gateway

DEFAULT_MAX_OUTPUT_TOKENS = 2000
JSON_INSTRUCTION = "Return only one valid JSON object and no other text."


def _split_messages(messages: list[dict], response_format: dict | None) -> tuple[str, list[dict]]:
    system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    if response_format and response_format.get("type") == "json_object":
        system_parts.append(JSON_INSTRUCTION)
    rest = [
        {"role": "assistant" if m.get("role") == "assistant" else "user", "content": m.get("content", "")}
        for m in messages
        if m.get("role") != "system"
    ]
    return "\n".join(system_parts).strip(), rest


def call_ai_chat_with_meta(messages, slot="bulk", max_tokens=None, response_format=None, feature="legacy") -> dict:
    system, rest = _split_messages(messages, response_format)
    result = gateway.generate_text(slot, system, rest, max_tokens or DEFAULT_MAX_OUTPUT_TOKENS, feature)
    return {"content": result.text, "provider": result.provider, "model": result.model, "latency_ms": result.latency_ms}


def call_ai_chat(messages, slot="bulk", max_tokens=None, response_format=None, feature="legacy") -> str:
    return call_ai_chat_with_meta(messages, slot, max_tokens, response_format, feature)["content"]


def call_ai_chat_stream(messages, slot="reasoning", feature="legacy"):
    yield call_ai_chat(messages, slot=slot, feature=feature)
