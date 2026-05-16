from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import cv
from app.routers.cv import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


EXPECTED_CV_DATA = {
    "analysis_feedback": {
        "strengths": ["Clear backend focus"],
        "weaknesses": ["Needs more metrics"],
        "overall_score": 84,
    },
    "personal_info": {
        "name": "Jane Doe",
        "title": "Backend Engineer",
        "email": "jane@example.com",
        "phone": "0123456789",
        "linkedin": "linkedin.com/in/janedoe",
        "location": "Ho Chi Minh City",
        "summary": "Experienced backend engineer.",
    },
    "skills": ["Python", "FastAPI"],
    "experience": [
        {
            "company": "SpeakCV",
            "role": "Backend Engineer",
            "period": "2023-2025",
            "achievements": ["Built APIs", "Improved reliability"],
        }
    ],
    "education": [
        {
            "school": "HCMUT",
            "degree": "BEng",
            "period": "2018-2022",
        }
    ],
    "projects": [
        {
            "name": "Interview Platform",
            "description": "AI interview tooling",
            "technologies": ["Python", "React"],
        }
    ],
}


def fake_parse_and_validate_cv(raw_text: str):
    assert raw_text == "Raw CV text to parse"
    return EXPECTED_CV_DATA


def test_post_parse_master_cv_returns_validated_structured_cv(monkeypatch):
    monkeypatch.setattr(cv, "parse_and_validate_cv", fake_parse_and_validate_cv)

    response = client.post(
        "/api/cv/parse-master-cv",
        json={"raw_text": "Raw CV text to parse"},
    )

    assert response.status_code == 200
    assert response.json() == {"cv_data": EXPECTED_CV_DATA}
