"""edge-tts adapter (free text to speech). Needs no key."""
import asyncio
import concurrent.futures

import edge_tts as edge_tts_sdk

from app.ai.types import AIProviderError, ProviderAudio, Usage

DEFAULT_VOICES = {"vi": "vi-VN-HoaiMyNeural", "ko": "ko-KR-SunHiNeural"}
FALLBACK_VOICE = "en-US-AndrewMultilingualNeural"


async def _collect(text: str, voice: str) -> bytes:
    chunks = []
    async for chunk in edge_tts_sdk.Communicate(text, voice).stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


class EdgeTTSProvider:
    def synthesize(self, *, model, text, language, voice) -> ProviderAudio:
        chosen = voice or DEFAULT_VOICES.get(language, FALLBACK_VOICE)
        try:
            # A worker thread gets its own event loop, so this also works inside FastAPI's running loop.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                audio = pool.submit(asyncio.run, _collect(text, chosen)).result()
        except Exception as exc:
            raise AIProviderError(f"edge-tts call failed: {type(exc).__name__}") from None
        if not audio:
            raise AIProviderError("edge-tts returned no audio")
        return ProviderAudio(audio=audio, mime_type="audio/mpeg", usage=Usage(characters=len(text)))
