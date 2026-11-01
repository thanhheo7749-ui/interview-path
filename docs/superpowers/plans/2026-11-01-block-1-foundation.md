# Block 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the system safe and honest, make AI vendors swappable through a neutral gateway, and add companies, departments and members with a real HR portal login.

**Architecture:** One FastAPI backend (`SpeakCV/src/backend`) serves two frontends: the Next.js candidate app (`SpeakCV/src/frontend`) and the Vite HR portal (`interviewpath/interviewpath-demo`). All AI access goes through `app/ai/gateway.py`. All company APIs live under `/api/companies/{company_id}/...` behind one `require_member` dependency. Schema changes go through Alembic.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, MySQL 8.0 (SQLite in tests), slowapi, Pydantic v2, Next.js 16, React 18/Vite, react-i18next, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-01-block-1-foundation-design.md`, parent `docs/superpowers/specs/2026-11-01-hiring-platform-overview-design.md`.

## Global Constraints

- Git commit messages: a single line, no body, never a `Co-Authored-By` trailer. Commit only the files your task touches.
- Never print, log, copy into docs, or commit the values of `.env`, `SpeakCV/.env`, API keys, or passwords. Show variable names only.
- Do not rewrite git history. Do not push. Do not touch Docker containers you did not start (other projects run on this machine).
- Business code imports only `app.ai.gateway`. Vendor SDKs (`anthropic`, `openai`, `google.genai`, `voyageai`, `edge_tts`) are imported only under `app/ai/providers/`.
- Never send `temperature` or `top_p` to any vendor.
- JSON schemas sent to vendors use only objects, arrays, strings, numbers, booleans, enums and `required`, with `additionalProperties: false`. Other constraints are enforced in Pydantic after the response.
- `generate_structured` validates and retries once with the validation error; a second failure raises `AIOutputError`.
- No automatic cross-vendor failover.
- `AIProviderError` maps to HTTP 503, `AIOutputError` to HTTP 502. Never swallow them into fake content.
- `SECRET_KEY` is required with at least 32 characters. There are no default credentials anywhere.
- `APP_ENV=production` refuses to start with any `fake` slot.
- `MAX_UPLOAD_MB` defaults to 20. Oversized uploads get 413, unsupported types get 415. Client filenames are never used to write files.
- Non-members of a company get 403 on every `/api/companies/{company_id}/...` route. Platform `admin` has no implicit company access.
- `make test` needs no network and no real AI keys; it uses the `fake` provider and SQLite.
- Backend Python environment: `SpeakCV/src/backend/.venv` (created in Task 1). Run tests with `make test` from the repo root, or `.venv/bin/python -m pytest <path> -q` from `SpeakCV/src/backend`.

## Review Focus

- A slot pointing at a vendor that cannot serve it (for example `AI_EMBEDDING_PROVIDER=anthropic`): startup fails and names the variable. Test in Task 4.
- An upload whose filename is `../../etc/passwd.webm`: nothing is written using that name. Test in Task 8.
- A member removed from a company while holding a valid token: the next request gets 403 with no re-login. Test in Task 12.
- Removing or demoting a company's last HR member, which would lock the company: 409. Test in Task 12.
- An expired token in the portal: the user lands on the login page instead of a blank or broken screen. Test in Task 13.

---

### Task 1: Repository cleanup and test harness

**Files:**
- Create: `.env.example`, `docs/operations/environment.md`, `SpeakCV/src/backend/requirements-dev.txt`, `SpeakCV/src/backend/pytest.ini`, `SpeakCV/src/backend/.dockerignore`, `SpeakCV/src/backend/tests/test_repo_hygiene.py`
- Modify: `.gitignore`, `Makefile`, `SpeakCV/src/backend/tests/conftest.py`, `SpeakCV/src/backend/Dockerfile`
- Delete: `SpeakCV/.env.example`, `SpeakCV/src/backend/.env.example` (root `.env.example` becomes the single source)
- Untrack, keeping local copies: `.env`, `SpeakCV/.env`, `SpeakCV/.claude/worktrees/`

**Interfaces:**
- Produces: `make test`; `SpeakCV/src/backend/.venv`; the environment variable catalogue in `.env.example`; test environment set in `conftest.py` before any `app` import.

- [ ] **Step 1: Tag the mockup**

```bash
git tag mockup-2026-11 main
```

- [ ] **Step 2: Create the backend environment**

Python 3.10 reached end of life in October 2026 and the Google client warns about it, so the project moves to 3.12.

```bash
cd SpeakCV/src/backend
uv venv --python 3.12 .venv
```

Change the first line of `SpeakCV/src/backend/Dockerfile` from `FROM python:3.10-slim` to `FROM python:3.12-slim`.

Create `SpeakCV/src/backend/requirements-dev.txt`:

```
-r requirements.txt
pytest
httpx
```

Create `SpeakCV/src/backend/pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
filterwarnings =
    ignore::DeprecationWarning
    ignore::FutureWarning
```

Create `SpeakCV/src/backend/.dockerignore`:

```
.venv
__pycache__
*.pyc
tests
.env
```

```bash
uv pip install --python .venv/bin/python -q -r requirements-dev.txt
```

- [ ] **Step 3: Write the failing hygiene test**

Create `SpeakCV/src/backend/tests/test_repo_hygiene.py`:

```python
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
```

- [ ] **Step 4: Run it to verify it fails**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_repo_hygiene.py -q`
Expected: FAIL (tracked `.env`, no root `.env.example`).

- [ ] **Step 5: Clean the repository**

Append to `.gitignore` (the existing `# Environment files` heading is empty; put the env rules under it):

```
.env
.env.*
!.env.example
.claude/worktrees/
.superpowers/
.playwright-mcp/
*.sql
.venv/
```

```bash
git rm --cached --quiet .env SpeakCV/.env
git rm -r --cached --quiet SpeakCV/.claude/worktrees
git rm --quiet SpeakCV/.env.example SpeakCV/src/backend/.env.example
```

Create `.env.example` at the repo root with exactly these variables:

```
# Copy to .env and fill in. Never commit .env.

# Runtime
APP_ENV=development
LEGACY_B2C_ENABLED=false
NEXT_PUBLIC_LEGACY_B2C_ENABLED=false
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
MAX_UPLOAD_MB=20
# Trusted proxy addresses for client IPs. Use * only when the backend is reachable solely through Caddy.
FORWARDED_ALLOW_IPS=127.0.0.1

# Auth. SECRET_KEY needs at least 32 characters: openssl rand -hex 32
SECRET_KEY=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=3000
GOOGLE_CLIENT_ID=
NEXT_PUBLIC_GOOGLE_CLIENT_ID=

# Database. DATABASE_URL must use the same password as MYSQL_ROOT_PASSWORD.
MYSQL_DATABASE=speakcv
MYSQL_ROOT_PASSWORD=
DATABASE_URL=

# Optional platform admin, created only if absent and never overwritten
ADMIN_EMAIL=
ADMIN_PASSWORD=
ADMIN_NAME=Admin

# AI slots. Provider: anthropic, openai, gemini, voyage, edge_tts, fake.
# Anthropic has no embedding model and lists no speech services, so a Claude setup needs a second vendor.
AI_REASONING_PROVIDER=fake
AI_REASONING_MODEL=
AI_BULK_PROVIDER=fake
AI_BULK_MODEL=
AI_EMBEDDING_PROVIDER=fake
AI_EMBEDDING_MODEL=
AI_EMBEDDING_DIM=
AI_STT_PROVIDER=fake
AI_STT_MODEL=
AI_TTS_PROVIDER=fake
AI_TTS_MODEL=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
GEMINI_API_KEY=
VOYAGE_API_KEY=

# Frontends
NEXT_PUBLIC_API_URL=http://localhost:8001
VITE_API_URL=http://localhost:8001
VITE_SPEAKCV_URL=http://localhost:3000

# Ports and domains
INTERVIEWPATH_PORT=5173
SPEAKCV_FRONTEND_PORT=3000
SPEAKCV_BACKEND_PORT=8001
ENABLE_PROXY=0
PUBLIC_HOST=auto
PRIMARY_DOMAIN=
SPEAKCV_DOMAIN=
API_DOMAIN=

# Legacy consumer features, used only with LEGACY_B2C_ENABLED=true
VNPAY_TMN_CODE=
VNPAY_HASH_SECRET=
VNPAY_PAYMENT_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
VNPAY_RETURN_URL=http://localhost:3000/upgrade/success
```

Create `docs/operations/environment.md`:

```markdown
# Environment files

`.env` and `SpeakCV/.env` are no longer tracked. Copy `.env.example` to `.env` and fill it in.

## Before pulling this change on any machine, including the VPS

Git deletes a file when a pull removes it from tracking. Back up first:

    cp .env ~/env-backup-interview-path && chmod 600 ~/env-backup-interview-path

After the pull, restore it, then add the new variables listed in `.env.example`.
Switching between a branch that tracks `.env` and one that does not has the same effect.

## Secrets exposed in history

History was not rewritten, because the repository is private. Rotate every value that was tracked:
the AI proxy key, `SECRET_KEY`, the MySQL root password and the admin password. If this repository
ever goes public or to the organiser, publish from a new repository, because old dumps remain in history.
```

- [ ] **Step 6: Set the test environment and add `make test`**

Replace `SpeakCV/src/backend/tests/conftest.py` with:

```python
import os
import sys
from pathlib import Path

os.environ.update(
    {
        "APP_ENV": "test",
        "SECRET_KEY": "test-only-secret-key-0123456789abcdef",
        "DATABASE_URL": "sqlite://",
        "LEGACY_B2C_ENABLED": "false",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "MAX_UPLOAD_MB": "1",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "AI_REASONING_PROVIDER": "fake",
        "AI_BULK_PROVIDER": "fake",
        "AI_EMBEDDING_PROVIDER": "fake",
        "AI_STT_PROVIDER": "fake",
        "AI_TTS_PROVIDER": "fake",
    }
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
```

Add to the root `Makefile`, and add `test` to the `.PHONY` line:

```make
BACKEND_DIR = SpeakCV/src/backend
BACKEND_PY = $(if $(wildcard $(BACKEND_DIR)/.venv/bin/python),.venv/bin/python,python3)

test:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m pytest -q
```

- [ ] **Step 7: Run the full suite**

Run: `make test`
Expected: all tests pass, including `test_repo_hygiene.py` once the deletions are staged. `git ls-files` is checked against the index, so run it after the `git rm` commands.

- [ ] **Step 8: Commit**

```bash
git add .gitignore .env.example Makefile docs/operations/environment.md SpeakCV/src/backend/Dockerfile SpeakCV/src/backend/.dockerignore SpeakCV/src/backend/pytest.ini SpeakCV/src/backend/requirements-dev.txt SpeakCV/src/backend/tests/conftest.py SpeakCV/src/backend/tests/test_repo_hygiene.py
git commit -m "chore: untrack secrets and worktree copies, add env example and make test"
```

Confirm `git status` shows nothing staged and `.env` still exists on disk (`test -f .env`). Report in your final message that the tag and the untracking are done; do not print file contents.

---

### Task 2: Required configuration and login hardening

**Files:**
- Create: `SpeakCV/src/backend/app/core/settings.py`, `app/core/rate_limit.py`, `tests/helpers.py`, `tests/test_settings.py`, `tests/test_seed_admin.py`, `tests/test_auth_hardening.py`
- Modify: `app/auth/security.py`, `app/core/config.py`, `app/database/database.py`, `app/main.py`, `app/routers/auth.py`, `requirements.txt`, `tests/conftest.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `scripts/sync-vps-env.sh`, `scripts/vps-deploy.sh`, `interviewpath/interviewpath-demo/Dockerfile.prod`
- Remove `load_dotenv` from: `app/ai_service.py`, `app/routers/interview.py`, `app/routers/jobs.py`

All backend paths in this task are relative to `SpeakCV/src/backend`.

**Interfaces:**
- Produces:
  - `app.core.settings`: `ConfigError(RuntimeError)`, `required(name) -> str`, `secret_key() -> str`, `database_url() -> str`, `flag(name, default=False) -> bool`, `csv_list(name) -> list[str]`, `max_upload_bytes() -> int`
  - `app.main.create_app() -> FastAPI`, and module-level `app = create_app()`
  - `tests/conftest.py` fixtures: `db` (a Session), `app`, `client` (a TestClient), autouse table reset
  - `tests/helpers.py`: `make_user(db, email, role="user") -> User`, `auth_header(email) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings.py`:

```python
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
```

Create `tests/test_seed_admin.py`:

```python
from app.auth.security import verify_password
from app.database.sql_models import User
from app.main import seed_admin


def test_seed_creates_admin_when_absent(db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.test")
    monkeypatch.setenv("ADMIN_PASSWORD", "first-password")
    seed_admin()
    user = db.query(User).filter_by(email="ops@example.test").one()
    assert user.role == "admin"
    assert verify_password("first-password", user.hashed_password)


def test_seed_never_overwrites_an_existing_user(db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.test")
    monkeypatch.setenv("ADMIN_PASSWORD", "first-password")
    seed_admin()
    monkeypatch.setenv("ADMIN_PASSWORD", "second-password")
    seed_admin()
    db.expire_all()
    user = db.query(User).filter_by(email="ops@example.test").one()
    assert verify_password("first-password", user.hashed_password)


def test_seed_does_nothing_without_configuration(db, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    seed_admin()
    assert db.query(User).count() == 0
```

Create `tests/test_auth_hardening.py`:

```python
from app.core.rate_limit import limiter
from app.routers import auth as auth_router


class FakeResponse:
    def __init__(self, payload, ok=True):
        self._payload = payload
        self.ok = ok

    def json(self):
        return self._payload


def _google_stub(aud):
    def fake_get(url, **kwargs):
        if "tokeninfo" in url:
            return FakeResponse({"aud": aud})
        return FakeResponse({"email": "g@example.test", "name": "G"})
    return fake_get


def test_google_token_for_another_app_is_rejected(client, monkeypatch):
    monkeypatch.setattr(auth_router.requests, "get", _google_stub("some-other-app"))
    response = client.post("/api/auth/google", json={"token": "t"})
    assert response.status_code == 401


def test_google_token_for_this_app_is_accepted(client, monkeypatch):
    monkeypatch.setattr(auth_router.requests, "get", _google_stub("test-google-client-id"))
    response = client.post("/api/auth/google", json={"token": "t"})
    assert response.status_code == 200


def test_google_login_is_unavailable_without_client_id(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    response = client.post("/api/auth/google", json={"token": "t"})
    assert response.status_code == 503


def test_login_is_rate_limited(client):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            client.post("/api/login", json={"email": "a@example.test", "password": "x"}).status_code
            for _ in range(11)
        ]
    finally:
        limiter.enabled = False
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_cors_allows_only_configured_origins(client):
    allowed = client.options(
        "/api/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    denied = client.options(
        "/api/login",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
```

Create `tests/helpers.py`:

```python
from app.auth.security import create_access_token
from app.database.sql_models import User


def make_user(db, email, role="user"):
    user = User(email=email, full_name=email.split("@")[0], hashed_password="not-a-real-hash", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_header(email):
    return {"Authorization": f"Bearer {create_access_token({'sub': email})}"}
```

Append to `tests/conftest.py`:

```python
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_tables():
    from app.database import sql_models  # noqa: F401
    from app.database.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    from app.database.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_settings.py tests/test_seed_admin.py tests/test_auth_hardening.py -q`
Expected: FAIL (no `create_app`, no `app.core.rate_limit`, default secret still accepted).

- [ ] **Step 3: Implement settings**

Create `app/core/settings.py`:

```python
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
```

Change `app/auth/security.py`: remove `load_dotenv`, read `SECRET_KEY = settings.secret_key()` from `app.core.settings`, and replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.

Change `app/core/config.py`: remove `load_dotenv` and the `SECRET_KEY`, `JWT_ALGORITHM` and `ACCESS_TOKEN_EXPIRE_MINUTES` attributes; first `grep -rn "settings\.\(SECRET_KEY\|JWT_ALGORITHM\|ACCESS_TOKEN\)" app` and fix any use to import from `app.auth.security`. Import `app.core.settings` at the top so env files load first.

Change `app/database/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import settings

SQLALCHEMY_DATABASE_URL = settings.database_url()

_engine_kwargs = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if SQLALCHEMY_DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Keep the licence header already at the top of each file you edit.

Remove every remaining `load_dotenv` call and import from `app/main.py`, `app/ai_service.py`, `app/routers/interview.py` and `app/routers/jobs.py`. Verify: `grep -rn load_dotenv app core` prints only `app/core/settings.py`.

- [ ] **Step 4: Implement rate limiting, Google audience check, safe seeding, `create_app`**

Add `slowapi` to `requirements.txt` and install it into `.venv`.

Create `app/core/rate_limit.py`:

```python
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

LOGIN_LIMIT = "10/minute"

limiter = Limiter(key_func=get_remote_address, enabled=os.environ.get("APP_ENV") != "test")
```

In `app/routers/auth.py`:
- Add `request: Request` as the first parameter of `register` and `login`, and decorate both with `@limiter.limit(LOGIN_LIMIT)` beneath the route decorator.
- In `login_google`, read `client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()` at the top; if empty raise `HTTPException(503, "Google login is not configured")`. The frontend sends a Google access token, so verify audience before calling userinfo:

```python
tokeninfo = requests.get(
    "https://oauth2.googleapis.com/tokeninfo",
    params={"access_token": google_data.token},
    timeout=10,
)
if not tokeninfo.ok or tokeninfo.json().get("aud") != client_id:
    raise ValueError("Token was not issued for this application")
```

Add `timeout=10` to the existing userinfo request. Replace `random.choices` with `secrets.token_urlsafe(32)` for the unusable password.

In `app/main.py`, rewrite the bottom half so that:
- `seed_admin()` reads `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` with no credential defaults (`ADMIN_NAME` may default to `"Admin"`), returns if email or password is empty, returns if a user with that email exists, and otherwise creates the user with `role="admin"`. It never changes an existing user.
- `create_app()` builds the app, sets `app.state.limiter = limiter`, registers `RateLimitExceeded` with slowapi's `_rate_limit_exceeded_handler`, adds `CORSMiddleware` with `allow_origins=settings.csv_list("ALLOWED_ORIGINS")`, `allow_credentials=True`, `allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]`, `allow_headers=["Authorization", "Content-Type"]`, and the existing `expose_headers`, then includes the existing routers.
- Module level: `app = create_app()`.
- Delete `default_origins` and `CORS_ORIGINS`.
- Keep `sql_models.Base.metadata.create_all` and `ensure_profile_master_cv_column` for now; Task 3 removes them.

- [ ] **Step 5: Remove credential defaults from compose and deploy scripts**

`docker-compose.yml`, service `speakcv-backend`: replace the `environment` block with:

```yaml
    env_file:
      - ./.env
    environment:
      DATABASE_URL: mysql+pymysql://root:${MYSQL_ROOT_PASSWORD:?set MYSQL_ROOT_PASSWORD in .env}@db:3306/${MYSQL_DATABASE:?set MYSQL_DATABASE in .env}
```

Service `db`: `MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:?set MYSQL_ROOT_PASSWORD in .env}` and `MYSQL_DATABASE: ${MYSQL_DATABASE:?set MYSQL_DATABASE in .env}`. Service `interviewpath-demo`: add `environment: { VITE_API_URL: "${VITE_API_URL:-http://localhost:8001}" }`.

`docker-compose.prod.yml`: `interviewpath-demo` gets build arg `VITE_API_URL: ${VITE_API_URL}`. `interviewpath/interviewpath-demo/Dockerfile.prod`: add `ARG VITE_API_URL` and `ENV VITE_API_URL=$VITE_API_URL` next to the existing `VITE_SPEAKCV_URL` lines.

`scripts/sync-vps-env.sh`:
- In the generated file, replace `CORS_ORIGINS=` with `ALLOWED_ORIGINS=`, add `APP_ENV=production`, `LEGACY_B2C_ENABLED=false`, `NEXT_PUBLIC_LEGACY_B2C_ENABLED=false`, `MAX_UPLOAD_MB=20`, `VITE_API_URL=http://localhost:8000`, and `GOOGLE_CLIENT_ID=${google_client_id}`.
- Replace the `# AI providers` and `# AI runtime tuning` sections with the Block 1 AI variables from `.env.example`, each read with `first_real "$(source_value X)" "$(base_value X)"`, including `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY`. Remove `GROQ_API_KEY`, `OPENAI_MODEL_GPT4O*` and the `AI_*` tuning variables.
- Replace the `admin_email` default `"admin@gmail.com"` so no default exists; if no real value is found, leave `ADMIN_EMAIL` empty.
- Stop generating a random `ADMIN_PASSWORD` when none is given; leave it empty, because the admin account is optional.

`scripts/vps-deploy.sh`:
- Set `ALLOWED_ORIGINS` instead of `CORS_ORIGINS` in `write_resolved_env`, and also set `VITE_API_URL` to the same value as `next_public_api_url`.
- Remove `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `required_keys`.
- Replace the `OPENAI_API_KEY or GEMINI_API_KEY` check with:

```bash
for slot in REASONING BULK EMBEDDING STT TTS; do
  require_value "AI_${slot}_PROVIDER"
  if [[ "$(read_env "AI_${slot}_PROVIDER")" == "fake" ]]; then
    echo "AI_${slot}_PROVIDER is fake; production refuses the fake provider." >&2
    exit 1
  fi
done
```

Validate syntax: `bash -n scripts/sync-vps-env.sh scripts/vps-deploy.sh`, and `MYSQL_ROOT_PASSWORD=x MYSQL_DATABASE=y docker compose -f docker-compose.yml --env-file .env.example config --quiet` (this reads only; it starts nothing).

- [ ] **Step 6: Run the tests**

Run: `make test`
Expected: all pass. If an existing test built its own `FastAPI()` app it keeps working; do not change those here.

- [ ] **Step 7: Commit**

```bash
git add SpeakCV/src/backend docker-compose.yml docker-compose.prod.yml scripts interviewpath/interviewpath-demo/Dockerfile.prod
git commit -m "feat: require secrets at startup, harden login, rate limits and CORS"
```

---

### Task 3: Alembic migrations

**Files:**
- Create: `SpeakCV/src/backend/alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_baseline.py`, `app/database/migrate.py`, `app/cli.py`, `tests/test_migrations.py`
- Modify: `app/main.py`, `requirements.txt`, `Dockerfile`

**Interfaces:**
- Consumes: `app.database.database.engine`, `Base`.
- Produces:
  - `app.database.migrate.run_migrations(connection=None) -> None`
  - `app.database.migrate.alembic_config() -> alembic.config.Config`
  - `BASELINE_REVISION = "0001_baseline"`
  - `python -m app.cli migrate`. `app/cli.py` uses `argparse` subcommands; Task 12 adds `create-company`.
  - Rule for later tasks: every model change ships with a new file in `alembic/versions/`, and `tests/test_migrations.py::test_head_matches_models` must stay green.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_migrations.py`:

```python
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.database import sql_models  # noqa: F401
from app.database.database import Base
from app.database.migrate import BASELINE_REVISION, run_migrations


def _new_engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path}/migrate.db")


def test_upgrade_creates_all_tables_on_an_empty_database(tmp_path):
    engine = _new_engine(tmp_path)
    with engine.begin() as connection:
        run_migrations(connection)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "user_profiles", "interview_history", "alembic_version"} <= tables


def test_head_matches_models(tmp_path):
    engine = _new_engine(tmp_path)
    with engine.begin() as connection:
        run_migrations(connection)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": False})
        diffs = compare_metadata(context, Base.metadata)
    assert diffs == []


def test_existing_database_is_stamped_and_keeps_its_data(tmp_path):
    engine = _new_engine(tmp_path)
    legacy_tables = [t for name, t in Base.metadata.tables.items() if name in BASELINE_TABLES]
    Base.metadata.create_all(engine, tables=legacy_tables)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (email, full_name, hashed_password) VALUES ('keep@example.test', 'K', 'h')"))

    with engine.begin() as connection:
        run_migrations(connection)

    with engine.connect() as connection:
        version_rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        kept = connection.execute(text("SELECT email FROM users")).fetchall()
    assert len(version_rows) == 1
    assert version_rows[0][0] >= BASELINE_REVISION
    assert kept == [("keep@example.test",)]


def test_running_twice_is_safe(tmp_path):
    engine = _new_engine(tmp_path)
    for _ in range(2):
        with engine.begin() as connection:
            run_migrations(connection)


BASELINE_TABLES = {
    "users", "user_profiles", "experiences", "educations", "interview_history", "jd_templates",
    "system_config", "transaction_history", "support_messages", "transactions", "company_questions",
    "ai_brain_versions", "ai_brain_nodes", "ai_brain_edges", "ai_brain_ingestion_jobs",
    "ai_brain_ingestion_candidates", "ai_brain_ingestion_files",
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_migrations.py -q`
Expected: FAIL with `ModuleNotFoundError: alembic` or `app.database.migrate`.

- [ ] **Step 3: Add Alembic**

Add `alembic` to `requirements.txt` and install it. Run `.venv/bin/alembic init alembic` from the backend directory, then edit:

`alembic.ini`: `script_location = alembic`; remove `sqlalchemy.url`. Add `prepend_sys_path = .`.

`alembic/env.py`, replace with:

```python
from alembic import context

from app.database import sql_models  # noqa: F401
from app.database.database import Base, engine

target_metadata = Base.metadata


def run_migrations_online():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with engine.connect() as new_connection:
        _run(new_connection)
        new_connection.commit()


def _run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported.")
run_migrations_online()
```

Generate the baseline against an empty SQLite file. `app/main.py` must not be imported by Alembic; `env.py` above imports only the database modules:

```bash
DATABASE_URL="sqlite:////tmp/alembic_baseline.db" APP_ENV=test SECRET_KEY=$(python3 -c "print('x'*40)") \
  .venv/bin/alembic revision --autogenerate -m "baseline" --rev-id 0001_baseline
rm -f /tmp/alembic_baseline.db
```

Read the generated `alembic/versions/0001_baseline*.py`, rename it to `0001_baseline.py`, and confirm it creates all 17 tables in `BASELINE_TABLES` with their indexes. MySQL needs lengths on every `String` column; `sql_models.py` provides them, so confirm none was lost.

Create `app/database/migrate.py`:

```python
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
```

Create `app/cli.py`:

```python
import argparse

from app.database.migrate import run_migrations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Upgrade the database schema to the latest revision")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "migrate":
        run_migrations()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

In `app/main.py`: delete `sql_models.Base.metadata.create_all(...)`, `ensure_profile_master_cv_column`, its call in `lifespan`, and the now-unused `inspect, text` import.

`Dockerfile`, last line:

```dockerfile
CMD ["sh", "-c", "python -m app.cli migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
```

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Verify against real MySQL**

This uses a throwaway container with its own name and port. Do not touch other containers.

```bash
docker run -d --name block1-mysql-check -e MYSQL_ROOT_PASSWORD=checkpass -e MYSQL_DATABASE=check -p 33081:3306 mysql:8.0
until docker exec block1-mysql-check mysqladmin ping -h 127.0.0.1 -pcheckpass --silent; do sleep 3; done
cd SpeakCV/src/backend
export APP_ENV=test SECRET_KEY=$(python3 -c "print('x'*40)") DATABASE_URL="mysql+pymysql://root:checkpass@127.0.0.1:33081/check"
uv pip install --python .venv/bin/python -q cryptography
.venv/bin/python -m app.cli migrate
.venv/bin/python -m app.cli migrate
docker exec block1-mysql-check mysql -pcheckpass check -e "SHOW TABLES; SELECT * FROM alembic_version;"
docker rm -f block1-mysql-check
```

Expected: both `migrate` runs exit 0, and all 17 tables plus `alembic_version` exist. MySQL 8 needs the `cryptography` package for its default authentication; it is already pulled in by `python-jose[cryptography]`, but confirm. Put the output in your report. `unset` the exported variables afterwards.

- [ ] **Step 6: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add Alembic with a baseline migration and stamping for existing databases"
```

---

### Task 4: AI gateway core and fake provider

**Files:**
- Create under `SpeakCV/src/backend/app/ai/`: `__init__.py`, `types.py`, `config.py`, `schema.py`, `usage.py`, `gateway.py`, `pricing.yaml`, `providers/__init__.py`, `providers/fake.py`
- Create: `alembic/versions/0002_ai_usage_logs.py`, `tests/test_ai_config.py`, `tests/test_ai_gateway.py`, `tests/test_ai_schema.py`
- Modify: `app/database/sql_models.py`, `app/main.py`, `requirements.txt`, `tests/conftest.py`

**Interfaces:**
- Consumes: `app.database.database.SessionLocal`.
- Produces the code below. Every later block calls these signatures. `slot` is `"reasoning"` or `"bulk"`. `messages` is a list of `{"role": "user"|"assistant", "content": str}`. `schema` is a Pydantic model class.
  - `gateway.generate_text(slot, system, messages, max_output_tokens, feature, company_id=None) -> TextResult`
  - `gateway.generate_structured(slot, system, messages, schema, max_output_tokens, feature, company_id=None) -> StructuredResult`
  - `gateway.embed(texts, kind, feature, company_id=None) -> EmbeddingResult`, with `kind` being `"query"` or `"document"`
  - `gateway.transcribe(audio, mime_type, languages, feature, company_id=None) -> TranscriptResult`
  - `gateway.synthesize(text, language, voice, feature, company_id=None) -> AudioResult`
  - Provider contract (`providers/__init__.py`): methods `generate_text(model, system, messages, max_output_tokens) -> ProviderText`, `generate_structured(model, system, messages, schema, max_output_tokens) -> ProviderText` whose `.text` is the raw JSON, `embed(model, texts, kind, dim) -> ProviderEmbedding`, `transcribe(model, audio, mime_type, languages) -> ProviderTranscript`, `synthesize(model, text, language, voice) -> ProviderAudio`. All arguments keyword-only.
  - Test hooks in `app.ai.providers.fake`: `enqueue(feature, text)`, `reset()`. Queued text is returned for the next text or structured call with that feature; with an empty queue a default is generated.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai_schema.py`:

```python
from enum import Enum
from typing import Literal, Optional

import pytest
from pydantic import BaseModel, Field

from app.ai.schema import to_strict_schema


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class Inner(BaseModel):
    label: str = Field(min_length=1, max_length=5)


class Outer(BaseModel):
    title: str
    score: float = 0.0
    count: int
    ok: bool
    color: Color
    kind: Literal["a", "b"]
    items: list[Inner]


def test_strict_schema_inlines_refs_and_forbids_extra_properties():
    schema = to_strict_schema(Outer)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["color"] == {"type": "string", "enum": ["red", "blue"]}
    assert schema["properties"]["kind"] == {"type": "string", "enum": ["a", "b"]}
    inner = schema["properties"]["items"]["items"]
    assert inner == {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "required": ["label"],
        "additionalProperties": False,
    }


def test_strict_schema_rejects_optional_with_a_clear_message():
    class Bad(BaseModel):
        name: Optional[str] = None

    with pytest.raises(ValueError, match="name"):
        to_strict_schema(Bad)
```

Create `tests/test_ai_config.py`:

```python
import pytest

from app.ai.config import load_config
from app.ai.types import AIConfigError


def _all_fake(monkeypatch):
    for slot in ("REASONING", "BULK", "EMBEDDING", "STT", "TTS"):
        monkeypatch.setenv(f"AI_{slot}_PROVIDER", "fake")
    monkeypatch.setenv("APP_ENV", "test")


def test_all_fake_is_valid_outside_production(monkeypatch):
    _all_fake(monkeypatch)
    config = load_config()
    assert config.slot("reasoning").provider == "fake"
    assert config.slot("embedding").dim == 64


def test_production_refuses_a_fake_slot(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(AIConfigError, match="AI_REASONING_PROVIDER"):
        load_config()


def test_missing_key_names_the_variable(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_BULK_PROVIDER", "openai")
    monkeypatch.setenv("AI_BULK_MODEL", "some-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AIConfigError, match="OPENAI_API_KEY"):
        load_config()


def test_missing_model_names_the_variable(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_BULK_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("AI_BULK_MODEL", raising=False)
    with pytest.raises(AIConfigError, match="AI_BULK_MODEL"):
        load_config()


def test_vendor_that_cannot_serve_a_slot_is_refused(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_EMBEDDING_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_EMBEDDING_MODEL", "x")
    monkeypatch.setenv("AI_EMBEDDING_DIM", "8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    with pytest.raises(AIConfigError, match="AI_EMBEDDING_PROVIDER"):
        load_config()


def test_unknown_provider_is_refused(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_STT_PROVIDER", "nonsense")
    with pytest.raises(AIConfigError, match="AI_STT_PROVIDER"):
        load_config()


def test_embedding_dim_is_required_for_a_real_vendor(monkeypatch):
    _all_fake(monkeypatch)
    monkeypatch.setenv("AI_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("AI_EMBEDDING_MODEL", "m")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("AI_EMBEDDING_DIM", raising=False)
    with pytest.raises(AIConfigError, match="AI_EMBEDDING_DIM"):
        load_config()
```

Create `tests/test_ai_gateway.py`:

```python
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.ai import gateway
from app.ai.providers import fake
from app.ai.types import AIOutputError, AIProviderError
from app.database.sql_models import AIUsageLog


class Answer(BaseModel):
    answer: str


USER = [{"role": "user", "content": "hello"}]


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


def test_generate_text_returns_text_and_logs_usage(db):
    result = gateway.generate_text("reasoning", "sys", USER, 100, "unit_test", company_id=7)
    assert result.provider == "fake"
    assert "hello" in result.text
    row = db.query(AIUsageLog).one()
    assert (row.feature, row.slot, row.company_id, row.success) == ("unit_test", "reasoning", 7, True)
    assert row.input_tokens > 0


def test_structured_retries_once_with_the_validation_error(db):
    fake.enqueue("unit_test", "not json")
    fake.enqueue("unit_test", '{"answer": "ok"}')
    result = gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test")
    assert result.value == Answer(answer="ok")
    assert db.query(AIUsageLog).count() == 2
    assert fake.last_messages()[-1]["role"] == "user"
    assert "validation" in fake.last_messages()[-1]["content"].lower()


def test_structured_second_failure_raises_output_error():
    fake.enqueue("unit_test", "bad")
    fake.enqueue("unit_test", "still bad")
    with pytest.raises(AIOutputError):
        gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test")


def test_structured_default_output_matches_schema():
    assert gateway.generate_structured("bulk", "sys", USER, Answer, 100, "unit_test").value.answer


def test_vendor_failure_becomes_provider_error_and_is_logged(db, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("socket closed")

    monkeypatch.setattr(fake.FakeProvider, "generate_text", lambda self, **kw: boom(**kw))
    with pytest.raises(AIProviderError):
        gateway.generate_text("reasoning", "sys", USER, 100, "unit_test")
    row = db.query(AIUsageLog).one()
    assert row.success is False
    assert row.error_type == "RuntimeError"


def test_embed_is_deterministic_and_reports_model_and_dimension():
    first = gateway.embed(["xin chào thế giới", "other"], "document", "unit_test")
    second = gateway.embed(["xin chào thế giới", "other"], "query", "unit_test")
    assert first.vectors == second.vectors
    assert first.dimension == 64 == len(first.vectors[0])
    assert first.model == "fake"


def test_fake_embedding_ranks_shared_words_higher():
    vectors = gateway.embed(["annual leave policy", "annual leave days", "kubernetes cluster"], "document", "unit_test").vectors
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    assert dot(vectors[0], vectors[1]) > dot(vectors[0], vectors[2])


def test_transcribe_returns_utf8_audio_bytes_as_text():
    result = gateway.transcribe("xin chào".encode(), "audio/webm", ["vi"], "unit_test")
    assert result.text == "xin chào"
    assert result.language == "vi"


def test_synthesize_returns_audio():
    result = gateway.synthesize("hello", "en", None, "unit_test")
    assert result.audio and result.mime_type == "audio/mpeg"


def test_usage_log_failure_does_not_break_the_call(monkeypatch):
    from app.ai import usage

    def broken_session():
        raise RuntimeError("database down")

    monkeypatch.setattr(usage, "SessionLocal", broken_session)
    assert gateway.generate_text("reasoning", "sys", USER, 100, "unit_test").text


def test_cost_is_estimated_from_pricing():
    from app.ai.types import Usage
    from app.ai.usage import estimate_cost

    assert estimate_cost("claude-opus-5-5", Usage(input_tokens=1_000_000, output_tokens=1_000_000)) == pytest.approx(24.0)
    assert estimate_cost("unknown-model", Usage(input_tokens=5)) is None


def test_ai_errors_map_to_http_status(app):
    @app.get("/_boom503")
    def boom503():
        raise AIProviderError("down")

    @app.get("/_boom502")
    def boom502():
        raise AIOutputError("bad")

    client = TestClient(app)
    assert client.get("/_boom503").status_code == 503
    assert client.get("/_boom502").status_code == 502
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_ai_schema.py tests/test_ai_config.py tests/test_ai_gateway.py -q`
Expected: FAIL with `ModuleNotFoundError: app.ai`.

- [ ] **Step 3: Implement**

Add `pyyaml` to `requirements.txt` and install it.

`app/ai/__init__.py` is empty.

`app/ai/types.py`:

```python
from dataclasses import dataclass

from pydantic import BaseModel


class AIError(Exception):
    """Base class for AI gateway errors."""


class AIConfigError(AIError):
    """Configuration is missing or invalid. Raised at startup."""


class AIProviderError(AIError):
    """A vendor call failed in a way that may succeed later. HTTP 503."""


class AIOutputError(AIError):
    """The vendor returned unusable output, or refused. HTTP 502."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    audio_seconds: float = 0.0
    characters: int = 0


@dataclass(frozen=True)
class ProviderText:
    text: str
    usage: Usage


@dataclass(frozen=True)
class ProviderEmbedding:
    vectors: list[list[float]]
    usage: Usage


@dataclass(frozen=True)
class ProviderTranscript:
    text: str
    language: str
    usage: Usage


@dataclass(frozen=True)
class ProviderAudio:
    audio: bytes
    mime_type: str
    usage: Usage


@dataclass(frozen=True)
class TextResult:
    text: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class StructuredResult:
    value: BaseModel
    raw_text: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dimension: int
    provider: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class AudioResult:
    audio: bytes
    mime_type: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int
```

`app/ai/config.py`:

```python
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
    base_url = os.environ.get("OPENAI_BASE_URL", OFFICIAL_OPENAI_URL).rstrip("/")
    if is_production and base_url != OFFICIAL_OPENAI_URL:
        logger.warning("OPENAI_BASE_URL is not the official endpoint. Never send real candidate data through a proxy.")
    return AIConfig(slots=slots)


@lru_cache(maxsize=1)
def get_config() -> AIConfig:
    return load_config()


def reset_config() -> None:
    get_config.cache_clear()
```

`app/ai/schema.py`:

```python
from pydantic import BaseModel

PRIMITIVES = {"string", "number", "integer", "boolean"}
MAX_DEPTH = 16


def to_strict_schema(model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to the JSON schema subset every vendor accepts.

    Objects, arrays, strings, numbers, booleans and enums only. Every property is required and
    additional properties are forbidden. Other constraints stay in Pydantic and run after the response.
    """
    raw = model.model_json_schema()
    return _convert(raw, raw.get("$defs", {}), model.__name__, 0)


def _unsupported(path: str, node: dict) -> ValueError:
    return ValueError(
        f"Unsupported schema at {path}: {sorted(node)}. Use objects, arrays, strings, numbers, "
        "booleans and enums only. Optional and unions are not allowed; use an empty value instead."
    )


def _convert(node: dict, defs: dict, path: str, depth: int) -> dict:
    if depth > MAX_DEPTH:
        raise ValueError(f"Schema at {path} is too deep or recursive.")
    if "$ref" in node:
        return _convert(defs[node["$ref"].rsplit("/", 1)[1]], defs, path, depth + 1)
    if "enum" in node:
        return {"type": node.get("type", "string"), "enum": list(node["enum"])}
    if "const" in node:
        return {"type": node.get("type", "string"), "enum": [node["const"]]}
    node_type = node.get("type")
    if node_type == "object" and "properties" in node:
        properties = {
            name: _convert(child, defs, f"{path}.{name}", depth + 1)
            for name, child in node["properties"].items()
        }
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }
    if node_type == "array" and "items" in node:
        return {"type": "array", "items": _convert(node["items"], defs, f"{path}[]", depth + 1)}
    if node_type in PRIMITIVES:
        return {"type": node_type}
    raise _unsupported(path, node)
```

`app/ai/pricing.yaml`:

```yaml
# USD per 1M tokens, read from vendor pricing pages. Recheck before relying on these.
# A model missing from this list logs a NULL estimated cost.
as_of: "2026-11-01"
models:
  claude-opus-5-5: {input_per_1m: 4.0, output_per_1m: 20.0}
  claude-sonnet-5-5: {input_per_1m: 2.0, output_per_1m: 10.0}
  claude-haiku-5-5: {input_per_1m: 0.10, output_per_1m: 0.50}
  gpt-6-astra: {input_per_1m: 10.0, output_per_1m: 50.0}
  gpt-6-luna: {input_per_1m: 0.10, output_per_1m: 0.50}
  gemini-3.8-flash: {input_per_1m: 0.75, output_per_1m: 3.75}
  gemini-3.5-flash-lite: {input_per_1m: 0.30, output_per_1m: 2.50}
  text-embedding-3-small: {input_per_1m: 0.02, output_per_1m: 0.0}
  text-embedding-3-large: {input_per_1m: 0.13, output_per_1m: 0.0}
  gemini-embedding-2: {input_per_1m: 0.20, output_per_1m: 0.0}
  fake: {input_per_1m: 0.0, output_per_1m: 0.0}
```

`app/ai/usage.py`:

```python
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
    price = _prices().get(model)
    if price is None:
        return None
    return (usage.input_tokens * price["input_per_1m"] + usage.output_tokens * price["output_per_1m"]) / 1_000_000


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
```

`app/ai/providers/__init__.py`:

```python
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
```

`app/ai/providers/fake.py`:

```python
"""Deterministic, offline provider used by all tests and by development without keys."""
import hashlib
import json
import math
import re
from collections import defaultdict, deque

from app.ai.schema import to_strict_schema
from app.ai.types import ProviderAudio, ProviderEmbedding, ProviderText, ProviderTranscript, Usage

_queues = defaultdict(deque)
_current_feature = {"value": None}
_last_messages = {"value": []}
_TOKEN = re.compile(r"\w+", re.UNICODE)


def enqueue(feature: str, text: str) -> None:
    """Return this text from the next text or structured call for this feature."""
    _queues[feature].append(text)


def reset() -> None:
    _queues.clear()
    _last_messages["value"] = []


def last_messages() -> list[dict]:
    return _last_messages["value"]


def set_feature(feature: str) -> None:
    _current_feature["value"] = feature


def _usage(system: str, messages: list[dict], output: str) -> Usage:
    input_chars = len(system or "") + sum(len(m["content"]) for m in messages)
    return Usage(input_tokens=max(1, input_chars // 4), output_tokens=max(1, len(output) // 4))


def _default_value(schema: dict):
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema["type"]
    if kind == "object":
        return {name: _default_value(child) for name, child in schema["properties"].items()}
    if kind == "array":
        return []
    if kind == "string":
        return "fake"
    if kind == "boolean":
        return False
    return 0


class FakeProvider:
    def _next(self) -> str | None:
        queue = _queues.get(_current_feature["value"])
        return queue.popleft() if queue else None

    def generate_text(self, *, model, system, messages, max_output_tokens) -> ProviderText:
        _last_messages["value"] = list(messages)
        text = self._next()
        if text is None:
            text = f"[fake:{model}] {messages[-1]['content'][:80]}"
        return ProviderText(text=text, usage=_usage(system, messages, text))

    def generate_structured(self, *, model, system, messages, schema, max_output_tokens) -> ProviderText:
        _last_messages["value"] = list(messages)
        text = self._next()
        if text is None:
            text = json.dumps(_default_value(to_strict_schema(schema)), ensure_ascii=False)
        return ProviderText(text=text, usage=_usage(system, messages, text))

    def embed(self, *, model, texts, kind, dim) -> ProviderEmbedding:
        vectors = [self._embed_one(text, dim) for text in texts]
        return ProviderEmbedding(vectors=vectors, usage=Usage(input_tokens=sum(len(t) // 4 + 1 for t in texts)))

    @staticmethod
    def _embed_one(text: str, dim: int) -> list[float]:
        vector = [0.0] * dim
        for token in _TOKEN.findall(text.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % dim
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]

    def transcribe(self, *, model, audio, mime_type, languages) -> ProviderTranscript:
        text = audio.decode("utf-8", errors="ignore").strip() or "fake transcript"
        return ProviderTranscript(
            text=text,
            language=languages[0] if languages else "en",
            usage=Usage(audio_seconds=len(audio) / 16000),
        )

    def synthesize(self, *, model, text, language, voice) -> ProviderAudio:
        return ProviderAudio(audio=b"FAKEAUDIO:" + text.encode("utf-8"), mime_type="audio/mpeg", usage=Usage(characters=len(text)))
```

`app/ai/gateway.py`:

```python
"""The only entry point business code uses for AI. Names no vendor."""
import json
import time
from typing import Callable

from pydantic import BaseModel, ValidationError

from app.ai.config import get_config
from app.ai.providers import fake as fake_provider
from app.ai.providers import get_provider
from app.ai.types import (
    AIError,
    AIOutputError,
    AIProviderError,
    AudioResult,
    EmbeddingResult,
    StructuredResult,
    TextResult,
    TranscriptResult,
    Usage,
)
from app.ai.usage import log_usage

STRUCTURED_ATTEMPTS = 2


def _call(slot_name: str, feature: str, company_id: int | None, invoke: Callable):
    """Run one vendor call, write one usage row, and normalise unexpected errors."""
    slot = get_config().slot(slot_name)
    provider = get_provider(slot.provider)
    if slot.provider == "fake":
        fake_provider.set_feature(feature)
    started = time.perf_counter()
    common = {"feature": feature, "slot": slot_name, "provider": slot.provider, "model": slot.model, "company_id": company_id}
    try:
        result = invoke(provider, slot)
    except AIError as exc:
        log_usage(**common, usage=Usage(), latency_ms=_elapsed_ms(started), success=False, error_type=type(exc).__name__)
        raise
    except Exception as exc:
        log_usage(**common, usage=Usage(), latency_ms=_elapsed_ms(started), success=False, error_type=type(exc).__name__)
        raise AIProviderError(f"{slot.provider} call failed: {type(exc).__name__}") from exc
    latency_ms = _elapsed_ms(started)
    log_usage(**common, usage=result.usage, latency_ms=latency_ms, success=True)
    return result, slot, latency_ms


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def generate_text(slot, system, messages, max_output_tokens, feature, company_id=None) -> TextResult:
    result, config, latency_ms = _call(
        slot, feature, company_id,
        lambda provider, cfg: provider.generate_text(
            model=cfg.model, system=system, messages=messages, max_output_tokens=max_output_tokens
        ),
    )
    return TextResult(text=result.text, provider=config.provider, model=config.model, usage=result.usage, latency_ms=latency_ms)


def generate_structured(slot, system, messages, schema: type[BaseModel], max_output_tokens, feature, company_id=None) -> StructuredResult:
    attempt_messages = list(messages)
    last_error = None
    for _ in range(STRUCTURED_ATTEMPTS):
        current = list(attempt_messages)
        result, config, latency_ms = _call(
            slot, feature, company_id,
            lambda provider, cfg: provider.generate_structured(
                model=cfg.model, system=system, messages=current, schema=schema, max_output_tokens=max_output_tokens
            ),
        )
        try:
            value = schema.model_validate_json(result.text)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            attempt_messages = current + [
                {"role": "assistant", "content": result.text},
                {"role": "user", "content": f"Your previous response failed validation: {exc}. Return only corrected JSON."},
            ]
            continue
        return StructuredResult(
            value=value, raw_text=result.text, provider=config.provider, model=config.model,
            usage=result.usage, latency_ms=latency_ms,
        )
    raise AIOutputError(f"Structured output for feature {feature} failed validation twice: {last_error}")


def embed(texts, kind, feature, company_id=None) -> EmbeddingResult:
    if kind not in {"query", "document"}:
        raise ValueError("kind must be 'query' or 'document'")
    result, config, latency_ms = _call(
        "embedding", feature, company_id,
        lambda provider, cfg: provider.embed(model=cfg.model, texts=texts, kind=kind, dim=cfg.dim),
    )
    return EmbeddingResult(
        vectors=result.vectors, model=config.model, dimension=config.dim, provider=config.provider,
        usage=result.usage, latency_ms=latency_ms,
    )


def transcribe(audio, mime_type, languages, feature, company_id=None) -> TranscriptResult:
    result, config, latency_ms = _call(
        "stt", feature, company_id,
        lambda provider, cfg: provider.transcribe(model=cfg.model, audio=audio, mime_type=mime_type, languages=languages),
    )
    return TranscriptResult(
        text=result.text, language=result.language, provider=config.provider, model=config.model,
        usage=result.usage, latency_ms=latency_ms,
    )


def synthesize(text, language, voice, feature, company_id=None) -> AudioResult:
    result, config, latency_ms = _call(
        "tts", feature, company_id,
        lambda provider, cfg: provider.synthesize(model=cfg.model, text=text, language=language, voice=voice),
    )
    return AudioResult(
        audio=result.audio, mime_type=result.mime_type, provider=config.provider, model=config.model,
        usage=result.usage, latency_ms=latency_ms,
    )
```

Add `AIUsageLog` to `app/database/sql_models.py` (add `Boolean`/`Float` imports if missing; both are already imported):

```python
class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    company_id = Column(Integer, nullable=True, index=True)
    feature = Column(String(100), nullable=False, index=True)
    slot = Column(String(20), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    audio_seconds = Column(Float, nullable=False, default=0.0)
    characters = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False)
    error_type = Column(String(100), nullable=True)
```

Generate the migration, naming the file and revision `0002_ai_usage_logs` with `down_revision = "0001_baseline"`. `alembic revision --autogenerate` against a SQLite file migrated to head yields it; read it and confirm it creates only this table.

In `app/main.py` `create_app()`: call `load_config()` from `app.ai.config` first so bad AI configuration fails startup, and register exception handlers:

```python
@app.exception_handler(AIProviderError)
async def _ai_provider_error(_request, _exc):
    return JSONResponse(status_code=503, content={"detail": "The AI service is temporarily unavailable. Please try again."})

@app.exception_handler(AIOutputError)
async def _ai_output_error(_request, _exc):
    return JSONResponse(status_code=502, content={"detail": "The AI service returned an unusable response. Please try again."})
```

Add to `tests/conftest.py` `_fresh_tables`: `from app.ai.config import reset_config; reset_config()` before and after `yield`, because `test_ai_config.py` changes the environment and `get_config` is cached.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass, including `test_head_matches_models`.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add provider-neutral AI gateway with fake provider and usage logging"
```

---

### Task 5: Anthropic adapter

**Files:**
- Create: `SpeakCV/src/backend/app/ai/providers/anthropic.py`, `tests/test_ai_provider_anthropic.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: the provider contract from Task 4 (`generate_text`, `generate_structured`; keyword-only), `ProviderText`, `Usage`, `AIProviderError`, `AIOutputError`.
- Produces: `AnthropicProvider` with those two methods. It raises no other exception types for vendor failures.

- [ ] **Step 1: Read the current SDK documentation**

Read `/tmp/claude-1000/bundled-skills/2.1.316/a910c0dce63eecd8862fff6681280f38/claude-api/SKILL.md`, then its `python/claude-api/` reference files on messages, structured output, streaming, refusals and model fallbacks. Do not rely on memory: the API has changed. Only use names documented there. Add `anthropic` to `requirements.txt` and install it.

- [ ] **Step 2: Write the failing tests**

Use a stub client assigned to `provider._client` that records keyword arguments and returns SDK-shaped objects (`SimpleNamespace` with `content`, `stop_reason`, `usage`). Tests must cover:

1. `generate_text` sends `model`, `system`, `messages` and `max_tokens`, and the request has no `temperature`, no `top_p`, and no disabled-thinking setting.
2. `output_config.effort` is sent explicitly on models that accept it. Default value `high`, overridable with env var `ANTHROPIC_EFFORT`.
3. `generate_structured` calls `client.messages.parse()` with the Pydantic schema and returns the raw JSON text in `ProviderText.text`.
4. `stop_reason == "refusal"` raises `AIOutputError` before any content is read. Give the stub a `content` property that raises, so reading it first fails the test.
5. `stop_reason == "max_tokens"` raises `AIOutputError`.
6. Usage maps to `Usage(input_tokens, output_tokens)`.
7. `anthropic.APIConnectionError` and a 500 `APIStatusError` raise `AIProviderError`, and the message contains no API key.
8. Server-side `fallbacks` are sent for Opus and Sonnet models as the skill specifies, and not when env var `ANTHROPIC_FALLBACKS_ENABLED=false`.

- [ ] **Step 3: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_ai_provider_anthropic.py -q`
Expected: FAIL with `ModuleNotFoundError: app.ai.providers.anthropic`.

- [ ] **Step 4: Implement**

Create `AnthropicProvider` with `self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])` in `__init__`. Follow the skill for requests with long inputs or large `max_tokens`: stream and use the final message helper where it requires that. If `messages.parse()` itself raises on output that fails schema validation, return the raw text in `ProviderText` when the SDK exposes it, so the gateway's retry runs; otherwise raise `AIOutputError`. Write the SDK import as `import anthropic as anthropic_sdk`. The module sits inside a package, so this absolute import resolves to the SDK and not to the file itself.

- [ ] **Step 5: Run the tests**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_ai_provider_anthropic.py tests/test_ai_gateway.py -q`
Expected: PASS. No real API call is made anywhere. State in your report that the adapter has not been exercised against the live API.

- [ ] **Step 6: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add Anthropic adapter for the AI gateway"
```

---

### Task 6: OpenAI, Gemini, Voyage and edge-tts adapters

**Files:**
- Create under `SpeakCV/src/backend/app/ai/providers/`: `openai.py`, `gemini.py`, `voyage.py`, `edge_tts.py`
- Create: `tests/test_ai_provider_openai.py`, `tests/test_ai_provider_gemini.py`, `tests/test_ai_provider_voyage.py`, `tests/test_ai_provider_edge_tts.py`
- Modify: `requirements.txt` (add `google-genai`, `voyageai`; keep `openai`, `edge-tts`; remove `google-generativeai` only in Task 7, where its import is removed)

**Interfaces:**
- Consumes: provider contract from Task 4, and `app.ai.schema.to_strict_schema`.
- Produces:
  - `OpenAIProvider`: `generate_text`, `generate_structured`, `embed`, `transcribe`, `synthesize`, using `OPENAI_BASE_URL` (default official).
  - `GeminiProvider`: `generate_text`, `generate_structured`, `embed`, `transcribe`, `synthesize`.
  - `VoyageProvider`: `embed`, passing `input_type` from `kind`.
  - `EdgeTTSProvider`: `synthesize`.

- [ ] **Step 1: Read the current vendor documentation**

Use the `mcp__context7__*` tools (load through ToolSearch) or the `web-fetch` route for each. Do not rely on memory; this project's spec found that it could not confirm the current Python shape for OpenAI structured outputs.

- OpenAI: structured outputs guide for the current Python SDK; `gpt-transcribe` (takes a `languages` array); `gpt-4o-mini-tts`; embeddings `dimensions` parameter.
- Gemini: `google-genai` SDK. Its docs show `client.interactions.create` with `response_format`. Text models accept audio for STT. `gemini-3.8-flash-tts` for TTS. Embeddings use `gemini-embedding-2`.
- Voyage: `voyageai` client `embed(texts, model=..., input_type=...)`.
- edge-tts: `edge_tts.Communicate(text, voice).stream()` is async.

Record in your report which URL or doc each request shape came from.

- [ ] **Step 2: Write the failing tests**

Stub each SDK client on `provider._client` as in Task 5. Cover for each provider:

1. Requests contain no `temperature` and no `top_p`.
2. Structured requests send `to_strict_schema(schema)` (or the vendor's documented equivalent) and return raw JSON text.
3. Usage maps into `Usage`.
4. A connection error and a 5xx raise `AIProviderError`; a refusal or empty output raises `AIOutputError`.
5. OpenAI: `OPENAI_BASE_URL` reaches the client; default is `https://api.openai.com/v1`; `transcribe` passes `languages`; `embed` passes `dimensions=dim`.
6. Voyage: `kind="query"` sends `input_type="query"`, `kind="document"` sends `input_type="document"`.
7. edge-tts: with `voice=None`, language `vi` uses `vi-VN-HoaiMyNeural`, `ko` uses `ko-KR-SunHiNeural`, and anything else uses `en-US-AndrewMultilingualNeural`; an explicit voice wins; calling `synthesize` from inside a running event loop works (test with `asyncio.run` wrapping the call); no audio raises `AIProviderError`; `Usage.characters` is set.

- [ ] **Step 3: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_ai_provider_openai.py tests/test_ai_provider_gemini.py tests/test_ai_provider_voyage.py tests/test_ai_provider_edge_tts.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement**

Each provider builds its SDK client in `__init__` from its env var, and exposes `self._client`. Name the SDK import with an alias, for example `import openai as openai_sdk`. For `EdgeTTSProvider.synthesize`, run the coroutine in a worker thread so it works inside FastAPI's running loop:

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    audio = pool.submit(asyncio.run, _collect(text, chosen_voice)).result()
```

- [ ] **Step 5: Run the tests**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_ai_provider_openai.py tests/test_ai_provider_gemini.py tests/test_ai_provider_voyage.py tests/test_ai_provider_edge_tts.py -q`
Expected: PASS with no network access. State in your report that these adapters have not been exercised against live APIs.

- [ ] **Step 6: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add OpenAI, Gemini, Voyage and edge-tts adapters for the AI gateway"
```

---

### Task 7: Legacy AI module delegates to the gateway

**Files:**
- Rewrite: `SpeakCV/src/backend/app/ai_service.py`
- Create: `tests/test_ai_service_legacy.py`, `tests/test_vendor_boundary.py`
- Modify: `app/routers/interview.py`, `app/routers/cv.py`, `app/routers/admin.py`, `app/routers/jobs.py`, `requirements.txt`

**Interfaces:**
- Consumes: `app.ai.gateway`.
- Produces:
  - `call_ai_chat(messages, slot="bulk", max_tokens=None, response_format=None, feature="legacy") -> str`
  - `call_ai_chat_with_meta(...same...) -> dict` with `content`, `provider`, `model`, `latency_ms`
  - `call_ai_chat_stream(messages, slot="reasoning", feature="legacy")`, a generator yielding the whole text once

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vendor_boundary.py`:

```python
import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
VENDOR_MODULES = {"anthropic", "openai", "voyageai", "edge_tts", "groq"}
VENDOR_PREFIXES = ("google.genai", "google.generativeai")
VENDOR_HOSTS = ("api.groq.com", "api.openai.com", "generativelanguage.googleapis.com", "api.anthropic.com", "newapi.")


def _source_files():
    for root in ("app", "core"):
        for path in (BACKEND / root).rglob("*.py"):
            if "ai/providers" not in path.as_posix():
                yield path


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_only_providers_import_vendor_sdks():
    offenders = []
    for path in _source_files():
        for name in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            if name.split(".")[0] in VENDOR_MODULES or name.startswith(VENDOR_PREFIXES):
                offenders.append(f"{path.relative_to(BACKEND)}: {name}")
    assert offenders == []


def test_business_code_never_calls_vendor_hosts_directly():
    offenders = []
    for path in _source_files():
        if path.as_posix().endswith("app/ai/config.py"):
            continue  # holds the official default endpoint
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.relative_to(BACKEND)}: {host}" for host in VENDOR_HOSTS if host in text]
    assert offenders == []
```

Create `tests/test_ai_service_legacy.py`:

```python
from app.ai.providers import fake
from app.ai_service import call_ai_chat, call_ai_chat_stream, call_ai_chat_with_meta
from app.database.sql_models import AIUsageLog


def test_system_messages_move_to_the_system_argument_and_usage_is_logged(db):
    text = call_ai_chat(
        [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hello"}],
        slot="reasoning",
    )
    assert "hello" in text
    assert all(m["role"] != "system" for m in fake.last_messages())
    row = db.query(AIUsageLog).one()
    assert (row.slot, row.feature) == ("reasoning", "legacy")


def test_with_meta_keeps_its_shape():
    meta = call_ai_chat_with_meta([{"role": "user", "content": "hi"}])
    assert set(meta) == {"content", "provider", "model", "latency_ms"}
    assert meta["provider"] == "fake"


def test_stream_yields_the_whole_text():
    chunks = list(call_ai_chat_stream([{"role": "user", "content": "hi"}]))
    assert len(chunks) == 1 and "hi" in chunks[0]


def test_json_response_format_is_requested_in_the_system_prompt(monkeypatch):
    seen = {}
    from app import ai_service

    real = ai_service.gateway.generate_text

    def spy(slot, system, messages, max_output_tokens, feature, company_id=None):
        seen["system"] = system
        return real(slot, system, messages, max_output_tokens, feature, company_id)

    monkeypatch.setattr(ai_service.gateway, "generate_text", spy)
    call_ai_chat([{"role": "user", "content": "x"}], response_format={"type": "json_object"})
    assert "JSON" in seen["system"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_vendor_boundary.py tests/test_ai_service_legacy.py -q`
Expected: FAIL (`import google.generativeai`, `import edge_tts`, `api.groq.com`, wrong signature).

- [ ] **Step 3: Rewrite `app/ai_service.py`**

```python
"""Compatibility layer for legacy routes. New code calls app.ai.gateway directly."""
from app.ai import gateway

DEFAULT_MAX_OUTPUT_TOKENS = 2000
JSON_INSTRUCTION = "Return only one valid JSON object and no other text."


def _split_messages(messages: list[dict], response_format: dict | None) -> tuple[str, list[dict]]:
    system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    if response_format and response_format.get("type") == "json_object":
        system_parts.append(JSON_INSTRUCTION)
    rest = [
        {"role": "assistant" if m.get("role") == "assistant" else "user", "content": m.get("content", "")}
        for m in messages
        if m.get("role") != "system"
    ]
    return "\n".join(system_parts).strip(), rest


def call_ai_chat_with_meta(messages, slot="bulk", max_tokens=None, response_format=None, feature="legacy") -> dict:
    system, rest = _split_messages(messages, response_format)
    result = gateway.generate_text(slot, system, rest, max_tokens or DEFAULT_MAX_OUTPUT_TOKENS, feature)
    return {"content": result.text, "provider": result.provider, "model": result.model, "latency_ms": result.latency_ms}


def call_ai_chat(messages, slot="bulk", max_tokens=None, response_format=None, feature="legacy") -> str:
    return call_ai_chat_with_meta(messages, slot, max_tokens, response_format, feature)["content"]


def call_ai_chat_stream(messages, slot="reasoning", feature="legacy"):
    yield call_ai_chat(messages, slot=slot, feature=feature)
```

- [ ] **Step 4: Update callers**

- In `cv.py`, `admin.py`, `jobs.py`, `interview.py`: replace `model="gpt-4.1"` and `model="gpt-4o"` with `slot="reasoning"`. Replace `model="gpt-4.1-mini"`, `model="gpt-4o-mini"`, or no model with `slot="bulk"`. Remove `temperature=` and `timeout=` arguments, and the code in `interview.py` that reads the `temperature` system config for this call.
- In `interview.py`, remove `import edge_tts`, `import requests`, `api_key`, and the `if not api_key:` check.
- Replace the TTS block in `/api/chat` with `gateway.synthesize(ai_text, requested_lang or "vi", voice, feature="legacy_interview_tts")`, returning `audio.audio` through `io.BytesIO`. Keep the existing fallback that returns an empty stream with the text headers on `AIError`; the text still reaches the client and the failure is visible as "Audio error."
- Replace the Groq call in `/api/transcribe` with `gateway.transcribe(content, file.content_type or "audio/webm", [lang], feature="legacy_interview_stt")`. Keep the phrase filter and the English-quality check. An `AIError` propagates instead of returning an empty transcript.
- Any `except Exception` around an AI call in `cv.py`, `admin.py`, `interview.py` must not hide `AIProviderError` or `AIOutputError`: add `except AIError: raise` before it. Do this for every call site, including `/api/hint`, where the bare `except:` becomes `except AIError: raise` followed by the existing message only for other exceptions.

In `requirements.txt` remove `google-generativeai`. Run `uv pip uninstall --python .venv/bin/python google-generativeai` and confirm tests still pass.

- [ ] **Step 5: Run the tests**

Run: `make test`
Expected: all pass. `grep -rn "gemini-2.0-flash\|newapi\.\|GEMINI_MODEL_MAP\|GROQ" SpeakCV/src/backend/app SpeakCV/src/backend/core` prints nothing.

- [ ] **Step 6: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "refactor: route legacy AI calls, STT and TTS through the gateway"
```

---

### Task 8: Login on AI routes and safe uploads

**Files:**
- Create: `SpeakCV/src/backend/app/core/uploads.py`, `tests/test_uploads.py`, `tests/test_ai_routes_require_login.py`
- Modify: `app/routers/interview.py`, `app/routers/cv.py`, `app/routers/jobs.py`, `app/routers/admin.py`, `tests/test_cv_extract_text_route.py`, `SpeakCV/src/frontend/services/api.ts` (only if a call to a now-protected route sends no token)

**Interfaces:**
- Consumes: `app.routers.profile.get_current_user`, `app.core.settings.max_upload_bytes`.
- Produces:
  - `app.core.uploads.read_upload(file: UploadFile, allowed_types: set[str]) -> bytes` (async), raising `HTTPException(415)` or `HTTPException(413)`
  - `CV_TYPES`, `AUDIO_TYPES`, `DOCUMENT_TYPES` constants. Later blocks use this helper for every upload.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_uploads.py`:

```python
import os

import pytest
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient

from app.core.uploads import AUDIO_TYPES, read_upload
from app.database.sql_models import User  # noqa: F401
from app.routers import interview
from app.routers.profile import get_current_user


@pytest.fixture
def upload_client():
    app = FastAPI()

    @app.post("/upload")
    async def upload(file: UploadFile = File(...)):
        return {"size": len(await read_upload(file, AUDIO_TYPES))}

    return TestClient(app)


def test_allowed_upload_returns_its_content(upload_client):
    response = upload_client.post("/upload", files={"file": ("a.webm", b"abc", "audio/webm")})
    assert response.json() == {"size": 3}


def test_oversized_upload_gets_413(upload_client):
    too_big = b"x" * (1024 * 1024 + 1)  # conftest sets MAX_UPLOAD_MB=1
    response = upload_client.post("/upload", files={"file": ("a.webm", too_big, "audio/webm")})
    assert response.status_code == 413


def test_unsupported_type_gets_415(upload_client):
    response = upload_client.post("/upload", files={"file": ("a.exe", b"abc", "application/x-msdownload")})
    assert response.status_code == 415


def test_mime_parameters_are_ignored(upload_client):
    response = upload_client.post("/upload", files={"file": ("a.webm", b"abc", "audio/webm;codecs=opus")})
    assert response.status_code == 200


def test_transcribe_never_writes_a_file_named_by_the_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = FastAPI()
    app.include_router(interview.router)
    app.dependency_overrides[get_current_user] = lambda: User(id=1, email="a@example.test")
    client = TestClient(app)
    response = client.post(
        "/api/transcribe",
        files={"file": ("../../evil_upload.webm", "xin chào các bạn".encode(), "audio/webm")},
        data={"lang": "vi"},
    )
    assert response.status_code == 200
    assert not (tmp_path.parent.parent / "evil_upload.webm").exists()
    assert os.listdir(tmp_path) == []
```

Create `tests/test_ai_routes_require_login.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import cv, interview, jobs

PROTECTED = [
    (interview.router, "post", "/api/transcribe"),
    (interview.router, "post", "/api/chat"),
    (interview.router, "post", "/api/hint"),
    (interview.router, "post", "/api/end-interview"),
    (cv.router, "post", "/api/cv/interview-context"),
    (cv.router, "post", "/api/generate-cv"),
    (cv.router, "post", "/api/review-cv"),
    (cv.router, "post", "/api/cv/upload-makeover"),
    (cv.router, "post", "/api/cv/tailor"),
    (cv.router, "post", "/api/cv/extract-text"),
    (jobs.router, "post", "/api/jobs/match"),
]


@pytest.mark.parametrize("router,method,path", PROTECTED)
def test_ai_route_requires_login(router, method, path):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert getattr(client, method)(path).status_code == 401
```

Task 10 deletes `jobs.py` and removes its row from this list.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_uploads.py tests/test_ai_routes_require_login.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Create `app/core/uploads.py`:

```python
from fastapi import HTTPException, UploadFile

from app.core.settings import max_upload_bytes

CHUNK_SIZE = 1024 * 1024
CV_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
DOCUMENT_TYPES = CV_TYPES | {"text/markdown"}
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav"}


async def read_upload(file: UploadFile, allowed_types: set[str]) -> bytes:
    """Read an upload into memory, enforcing type and size. Never uses the client's filename."""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type or 'unknown'}")
    limit = max_upload_bytes()
    chunks, total = [], 0
    while chunk := await file.read(CHUNK_SIZE):
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"File is larger than the {limit // (1024 * 1024)} MB limit")
        chunks.append(chunk)
    return b"".join(chunks)
```

- Add `current_user: sql_models.User = Depends(get_current_user)` to each route in `PROTECTED`. For `cv.py`, import `Depends`, `sql_models` and `get_current_user` from `.profile`. Keep the route's existing parameters. Dependencies run before body validation, so unauthenticated requests get 401.
- In `/api/chat`, delete `guest_ip_tracker` and all guest branches. Use the `current_user` dependency. Keep the credit check, now raising 403 directly with no surrounding `try/except`.
- Replace every direct file read: `/api/transcribe` uses `read_upload(file, AUDIO_TYPES)` and no temp file. `cv.extract_text_from_cv` uses `read_upload(file, CV_TYPES)` and keeps using the lowercased filename only to decide the parser. Extension-based parsing must not write to disk under the client's name; if it needs a temp file use `tempfile.NamedTemporaryFile`. `/api/jobs/match` goes through `extract_text_from_cv`. `admin.py` `/api/admin/ai-brain/ingestion/upload` uses `read_upload(file, DOCUMENT_TYPES)`.
- Verify: `grep -n "open(.*filename\|temp_{" SpeakCV/src/backend/app -r` prints nothing.
- Update `tests/test_cv_extract_text_route.py` with `app.dependency_overrides[get_current_user]` so it still passes. Do the same for any other existing test that now gets 401.
- In `SpeakCV/src/frontend/services/api.ts` and the hooks, confirm calls to these routes attach `Authorization`. `grep -n "api/chat\|/transcribe\|/hint\|generate-cv\|review-cv\|upload-makeover\|cv/tailor\|interview-context\|extract-text" -r SpeakCV/src/frontend/services SpeakCV/src/frontend/hooks SpeakCV/src/frontend/components`. Add the header where it is missing, reading the token the same way the file already does for authenticated calls.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend SpeakCV/src/frontend
git commit -m "feat: require login on AI routes and enforce upload type and size limits"
```

---

### Task 9: Legacy consumer features behind a flag (backend)

**Files:**
- Create: `SpeakCV/src/backend/tests/test_legacy_flag.py`
- Modify: `app/main.py`, `app/routers/profile.py`, `app/routers/admin.py`

**Interfaces:**
- Consumes: `app.core.settings.flag`.
- Produces: `create_app(legacy_b2c: bool | None = None) -> FastAPI` (`None` reads `LEGACY_B2C_ENABLED`). `app.routers.profile.legacy_router` holds `/api/upgrade-pro`. `app.routers.admin.legacy_brain_router` holds all `/api/admin/ai-brain/*` routes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_legacy_flag.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

LEGACY_PATHS = [
    ("post", "/api/chat"),
    ("post", "/api/transcribe"),
    ("post", "/api/hint"),
    ("get", "/api/history"),
    ("post", "/api/upgrade-pro"),
    ("get", "/api/my-stats"),
    ("get", "/api/questions"),
    ("post", "/api/jobs/match"),
    ("get", "/api/admin/ai-brain/versions"),
    ("post", "/api/admin/ai-brain/ingestion/jobs"),
]


def _paths(app):
    return {getattr(route, "path", "") for route in app.routes}


@pytest.mark.parametrize("method,path", LEGACY_PATHS)
def test_legacy_routes_are_404_when_the_flag_is_off(method, path):
    client = TestClient(create_app(legacy_b2c=False))
    assert getattr(client, method)(path).status_code == 404


def test_flag_off_mounts_no_payment_or_support_routes():
    paths = _paths(create_app(legacy_b2c=False))
    assert not [p for p in paths if "vnpay" in p or "instant-upgrade" in p or "create-url" in p]
    assert not [p for p in paths if "/ws/" in p or "active-chats" in p or "/quota/" in p]


def test_flag_on_mounts_legacy_routes():
    paths = _paths(create_app(legacy_b2c=True))
    assert {"/api/chat", "/api/upgrade-pro", "/api/admin/ai-brain/versions"} <= paths


def test_core_routes_stay_mounted_when_the_flag_is_off():
    paths = _paths(create_app(legacy_b2c=False))
    assert {"/api/login", "/api/register", "/api/my-profile", "/api/cv/extract-text", "/api/admin/dashboard"} <= paths


def test_default_reads_the_environment(monkeypatch):
    monkeypatch.setenv("LEGACY_B2C_ENABLED", "true")
    assert "/api/chat" in _paths(create_app())
    monkeypatch.setenv("LEGACY_B2C_ENABLED", "false")
    assert "/api/chat" not in _paths(create_app())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_legacy_flag.py -q`
Expected: FAIL (`create_app` takes no argument).

- [ ] **Step 3: Implement**

- `profile.py`: add `legacy_router = APIRouter(prefix="/api", tags=["profile"])`, and change `/upgrade-pro` to use it.
- `admin.py`: add `legacy_brain_router = APIRouter()` and move every `/api/admin/ai-brain/*` decorator to it. Keep function bodies in place.
- `main.py`: move the imports of `interview`, `support`, `payment`, `jobs`, `stats`, `questions` out of the module top and inside a helper, so a disabled deployment never imports them:

```python
def _include_legacy_routers(app: FastAPI) -> None:
    from .routers import interview, jobs, payment, questions, stats, support

    app.include_router(profile.legacy_router)
    app.include_router(admin.legacy_brain_router)
    for module in (interview, support, payment, jobs, stats, questions):
        app.include_router(module.router)


def create_app(legacy_b2c: bool | None = None) -> FastAPI:
    ...
    app.include_router(profile.router)
    app.include_router(auth.router)
    app.include_router(cv.router)
    app.include_router(admin.router)
    enabled = settings.flag("LEGACY_B2C_ENABLED") if legacy_b2c is None else legacy_b2c
    if enabled:
        _include_legacy_routers(app)
    return app
```

Any test that imports `app.routers.interview` directly keeps working, since the modules still exist.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: disable legacy consumer routes unless LEGACY_B2C_ENABLED is set"
```

---

### Task 10: Remove fake claims from the backend

**Files:**
- Delete: `SpeakCV/src/backend/core/knowledge_graph.py`, `app/routers/jobs.py`, `tests/test_cv_parse_master_cv_route.py`
- Create: `tests/test_no_fake_claims_backend.py`
- Modify: `core/__init__.py`, `app/routers/interview.py`, `app/routers/cv.py`, `app/models.py`, `app/main.py`, `app/services/interview_report_builder.py`, `tests/test_interview_report_builder.py`, `tests/test_ai_routes_require_login.py`, `tests/test_legacy_flag.py`, `requirements.txt`

**Interfaces:**
- Produces: `build_structured_report` output no longer contains `pii_anonymized`, `evidence_grounded` or `estimated_minutes_saved`. Task 11 removes the frontend readers.

Ruling recorded in this plan: `MOCK_JOBS` is the only data behind `/api/jobs/match`, so deleting it per spec section 5 leaves nothing to serve. The whole `jobs` router goes. Spec section 4's mention of `jobs` is satisfied trivially.

- [ ] **Step 1: Write the failing test**

Create `tests/test_no_fake_claims_backend.py`:

```python
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(
    r"pii_anonymized|evidence_grounded|minutes_saved|MOCK_JOBS|parse-master-cv|parse_master_cv"
    r"|knowledge_graph|get_next_topic|networkx"
)


def test_removed_identifiers_are_gone_from_active_backend_code():
    offenders = []
    roots = [BACKEND / "app", BACKEND / "core", BACKEND / "requirements.txt"]
    for root in roots:
        files = [root] if root.is_file() else root.rglob("*.py")
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if FORBIDDEN.search(line):
                    offenders.append(f"{path.relative_to(BACKEND)}:{number}")
    assert offenders == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_no_fake_claims_backend.py -q`
Expected: FAIL listing current occurrences.

- [ ] **Step 3: Remove**

- `services/interview_report_builder.py`: delete `estimated_minutes_saved`, `pii_anonymized` and `evidence_grounded` from both dictionaries (lines near 136-138 and 159-161).
- `tests/test_interview_report_builder.py`: delete the assertions on those fields (lines near 393-395), and assert instead that the keys are absent from `hr_rec`.
- `routers/jobs.py`: delete the file. Remove `jobs` from the import and tuple in `main._include_legacy_routers`. Remove the `/api/jobs/match` entries from `tests/test_ai_routes_require_login.py` and `tests/test_legacy_flag.py`.
- `routers/cv.py`: delete `/api/cv/parse-master-cv`, `parse_and_validate_cv` if nothing else uses it, and `models.CVParseMasterCVRequest`. Delete `tests/test_cv_parse_master_cv_route.py`. Check `grep -rn "parse_and_validate\|CVParseMasterCV" app tests` afterward, and keep any helper that `tests/test_profile_master_cv_structured.py` still needs for a real feature.
- `core/knowledge_graph.py`: delete. In `core/__init__.py` remove its imports and `__all__` entries. In `routers/interview.py` remove the import and replace the fallback:

```python
current_topic = request.current_topic or "General"
...
next_topic = target_topics[0] if target_topics else current_topic
```

Also change the log line `[Knowledge Graph]` near line 327 to `[Interview Routing]`, and the comment `=== KNOWLEDGE GRAPH / CONTEXT` to `=== CONTEXT`.
- `requirements.txt`: remove `networkx` and its comment. Run `uv pip uninstall --python .venv/bin/python networkx`.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A SpeakCV/src/backend
git commit -m "fix: remove fake claims, mock jobs and the hardcoded topic graph from the backend"
```

---

### Task 11: Candidate app: fake claims and legacy flag

**Files:**
- Create: `SpeakCV/src/frontend/lib/features.ts`, `app/interview/layout.tsx`, `app/dashboard/layout.tsx`, `app/questions/layout.tsx`, `app/upgrade/layout.tsx`
- Modify: `components/Interview/SetupForm.tsx`, `components/Interview/InterviewLayout.tsx`, `components/Interview/ChatBox.tsx`, `components/Interview/PlannerSignals.tsx`, `components/Modals/ReportModal.tsx`, `app/interview/page.tsx`, `app/page.tsx`, `app/login/page.tsx`, `app/layout.tsx`, `app/profile/page.tsx`, `app/admin/page.tsx`, `components/Admin/AdminSidebar.tsx`, `services/api.ts`, `context/SubscriptionContext.tsx`, `Dockerfile`
- Modify: `docker-compose.yml`, `docker-compose.prod.yml`

All frontend paths are relative to `SpeakCV/src/frontend`.

**Interfaces:**
- Consumes: backend without `pii_anonymized`, `evidence_grounded`, `estimated_minutes_saved`, or `/api/cv/parse-master-cv`.
- Produces: `LEGACY_B2C` boolean from `lib/features.ts`. Block 3 adds the candidate flow on top of this cleaned app.

- [ ] **Step 1: Baseline**

```bash
cd SpeakCV/src/frontend && npm ci && npm run lint 2>&1 | tail -5; npm run build 2>&1 | tail -5
```

Record the lint error count in your report. You must not add new lint errors, and `npm run build` must pass at the end.

- [ ] **Step 2: Write the failing check**

The candidate app has no test runner, and adding one is out of scope. Add `SpeakCV/src/backend/tests/test_no_fake_claims_frontend.py`:

```python
import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
FORBIDDEN = re.compile(
    r"ENTERPRISE_DEMO_PRESETS|DEMO_SAMPLE_ANSWERS|Instant HR|PII Masked|pii_anonymized|evidence_grounded"
    r"|minutes_saved|mins saved|parse-master-cv|parseMasterCv|presetPassword|presetEmail"
)


def test_removed_identifiers_are_gone_from_the_candidate_app():
    if not FRONTEND.exists():
        pytest.skip("frontend not present")
    offenders = []
    for root in ("app", "components", "services", "hooks", "context"):
        for path in (FRONTEND / root).rglob("*"):
            if path.suffix in {".ts", ".tsx"}:
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if FORBIDDEN.search(line):
                        offenders.append(f"{path.relative_to(FRONTEND)}:{number}")
    assert offenders == []
```

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_no_fake_claims_frontend.py -q`
Expected: FAIL.

- [ ] **Step 3: Remove fake claims**

- `SetupForm.tsx`: delete `ENTERPRISE_DEMO_PRESETS`, `applyPreset`, the fixed-78% CV-JD panel and the preset buttons. `InterviewLayout.tsx`: delete the preset import and use (`kPreset`), and the "Instant HR & Coaching Report" badge.
- `ChatBox.tsx`: delete `DEMO_SAMPLE_ANSWERS` and its render block.
- `app/interview/page.tsx`: delete the hardcoded report near lines 259-261 and the hardcoded 8.6 "Instant HR & Coaching Report" content. `grep -n "8\.6" app/interview/page.tsx components/Interview/InterviewLayout.tsx` must print nothing.
- `PlannerSignals.tsx`, `ReportModal.tsx`, `SetupForm.tsx`, `InterviewLayout.tsx`: delete "PII Masked" badges; `grep -rn "PII" components app` afterward.
- `ReportModal.tsx`: delete `estimated_minutes_saved`, `pii_anonymized`, `evidence_grounded` and the "mins saved" display.
- `services/api.ts`: delete the function calling `cv/parse-master-cv` (near line 218), and its callers (`grep -rn` the function name).
- `app/page.tsx`: delete the static testimonials section (`id="testimonials"`, near line 447) and the nav link to `#testimonials` (near line 134).
- `app/login/page.tsx`: delete the code reading `email` and `password` from the query string (near lines 25-26), and any auto-submit. Keep a `redirect` parameter only if it is restricted to same-site paths starting with `/` and not `//`.

- [ ] **Step 4: Add the flag**

Create `lib/features.ts`:

```ts
export const LEGACY_B2C = process.env.NEXT_PUBLIC_LEGACY_B2C_ENABLED === "true";
```

Create one server layout per legacy route family, `app/interview/layout.tsx`, `app/dashboard/layout.tsx`, `app/questions/layout.tsx`, `app/upgrade/layout.tsx`:

```tsx
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { LEGACY_B2C } from "@/lib/features";

export default function Layout({ children }: { children: ReactNode }) {
  if (!LEGACY_B2C) notFound();
  return <>{children}</>;
}
```

Hide the rest with `LEGACY_B2C`:
- `app/layout.tsx`: render `SupportChatWidget` only when enabled, if it is mounted there.
- `context/SubscriptionContext.tsx`: when disabled, make no network calls and expose a neutral state.
- `app/page.tsx`: hide `PricingSection`, job match (`JobRecommendations`), CV builder entry points and links to `/interview`, `/dashboard`, `/questions`. The remaining page must make sense: product name, one-line statement "Every CV gets a conversation. Every decision has evidence.", and login and register links.
- `app/profile/page.tsx`: hide credits and upgrade. Also `SubscriptionModal`, `CheckoutModal`, `GenCVModal`, `ReviewCVModal`, `TailorJDModal` entry points anywhere outside `/interview`.
- `app/admin/page.tsx`, `AdminSidebar.tsx`: hide tabs that call routes disabled by the flag: `BrainGraphPanel`, `QuestionsTab`, `SupportTab`, and `TransactionsTab` if its route is under `payment`.
- After login, redirect to `/profile`, not `/interview`, when disabled. `grep -rn '"/interview"\|"/dashboard"\|"/questions"\|/upgrade' app components context` and guard each link.

Add to `Dockerfile` beside the other build args:

```dockerfile
ARG NEXT_PUBLIC_LEGACY_B2C_ENABLED=false
ENV NEXT_PUBLIC_LEGACY_B2C_ENABLED=$NEXT_PUBLIC_LEGACY_B2C_ENABLED
```

Add `NEXT_PUBLIC_LEGACY_B2C_ENABLED: ${NEXT_PUBLIC_LEGACY_B2C_ENABLED:-false}` to the `speakcv-frontend` build args in both compose files.

- [ ] **Step 5: Verify**

```bash
cd SpeakCV/src/frontend
npm run lint 2>&1 | tail -5
NEXT_PUBLIC_API_URL=http://localhost:8001 npm run build 2>&1 | tail -5
(PORT=3111 npx next start &) ; sleep 5
for p in / /login /register /interview /dashboard /questions /upgrade/success; do printf "%s " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:3111$p"; done
pkill -f "next start" || true
NEXT_PUBLIC_LEGACY_B2C_ENABLED=true NEXT_PUBLIC_API_URL=http://localhost:8001 npm run build 2>&1 | tail -3
cd ../backend && .venv/bin/python -m pytest tests/test_no_fake_claims_frontend.py -q
```

Expected: `/`, `/login`, `/register` return 200. `/interview`, `/dashboard`, `/questions`, `/upgrade/success` return 404. Both builds pass. Rebuild with the flag off, or remove `.next`, before finishing. `pkill -f "next start"` must only match the process you started; check with `pgrep -af "next start"` first and kill that PID instead if anything else matches.

- [ ] **Step 6: Commit**

```bash
git add SpeakCV/src/frontend SpeakCV/src/backend/tests/test_no_fake_claims_frontend.py docker-compose.yml docker-compose.prod.yml
git commit -m "fix: remove fake claims from the candidate app and hide legacy pages behind a flag"
```

---

### Task 12: Companies, departments, members and authorization

**Files:**
- Create: `SpeakCV/src/backend/app/auth/dependencies.py`, `app/routers/companies.py`, `app/schemas/__init__.py`, `app/schemas/companies.py`, `alembic/versions/0003_companies.py`, `tests/test_company_isolation.py`, `tests/test_company_api.py`, `tests/test_cli_create_company.py`
- Modify: `app/database/sql_models.py`, `app/main.py`, `app/routers/profile.py`, `app/cli.py`

**Interfaces:**
- Consumes: `app.auth.security.verify_token`, `app.database.database.get_db`, `tests/helpers.py`.
- Produces, for all later blocks:
  - Models `Company`, `Department`, `CompanyMember`
  - `app.auth.dependencies.get_authenticated_user(token, db) -> User`, which raises 401 if the token is invalid or the user is gone
  - `app.auth.dependencies.require_member(*roles) -> dependency returning CompanyMember`. The route's path parameter must be named `company_id`. With no roles, any member passes. Membership is read from the database on each request.
  - `MEMBER_ROLES = ("hr", "manager", "employee")`
  - Company routes live under `/api/companies/{company_id}/...`, and `tests/test_company_isolation.py` automatically covers every such route, including those later blocks add.
  - `python -m app.cli create-company --slug --name --hr-email --hr-name [--sample] [--locale en]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_company_isolation.py`:

```python
"""Walks every route under /api/companies/{company_id}. New routes are covered automatically."""
import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.database.sql_models import Company, CompanyMember
from app.main import create_app
from tests.helpers import auth_header, make_user

PREFIX = "/api/companies/{company_id}"


def company_routes(app):
    found = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith(PREFIX):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                found.append((method, route.path))
    return sorted(found)


def fill(path, company_id):
    path = path.replace("{company_id}", str(company_id))
    return re.sub(r"\{[^}]+\}", "1", path)


@pytest.fixture
def two_companies(db):
    a = Company(slug="a", name="A")
    b = Company(slug="b", name="B")
    db.add_all([a, b])
    db.commit()
    hr_a = make_user(db, "hr-a@example.test")
    db.add(CompanyMember(company_id=a.id, user_id=hr_a.id, role="hr"))
    db.commit()
    return a.id, b.id


def test_there_are_routes_to_check():
    assert len(company_routes(create_app(legacy_b2c=True))) >= 10


def test_member_of_another_company_gets_403_everywhere(two_companies):
    _, b_id = two_companies
    app = create_app(legacy_b2c=True)
    client = TestClient(app)
    headers = auth_header("hr-a@example.test")
    for method, path in company_routes(app):
        response = client.request(method, fill(path, b_id), headers=headers, json={})
        assert response.status_code == 403, f"{method} {path} returned {response.status_code}"


def test_anonymous_gets_401_everywhere(two_companies):
    _, b_id = two_companies
    app = create_app(legacy_b2c=True)
    client = TestClient(app)
    for method, path in company_routes(app):
        response = client.request(method, fill(path, b_id), json={})
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}"


def test_platform_admin_has_no_implicit_company_access(db, two_companies):
    _, b_id = two_companies
    make_user(db, "root@example.test", role="admin")
    client = TestClient(create_app())
    response = client.get(f"/api/companies/{b_id}", headers=auth_header("root@example.test"))
    assert response.status_code == 403


def test_a_nonexistent_company_looks_the_same_as_a_forbidden_one(two_companies):
    client = TestClient(create_app())
    response = client.get("/api/companies/999999", headers=auth_header("hr-a@example.test"))
    assert response.status_code == 403
```

Create `tests/test_company_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.database.sql_models import Company, CompanyMember, Department, User
from app.main import create_app
from tests.helpers import auth_header, make_user


@pytest.fixture
def api():
    return TestClient(create_app())


@pytest.fixture
def company(db):
    row = Company(slug="acme", name="Acme", is_sample=True)
    db.add(row)
    db.commit()
    return row.id


@pytest.fixture
def people(db, company):
    result = {}
    for role in ("hr", "manager", "employee"):
        user = make_user(db, f"{role}@example.test")
        db.add(CompanyMember(company_id=company, user_id=user.id, role=role))
        result[role] = auth_header(user.email)
    db.commit()
    return result


ENDPOINTS = [
    ("GET", "/api/companies/{c}", {"hr", "manager", "employee"}, 200),
    ("PATCH", "/api/companies/{c}", {"hr"}, 200),
    ("GET", "/api/companies/{c}/departments", {"hr", "manager", "employee"}, 200),
    ("POST", "/api/companies/{c}/departments", {"hr"}, 201),
    ("GET", "/api/companies/{c}/members", {"hr"}, 200),
]


@pytest.mark.parametrize("method,path,allowed,ok_status", ENDPOINTS)
def test_role_matrix(api, company, people, method, path, allowed, ok_status):
    for role, headers in people.items():
        body = {"name": f"Dept {role}"} if method == "POST" else {"name": f"Name {role}"} if method == "PATCH" else None
        response = api.request(method, path.format(c=company), headers=headers, json=body)
        assert response.status_code == (ok_status if role in allowed else 403), f"{role} {method} {path}"


def test_me_lists_memberships(api, company, people):
    body = api.get("/api/me", headers=people["hr"]).json()
    assert body["email"] == "hr@example.test"
    assert body["memberships"] == [
        {
            "member_id": body["memberships"][0]["member_id"],
            "company_id": company,
            "company_slug": "acme",
            "company_name": "Acme",
            "is_sample": True,
            "role": "hr",
            "department_id": None,
        }
    ]


def test_me_for_a_candidate_has_no_memberships(api, db):
    make_user(db, "cand@example.test")
    assert api.get("/api/me", headers=auth_header("cand@example.test")).json()["memberships"] == []


def test_patch_company_cannot_change_protected_fields(api, db, company, people):
    response = api.patch(
        f"/api/companies/{company}",
        headers=people["hr"],
        json={"name": "New", "slug": "hacked", "is_sample": False, "kb_version": 99},
    )
    assert response.status_code == 200
    db.expire_all()
    row = db.get(Company, company)
    assert (row.name, row.slug, row.is_sample, row.kb_version) == ("New", "acme", True, 0)


def test_department_tree_rules(api, company, people):
    url = f"/api/companies/{company}/departments"
    parent = api.post(url, headers=people["hr"], json={"name": "Engineering"}).json()
    child = api.post(url, headers=people["hr"], json={"name": "Backend", "parent_id": parent["id"]}).json()

    assert api.post(url, headers=people["hr"], json={"name": "Engineering"}).status_code == 409
    assert api.delete(f"{url}/{parent['id']}", headers=people["hr"]).status_code == 409

    assert api.patch(f"{url}/{parent['id']}", headers=people["hr"], json={"parent_id": child["id"]}).status_code == 409
    assert api.patch(f"{url}/{child['id']}", headers=people["hr"], json={"parent_id": child["id"]}).status_code == 409

    assert api.delete(f"{url}/{child['id']}", headers=people["hr"]).status_code == 204
    assert api.delete(f"{url}/{parent['id']}", headers=people["hr"]).status_code == 204


def test_department_parent_must_belong_to_this_company(api, db, company, people):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    foreign = Department(company_id=other.id, name="Foreign")
    db.add(foreign)
    db.commit()
    url = f"/api/companies/{company}/departments"
    assert api.post(url, headers=people["hr"], json={"name": "X", "parent_id": foreign.id}).status_code == 404
    assert api.patch(f"{url}/{foreign.id}", headers=people["hr"], json={"name": "Y"}).status_code == 404


def test_department_with_a_member_cannot_be_deleted(api, db, company, people):
    url = f"/api/companies/{company}/departments"
    dept = api.post(url, headers=people["hr"], json={"name": "Ops"}).json()
    members = api.get(f"/api/companies/{company}/members", headers=people["hr"]).json()
    employee = next(m for m in members if m["role"] == "employee")
    api.patch(f"/api/companies/{company}/members/{employee['id']}", headers=people["hr"], json={"department_id": dept["id"]})
    assert api.delete(f"{url}/{dept['id']}", headers=people["hr"]).status_code == 409


def test_add_member_for_a_new_email_creates_a_user_and_returns_the_password_once(api, db, company, people):
    url = f"/api/companies/{company}/members"
    response = api.post(url, headers=people["hr"], json={"email": "new@example.test", "full_name": "New", "role": "employee"})
    assert response.status_code == 201
    assert response.json()["temporary_password"]
    assert db.query(User).filter_by(email="new@example.test").count() == 1
    listed = api.get(url, headers=people["hr"]).json()
    assert all("temporary_password" not in row for row in listed)


def test_add_member_for_an_existing_user_never_touches_their_password(api, db, company, people):
    user = make_user(db, "exists@example.test")
    original_hash = user.hashed_password
    response = api.post(f"/api/companies/{company}/members", headers=people["hr"], json={"email": "exists@example.test", "role": "employee"})
    assert response.status_code == 201
    assert response.json()["temporary_password"] is None
    db.expire_all()
    assert db.get(User, user.id).hashed_password == original_hash


def test_add_member_twice_conflicts_and_bad_role_is_rejected(api, db, company, people):
    url = f"/api/companies/{company}/members"
    assert api.post(url, headers=people["hr"], json={"email": "employee@example.test", "role": "employee"}).status_code == 409
    assert api.post(url, headers=people["hr"], json={"email": "x@example.test", "role": "owner"}).status_code == 422


def test_removed_member_loses_access_immediately_with_the_same_token(api, company, people):
    headers = people["employee"]
    assert api.get(f"/api/companies/{company}", headers=headers).status_code == 200
    members = api.get(f"/api/companies/{company}/members", headers=people["hr"]).json()
    employee = next(m for m in members if m["role"] == "employee")
    assert api.delete(f"/api/companies/{company}/members/{employee['id']}", headers=people["hr"]).status_code == 204
    assert api.get(f"/api/companies/{company}", headers=headers).status_code == 403


def test_the_last_hr_cannot_be_removed_or_demoted(api, company, people):
    url = f"/api/companies/{company}/members"
    hr = next(m for m in api.get(url, headers=people["hr"]).json() if m["role"] == "hr")
    assert api.delete(f"{url}/{hr['id']}", headers=people["hr"]).status_code == 409
    assert api.patch(f"{url}/{hr['id']}", headers=people["hr"], json={"role": "employee"}).status_code == 409

    api.post(url, headers=people["hr"], json={"email": "hr2@example.test", "role": "hr"})
    assert api.patch(f"{url}/{hr['id']}", headers=people["hr"], json={"role": "employee"}).status_code == 200


def test_member_from_another_company_cannot_be_edited(api, db, company, people):
    other = Company(slug="other", name="Other")
    db.add(other)
    db.commit()
    stranger = make_user(db, "stranger@example.test")
    foreign = CompanyMember(company_id=other.id, user_id=stranger.id, role="employee")
    db.add(foreign)
    db.commit()
    url = f"/api/companies/{company}/members/{foreign.id}"
    assert api.patch(url, headers=people["hr"], json={"role": "hr"}).status_code == 404
    assert api.delete(url, headers=people["hr"]).status_code == 404


def test_deleted_user_with_a_valid_token_gets_401(api, db, company):
    ghost = make_user(db, "ghost@example.test")
    headers = auth_header(ghost.email)
    db.delete(ghost)
    db.commit()
    assert api.get(f"/api/companies/{company}", headers=headers).status_code == 401
```

Create `tests/test_cli_create_company.py`:

```python
from app.auth.security import verify_password
from app.cli import main
from app.database.sql_models import Company, CompanyMember, User


def test_create_company_makes_the_first_hr_user_and_prints_a_password_once(db, capsys):
    code = main(["create-company", "--slug", "sori", "--name", "Sori Labs", "--hr-email", "hr@sori.test", "--hr-name", "Sori HR", "--sample"])
    assert code == 0
    company = db.query(Company).filter_by(slug="sori").one()
    assert company.is_sample is True
    user = db.query(User).filter_by(email="hr@sori.test").one()
    member = db.query(CompanyMember).filter_by(company_id=company.id, user_id=user.id).one()
    assert member.role == "hr"
    output = capsys.readouterr().out
    password = next(line.split()[-1] for line in output.splitlines() if "password" in line.lower())
    assert verify_password(password, user.hashed_password)


def test_create_company_for_an_existing_user_keeps_their_password(db, capsys):
    user = User(email="hr@sori.test", full_name="HR", hashed_password="existing-hash")
    db.add(user)
    db.commit()
    assert main(["create-company", "--slug", "sori", "--name", "Sori", "--hr-email", "hr@sori.test", "--hr-name", "HR"]) == 0
    db.expire_all()
    assert db.get(User, user.id).hashed_password == "existing-hash"
    assert "password" not in capsys.readouterr().out.lower()


def test_duplicate_slug_fails_clearly(db, capsys):
    args = ["create-company", "--slug", "sori", "--name", "Sori", "--hr-email", "hr@sori.test", "--hr-name", "HR"]
    assert main(args) == 0
    assert main(args) != 0
    assert "sori" in capsys.readouterr().err
```

`tests/__init__.py` may be needed for `from tests.helpers import ...`. With `pythonpath = .` in `pytest.ini` and `tests/__init__.py` absent, namespace packages resolve it; add an empty `tests/__init__.py` only if imports fail.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd SpeakCV/src/backend && .venv/bin/python -m pytest tests/test_company_isolation.py tests/test_company_api.py tests/test_cli_create_company.py -q`
Expected: FAIL with `ImportError: cannot import name 'Company'`.

- [ ] **Step 3: Implement models and migration**

Add to `sql_models.py` (import `UniqueConstraint`, `CheckConstraint`):

```python
class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_sample = Column(Boolean, nullable=False, default=False)
    default_locale = Column(String(10), nullable=False, default="en")
    retention_days = Column(Integer, nullable=False, default=90)
    kb_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("company_id", "parent_id", "name", name="uq_department_sibling_name"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CompanyMember(Base):
    __tablename__ = "company_members"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_member"),
        CheckConstraint("role IN ('hr', 'manager', 'employee')", name="ck_company_member_role"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

Generate `alembic/versions/0003_companies.py`, `down_revision = "0002_ai_usage_logs"`, as in Task 4.

The database unique constraint does not stop duplicate top-level names, because SQL treats `NULL` parents as distinct. The API checks sibling names in code.

- [ ] **Step 4: Implement authorization**

Create `app/auth/dependencies.py`:

```python
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import security
from app.database.database import get_db
from app.database.sql_models import CompanyMember, User

MEMBER_ROLES = ("hr", "manager", "employee")


def get_authenticated_user(token: str = Depends(security.oauth2_scheme), db: Session = Depends(get_db)) -> User:
    email = security.verify_token(token)
    user = db.query(User).filter(User.email == email).first() if email else None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def require_member(*roles: str):
    """Authorize against the database on each request, so revoking a membership takes effect at once."""
    unknown = set(roles) - set(MEMBER_ROLES)
    if unknown:
        raise ValueError(f"Unknown member roles: {sorted(unknown)}")

    def dependency(
        company_id: int,
        user: User = Depends(get_authenticated_user),
        db: Session = Depends(get_db),
    ) -> CompanyMember:
        member = (
            db.query(CompanyMember)
            .filter(CompanyMember.company_id == company_id, CompanyMember.user_id == user.id)
            .first()
        )
        if member is None or (roles and member.role not in roles):
            raise HTTPException(status_code=403, detail="You do not have access to this resource")
        return member

    return dependency
```

Non-integer company IDs get 422 from FastAPI, which reveals nothing.

Keep `profile.get_current_user` behaving the same for legacy callers, but make it reuse the new dependency: its body becomes `sync_user_tokens(user, db); return user`, with `user: User = Depends(get_authenticated_user)`. Existing tests override `get_current_user` and are unaffected. A missing user now gets 401 instead of 404.

- [ ] **Step 5: Implement the API**

Create `app/schemas/companies.py` with Pydantic models:

```python
from typing import Literal, Optional

from pydantic import BaseModel, Field

MemberRole = Literal["hr", "manager", "employee"]


class CompanyOut(BaseModel):
    id: int
    slug: str
    name: str
    is_sample: bool
    default_locale: str
    retention_days: int
    kb_version: int


class CompanyPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    default_locale: Optional[str] = Field(default=None, max_length=10)
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: Optional[int] = None


class DepartmentPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    parent_id: Optional[int] = None


class DepartmentOut(BaseModel):
    id: int
    company_id: int
    parent_id: Optional[int]
    name: str


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: MemberRole
    department_id: Optional[int] = None


class MemberPatch(BaseModel):
    role: Optional[MemberRole] = None
    department_id: Optional[int] = None


class MemberOut(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: Optional[str]
    department_id: Optional[int]
    role: str


class MemberCreated(MemberOut):
    temporary_password: Optional[str] = None


class MembershipOut(BaseModel):
    member_id: int
    company_id: int
    company_slug: str
    company_name: str
    is_sample: bool
    role: str
    department_id: Optional[int]


class MeOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    memberships: list[MembershipOut]
```

Create `app/routers/companies.py` with `router = APIRouter()`. Every path under `/api/companies/{company_id}` uses `require_member` as below. Use `model_fields_set` in PATCH handlers so that `parent_id: null` means "move to the top level" and an omitted field means "leave unchanged".

| Route | Dependency | Behaviour |
|---|---|---|
| `GET /api/me` | `get_authenticated_user` | `MeOut` |
| `GET /api/companies/{company_id}` | `require_member()` | `CompanyOut` |
| `PATCH /api/companies/{company_id}` | `require_member("hr")` | Only `CompanyPatch` fields change. Extra fields in the body are ignored |
| `GET .../departments` | `require_member()` | Flat list, the portal builds the tree |
| `POST .../departments` | `require_member("hr")` | 201. `parent_id` from another company or absent: 404. Sibling with the same name, including top level: 409 |
| `PATCH .../departments/{dept_id}` | `require_member("hr")` | Department outside this company: 404. Parent outside: 404. Parent is itself or a descendant: 409. Sibling name clash: 409 |
| `DELETE .../departments/{dept_id}` | `require_member("hr")` | 204. Has child departments or members: 409. Outside: 404 |
| `GET .../members` | `require_member("hr")` | `list[MemberOut]`, joined with `users` |
| `POST .../members` | `require_member("hr")` | 201 `MemberCreated`. `department_id` outside: 404. Email normalised with `.strip().lower()`. Already a member: 409. No such user: create one with `secrets.token_urlsafe(12)`, hash it, return it once as `temporary_password`. Existing user: password untouched, `temporary_password` is null |
| `PATCH .../members/{member_id}` | `require_member("hr")` | Outside: 404. Demoting the last HR: 409 |
| `DELETE .../members/{member_id}` | `require_member("hr")` | 204. Outside: 404. Removing the last HR: 409 |

Register the router in `create_app` before the legacy check.

Add `create-company` to `app/cli.py`:
- Arguments `--slug`, `--name`, `--hr-email`, `--hr-name`, `--sample` (flag), `--locale` (default `en`).
- Duplicate slug: print to stderr naming the slug, return 1.
- Email normalised as above. No such user: create with a random password and print `Temporary password for <email>: <password>` once. Existing user: keep the password, and print nothing containing the word "password".
- Add the membership with role `hr`.
- Use `SessionLocal` and close it.

- [ ] **Step 6: Run the tests**

Run: `make test`
Expected: all pass, including `test_head_matches_models`.

- [ ] **Step 7: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add companies, departments and members with enforced company isolation"
```

---

### Task 13: HR portal: login, company settings and cleanup

**Files, relative to `interviewpath/interviewpath-demo`:**
- Delete: `src/routes/N8nWorkflowPage.jsx`, `src/routes/InterviewPage.jsx`, `src/components/n8n/`, `src/components/InterviewRoom.jsx`, `src/components/CameraPreview.jsx`, `src/data/mockN8nWorkflow.js`, `src/data/mockInterview.js`
- Create: `src/lib/api.js`, `src/lib/tree.js`, `src/auth/AuthContext.jsx`, `src/auth/RequireAuth.jsx`, `src/company/CompanyContext.jsx`, `src/routes/LoginPage.jsx`, `src/routes/CompanySettingsPage.jsx`, `src/components/SampleBanner.jsx`, `src/components/DepartmentTree.jsx`, `src/components/MemberTable.jsx`, `src/components/LanguageSwitch.jsx`, `src/i18n/index.js`, `src/i18n/en.json`, `src/i18n/vi.json`, `eslint.config.js`, `playwright.config.js`, `e2e/login.spec.js`, `e2e/start-backend.sh`, `.gitignore`
- Modify: `src/App.jsx`, `src/main.jsx`, `src/components/Sidebar.jsx`, `package.json`

`WorkflowPage.jsx`, `KnowledgeGraphPage.jsx`, `KnowledgeGraph.jsx`, `CandidateCard.jsx`, `CandidateDetailPanel.jsx`, `mockCandidates.js`, `mockGraph.js`, `MetricCard.jsx` stay on disk until Blocks 2 and 3 connect them; they are removed from the routes and menu, so no page shows mock data.

**Interfaces:**
- Consumes: `POST /api/login` (`{email, password}` returns `{access_token, ...}`), `GET /api/me`, and the company endpoints from Task 12.
- Produces, for Blocks 2 to 5:
  - `src/lib/api.js`: `api(path, {method, body, formData})` returning parsed JSON or `null` on 204, throwing `ApiError {status, message}`, and redirecting to `/login` on 401
  - `useAuth()` returning `{token, user, login, logout, loading}`
  - `useCompany()` returning `{memberships, company, membership, selectCompany, refresh}`
  - `RequireAuth` route guard, `SampleBanner`, the i18n setup with `en` default and `vi`

- [ ] **Step 1: Install tooling**

```bash
cd interviewpath/interviewpath-demo
npm install i18next react-i18next
npm install -D eslint @eslint/js eslint-plugin-react-hooks eslint-plugin-react-refresh globals @playwright/test
npx playwright install chromium
```

Add scripts to `package.json`: `"lint": "eslint src e2e"`, `"test:e2e": "playwright test"`.

Create `eslint.config.js`:

```js
import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  { ignores: ['dist', 'playwright-report', 'test-results'] },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}', 'e2e/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
];
```

Create `.gitignore`: `playwright-report/`, `test-results/`, `e2e/.tmp/`.

Lint covers `src`, so files staying on disk but out of routes must pass or be excluded. Add them to `ignores`: `src/routes/WorkflowPage.jsx`, `src/routes/KnowledgeGraphPage.jsx`, `src/components/KnowledgeGraph.jsx`, `src/components/CandidateCard.jsx`, `src/components/CandidateDetailPanel.jsx`, `src/components/MetricCard.jsx`, `src/components/Toast.jsx`, `src/data/**`.

- [ ] **Step 2: Write the failing end-to-end test**

Create `e2e/start-backend.sh`:

```bash
#!/usr/bin/env bash
# Starts the real backend on SQLite with fake AI. Creates a sample company and one HR user.
set -euo pipefail
cd "$(dirname "$0")/../../../SpeakCV/src/backend"
E2E_DB="${E2E_DB:-/tmp/portal_e2e_$$.db}"
rm -f "$E2E_DB"
export APP_ENV=development
export SECRET_KEY=e2e-only-secret-key-0123456789abcdef-e2e
export DATABASE_URL="sqlite:///$E2E_DB"
export ALLOWED_ORIGINS=http://localhost:5199
export ADMIN_EMAIL= ADMIN_PASSWORD=
for slot in REASONING BULK EMBEDDING STT TTS; do export "AI_${slot}_PROVIDER=fake"; done
PY=.venv/bin/python
$PY -m app.cli migrate
HR_PASSWORD=$($PY -m app.cli create-company --slug e2e --name "E2E Company" --hr-email hr@e2e.test --hr-name "E2E HR" --sample | awk '/Temporary password/ {print $NF}')
printf '%s' "$HR_PASSWORD" > /tmp/portal_e2e_password
exec $PY -m uvicorn app.main:app --port 8099
```

`chmod +x e2e/start-backend.sh`.

Create `playwright.config.js`:

```js
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://localhost:5199' },
  webServer: [
    { command: 'bash e2e/start-backend.sh', url: 'http://localhost:8099/docs', reuseExistingServer: false, timeout: 60000 },
    {
      command: 'VITE_API_URL=http://localhost:8099 npx vite --port 5199 --strictPort',
      url: 'http://localhost:5199',
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
```

Create `e2e/login.spec.js`:

```js
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

const password = () => readFileSync('/tmp/portal_e2e_password', 'utf8');

async function signIn(page) {
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email').fill('hr@e2e.test');
  await page.getByLabel('Password').fill(password());
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Company settings' })).toBeVisible();
}

test('wrong password shows an error and stays on login', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('hr@e2e.test');
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test('HR manages departments and members in the real database', async ({ page }) => {
  await signIn(page);
  await expect(page.getByText('Sample data')).toBeVisible();

  await page.getByLabel('New department name').fill('Engineering');
  await page.getByRole('button', { name: 'Add department' }).click();
  await expect(page.getByRole('treeitem', { name: /Engineering/ })).toBeVisible();

  await page.getByLabel('Member email').fill('new.employee@e2e.test');
  await page.getByLabel('Member role').selectOption('employee');
  await page.getByRole('button', { name: 'Add member' }).click();
  await expect(page.getByRole('cell', { name: 'new.employee@e2e.test' })).toBeVisible();
  await expect(page.getByText(/temporary password/i)).toBeVisible();

  await page.reload();
  await expect(page.getByRole('treeitem', { name: /Engineering/ })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'new.employee@e2e.test' })).toBeVisible();
});

test('language switches to Vietnamese', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: 'Tiếng Việt' }).click();
  await expect(page.getByRole('heading', { name: 'Cài đặt công ty' })).toBeVisible();
});

test('an expired token lands on the login page', async ({ page }) => {
  await signIn(page);
  await page.evaluate(() => sessionStorage.setItem('portal_token', 'not-a-valid-token'));
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
});

test('no page mentions the removed demo features', async ({ page }) => {
  await signIn(page);
  await expect(page.getByText(/n8n/i)).toHaveCount(0);
  await expect(page.getByRole('link', { name: /RAG Knowledge Graph|Workflow/ })).toHaveCount(0);
});
```

Run: `npx playwright test --reporter=line`
Expected: FAIL.

- [ ] **Step 3: Implement the API client and auth**

`src/lib/api.js`:

```js
const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8001').replace(/\/$/, '');
const TOKEN_KEY = 'portal_token';

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (token) => sessionStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);

export async function api(path, { method = 'GET', body, formData, skipAuthRedirect = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });

  if (response.status === 401 && !skipAuthRedirect) {
    clearToken();
    if (window.location.pathname !== '/login') window.location.assign('/login');
    throw new ApiError(401, 'Session expired');
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof detail.detail === 'string' ? detail.detail : `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}
```

`src/auth/AuthContext.jsx`: holds `user` (from `GET /api/me`) and `loading`. On mount, if a token exists, load `/api/me`. `login(email, password)` calls `api('/api/login', {method:'POST', body:{email, password}, skipAuthRedirect:true})`, stores the token, and loads `/api/me`. `logout()` clears the token and user, and navigates to `/login`. A failed `/api/me` with 401 is already redirected by `api`.

`src/auth/RequireAuth.jsx`: while `loading` show a neutral status; with no token `<Navigate to="/login" replace />`; otherwise render children.

`src/company/CompanyContext.jsx`: reads `user.memberships`, keeps the selected `company_id` in `sessionStorage` under `portal_company`, defaults to the first membership. Loads `GET /api/companies/{id}` into `company`. `membership` is the selected one. A user with no memberships sees a clear message on the settings page: "This account is not a member of any company." Add `refresh`.

`src/lib/tree.js`:

```js
export function buildTree(departments) {
  const byId = new Map(departments.map((d) => [d.id, { ...d, children: [] }]));
  const roots = [];
  for (const node of byId.values()) {
    const parent = node.parent_id == null ? null : byId.get(node.parent_id);
    (parent ? parent.children : roots).push(node);
  }
  const sort = (nodes) => nodes.sort((a, b) => a.name.localeCompare(b.name)).forEach((n) => sort(n.children));
  sort(roots);
  return roots;
}
```

- [ ] **Step 4: Implement pages, i18n and cleanup**

`src/i18n/index.js`: initialise `i18next` with `react-i18next`, resources from `en.json` and `vi.json`, `lng` from `localStorage.portal_lang` or `en`, `fallbackLng: 'en'`. `LanguageSwitch` renders buttons `English` and `Tiếng Việt`, setting the language and storing it. Import `./i18n` in `src/main.jsx`, and wrap `App` in `AuthProvider` inside `BrowserRouter`.

All visible strings come from i18n. Keys and the English values the tests rely on: `login.email` "Email", `login.password` "Password", `login.submit` "Sign in", `settings.title` "Company settings", `banner.sample` "Sample data", `departments.newName` "New department name", `departments.add` "Add department", `members.email` "Member email", `members.role` "Member role", `members.add` "Add member", `members.temporaryPassword` "Temporary password, shown once". Vietnamese: `settings.title` "Cài đặt công ty"; translate the rest.

`LoginPage.jsx`: email and password inputs with `<label>`, a submit button, and errors in `role="alert"`. Redirect to `/settings` on success, and if already logged in.

`CompanySettingsPage.jsx`: `<h1>` title, `DepartmentTree` and `MemberTable`.
- `DepartmentTree.jsx`: loads `/departments`, renders nested `role="tree"`/`role="treeitem"` from `buildTree`, a form with the new name and an optional parent `<select>`, inline rename, and delete. Show the API message on 409.
- `MemberTable.jsx`: `<table>` with email, name, role `<select>`, department `<select>`, remove. The add form has email, optional name, role and department. After creating a member with a `temporary_password`, show it once in a dismissible notice. Hidden for non-HR, who see a read-only company name and department list, because `GET /members` is HR-only.

`SampleBanner.jsx`: renders `banner.sample` when `company?.is_sample`, placed at the top of the main area on every authenticated page.

`Sidebar.jsx`: remove the credentials link and the `speakCvUrl` block entirely. Nav contains only Company settings. Bottom area shows the company name, a company switcher if more than one membership, `LanguageSwitch`, and Sign out.

`App.jsx`:

```jsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route element={<RequireAuth><CompanyProvider><PortalLayout /></CompanyProvider></RequireAuth>}>
    <Route path="/settings" element={<CompanySettingsPage />} />
    <Route path="*" element={<Navigate to="/settings" replace />} />
  </Route>
</Routes>
```

`PortalLayout` renders `Sidebar`, `SampleBanner` and `<Outlet />`, keeping the existing `ml-64` layout.

Delete the files listed under Delete. Delete the unused `reactflow` dependency from `package.json` only if nothing imports it after the deletions (`grep -rn reactflow src`). Keep `react-force-graph-2d` and `@dnd-kit/core`; Blocks 2 and 3 use them.

- [ ] **Step 5: Verify**

```bash
npm run lint
npm run build
npx playwright test --reporter=line
grep -rn "admin123\|admin@gmail\|password=" src || echo clean
```

Expected: lint clean, build passes, all Playwright tests pass, and `clean` printed. Check that `git status` shows no `.db` file, no password file in the repo, and no test artefacts.

- [ ] **Step 6: Commit**

```bash
git add -A interviewpath/interviewpath-demo
git commit -m "feat: real HR portal login and company settings, remove mock pages"
```

---

## Block acceptance (controller, after Task 13)

The controller runs these itself and reads the output. Spec section 12:

1. `git ls-files | grep -E '(^|/)\.env$|\.claude/worktrees/|\.sql$'` prints nothing.
2. `cd SpeakCV/src/backend && env -u SECRET_KEY APP_ENV=test DATABASE_URL=sqlite:// .venv/bin/python -c "import app.main"` exits non-zero naming `SECRET_KEY`.
3. `tests/test_company_isolation.py` passes.
4. `e2e/login.spec.js` passes against the real backend.
5. `grep -rnE 'ENTERPRISE_DEMO_PRESETS|DEMO_SAMPLE_ANSWERS|Instant HR|PII Masked|pii_anonymized|evidence_grounded|minutes_saved|MOCK_JOBS|parse-master-cv|get_next_topic|networkx|mockN8n|mockInterview' SpeakCV/src/backend/app SpeakCV/src/backend/core SpeakCV/src/backend/requirements.txt SpeakCV/src/frontend/app SpeakCV/src/frontend/components SpeakCV/src/frontend/services interviewpath/interviewpath-demo/src` prints nothing.
6. `test_vendor_boundary.py` passes, and all gateway tests pass with `fake`.
7. `make test` passes.

Then dispatch the final whole-branch review on `worker-opus`.
