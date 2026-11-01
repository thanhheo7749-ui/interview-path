"""OpenAI adapter (Chat Completions, embeddings, transcription, speech). Reads OPENAI_API_KEY and OPENAI_BASE_URL."""
import os

import openai as openai_sdk

from app.ai.schema import to_strict_schema
from app.ai.types import AIOutputError, AIProviderError, ProviderAudio, ProviderEmbedding, ProviderText, ProviderTranscript, Usage

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_VOICE = "alloy"
_EXTENSIONS = {"audio/webm": "webm", "audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3",
               "audio/mp4": "mp4", "audio/m4a": "m4a", "audio/ogg": "ogg", "audio/flac": "flac"}


class OpenAIProvider:
    def __init__(self):
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or DEFAULT_BASE_URL
        self._client = openai_sdk.OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url)

    def _run(self, call, **kwargs):
        try:
            return call(**kwargs)
        except openai_sdk.APIStatusError as exc:
            raise AIProviderError(f"openai call failed: HTTP {exc.status_code}") from None
        except openai_sdk.APIError as exc:
            raise AIProviderError(f"openai call failed: {type(exc).__name__}") from None

    def generate_text(self, *, model, system, messages, max_output_tokens) -> ProviderText:
        return self._chat(model, system, messages, max_output_tokens, None)

    def generate_structured(self, *, model, system, messages, schema, max_output_tokens) -> ProviderText:
        # Raw JSON text is returned; the gateway validates it with Pydantic and retries on failure.
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "strict": True, "schema": to_strict_schema(schema)},
        }
        return self._chat(model, system, messages, max_output_tokens, response_format)

    def _chat(self, model, system, messages, max_output_tokens, response_format) -> ProviderText:
        kwargs = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + list(messages),
            "max_completion_tokens": max_output_tokens,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        response = self._run(self._client.chat.completions.create, **kwargs)
        choice = response.choices[0]
        usage = Usage(input_tokens=response.usage.prompt_tokens, output_tokens=response.usage.completion_tokens)
        if choice.message.refusal:
            raise AIOutputError("OpenAI refused the request", usage=usage)
        if choice.finish_reason == "length":
            raise AIOutputError("OpenAI output was cut off at the token limit", usage=usage)
        if choice.finish_reason == "content_filter":
            raise AIOutputError("OpenAI output was blocked by the content filter", usage=usage)
        if not choice.message.content:
            raise AIOutputError("OpenAI returned no text", usage=usage)
        return ProviderText(text=choice.message.content, usage=usage)

    def embed(self, *, model, texts, kind, dim) -> ProviderEmbedding:
        # OpenAI embeddings have no query/document distinction, so kind is unused.
        response = self._run(self._client.embeddings.create, model=model, input=list(texts), dimensions=dim)
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if len(vectors) != len(texts):
            raise AIOutputError("OpenAI returned a different number of embeddings than inputs")
        return ProviderEmbedding(vectors=vectors, usage=Usage(input_tokens=response.usage.prompt_tokens))

    def transcribe(self, *, model, audio, mime_type, languages) -> ProviderTranscript:
        extension = _EXTENSIONS.get(mime_type, "bin")
        kwargs = {"model": model, "file": (f"audio.{extension}", audio, mime_type)}
        if languages:
            kwargs["languages"] = list(languages)  # gpt-transcribe: replaces the singular `language`
        response = self._run(self._client.audio.transcriptions.create, **kwargs)
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise AIOutputError("OpenAI returned an empty transcript")
        return ProviderTranscript(text=text, language=languages[0] if languages else "", usage=_transcription_usage(response))

    def synthesize(self, *, model, text, language, voice) -> ProviderAudio:
        # The model detects the language from the text, so `language` is unused.
        response = self._run(
            self._client.audio.speech.create, model=model, input=text, voice=voice or DEFAULT_VOICE, response_format="mp3"
        )
        if not response.content:
            raise AIOutputError("OpenAI returned no audio")
        return ProviderAudio(audio=response.content, mime_type="audio/mpeg", usage=Usage(characters=len(text)))


def _transcription_usage(response) -> Usage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return Usage()
    if getattr(usage, "type", None) == "duration":
        return Usage(audio_seconds=float(usage.seconds))
    return Usage(input_tokens=getattr(usage, "input_tokens", 0) or 0, output_tokens=getattr(usage, "output_tokens", 0) or 0)
