import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SECRET_NAMES = {"SECRET_KEY", "MYSQL_ROOT_PASSWORD", "ADMIN_PASSWORD", "ANTHROPIC_API_KEY",
                "OPENAI_API_KEY", "GEMINI_API_KEY", "VOYAGE_API_KEY"}


def tracked_files():
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("no git checkout")
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def env_example():
    pairs = {}
    for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition("=")
            pairs[key.strip()] = value.strip()
    return pairs


def test_no_env_file_with_values_is_tracked():
    for path in tracked_files():
        name = path.rsplit("/", 1)[-1]
        if name.startswith(".env"):
            assert name == ".env.example", f"tracked env file: {path}"


def test_no_worktree_copies_or_sql_dumps_are_tracked():
    for path in tracked_files():
        assert ".claude/worktrees/" not in path
        assert not path.endswith(".sql")


def test_env_example_holds_no_secret_values():
    pairs = env_example()
    for name in SECRET_NAMES:
        assert name in pairs, f"{name} missing from .env.example"
        assert pairs[name] == "", f"{name} must be empty in .env.example"


def test_env_example_sets_every_ai_slot_to_fake():
    pairs = env_example()
    for slot in ("REASONING", "BULK", "EMBEDDING", "STT", "TTS"):
        assert pairs[f"AI_{slot}_PROVIDER"] == "fake"
