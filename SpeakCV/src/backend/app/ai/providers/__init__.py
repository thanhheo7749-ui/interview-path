"""Vendor adapters. Only this package imports vendor SDKs, and only when that vendor is configured."""
from functools import lru_cache
from importlib import import_module

_PROVIDER_CLASSES = {
    "fake": ("app.ai.providers.fake", "FakeProvider"),
    "anthropic": ("app.ai.providers.anthropic", "AnthropicProvider"),
    "openai": ("app.ai.providers.openai", "OpenAIProvider"),
    "gemini": ("app.ai.providers.gemini", "GeminiProvider"),
    "voyage": ("app.ai.providers.voyage", "VoyageProvider"),
    "edge_tts": ("app.ai.providers.edge_tts", "EdgeTTSProvider"),
}


@lru_cache(maxsize=None)
def get_provider(name: str):
    module_name, class_name = _PROVIDER_CLASSES[name]
    return getattr(import_module(module_name), class_name)()
