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


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_tables():
    from app.database import sql_models  # noqa: F401
    from app.ai.config import reset_config
    from app.database.database import Base, engine

    from app.ai.providers import fake

    reset_config()
    fake.reset()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    reset_config()


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
