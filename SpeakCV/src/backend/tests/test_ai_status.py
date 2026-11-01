from tests.helpers import auth_header, make_user


def test_ai_status_lists_fake_slots(client, db):
    make_user(db, "u@example.test")
    body = client.get("/api/ai-status", headers=auth_header("u@example.test")).json()
    assert set(body["fake_slots"]) == {"reasoning", "bulk", "embedding", "stt", "tts"}


def test_ai_status_requires_login(client):
    assert client.get("/api/ai-status").status_code == 401
