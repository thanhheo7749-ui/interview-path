"""Anthropic adapter. Reads only ANTHROPIC_API_KEY, ANTHROPIC_EFFORT and ANTHROPIC_FALLBACKS_ENABLED."""
import os
import re

import anthropic as anthropic_sdk

from app.ai.schema import to_strict_schema
from app.ai.types import AIConfigError, AIOutputError, AIProviderError, ProviderText, Usage

EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max"}
DEFAULT_EFFORT = "high"
# Claude 5 family models take output_config.effort. Older models (for example Haiku 4.5) reject it.
_EFFORT_MODELS = re.compile(r"^claude-(opus|sonnet|haiku)-5")
# Server-side fallbacks are documented for Opus and Sonnet; Haiku 5.5 has no server-side fallback.
_FALLBACK_MODELS = re.compile(r"^claude-(opus|sonnet)-5")
_FALLBACK_BETA = "server-side-fallback-2026-07-01"  # required by fallbacks="default"
# The SDK refuses non-streaming requests it estimates to take over ~10 minutes. Stream above this.
_STREAM_ABOVE_TOKENS = 16000


class AnthropicProvider:
    def __init__(self):
        self._client = anthropic_sdk.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._effort = os.environ.get("ANTHROPIC_EFFORT", DEFAULT_EFFORT).strip().lower() or DEFAULT_EFFORT
        if self._effort not in EFFORT_LEVELS:
            raise AIConfigError(f"ANTHROPIC_EFFORT must be one of {sorted(EFFORT_LEVELS)}")
        self._fallbacks = os.environ.get("ANTHROPIC_FALLBACKS_ENABLED", "true").strip().lower() not in {"false", "0", "no", "off"}

    def generate_text(self, *, model, system, messages, max_output_tokens) -> ProviderText:
        return self._to_text(self._call(model, system, messages, max_output_tokens, None))

    def generate_structured(self, *, model, system, messages, schema, max_output_tokens) -> ProviderText:
        # Raw JSON text is returned; the gateway validates it with Pydantic and retries on failure.
        return self._to_text(self._call(model, system, messages, max_output_tokens, schema))

    def _call(self, model, system, messages, max_output_tokens, schema):
        kwargs = {"model": model, "system": system, "messages": messages, "max_tokens": max_output_tokens}
        output_config = {}
        if _EFFORT_MODELS.match(model):
            output_config["effort"] = self._effort
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": to_strict_schema(schema)}
        if output_config:
            kwargs["output_config"] = output_config
        namespace = self._client.messages
        if self._fallbacks and _FALLBACK_MODELS.match(model):
            # fallbacks="default" is documented for Opus 5 and Sonnet 5.5, unverified for Opus 5.5.
            # If the API rejects it, the call fails with an error rather than silently skipping it.
            namespace = self._client.beta.messages
            kwargs["betas"] = [_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        try:
            if max_output_tokens > _STREAM_ABOVE_TOKENS:
                with namespace.stream(**kwargs) as stream:
                    return stream.get_final_message()
            return namespace.create(**kwargs)
        except anthropic_sdk.APIStatusError as exc:
            raise AIProviderError(f"anthropic call failed: HTTP {exc.status_code}") from None
        except anthropic_sdk.APIError as exc:
            raise AIProviderError(f"anthropic call failed: {type(exc).__name__}") from None

    @staticmethod
    def _to_text(response) -> ProviderText:
        usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
        # Refusal and truncation are checked before any content is read.
        if response.stop_reason == "refusal":
            raise AIOutputError("Anthropic refused the request", usage=usage)
        if response.stop_reason == "max_tokens":
            raise AIOutputError("Anthropic output was cut off at max_tokens", usage=usage)
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text:
            raise AIOutputError("Anthropic returned no text", usage=usage)
        return ProviderText(text=text, usage=usage)
