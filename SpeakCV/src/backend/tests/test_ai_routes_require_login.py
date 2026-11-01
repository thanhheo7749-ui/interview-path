import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import cv, interview

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
]


@pytest.mark.parametrize("router,method,path", PROTECTED)
def test_ai_route_requires_login(router, method, path):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert getattr(client, method)(path).status_code == 401
