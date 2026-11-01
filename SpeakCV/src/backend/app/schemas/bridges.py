from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

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
