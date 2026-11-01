from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database.database import engine

BASELINE_REVISION = "0001_baseline"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def _upgrade(connection) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    tables = set(inspect(connection).get_table_names())
    if "alembic_version" not in tables and "users" in tables:
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")


def run_migrations(connection=None) -> None:
    """Upgrade to head. A database created before Alembic is stamped at the baseline first, losing no data."""
    if connection is not None:
        _upgrade(connection)
        return
    with engine.begin() as new_connection:
        _upgrade(new_connection)
