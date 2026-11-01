from typing import Literal

from pydantic import BaseModel, Field, StrictInt

Language = Literal["ko", "vi", "en"]


class BriefIn(BaseModel):
    language: Language = "ko"


class PointEdit(BaseModel):
    evidence_id: str
    summary: str = Field(max_length=2000)


class QuestionEdit(BaseModel):
    evidence_id: str
    question: str = Field(max_length=2000)


class BriefPatch(BaseModel):
    """Wording only. Quotes and recording times are never accepted; the server reads them from the evidence."""
    strengths: list[PointEdit] | None = None
    to_clarify: list[PointEdit] | None = None
    questions: list[QuestionEdit] | None = None


class ScoreIn(BaseModel):
    requirement_id: StrictInt
    score: StrictInt = Field(ge=1, le=5)


class ScorecardIn(BaseModel):
    scores: list[ScoreIn] = Field(min_length=1, max_length=100)
    recommendation: Literal["hire", "no_hire"]
    notes: str = Field(default="", max_length=5000)


class OutcomeIn(BaseModel):
    outcome: Literal["hired", "not_hired", "offer_declined"]
