"""Environment configuration. Real environment variables always win over .env files."""
import os
from pathlib import Path

from dotenv import load_dotenv

MIN_SECRET_LENGTH = 32
DEFAULT_MAX_UPLOAD_MB = 20


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is missing or invalid."""


def _load_env_files() -> None:
    if os.environ.get("APP_ENV") == "test":
        return
    backend_root = Path(__file__).resolve().parents[2]
    candidates = [backend_root / ".env"]
    if len(backend_root.parents) > 2:
        candidates.append(backend_root.parents[2] / ".env")
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)


_load_env_files()


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required. Set it in the environment or in .env (see .env.example).")
    return value


def secret_key() -> str:
    value = required("SECRET_KEY")
    if len(value) < MIN_SECRET_LENGTH:
        raise ConfigError(f"SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters.")
    return value


def database_url() -> str:
    return required("DATABASE_URL")


def flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def csv_list(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def max_upload_bytes() -> int:
    return int(os.environ.get("MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)) * 1024 * 1024
