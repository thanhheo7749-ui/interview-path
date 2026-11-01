"""Deterministic, offline provider used by all tests and by development without keys."""
import hashlib
import json
import math
import re
from collections import defaultdict, deque

from app.ai.schema import to_strict_schema
from app.ai.types import ProviderAudio, ProviderEmbedding, ProviderText, ProviderTranscript, Usage

_queues = defaultdict(deque)
_responders = {}
_last_system = {"value": ""}
_current_feature = {"value": None}
_last_messages = {"value": []}
_TOKEN = re.compile(r"\w+", re.UNICODE)


def enqueue(feature: str, text: str) -> None:
    """Return this text from the next text or structured call for this feature."""
    _queues[feature].append(text)


def register(feature: str, fn) -> None:
    """Answer calls for this feature with fn(system, messages, schema) -> text once the queue is empty."""
    _responders[feature] = fn


def last_system() -> str:
    return _last_system["value"]


def reset() -> None:
    _queues.clear()
    _responders.clear()
    _last_system["value"] = ""
    _last_messages["value"] = []


def last_messages() -> list[dict]:
    return _last_messages["value"]


def set_feature(feature: str) -> None:
    _current_feature["value"] = feature


def _usage(system: str, messages: list[dict], output: str) -> Usage:
    input_chars = len(system or "") + sum(len(m["content"]) for m in messages)
    return Usage(input_tokens=max(1, input_chars // 4), output_tokens=max(1, len(output) // 4))


def _default_value(schema: dict):
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema["type"]
    if kind == "object":
        return {name: _default_value(child) for name, child in schema["properties"].items()}
    if kind == "array":
        return []
    if kind == "string":
        return "fake"
    if kind == "boolean":
        return False
    return 0


class FakeProvider:
    def _next(self, system: str, messages: list[dict], schema: dict | None) -> str | None:
        _last_system["value"] = system or ""
        queue = _queues.get(_current_feature["value"])
        if queue:
            return queue.popleft()
        responder = _responders.get(_current_feature["value"])
        return responder(system, messages, schema) if responder else None

    def generate_text(self, *, model, system, messages, max_output_tokens) -> ProviderText:
        _last_messages["value"] = list(messages)
        text = self._next(system, messages, None)
        if text is None:
            text = f"[fake:{model}] {messages[-1]['content'][:80]}"
        return ProviderText(text=text, usage=_usage(system, messages, text))

    def generate_structured(self, *, model, system, messages, schema, max_output_tokens) -> ProviderText:
        _last_messages["value"] = list(messages)
        text = self._next(system, messages, schema)
        if text is None:
            text = json.dumps(_default_value(to_strict_schema(schema)), ensure_ascii=False)
        return ProviderText(text=text, usage=_usage(system, messages, text))

    def embed(self, *, model, texts, kind, dim) -> ProviderEmbedding:
        vectors = [self._embed_one(text, dim) for text in texts]
        return ProviderEmbedding(vectors=vectors, usage=Usage(input_tokens=sum(len(t) // 4 + 1 for t in texts)))

    @staticmethod
    def _embed_one(text: str, dim: int) -> list[float]:
        vector = [0.0] * dim
        for token in _TOKEN.findall(text.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % dim
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]

    def transcribe(self, *, model, audio, mime_type, languages) -> ProviderTranscript:
        try:
            text = audio.decode("utf-8").strip() or "fake transcript"
        except UnicodeDecodeError:  # real browser audio, so a session can run end to end
            text = "fake transcript"
        return ProviderTranscript(
            text=text,
            language=languages[0] if languages else "en",
            usage=Usage(audio_seconds=len(audio) / 16000),
        )

    def synthesize(self, *, model, text, language, voice) -> ProviderAudio:
        return ProviderAudio(audio=b"FAKEAUDIO:" + text.encode("utf-8"), mime_type="audio/mpeg", usage=Usage(characters=len(text)))
