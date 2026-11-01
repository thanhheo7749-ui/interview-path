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
