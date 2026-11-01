import os

import pytest
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient

from app.core.uploads import AUDIO_TYPES, CV_TYPES, DOCUMENT_TYPES, read_upload
from app.database.sql_models import User  # noqa: F401
from app.main import create_app
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


def test_missing_type_is_guessed_from_the_extension(upload_client):
    response = upload_client.post("/upload", files={"file": ("a.webm", b"abc", "application/octet-stream")})
    assert response.status_code == 200


UPLOAD_ROUTES = [
    ("/api/cv/extract-text", "a.pdf", "application/pdf"),
    ("/api/review-cv", "a.pdf", "application/pdf"),
    ("/api/cv/upload-makeover", "a.pdf", "application/pdf"),
    ("/api/transcribe", "a.webm", "audio/webm"),
    ("/api/admin/ai-brain/ingestion/upload", "a.pdf", "application/pdf"),
]


@pytest.fixture
def real_routes():
    """Every real upload route, reached as an admin so that only the upload checks can refuse."""
    app = create_app(legacy_b2c=True)
    app.dependency_overrides[get_current_user] = lambda: User(id=1, email="a@example.test", role="admin")
    return TestClient(app)


@pytest.mark.parametrize("path,name,mime", UPLOAD_ROUTES)
def test_real_route_refuses_an_oversized_upload(real_routes, path, name, mime):
    too_big = b"x" * (1024 * 1024 + 1)  # conftest sets MAX_UPLOAD_MB=1
    assert real_routes.post(path, files={"file": (name, too_big, mime)}).status_code == 413


@pytest.mark.parametrize("path,name,mime", UPLOAD_ROUTES)
def test_real_route_refuses_an_unsupported_type(real_routes, path, name, mime):
    assert real_routes.post(path, files={"file": ("a.exe", b"abc", "application/x-msdownload")}).status_code == 415


def test_admin_ingestion_upload_still_requires_an_admin():
    app = create_app(legacy_b2c=True)
    app.dependency_overrides[get_current_user] = lambda: User(id=2, email="u@example.test", role="user")
    response = TestClient(app).post("/api/admin/ai-brain/ingestion/upload", files={"file": ("a.exe", b"abc", "application/x-msdownload")})
    assert response.status_code == 403


def test_cv_uploads_do_not_accept_plain_text_but_documents_do():
    assert "text/plain" not in CV_TYPES
    assert "text/plain" in DOCUMENT_TYPES
    assert CV_TYPES < DOCUMENT_TYPES
