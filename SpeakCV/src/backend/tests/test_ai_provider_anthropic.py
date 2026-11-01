from types import SimpleNamespace

import anthropic as sdk
import httpx
import pytest
from pydantic import BaseModel, Field

from app.ai import gateway
from app.ai.schema import to_strict_schema
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.types import AIOutputError, AIProviderError, Usage

USER = [{"role": "user", "content": "hi"}]
KEY = "sk-ant-secret-key-value"


class Answer(BaseModel):
    answer: str


def _text(text="ok", stop="end_turn", inp=11, out=7):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)], stop_reason=stop,
        usage=SimpleNamespace(input_tokens=inp, output_tokens=out), parsed_output=None,
    )


class Namespace:
    def __init__(self, result):
        self.result, self.calls = result, []

    def _run(self, kind, kwargs):
        self.calls.append((kind, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def create(self, **kw):
        return self._run("create", kw)

    def parse(self, **kw):
        raise AssertionError("parse must not be called")


class Client:
    def __init__(self, result):
        self.messages = Namespace(result)
        self.beta = SimpleNamespace(messages=Namespace(result))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.delenv("ANTHROPIC_EFFORT", raising=False)
    monkeypatch.delenv("ANTHROPIC_FALLBACKS_ENABLED", raising=False)


def make(result):
    provider = AnthropicProvider()
    provider._client = Client(result)
    return provider


def text_call(provider, model="claude-haiku-5-5", **extra):
    return provider.generate_text(model=model, system="sys", messages=USER, max_output_tokens=500, **extra)


def test_generate_text_request_shape():
    provider = make(_text("hello"))
    result = text_call(provider)
    kind, kw = provider._client.messages.calls[0]
    assert kind == "create"
    assert (kw["model"], kw["system"], kw["messages"], kw["max_tokens"]) == ("claude-haiku-5-5", "sys", USER, 500)
    assert "temperature" not in kw and "top_p" not in kw and "thinking" not in kw
    assert result.text == "hello"


def test_effort_default_and_override(monkeypatch):
    provider = make(_text())
    text_call(provider, "claude-haiku-5-5")
    assert provider._client.messages.calls[0][1]["output_config"] == {"effort": "high"}
    monkeypatch.setenv("ANTHROPIC_EFFORT", "medium")
    provider = make(_text())
    text_call(provider, "claude-haiku-5-5")
    assert provider._client.messages.calls[0][1]["output_config"] == {"effort": "medium"}


def test_effort_not_sent_to_models_without_it():
    provider = make(_text())
    text_call(provider, "claude-haiku-4-5")
    assert "output_config" not in provider._client.messages.calls[0][1]


def test_structured_uses_create_with_json_schema_and_never_parse():
    provider = make(_text('{"answer": "x"}'))
    result = provider.generate_structured(
        model="claude-haiku-5-5", system="sys", messages=USER, schema=Answer, max_output_tokens=500
    )
    kind, kw = provider._client.messages.calls[0]
    assert kind == "create" and "output_format" not in kw
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": to_strict_schema(Answer)}
    assert kw["output_config"]["effort"] == "high"
    assert all(k != "parse" for k, _ in provider._client.messages.calls + provider._client.beta.messages.calls)
    assert result.text == '{"answer": "x"}'


def test_empty_structured_response_raises():
    empty = _text("")
    with pytest.raises(AIOutputError):
        make(empty).generate_structured(
            model="claude-haiku-5-5", system="s", messages=USER, schema=Answer, max_output_tokens=100
        )


def test_refusal_raises_before_reading_content():
    class Refused:
        stop_reason = "refusal"
        usage = SimpleNamespace(input_tokens=1, output_tokens=0)

        @property
        def content(self):
            raise AssertionError("content read before checking the refusal")

    with pytest.raises(AIOutputError):
        text_call(make(Refused()))


def test_max_tokens_raises():
    with pytest.raises(AIOutputError):
        text_call(make(_text(stop="max_tokens")))


@pytest.mark.parametrize("response", [_text(stop="max_tokens", inp=30, out=2), _text(stop="refusal", inp=30, out=2), _text("", inp=30, out=2)])
def test_output_errors_carry_the_tokens_that_were_billed(response):
    with pytest.raises(AIOutputError) as info:
        text_call(make(response))
    assert info.value.usage == Usage(input_tokens=30, output_tokens=2)


def test_usage_mapping():
    assert text_call(make(_text(inp=21, out=5))).usage == Usage(input_tokens=21, output_tokens=5)


def _status_error(code):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages", headers={"x-api-key": KEY})
    response = httpx.Response(code, request=request, json={"error": {"message": f"bad {KEY}"}})
    return sdk.APIStatusError("boom " + KEY, response=response, body=None)


@pytest.mark.parametrize("error", [
    sdk.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")),
    _status_error(500),
])
def test_vendor_errors_become_provider_error_without_key(error):
    with pytest.raises(AIProviderError) as info:
        text_call(make(error))
    assert KEY not in str(info.value) and "sk-ant" not in str(info.value)
    assert info.value.__cause__ is None


@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-sonnet-5-5"])
def test_fallbacks_sent_for_opus_and_sonnet(model):
    provider = make(_text())
    text_call(provider, model)
    assert provider._client.messages.calls == []
    _, kw = provider._client.beta.messages.calls[0]
    assert kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"] == {"effort": "high"}


def test_fallbacks_not_sent_for_haiku():
    provider = make(_text())
    text_call(provider, "claude-haiku-5-5")
    assert provider._client.beta.messages.calls == []
    assert "fallbacks" not in provider._client.messages.calls[0][1]


def test_fallbacks_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_FALLBACKS_ENABLED", "false")
    provider = make(_text())
    text_call(provider, "claude-opus-5-5")
    assert provider._client.beta.messages.calls == []
    kw = provider._client.messages.calls[0][1]
    assert "fallbacks" not in kw and "betas" not in kw


class Strict(BaseModel):
    n: int = Field(ge=5)


def test_pydantic_only_failure_is_returned_raw_and_gateway_retries(monkeypatch):
    first, second = _text('{"n": 1}'), _text('{"n": 9}')
    provider = make(first)
    results = iter([first, second])
    provider._client.messages.create = lambda **kw: next(results)
    slot = SimpleNamespace(provider="anthropic", model="claude-haiku-5-5")
    monkeypatch.setattr(gateway, "get_config", lambda: SimpleNamespace(slot=lambda name: slot))
    monkeypatch.setattr(gateway, "get_provider", lambda name: provider)
    monkeypatch.setattr(gateway, "log_usage", lambda **kw: None)
    raw = provider.generate_structured(
        model="claude-haiku-5-5", system="s", messages=USER, schema=Strict, max_output_tokens=100
    )
    assert raw.text == '{"n": 1}'
    results = iter([first, second])
    out = gateway.generate_structured("reasoning", "s", USER, Strict, 100, "unit_test")
    assert out.value.n == 9


def test_large_max_tokens_streams_and_reads_final_message():
    final = _text("streamed")

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return final

    class Streaming(Namespace):
        def stream(self, **kw):
            self.calls.append(("stream", kw))
            return Stream()

    provider = make(final)
    provider._client.messages = Streaming(final)
    result = provider.generate_text(model="claude-haiku-5-5", system="s", messages=USER, max_output_tokens=32000)
    assert result.text == "streamed"
    assert provider._client.messages.calls[0][0] == "stream"
