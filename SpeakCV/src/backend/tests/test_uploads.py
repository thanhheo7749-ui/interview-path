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
