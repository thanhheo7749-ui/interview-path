from types import SimpleNamespace

import httpx
import openai as sdk
import pytest
from pydantic import BaseModel

from app.ai.providers.openai import DEFAULT_BASE_URL, OpenAIProvider
from app.ai.schema import to_strict_schema
from app.ai.types import AIOutputError, AIProviderError, Usage

USER = [{"role": "user", "content": "hi"}]
KEY = "sk-openai-secret-key-value"


class Answer(BaseModel):
    answer: str


def _chat(text="ok", finish="stop", refusal=None, inp=11, out=7):
    message = SimpleNamespace(content=text, refusal=refusal)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=inp, completion_tokens=out),
    )


class Recorder:
    def __init__(self, result):
        self.result, self.calls = result, []

    def create(self, **kw):
        self.calls.append(kw)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def stub(provider, chat=None, embeddings=None, transcriptions=None, speech=None):
    provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=Recorder(chat)),
        embeddings=Recorder(embeddings),
        audio=SimpleNamespace(transcriptions=Recorder(transcriptions), speech=Recorder(speech)),
    )
    return provider


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)


def text_call(provider):
    return provider.generate_text(model="m", system="sys", messages=USER, max_output_tokens=500)


def test_default_base_url_reaches_client():
    assert DEFAULT_BASE_URL == "https://api.openai.com/v1"
    assert str(OpenAIProvider()._client.base_url).rstrip("/") == "https://api.openai.com/v1"


def test_custom_base_url_reaches_client(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example.com/v1")
    assert str(OpenAIProvider()._client.base_url).rstrip("/") == "https://proxy.example.com/v1"


def test_generate_text_request_shape_and_usage():
    provider = stub(OpenAIProvider(), chat=_chat("hello", inp=21, out=5))
    result = text_call(provider)
    kw = provider._client.chat.completions.calls[0]
    assert kw["model"] == "m" and kw["max_completion_tokens"] == 500
    assert kw["messages"] == [{"role": "system", "content": "sys"}] + USER
    assert "temperature" not in kw and "top_p" not in kw and "response_format" not in kw
    assert result.text == "hello"
    assert result.usage == Usage(input_tokens=21, output_tokens=5)


def test_structured_sends_strict_schema_and_returns_raw_json():
    provider = stub(OpenAIProvider(), chat=_chat('{"answer": "x"}'))
    result = provider.generate_structured(model="m", system="s", messages=USER, schema=Answer, max_output_tokens=100)
    kw = provider._client.chat.completions.calls[0]
    assert kw["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Answer", "strict": True, "schema": to_strict_schema(Answer)},
    }
    assert "temperature" not in kw and "top_p" not in kw
    assert result.text == '{"answer": "x"}'


def test_refusal_empty_and_truncated_raise_output_error():
    for response in (_chat(None, refusal="no"), _chat(""), _chat("{", finish="length"), _chat("x", finish="content_filter")):
        with pytest.raises(AIOutputError):
            text_call(stub(OpenAIProvider(), chat=response))


def _status_error(code):
    request = httpx.Request("POST", "https://api.openai.com/v1/x", headers={"authorization": KEY})
    response = httpx.Response(code, request=request, json={"error": {"message": KEY}})
    return sdk.APIStatusError("boom " + KEY, response=response, body=None)


@pytest.mark.parametrize("error", [
    sdk.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com")),
    _status_error(500), _status_error(429), _status_error(401),
])
def test_vendor_errors_become_provider_error_without_key(error):
    with pytest.raises(AIProviderError) as info:
        text_call(stub(OpenAIProvider(), chat=error))
    assert KEY not in str(info.value) and info.value.__cause__ is None


def test_embed_passes_dimensions_and_orders_by_index():
    response = SimpleNamespace(
        data=[SimpleNamespace(index=1, embedding=[0.0, 1.0]), SimpleNamespace(index=0, embedding=[1.0, 0.0])],
        usage=SimpleNamespace(prompt_tokens=9, total_tokens=9),
    )
    provider = stub(OpenAIProvider(), embeddings=response)
    result = provider.embed(model="e", texts=["a", "b"], kind="document", dim=2)
    kw = provider._client.embeddings.calls[0]
    assert kw["dimensions"] == 2 and kw["input"] == ["a", "b"] and kw["model"] == "e"
    assert result.vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert result.usage == Usage(input_tokens=9)


def test_transcribe_passes_languages_and_maps_duration_usage():
    response = SimpleNamespace(text="xin chao", usage=SimpleNamespace(type="duration", seconds=3.5))
    provider = stub(OpenAIProvider(), transcriptions=response)
    result = provider.transcribe(model="t", audio=b"abc", mime_type="audio/webm", languages=["vi", "en"])
    kw = provider._client.audio.transcriptions.calls[0]
    assert kw["languages"] == ["vi", "en"] and kw["model"] == "t" and "language" not in kw
    assert kw["file"][1] == b"abc" and kw["file"][2] == "audio/webm"
    assert "temperature" not in kw
    assert result.text == "xin chao" and result.language == "vi"
    assert result.usage == Usage(audio_seconds=3.5)


def test_transcribe_token_usage_and_empty_text():
    response = SimpleNamespace(text="hi", usage=SimpleNamespace(type="tokens", input_tokens=4, output_tokens=2))
    result = stub(OpenAIProvider(), transcriptions=response).transcribe(
        model="t", audio=b"a", mime_type="audio/wav", languages=[])
    assert result.usage == Usage(input_tokens=4, output_tokens=2)
    with pytest.raises(AIOutputError):
        stub(OpenAIProvider(), transcriptions=SimpleNamespace(text="", usage=None)).transcribe(
            model="t", audio=b"a", mime_type="audio/wav", languages=["en"])


def test_synthesize_request_and_usage():
    provider = stub(OpenAIProvider(), speech=SimpleNamespace(content=b"MP3"))
    result = provider.synthesize(model="s", text="hello", language="en", voice=None)
    kw = provider._client.audio.speech.calls[0]
    assert kw["model"] == "s" and kw["input"] == "hello" and kw["voice"] and kw["response_format"] == "mp3"
    assert result.audio == b"MP3" and result.mime_type == "audio/mpeg"
    assert result.usage == Usage(characters=5)
    provider.synthesize(model="s", text="hello", language="en", voice="marin")
    assert provider._client.audio.speech.calls[1]["voice"] == "marin"
    with pytest.raises(AIOutputError):
        stub(OpenAIProvider(), speech=SimpleNamespace(content=b"")).synthesize(
            model="s", text="x", language="en", voice=None)
