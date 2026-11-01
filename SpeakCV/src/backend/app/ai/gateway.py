"""The only entry point business code uses for AI. Names no vendor."""
import time
from typing import Callable

from pydantic import BaseModel

from app.ai.config import get_config
from app.ai.providers import fake as fake_provider
from app.ai.providers import get_provider
from app.ai.types import (
    AIOutputError,
    AIProviderError,
    AudioResult,
    EmbeddingResult,
    StructuredResult,
    TextResult,
    TranscriptResult,
    Usage,
)
from app.ai.usage import log_usage

STRUCTURED_ATTEMPTS = 2


def _call(slot_name: str, feature: str, company_id: int | None, invoke: Callable, validate: Callable | None = None):
    """Run one vendor call, write one usage row, and normalise unexpected errors.

    `validate(result)` runs before the row is written. If it raises, the row records a failure with the
    tokens the call still cost, and the validation error is re-raised for the caller to handle.
    """
    slot = get_config().slot(slot_name)
    started = time.perf_counter()
    common = {"feature": feature, "slot": slot_name, "provider": slot.provider, "model": slot.model, "company_id": company_id}
    try:
        provider = get_provider(slot.provider)
        if slot.provider == "fake":
            fake_provider.set_feature(feature)
        result = invoke(provider, slot)
    except (AIOutputError, AIProviderError) as exc:
        usage = getattr(exc, "usage", None) or Usage()
        log_usage(**common, usage=usage, latency_ms=_elapsed_ms(started), success=False, error_type=type(exc).__name__)
        raise
    except Exception as exc:
        log_usage(**common, usage=Usage(), latency_ms=_elapsed_ms(started), success=False, error_type=type(exc).__name__)
        raise AIProviderError(f"{slot.provider} call failed: {type(exc).__name__}") from exc
    latency_ms = _elapsed_ms(started)
    if validate is not None:
        try:
            validate(result)
        except ValueError:  # pydantic's ValidationError and json's JSONDecodeError are both ValueErrors
            log_usage(**common, usage=result.usage, latency_ms=latency_ms, success=False, error_type="ValidationError")
            raise
    log_usage(**common, usage=result.usage, latency_ms=latency_ms, success=True)
    return result, slot, latency_ms


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def generate_text(slot, system, messages, max_output_tokens, feature, company_id=None) -> TextResult:
    result, config, latency_ms = _call(
        slot, feature, company_id,
        lambda provider, cfg: provider.generate_text(
            model=cfg.model, system=system, messages=messages, max_output_tokens=max_output_tokens
        ),
    )
    return TextResult(text=result.text, provider=config.provider, model=config.model, usage=result.usage, latency_ms=latency_ms)


def generate_structured(slot, system, messages, schema: type[BaseModel], max_output_tokens, feature, company_id=None) -> StructuredResult:
    attempt_messages = list(messages)
    last_error = None
    for _ in range(STRUCTURED_ATTEMPTS):
        current = list(attempt_messages)
        attempt = {}

        def validate(result):
            attempt["text"] = result.text
            attempt["value"] = schema.model_validate_json(result.text)

        try:
            result, config, latency_ms = _call(
                slot, feature, company_id,
                lambda provider, cfg: provider.generate_structured(
                    model=cfg.model, system=system, messages=current, schema=schema, max_output_tokens=max_output_tokens
                ),
                validate=validate,
            )
        except ValueError as exc:
            last_error = exc
            attempt_messages = current + [
                {"role": "assistant", "content": attempt["text"]},
                {"role": "user", "content": f"Your previous response failed validation: {exc}. Return only corrected JSON."},
            ]
            continue
        value = attempt["value"]
        return StructuredResult(
            value=value, raw_text=result.text, provider=config.provider, model=config.model,
            usage=result.usage, latency_ms=latency_ms,
        )
    raise AIOutputError(f"Structured output for feature {feature} failed validation twice: {last_error}")


def embed(texts, kind, feature, company_id=None) -> EmbeddingResult:
    if kind not in {"query", "document"}:
        raise ValueError("kind must be 'query' or 'document'")
    result, config, latency_ms = _call(
        "embedding", feature, company_id,
        lambda provider, cfg: provider.embed(model=cfg.model, texts=texts, kind=kind, dim=cfg.dim),
    )
    return EmbeddingResult(
        vectors=result.vectors, model=config.model, dimension=config.dim, provider=config.provider,
        usage=result.usage, latency_ms=latency_ms,
    )


def transcribe(audio, mime_type, languages, feature, company_id=None) -> TranscriptResult:
    result, config, latency_ms = _call(
        "stt", feature, company_id,
        lambda provider, cfg: provider.transcribe(model=cfg.model, audio=audio, mime_type=mime_type, languages=languages),
    )
    return TranscriptResult(
        text=result.text, language=result.language, provider=config.provider, model=config.model,
        usage=result.usage, latency_ms=latency_ms,
    )


def synthesize(text, language, voice, feature, company_id=None) -> AudioResult:
    result, config, latency_ms = _call(
        "tts", feature, company_id,
        lambda provider, cfg: provider.synthesize(model=cfg.model, text=text, language=language, voice=voice),
    )
    return AudioResult(
        audio=result.audio, mime_type=result.mime_type, provider=config.provider, model=config.model,
        usage=result.usage, latency_ms=latency_ms,
    )
