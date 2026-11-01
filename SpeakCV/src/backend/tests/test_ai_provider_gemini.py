import base64
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from pydantic import BaseModel

from app.ai.providers.gemini import GeminiProvider
from app.ai.schema import to_strict_schema
from app.ai.types import AIOutputError, AIProviderError, Usage

USER = [{"role": "user", "content": "hi"}]
KEY = "AIza-gemini-secret-key"


class Answer(BaseModel):
    answer: str


def _usage(inp=11, out=7, thought=0):
    return SimpleNamespace(total_input_tokens=inp, total_output_tokens=out, total_thought_tokens=thought)


def _interaction(text="ok", status="completed", usage=None, audio=None):
    return SimpleNamespace(status=status, output_text=text, output_audio=audio, usage=usage or _usage())


class Recorder:
    def __init__(self, result):
        self.result, self.calls = result, []

    def __call__(self, **kw):
        self.calls.append(kw)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def stub(provider, interaction=None, embed=None):
    provider._client = SimpleNamespace(
        interactions=SimpleNamespace(create=Recorder(interaction)),
        models=SimpleNamespace(embed_content=Recorder(embed)),
    )
    return provider


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)


def text_call(provider):
    return provider.generate_text(model="g", system="sys", messages=USER, max_output_tokens=500)


def test_generate_text_request_shape_and_usage():
    provider = stub(GeminiProvider(), _interaction("hello", usage=_usage(21, 5, 3)))
    messages = USER + [{"role": "assistant", "content": "yo"}, {"role": "user", "content": "more"}]
    result = provider.generate_text(model="g", system="sys", messages=messages, max_output_tokens=500)
    kw = provider._client.interactions.create.calls[0]
    assert kw["model"] == "g" and kw["system_instruction"] == "sys"
    assert kw["generation_config"] == {"max_output_tokens": 500}
    assert [s["type"] for s in kw["input"]] == ["user_input", "model_output", "user_input"]
    assert kw["input"][1]["content"] == [{"type": "text", "text": "yo"}]
    assert "temperature" not in kw["generation_config"] and "top_p" not in kw["generation_config"]
    assert "response_format" not in kw
    assert result.text == "hello"
    assert result.usage == Usage(input_tokens=21, output_tokens=8)


def test_structured_sends_strict_schema_and_returns_raw_json():
    provider = stub(GeminiProvider(), _interaction('{"answer": "x"}'))
    result = provider.generate_structured(model="g", system="s", messages=USER, schema=Answer, max_output_tokens=100)
    kw = provider._client.interactions.create.calls[0]
    assert kw["response_format"] == {"type": "text", "mime_type": "application/json", "schema": to_strict_schema(Answer)}
    assert result.text == '{"answer": "x"}'


def test_empty_and_unfinished_raise_output_error():
    for response in (_interaction(""), _interaction(None), _interaction("{", status="incomplete")):
        with pytest.raises(AIOutputError):
            text_call(stub(GeminiProvider(), response))


def _api_error(code):
    return genai_errors.APIError(code, {"error": {"message": KEY, "status": "X"}})


@pytest.mark.parametrize("error", [
    httpx.ConnectError("down " + KEY), _api_error(500), _api_error(429), _api_error(401),
])
def test_vendor_errors_become_provider_error_without_key(error):
    with pytest.raises(AIProviderError) as info:
        text_call(stub(GeminiProvider(), error))
    assert KEY not in str(info.value) and info.value.__cause__ is None


def test_failed_status_is_provider_error():
    with pytest.raises(AIProviderError):
        text_call(stub(GeminiProvider(), _interaction("x", status="failed")))


def test_embed_uses_prefixes_not_task_type_and_dimensionality():
    embed = SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0, 0.0]), SimpleNamespace(values=[0.0, 1.0])])
    provider = stub(GeminiProvider(), embed=embed)
    result = provider.embed(model="gemini-embedding-2", texts=["a", "b"], kind="query", dim=2)
    kw = provider._client.models.embed_content.calls[0]
    assert kw["contents"] == ["task: search result | query: a", "task: search result | query: b"]
    assert kw["config"].output_dimensionality == 2 and kw["config"].task_type is None
    assert result.vectors == [[1.0, 0.0], [0.0, 1.0]]
    provider.embed(model="gemini-embedding-2", texts=["a", "b"], kind="document", dim=2)
    assert provider._client.models.embed_content.calls[1]["contents"] == [
        "title: none | text: a", "title: none | text: b"]


def test_embed_wrong_count_raises():
    with pytest.raises(AIOutputError):
        stub(GeminiProvider(), embed=SimpleNamespace(embeddings=[])).embed(
            model="m", texts=["a"], kind="query", dim=2)


def test_transcribe_sends_inline_audio():
    provider = stub(GeminiProvider(), _interaction("xin chao", usage=_usage(40, 6)))
    result = provider.transcribe(model="g", audio=b"abc", mime_type="audio/webm", languages=["vi"])
    kw = provider._client.interactions.create.calls[0]
    parts = kw["input"]
    audio = [p for p in parts if p["type"] == "audio"][0]
    assert audio == {"type": "audio", "data": base64.b64encode(b"abc").decode(), "mime_type": "audio/webm"}
    assert "vi" in [p for p in parts if p["type"] == "text"][0]["text"]
    assert "temperature" not in kw.get("generation_config", {})
    assert result.text == "xin chao" and result.language == "vi"
    assert result.usage.input_tokens == 40 and result.usage.output_tokens == 6
    with pytest.raises(AIOutputError):
        stub(GeminiProvider(), _interaction("")).transcribe(model="g", audio=b"a", mime_type="audio/wav", languages=[])


def test_synthesize_request_and_audio_decoding():
    audio = SimpleNamespace(data=base64.b64encode(b"RIFFwav").decode(), mime_type="audio/wav")
    provider = stub(GeminiProvider(), _interaction(None, audio=audio))
    result = provider.synthesize(model="tts", text="hello", language="en", voice=None)
    kw = provider._client.interactions.create.calls[0]
    assert kw["input"] == "hello" and kw["response_format"] == {"type": "audio"}
    assert kw["generation_config"]["speech_config"] == [{"voice": "Kore"}]
    assert result.audio == b"RIFFwav" and result.mime_type == "audio/wav"
    assert result.usage == Usage(characters=5)
    provider.synthesize(model="tts", text="hello", language="en", voice="Puck")
    assert provider._client.interactions.create.calls[1]["generation_config"]["speech_config"] == [{"voice": "Puck"}]
    with pytest.raises(AIOutputError):
        stub(GeminiProvider(), _interaction(None, audio=None)).synthesize(
            model="tts", text="x", language="en", voice=None)
