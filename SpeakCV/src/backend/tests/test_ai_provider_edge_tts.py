import asyncio

import pytest

from app.ai.providers import edge_tts as module
from app.ai.providers.edge_tts import EdgeTTSProvider
from app.ai.types import AIProviderError, Usage


class FakeCommunicate:
    instances = []
    chunks = [{"type": "WordBoundary"}, {"type": "audio", "data": b"AB"}, {"type": "audio", "data": b"CD"}]
    error = None

    def __init__(self, text, voice, **kw):
        self.text, self.voice, self.kw = text, voice, kw
        FakeCommunicate.instances.append(self)

    async def stream(self):
        if FakeCommunicate.error:
            raise FakeCommunicate.error
        for chunk in FakeCommunicate.chunks:
            yield chunk


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    FakeCommunicate.instances = []
    FakeCommunicate.error = None
    FakeCommunicate.chunks = [{"type": "WordBoundary"}, {"type": "audio", "data": b"AB"}, {"type": "audio", "data": b"CD"}]
    monkeypatch.setattr(module.edge_tts_sdk, "Communicate", FakeCommunicate)


def run(language="en", voice=None, text="hello"):
    return EdgeTTSProvider().synthesize(model="edge", text=text, language=language, voice=voice)


@pytest.mark.parametrize("language,voice", [
    ("vi", "vi-VN-HoaiMyNeural"), ("ko", "ko-KR-SunHiNeural"),
    ("en", "en-US-AndrewMultilingualNeural"), ("fr", "en-US-AndrewMultilingualNeural"),
])
def test_default_voice_by_language(language, voice):
    run(language)
    assert FakeCommunicate.instances[0].voice == voice


def test_explicit_voice_wins():
    run("vi", voice="en-GB-RyanNeural")
    assert FakeCommunicate.instances[0].voice == "en-GB-RyanNeural"


def test_audio_concatenated_and_usage_characters():
    result = run(text="hello")
    assert result.audio == b"ABCD" and result.mime_type == "audio/mpeg"
    assert result.usage == Usage(characters=5)


def test_works_inside_running_event_loop():
    async def main():
        return run()

    assert asyncio.run(main()).audio == b"ABCD"


def test_no_audio_raises_provider_error():
    FakeCommunicate.chunks = [{"type": "WordBoundary"}]
    with pytest.raises(AIProviderError):
        run()


def test_stream_failure_becomes_provider_error():
    FakeCommunicate.error = RuntimeError("socket closed")
    with pytest.raises(AIProviderError):
        run()
