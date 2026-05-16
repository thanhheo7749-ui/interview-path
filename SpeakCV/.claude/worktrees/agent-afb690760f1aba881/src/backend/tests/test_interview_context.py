from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.cv import router
from app.services.interview_context import analyze_interview_context


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_analyze_interview_context_builds_structured_summary_from_raw_text():
    result = analyze_interview_context(
        cv_text="Python, FastAPI, Docker, APIs",
        jd_text="We need Python, FastAPI, System Design, Docker",
    )

    assert result["match_score"] == 0.75
    assert result["highlighted_strengths"] == ["Docker", "FastAPI", "Python"]
    assert result["skill_gaps"] == ["System Design"]
    assert result["target_topics"] == ["System Design"]


def test_post_interview_context_returns_interview_context_only():
    response = client.post(
        "/api/cv/interview-context",
        json={
            "cv_text": "Python, FastAPI, Docker, APIs",
            "jd_text": "We need Python, FastAPI, System Design, Docker",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "interview_context": {
            "match_score": 0.75,
            "highlighted_strengths": ["Docker", "FastAPI", "Python"],
            "skill_gaps": ["System Design"],
            "target_topics": ["System Design"],
        }
    }
