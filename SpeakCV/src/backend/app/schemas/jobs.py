from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

Language = Literal["vi", "en", "ko"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Channel = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,50}$")]
Visibility = Literal["public", "internal", "confidential"]


class RequirementIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    must_have: bool = False
    visibility: Visibility = "public"
    node_id: Optional[int] = None


class RequirementOut(BaseModel):
    id: int
    node_id: Optional[int]
    text: str
    must_have: bool
    visibility: str
    position: int


class JobCreate(BaseModel):
    title: Title
    description: str = Field(default="", max_length=20000)
    department_id: Optional[int] = None
    role_node_id: Optional[int] = None
    interview_languages: list[Language] = Field(min_length=1, max_length=3)
    requirements: list[RequirementIn] = Field(default_factory=list, max_length=100)
    scheduling_enabled: bool = False
    interview_window_start: Optional[AwareDatetime] = None
    interview_window_end: Optional[AwareDatetime] = None
    interview_window_timezone: Optional[Annotated[str, StringConstraints(max_length=64)]] = None
    interview_sla_hours: Optional[int] = Field(default=None, ge=1, le=720)


class JobPatch(BaseModel):
    title: Optional[Title] = None
    description: Optional[str] = Field(default=None, max_length=20000)
    department_id: Optional[int] = None
    interview_languages: Optional[list[Language]] = Field(default=None, min_length=1, max_length=3)
    requirements: Optional[list[RequirementIn]] = Field(default=None, max_length=100)
    scheduling_enabled: Optional[bool] = None
    interview_window_start: Optional[AwareDatetime] = None
    interview_window_end: Optional[AwareDatetime] = None
    interview_window_timezone: Optional[Annotated[str, StringConstraints(max_length=64)]] = None
    interview_sla_hours: Optional[int] = Field(default=None, ge=1, le=720)


class ChannelsIn(BaseModel):
    channels: list[Channel] = Field(min_length=1, max_length=20)


class ChannelOut(BaseModel):
    id: int
    channel: str
    token: str
    click_count: int


class JobSummary(BaseModel):
    id: int
    title: str
    slug: Optional[str]
    status: str
    version: int
    department_id: Optional[int]
    published_at: Optional[datetime]


class JobOut(JobSummary):
    description: str
    role_node_id: Optional[int]
    interview_languages: list[str]
    requirements: list[RequirementOut]
    channels: list[ChannelOut]
    warnings: list[str] = []
    scheduling_enabled: bool = False
    interview_window_start: Optional[datetime] = None
    interview_window_end: Optional[datetime] = None
    interview_window_timezone: Optional[str] = None
    interview_sla_hours: Optional[int] = None


class RoleOption(BaseModel):
    id: int
    title: str
    department_id: Optional[int]
    department_name: Optional[str]


class Prefill(BaseModel):
    role_node_id: int
    title: str
    description: str
    department_id: Optional[int]
    requirements: list[RequirementIn]


class PublicRequirement(BaseModel):
    text: str
    must_have: bool


class PublicJob(BaseModel):
    slug: str
    title: str
    description: str
    company_name: str
    company_slug: str
    is_sample: bool
    interview_languages: list[str]
    status: str
    can_apply: bool
    requirements: list[PublicRequirement]
