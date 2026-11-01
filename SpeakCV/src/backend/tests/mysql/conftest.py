"""Setup for the tests that need a real MySQL. `make test-mysql` starts a throwaway server and sets TEST_MYSQL_URL.

tests/conftest.py forces SQLite through DATABASE_URL. This file runs after it and before any app module is imported,
so with TEST_MYSQL_URL set the app's own engine and sessions point at MySQL, including the ones the pipeline opens.
"""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

MYSQL_URL = os.environ.get("TEST_MYSQL_URL", "").strip()
THIS_DIR = os.path.dirname(os.path.abspath(__file__))

if MYSQL_URL:
    if "test" not in (make_url(MYSQL_URL).database or ""):
        # Every test drops this database.
        pytest.exit("TEST_MYSQL_URL must name a database with 'test' in its name.", returncode=2)
    os.environ["DATABASE_URL"] = MYSQL_URL


def pytest_collection_modifyitems(items):
    """The SQLite tests drop every table before each test, so they must never run against this server."""
    if MYSQL_URL and any(not str(item.path).startswith(THIS_DIR) for item in items):
        pytest.exit("TEST_MYSQL_URL is set: run `pytest tests/mysql` on its own, or `make test-mysql`.", returncode=2)


def _recreate_database() -> None:
    url = make_url(MYSQL_URL)
    server = create_engine(url.set(database=None))
    try:
        with server.begin() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{url.database}`"))
            connection.execute(text(f"CREATE DATABASE `{url.database}` CHARACTER SET utf8mb4"))
    finally:
        server.dispose()


@pytest.fixture(autouse=True)
def _fresh_tables():
    """Replaces the SQLite fixture of the same name: an empty database, built by the migrations."""
    from app.ai.config import reset_config
    from app.ai.providers import fake
    from app.brain import retriever
    from app.database import sql_models  # noqa: F401
    from app.database.database import engine
    from app.database.migrate import run_migrations

    reset_config()
    fake.reset()
    retriever.clear_vector_cache()
    engine.dispose()
    _recreate_database()
    run_migrations()
    yield
    reset_config()
    engine.dispose()
