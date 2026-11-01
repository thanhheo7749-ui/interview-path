"""Anthropic adapter. Reads only ANTHROPIC_API_KEY, ANTHROPIC_EFFORT and ANTHROPIC_FALLBACKS_ENABLED."""
import os
import re

import anthropic as anthropic_sdk

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
        response = self._call("create", model, system, messages, max_output_tokens, None)
        return self._to_text(response)

    def generate_structured(self, *, model, system, messages, schema, max_output_tokens) -> ProviderText:
        response = self._call("parse", model, system, messages, max_output_tokens, schema)
        text = self._to_text(response, allow_empty=True)
        if not text.text:
            parsed = getattr(response, "parsed_output", None)
            if parsed is None:
                raise AIOutputError("Anthropic returned no structured output")
            return ProviderText(text=parsed.model_dump_json(), usage=text.usage)
        return text

    def _call(self, method, model, system, messages, max_output_tokens, schema):
        kwargs = {"model": model, "system": system, "messages": messages, "max_tokens": max_output_tokens}
        if _EFFORT_MODELS.match(model):
            kwargs["output_config"] = {"effort": self._effort}
        if schema is not None:
            kwargs["output_format"] = schema
        namespace = self._client.messages
        if self._fallbacks and _FALLBACK_MODELS.match(model):
            namespace = self._client.beta.messages
            kwargs["betas"] = [_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        try:
            if max_output_tokens > _STREAM_ABOVE_TOKENS:
                with namespace.stream(**kwargs) as stream:
                    return stream.get_final_message()
            return getattr(namespace, method)(**kwargs)
        except anthropic_sdk.APIStatusError as exc:
            raise AIProviderError(f"anthropic call failed: HTTP {exc.status_code}") from None
        except anthropic_sdk.APIConnectionError as exc:
            raise AIProviderError(f"anthropic call failed: {type(exc).__name__}") from None
        except anthropic_sdk.APIError as exc:
            raise AIProviderError(f"anthropic call failed: {type(exc).__name__}") from None
        except ValueError as exc:
            # pydantic.ValidationError (a ValueError) from messages.parse: the SDK does not expose the raw text.
            raise AIOutputError("Anthropic output did not match the requested schema") from None

    @staticmethod
    def _to_text(response, allow_empty=False) -> ProviderText:
        # Refusal and truncation are checked before any content is read.
        if response.stop_reason == "refusal":
            raise AIOutputError("Anthropic refused the request")
        if response.stop_reason == "max_tokens":
            raise AIOutputError("Anthropic output was cut off at max_tokens")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text and not allow_empty:
            raise AIOutputError("Anthropic returned no text")
        usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
        return ProviderText(text=text, usage=usage)
