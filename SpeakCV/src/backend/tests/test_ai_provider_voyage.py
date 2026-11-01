from types import SimpleNamespace

import httpx
import requests
import pytest
import voyageai.error as vx

from app.ai.providers.voyage import VoyageProvider
from app.ai.types import AIProviderError, Usage

KEY = "pa-voyage-secret-key"


class Client:
    def __init__(self, result):
        self.result, self.calls = result, []

    def embed(self, texts, **kw):
        self.calls.append((texts, kw))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", KEY)


def make(result):
    provider = VoyageProvider()
    provider._client = Client(result)
    return provider


OK = SimpleNamespace(embeddings=[[1.0, 0.0], [0.0, 1.0]], total_tokens=12)


@pytest.mark.parametrize("kind", ["query", "document"])
def test_input_type_comes_from_kind(kind):
    provider = make(OK)
    result = provider.embed(model="voyage-x", texts=["a", "b"], kind=kind, dim=2)
    texts, kw = provider._client.calls[0]
    assert texts == ["a", "b"]
    assert kw == {"model": "voyage-x", "input_type": kind, "output_dimension": 2}
    assert result.vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert result.usage == Usage(input_tokens=12)


def test_no_temperature_or_top_p():
    provider = make(OK)
    provider.embed(model="m", texts=["a", "b"], kind="query", dim=2)
    assert "temperature" not in provider._client.calls[0][1] and "top_p" not in provider._client.calls[0][1]


@pytest.mark.parametrize("error", [
    vx.APIConnectionError("down " + KEY), vx.ServerError("500 " + KEY), vx.RateLimitError("429 " + KEY),
    vx.AuthenticationError("401 " + KEY), vx.Timeout("slow"), httpx.ConnectError("x " + KEY), requests.ConnectionError("x " + KEY),
])
def test_vendor_errors_become_provider_error_without_key(error):
    with pytest.raises(AIProviderError) as info:
        make(error).embed(model="m", texts=["a"], kind="query", dim=2)
    assert KEY not in str(info.value) and info.value.__cause__ is None


def test_wrong_vector_count_raises_output_error():
    from app.ai.types import AIOutputError
    with pytest.raises(AIOutputError):
        make(SimpleNamespace(embeddings=[[1.0]], total_tokens=1)).embed(model="m", texts=["a", "b"], kind="query", dim=1)
