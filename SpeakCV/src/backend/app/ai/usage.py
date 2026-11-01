import logging
from functools import lru_cache
from pathlib import Path

import yaml

from app.ai.types import Usage
from app.database.database import SessionLocal
from app.database.sql_models import AIUsageLog

logger = logging.getLogger(__name__)
PRICING_PATH = Path(__file__).with_name("pricing.yaml")


@lru_cache(maxsize=1)
def _prices() -> dict:
    return yaml.safe_load(PRICING_PATH.read_text(encoding="utf-8"))["models"]


def estimate_cost(model: str, usage: Usage) -> float | None:
    """A figure that left out part of the call would read as complete, so an unpriced part makes the whole None."""
    price = _prices().get(model)
    if price is None:
        return None
    parts = (
        (usage.input_tokens, "input_per_1m", 1_000_000),
        (usage.output_tokens, "output_per_1m", 1_000_000),
        (usage.audio_seconds, "per_audio_second", 1),
        (usage.characters, "per_1k_characters", 1_000),
    )
    if any(amount and key not in price for amount, key, _ in parts):
        return None
    return sum(amount * price[key] / divisor for amount, key, divisor in parts if amount)


def log_usage(*, feature, slot, provider, model, company_id, usage, latency_ms, success, error_type=None) -> None:
    """Write one row per vendor call. A logging failure never breaks the AI call."""
    try:
        session = SessionLocal()
        try:
            session.add(
                AIUsageLog(
                    company_id=company_id,
                    feature=feature,
                    slot=slot,
                    provider=provider,
                    model=model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    audio_seconds=usage.audio_seconds,
                    characters=usage.characters,
                    latency_ms=latency_ms,
                    estimated_cost_usd=estimate_cost(model, usage),
                    success=success,
                    error_type=error_type,
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.exception("Could not write ai_usage_logs row for feature %s", feature)
