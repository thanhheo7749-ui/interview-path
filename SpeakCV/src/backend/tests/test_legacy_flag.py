import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import iter_routes, route_path

LEGACY_PATHS = [
    ("post", "/api/chat"),
    ("post", "/api/transcribe"),
    ("post", "/api/hint"),
    ("get", "/api/history"),
    ("post", "/api/upgrade-pro"),
    ("get", "/api/my-stats"),
    ("get", "/api/questions"),
    ("get", "/api/admin/ai-brain/versions"),
    ("post", "/api/admin/ai-brain/ingestion/jobs"),
    ("post", "/api/generate-cv"),
    ("post", "/api/review-cv"),
    ("post", "/api/cv/upload-makeover"),
    ("post", "/api/cv/tailor"),
    ("post", "/api/cv/interview-context"),
]


def _paths(app):
    """Collect every mounted path, including routes nested inside included routers."""
    return {route_path(route) for route in iter_routes(app)} - {""}


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
    assert {"/api/generate-cv", "/api/review-cv", "/api/cv/upload-makeover", "/api/cv/tailor", "/api/cv/interview-context"} <= paths
    assert [p for p in paths if "/ws/" in p], "the walk must see websocket routes"


def test_core_routes_stay_mounted_when_the_flag_is_off():
    paths = _paths(create_app(legacy_b2c=False))
    assert {"/api/login", "/api/register", "/api/my-profile", "/api/cv/extract-text", "/api/admin/dashboard"} <= paths


def test_default_reads_the_environment(monkeypatch):
    monkeypatch.setenv("LEGACY_B2C_ENABLED", "true")
    assert "/api/chat" in _paths(create_app())
    monkeypatch.setenv("LEGACY_B2C_ENABLED", "false")
    assert "/api/chat" not in _paths(create_app())
