from typing import Literal, Optional

from pydantic import BaseModel, Field

MemberRole = Literal["hr", "manager", "employee"]


class CompanyOut(BaseModel):
    id: int
    slug: str
    name: str
    is_sample: bool
    default_locale: str
    retention_days: int
    kb_version: int


class CompanyPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    default_locale: Optional[str] = Field(default=None, max_length=10)
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: Optional[int] = None


class DepartmentPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    parent_id: Optional[int] = None


class DepartmentOut(BaseModel):
    id: int
    company_id: int
    parent_id: Optional[int]
    name: str


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: MemberRole
    department_id: Optional[int] = None


class MemberPatch(BaseModel):
    role: Optional[MemberRole] = None
    department_id: Optional[int] = None


class MemberOut(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: Optional[str]
    department_id: Optional[int]
    role: str


class MemberCreated(MemberOut):
    temporary_password: Optional[str] = None


class MembershipOut(BaseModel):
    member_id: int
    company_id: int
    company_slug: str
    company_name: str
    is_sample: bool
    role: str
    department_id: Optional[int]


class MeOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    memberships: list[MembershipOut]
