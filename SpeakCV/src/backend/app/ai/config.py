import logging
import os
from dataclasses import dataclass
from functools import lru_cache

from app.ai.types import AIConfigError
from app.core import settings  # noqa: F401  (loads .env files)

logger = logging.getLogger(__name__)

SLOTS = ("reasoning", "bulk", "embedding", "stt", "tts")
TEXT_VENDORS = {"anthropic", "openai", "gemini", "fake"}
CAPABILITIES = {
    "reasoning": TEXT_VENDORS,
    "bulk": TEXT_VENDORS,
    "embedding": {"openai", "gemini", "voyage", "fake"},
    "stt": {"openai", "gemini", "fake"},
    "tts": {"openai", "gemini", "edge_tts", "fake"},
}
PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "voyage": "VOYAGE_API_KEY",
}
KNOWN_PROVIDERS = set().union(*CAPABILITIES.values())
MODELLESS_DEFAULTS = {"fake": "fake", "edge_tts": "edge-tts"}
FAKE_EMBEDDING_DIM = 64
OFFICIAL_OPENAI_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class SlotConfig:
    slot: str
    provider: str
    model: str
    dim: int | None = None


@dataclass(frozen=True)
class AIConfig:
    slots: dict[str, SlotConfig]

    def slot(self, name: str) -> SlotConfig:
        return self.slots[name]


def _load_slot(slot: str, is_production: bool) -> SlotConfig:
    provider_var = f"AI_{slot.upper()}_PROVIDER"
    model_var = f"AI_{slot.upper()}_MODEL"
    provider = os.environ.get(provider_var, "").strip().lower()
    if not provider:
        raise AIConfigError(f"{provider_var} is required (see .env.example).")
    if provider not in KNOWN_PROVIDERS:
        raise AIConfigError(f"{provider_var}={provider} is not a known provider: {sorted(KNOWN_PROVIDERS)}.")
    if provider not in CAPABILITIES[slot]:
        raise AIConfigError(f"{provider_var}={provider} cannot serve the {slot} slot. Use one of {sorted(CAPABILITIES[slot])}.")
    if provider == "fake" and is_production:
        raise AIConfigError(f"{provider_var}=fake is refused when APP_ENV=production.")

    key_var = PROVIDER_KEYS.get(provider)
    if key_var and not os.environ.get(key_var, "").strip():
        raise AIConfigError(f"{key_var} is required because {provider_var}={provider}.")

    model = os.environ.get(model_var, "").strip() or MODELLESS_DEFAULTS.get(provider, "")
    if not model:
        raise AIConfigError(f"{model_var} is required because {provider_var}={provider}.")

    dim = None
    if slot == "embedding":
        raw_dim = os.environ.get("AI_EMBEDDING_DIM", "").strip()
        if raw_dim:
            if not raw_dim.isdigit() or int(raw_dim) < 1:
                raise AIConfigError("AI_EMBEDDING_DIM must be a positive integer.")
            dim = int(raw_dim)
        elif provider == "fake":
            dim = FAKE_EMBEDDING_DIM
        else:
            raise AIConfigError(f"AI_EMBEDDING_DIM is required because {provider_var}={provider}.")
    return SlotConfig(slot=slot, provider=provider, model=model, dim=dim)


def load_config() -> AIConfig:
    is_production = os.environ.get("APP_ENV", "").strip().lower() == "production"
    slots = {slot: _load_slot(slot, is_production) for slot in SLOTS}
    base_url = (os.environ.get("OPENAI_BASE_URL", "").strip() or OFFICIAL_OPENAI_URL).rstrip("/")
    if is_production and base_url != OFFICIAL_OPENAI_URL:
        logger.warning("OPENAI_BASE_URL is not the official endpoint. Never send real candidate data through a proxy.")
    return AIConfig(slots=slots)


@lru_cache(maxsize=1)
def get_config() -> AIConfig:
    return load_config()


def reset_config() -> None:
    get_config.cache_clear()
