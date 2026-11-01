"""Gemini adapter (google-genai Interactions API plus embed_content). Reads only GEMINI_API_KEY."""
import base64
import os

import httpx
from google import genai as genai_sdk
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.ai.schema import to_strict_schema
from app.ai.types import AIOutputError, AIProviderError, ProviderAudio, ProviderEmbedding, ProviderText, ProviderTranscript, Usage

DEFAULT_VOICE = "Kore"
# gemini-embedding-2 rejects task_type; the task is given as a text prefix instead.
_QUERY_PREFIX = "task: search result | query: "
_DOCUMENT_PREFIX = "title: none | text: "
_ROLE_STEP = {"user": "user_input", "assistant": "model_output"}


def _steps(messages: list[dict]) -> list[dict]:
    return [{"type": _ROLE_STEP[m["role"]], "content": [{"type": "text", "text": m["content"]}]} for m in messages]


def _usage(interaction) -> Usage:
    usage = getattr(interaction, "usage", None)
    if usage is None:
        return Usage()
    output = (getattr(usage, "total_output_tokens", 0) or 0) + (getattr(usage, "total_thought_tokens", 0) or 0)
    return Usage(input_tokens=getattr(usage, "total_input_tokens", 0) or 0, output_tokens=output)


class GeminiProvider:
    def __init__(self):
        self._client = genai_sdk.Client(api_key=os.environ["GEMINI_API_KEY"])

    def _run(self, call, **kwargs):
        try:
            return call(**kwargs)
        except genai_errors.APIError as exc:
            raise AIProviderError(f"gemini call failed: HTTP {exc.code}") from None
        except httpx.HTTPError as exc:
            raise AIProviderError(f"gemini call failed: {type(exc).__name__}") from None

    def _interact(self, **kwargs):
        interaction = self._run(self._client.interactions.create, **kwargs)
        if interaction.status == "failed":
            raise AIProviderError("gemini interaction failed")
        if interaction.status in {"incomplete", "budget_exceeded", "cancelled"}:
            raise AIOutputError(f"Gemini output was not completed: {interaction.status}", usage=_usage(interaction))
        return interaction

    def generate_text(self, *, model, system, messages, max_output_tokens) -> ProviderText:
        return self._text(model, system, messages, max_output_tokens, None)

    def generate_structured(self, *, model, system, messages, schema, max_output_tokens) -> ProviderText:
        # Raw JSON text is returned; the gateway validates it with Pydantic and retries on failure.
        response_format = {"type": "text", "mime_type": "application/json", "schema": to_strict_schema(schema)}
        return self._text(model, system, messages, max_output_tokens, response_format)

    def _text(self, model, system, messages, max_output_tokens, response_format) -> ProviderText:
        kwargs = {
            "model": model,
            "system_instruction": system,
            "input": _steps(messages),
            "generation_config": {"max_output_tokens": max_output_tokens},
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        interaction = self._interact(**kwargs)
        if not interaction.output_text:
            raise AIOutputError("Gemini returned no text", usage=_usage(interaction))
        return ProviderText(text=interaction.output_text, usage=_usage(interaction))

    def embed(self, *, model, texts, kind, dim) -> ProviderEmbedding:
        prefix = _QUERY_PREFIX if kind == "query" else _DOCUMENT_PREFIX
        response = self._run(
            self._client.models.embed_content,
            model=model,
            contents=[prefix + text for text in texts],
            config=genai_types.EmbedContentConfig(output_dimensionality=dim),
        )
        vectors = [list(item.values) for item in (response.embeddings or [])]
        if len(vectors) != len(texts):
            raise AIOutputError("Gemini returned a different number of embeddings than inputs")
        # The Developer API embedding response carries no token count.
        return ProviderEmbedding(vectors=vectors, usage=Usage())

    def transcribe(self, *, model, audio, mime_type, languages) -> ProviderTranscript:
        hint = f" The expected languages are: {', '.join(languages)}." if languages else ""
        prompt = f"Generate a verbatim transcript of the speech. Return only the transcript text.{hint}"
        interaction = self._interact(
            model=model,
            input=[
                {"type": "text", "text": prompt},
                {"type": "audio", "data": base64.b64encode(audio).decode("ascii"), "mime_type": mime_type},
            ],
        )
        text = (interaction.output_text or "").strip()
        if not text:
            raise AIOutputError("Gemini returned an empty transcript")
        return ProviderTranscript(text=text, language=languages[0] if languages else "", usage=_usage(interaction))

    def synthesize(self, *, model, text, language, voice) -> ProviderAudio:
        # The TTS model detects the language from the text, so `language` is unused.
        interaction = self._interact(
            model=model,
            input=text,
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice or DEFAULT_VOICE}]},
        )
        output = interaction.output_audio
        if output is None or not output.data:
            raise AIOutputError("Gemini returned no audio")
        return ProviderAudio(
            audio=base64.b64decode(output.data), mime_type=output.mime_type or "audio/wav", usage=Usage(characters=len(text))
        )
