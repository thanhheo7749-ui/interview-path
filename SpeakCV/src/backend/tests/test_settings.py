import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _import_app(env_overrides):
    env = {**os.environ, **env_overrides}
    env = {k: v for k, v in env.items() if v is not None}
    return subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )


def test_app_refuses_to_start_without_secret_key():
    result = _import_app({"SECRET_KEY": None})
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_app_refuses_a_short_secret_key():
    result = _import_app({"SECRET_KEY": "too-short"})
    assert result.returncode != 0
    assert "at least 32" in result.stderr


def test_app_refuses_to_start_without_database_url():
    result = _import_app({"DATABASE_URL": None})
    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_app_starts_with_valid_configuration():
    assert _import_app({}).returncode == 0
