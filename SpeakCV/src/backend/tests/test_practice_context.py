"""Practice context: company/jd_text/voice/mode saved per practice, and job_slug on applications."""
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.ai.providers import fake
from app.database.migrate import run_migrations
from app.database.sql_models import InterviewHistory, User
from app.main import create_app
from tests.helpers import auth_header, make_user
from tests.helpers_board import make_application, make_world

REPORT_JSON = json.dumps({
    "score": 7.5,
    "inferred_position": "Backend Developer",
    "overall_feedback": "Solid.",
    "details": [],
})


def test_migration_0011_adds_practice_context_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/migrate.db")
    with engine.begin() as connection:
        run_migrations(connection)
    columns = {c["name"] for c in inspect(engine).get_columns("interview_history")}
    assert {"company", "jd_text", "voice", "mode"} <= columns


def test_end_interview_stores_practice_context(db):
    user = make_user(db, "practice-context@example.test")
    fake.enqueue("legacy", REPORT_JSON)

    api = TestClient(create_app(legacy_b2c=True))
    response = api.post(
        "/api/end-interview",
        headers=auth_header(user.email),
        json={
            "history": "AI: Tell me about yourself.\nCandidate: I build backend services.",
            "jd_text": "  Backend role at Acme  ",
            "position": "Backend Developer",
            "company": "Acme",
            "voice": "vi-VN-HoaiMyNeural",
            "mode": "technical",
        },
    )
    assert response.status_code == 200, response.text
    history_id = response.json()["history_id"]

    row = db.get(InterviewHistory, history_id)
    assert row.company == "Acme"
    assert row.jd_text == "Backend role at Acme"
    assert row.voice == "vi-VN-HoaiMyNeural"
    assert row.mode == "technical"


def test_end_interview_blank_jd_text_is_stored_as_null(db):
    user = make_user(db, "practice-context-blank@example.test")
    fake.enqueue("legacy", REPORT_JSON)

    api = TestClient(create_app(legacy_b2c=True))
    response = api.post(
        "/api/end-interview",
        headers=auth_header(user.email),
        json={"history": "AI: Hi.\nCandidate: Hi.", "jd_text": "   ", "position": "Free"},
    )
    assert response.status_code == 200, response.text
    row = db.get(InterviewHistory, response.json()["history_id"])
    assert row.jd_text is None
    assert row.company is None


def test_get_application_returns_job_slug_for_owner(db):
    world = make_world(db)
    application = make_application(db, world["job"])
    candidate = db.get(User, application.candidate_user_id)

    api = TestClient(create_app())
    response = api.get(f"/api/applications/{application.id}", headers=auth_header(candidate.email))
    assert response.status_code == 200, response.text
    assert response.json()["job_slug"] == "backend"


def test_get_application_is_404_for_a_different_user(db):
    world = make_world(db)
    application = make_application(db, world["job"])
    other = make_user(db, "someone-else@example.test")

    api = TestClient(create_app())
    response = api.get(f"/api/applications/{application.id}", headers=auth_header(other.email))
    assert response.status_code == 404
    assert "backend" not in response.text
    assert "job_title" not in response.text
