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
