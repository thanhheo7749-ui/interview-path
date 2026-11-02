from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StrictInt, StringConstraints

from .jobs import Language

LineText = Annotated[str, StringConstraints(max_length=1000)]


class DraftFromRequestIn(BaseModel):
    role_node_id: Optional[int] = None


class DraftFromRoleIn(BaseModel):
    role_node_id: int
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = None


class AssistantIn(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class LinePatchIn(BaseModel):
    id: Optional[Annotated[str, StringConstraints(max_length=50)]] = None
    text: Optional[dict[Language, LineText]] = None
    source_node_ids: Optional[list[int]] = Field(default=None, max_length=50)
    is_requirement: Optional[bool] = None
    must_have: Optional[bool] = None
    conflict_dismissed: Optional[list[int]] = Field(default=None, max_length=50)
    delete: bool = False


class DraftPatchIn(BaseModel):
    lines: list[LinePatchIn] = Field(max_length=200)


class AcknowledgeIn(BaseModel):
    line_id: Optional[str] = None


class DraftVersionIn(BaseModel):
    """The version the page shows, so an approval or a publish covers what the person read."""
    version: StrictInt


class RequestChangesIn(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


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
    # Empty only for a manager who may read none of the application's requirements; the route checks which they may.
    scores: list[ScoreIn] = Field(max_length=100)
    recommendation: Literal["hire", "no_hire"]
    notes: str = Field(default="", max_length=5000)


class OutcomeIn(BaseModel):
    outcome: Literal["hired", "not_hired", "offer_declined"]


class HiringRequestIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    manager_user_id: StrictInt
    department_id: Optional[StrictInt] = None


class HiringRequestPatch(BaseModel):
    """Only the fields sent change. A department can be cleared with null; a request always has a manager."""
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = None
    manager_user_id: Optional[StrictInt] = None
    department_id: Optional[StrictInt] = None


class IntakeStartIn(BaseModel):
    language: Language = "ko"
