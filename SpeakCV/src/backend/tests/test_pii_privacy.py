from app.services.interview_context import analyze_interview_context, mask_pii_in_text


def test_mask_pii_in_text_redacts_email_and_phone_numbers():
    raw_cv = (
        "Nguyen Van A - Backend Developer\n"
        "Email: nguyenvana.dev@gmail.com | Phone: +84 908 885 090\n"
        "Skills: Python, FastAPI, Docker, PostgreSQL"
    )

    result = mask_pii_in_text(raw_cv)

    assert "nguyenvana.dev@gmail.com" not in result["masked_text"]
    assert "908 885 090" not in result["masked_text"]
    assert "[EMAIL_REDACTED]" in result["masked_text"]
    assert "[PHONE_REDACTED]" in result["masked_text"]
    assert result["pii_redacted_count"] == 2
    assert set(result["pii_types"]) == {"email", "phone"}


def test_analyze_interview_context_never_leaks_pii_into_skills_or_topics():
    raw_cv = "nguyenvana@gmail.com, 0908885090, Python, FastAPI, Docker"
    raw_jd = "We need Python, FastAPI, Docker, Kubernetes"

    context = analyze_interview_context(raw_cv, raw_jd)

    all_extracted = (
        context["highlighted_strengths"]
        + context["skill_gaps"]
        + context["target_topics"]
    )
    assert all("gmail.com" not in item for item in all_extracted)
    assert all("0908885090" not in item for item in all_extracted)
    assert context["highlighted_strengths"] == ["Docker", "FastAPI", "Python"]
