"""Production deploy configuration. Scripts run in a temp copy with a made-up .env, never the real one."""
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[2]
COMPOSE_PROD = REPO / "docker-compose.prod.yml"
FAKE_SECRET = "made-up-operator-value-1234"

needs_repo = pytest.mark.skipif(not COMPOSE_PROD.exists(), reason="repository root is not present")
needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")


def _backend_service():
    return yaml.safe_load(COMPOSE_PROD.read_text(encoding="utf-8"))["services"]["speakcv-backend"]


def _read_env(path: Path) -> dict:
    return dict(
        line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def _temp_repo(tmp_path: Path, old_env: str) -> Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    for name in ("sync-vps-env.sh", "vps-deploy.sh"):
        shutil.copy(REPO / "scripts" / name, root / "scripts" / name)
    (root / ".env").write_text(old_env, encoding="utf-8")
    return root


def _run_sync(root: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in {"OUT_FILE", "SOURCE_ENV"}}
    return subprocess.run(
        ["bash", "scripts/sync-vps-env.sh"], cwd=root, env=env, capture_output=True, text=True, check=True,
    )


def _resolved_env_for(tmp_path: Path, enable_proxy: str) -> dict:
    """Run the deploy script's config mode with a stub docker, then read what it resolved for compose."""
    old_env = "\n".join([
        f"ENABLE_PROXY={enable_proxy}",
        "PUBLIC_HOST=203.0.113.7",
        "PRIMARY_DOMAIN=portal.hire.test",
        "SPEAKCV_DOMAIN=speak.hire.test",
        "API_DOMAIN=api.hire.test",
        *[f"AI_{slot}_PROVIDER=openai" for slot in ("REASONING", "BULK", "EMBEDDING", "STT", "TTS")],
    ]) + "\n"
    root = _temp_repo(tmp_path, old_env)
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "docker"
    stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}"}
    for name in ("OUT_FILE", "SOURCE_ENV", "ENV_FILE", "COMPOSE_FILE", "RESOLVED_ENV_FILE"):
        env.pop(name, None)
    subprocess.run(["bash", "scripts/vps-deploy.sh", "config"], cwd=root, env=env, capture_output=True, text=True, check=True)
    return _read_env(root / ".omx" / "generated" / "vps.env")


@needs_repo
def test_backend_receives_the_resolved_allowed_origins():
    assert _backend_service()["environment"]["ALLOWED_ORIGINS"] == "${ALLOWED_ORIGINS}"


@needs_repo
def test_backend_receives_the_trusted_proxy_list():
    assert _backend_service()["environment"]["FORWARDED_ALLOW_IPS"] == "${FORWARDED_ALLOW_IPS}"


@needs_repo
def test_backend_port_binds_to_a_configurable_address():
    assert "${SPEAKCV_BACKEND_BIND:-127.0.0.1}:${SPEAKCV_BACKEND_PORT:-8000}:8000" in _backend_service()["ports"]


@needs_repo
@needs_bash
def test_direct_mode_exposes_the_backend_and_trusts_no_proxy(tmp_path):
    resolved = _resolved_env_for(tmp_path, "0")
    assert resolved["SPEAKCV_BACKEND_BIND"] == "0.0.0.0"
    assert resolved["FORWARDED_ALLOW_IPS"] == "127.0.0.1"
    assert resolved["ALLOWED_ORIGINS"] == "http://203.0.113.7:3000,http://203.0.113.7:5173"


@needs_repo
@needs_bash
def test_proxy_mode_hides_the_backend_and_trusts_caddy(tmp_path):
    resolved = _resolved_env_for(tmp_path, "1")
    assert resolved["SPEAKCV_BACKEND_BIND"] == "127.0.0.1"
    assert resolved["FORWARDED_ALLOW_IPS"] == "*"
    assert resolved["ALLOWED_ORIGINS"] == "https://portal.hire.test,https://speak.hire.test"


@needs_repo
@needs_bash
def test_sync_keeps_keys_the_template_does_not_write(tmp_path):
    root = _temp_repo(tmp_path, f"OPERATOR_ONLY_SETTING={FAKE_SECRET}\nANTHROPIC_EFFORT=max\n# a comment\nJWT_ALGORITHM=HS512\n")
    result = _run_sync(root)
    text = (root / ".env").read_text(encoding="utf-8")
    assert f"OPERATOR_ONLY_SETTING={FAKE_SECRET}\n" in text
    assert "ANTHROPIC_EFFORT=max\n" in text
    assert FAKE_SECRET not in result.stdout + result.stderr
    assert len(re.findall(r"^JWT_ALGORITHM=", text, re.M)) == 1
    assert "JWT_ALGORITHM=HS512\n" in text
    assert stat.S_IMODE((root / ".env").stat().st_mode) == 0o600


@needs_repo
@needs_bash
def test_sync_twice_does_not_duplicate_kept_keys(tmp_path):
    root = _temp_repo(tmp_path, f"OPERATOR_ONLY_SETTING={FAKE_SECRET}\n")
    _run_sync(root)
    first = (root / ".env").read_text(encoding="utf-8")
    _run_sync(root)
    second = (root / ".env").read_text(encoding="utf-8")
    assert second == first
    assert second.count("OPERATOR_ONLY_SETTING=") == 1


@needs_repo
def test_env_example_documents_operator_settings():
    keys = _read_env(REPO / ".env.example")
    assert {"ANTHROPIC_EFFORT", "ANTHROPIC_FALLBACKS_ENABLED", "STORAGE_DIR", "FORWARDED_ALLOW_IPS"} <= set(keys)


@needs_repo
def test_compose_and_env_example_warn_about_url_safe_database_password():
    for name in ("docker-compose.yml", ".env.example"):
        assert re.search(r"#.*MYSQL_ROOT_PASSWORD.*URL-safe", (REPO / name).read_text(encoding="utf-8")), name


@needs_repo
def test_caddy_limits_api_request_bodies():
    assert re.search(r"request_body\s*\{\s*max_size\s+\S+", (REPO / "deploy" / "Caddyfile").read_text(encoding="utf-8"))
    assert "request_body" in (REPO / "docs" / "operations" / "environment.md").read_text(encoding="utf-8")


def test_every_direct_dependency_is_pinned():
    lines = [line.split("#")[0].strip() for line in (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    requirements = [line for line in lines if line]
    assert requirements
    assert [line for line in requirements if not re.fullmatch(r"[A-Za-z0-9_.\-]+(\[[a-z0-9,]+\])?==[0-9][^\s]*", line)] == []
    names = {re.split(r"[\[=]", line)[0].lower() for line in requirements}
    assert "httpx" in names, "the Gemini adapter imports httpx directly"
