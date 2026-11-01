# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

import re
from typing import Any, Iterable, TypedDict

SKILL_PREFIXES = (
    "we need ",
    "required: ",
    "requirements: ",
    "must have ",
    "experience with ",
    "skills: ",
)

EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
PHONE_REGEX = re.compile(
    r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}\b"
)


class InterviewContextResult(TypedDict):
    match_score: float
    highlighted_strengths: list[str]
    skill_gaps: list[str]
    target_topics: list[str]
    priority_topics: list[str]
    question_plan_seed: dict[str, str | list[str]]


def mask_pii_in_text(text: str) -> dict[str, Any]:
    """Redact emails and phone numbers from CV/JD text before AI context analysis."""
    raw = text or ""
    pii_types: list[str] = []
    redacted_count = 0

    def _replace_email(_match: re.Match[str]) -> str:
        nonlocal redacted_count
        redacted_count += 1
        if "email" not in pii_types:
            pii_types.append("email")
        return "[EMAIL_REDACTED]"

    def _replace_phone(match: re.Match[str]) -> str:
        nonlocal redacted_count
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 9 or len(digits) > 15:
            return match.group(0)
        redacted_count += 1
        if "phone" not in pii_types:
            pii_types.append("phone")
        return "[PHONE_REDACTED]"

    masked = EMAIL_REGEX.sub(_replace_email, raw)
    masked = PHONE_REGEX.sub(_replace_phone, masked)

    return {
        "masked_text": masked,
        "pii_redacted_count": redacted_count,
        "pii_types": pii_types,
    }


def extract_skill_candidates(text: str) -> list[str]:
    sanitized = mask_pii_in_text(text or "")["masked_text"]
    normalized_text = sanitized.strip()
    if not normalized_text:
        return []

    segments = re.split(r"[\n,;|]+", normalized_text)
    candidates: list[str] = []
    seen: set[str] = set()

    for segment in segments:
        cleaned = segment.strip(" .:-\t()[]{}")
        if not cleaned:
            continue

        if "[EMAIL_REDACTED]" in cleaned or "[PHONE_REDACTED]" in cleaned:
            continue

        lowered = cleaned.lower()
        for prefix in SKILL_PREFIXES:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                lowered = cleaned.lower()
                break

        if (
            len(cleaned) < 2
            or lowered in seen
            or "[email_redacted]" in lowered
            or "[phone_redacted]" in lowered
        ):
            continue

        seen.add(lowered)
        candidates.append(cleaned)

    return candidates


def _normalize_skills(skills: Iterable[str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for skill in skills:
        cleaned = (skill or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        normalized.setdefault(key, cleaned)
    return normalized


def build_interview_context(cv_skills: list[str], jd_skills: list[str]) -> InterviewContextResult:
    cv_map = _normalize_skills(cv_skills)
    jd_map = _normalize_skills(jd_skills)

    matched_keys = sorted(set(cv_map) & set(jd_map))
    missing_keys = sorted(set(jd_map) - set(cv_map))

    highlighted_strengths = [cv_map[key] for key in matched_keys[:3]]
    skill_gaps = [jd_map[key] for key in missing_keys]
    target_topics = skill_gaps[:3] if skill_gaps else highlighted_strengths[:3]
    priority_topics = skill_gaps[:3] if skill_gaps else highlighted_strengths[:3]
    question_plan_seed = {
        "starter_topic": priority_topics[0] if priority_topics else "General Technical Fit",
        "strength_topics": highlighted_strengths,
        "gap_topics": skill_gaps,
    }

    return {
        "match_score": round(len(matched_keys) / max(len(jd_map), 1), 2),
        "highlighted_strengths": highlighted_strengths,
        "skill_gaps": skill_gaps,
        "target_topics": target_topics,
        "priority_topics": priority_topics,
        "question_plan_seed": question_plan_seed,
    }


def analyze_interview_context(cv_text: str, jd_text: str) -> InterviewContextResult:
    cv_skills = extract_skill_candidates(cv_text)
    jd_skills = extract_skill_candidates(jd_text)
    return build_interview_context(cv_skills, jd_skills)


__all__ = [
    "InterviewContextResult",
    "analyze_interview_context",
    "build_interview_context",
    "extract_skill_candidates",
    "mask_pii_in_text",
]
