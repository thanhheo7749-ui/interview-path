from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import cv
from app.routers.cv import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


async def fake_extract_text_from_cv(_file):
    return "Extracted CV text"



def test_post_extract_text_returns_extracted_text_only(monkeypatch):
    monkeypatch.setattr(cv, "extract_text_from_cv", fake_extract_text_from_cv)

    response = client.post(
        "/api/cv/extract-text",
        files={
            "file": (
                "resume.pdf",
                b"fake pdf bytes",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {"extracted_text": "Extracted CV text"}
