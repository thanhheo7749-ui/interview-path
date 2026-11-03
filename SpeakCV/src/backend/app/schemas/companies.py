from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

from app.auth.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH

MemberRole = Literal["hr", "manager", "employee"]
# Whitespace is stripped first, so a name of only spaces fails the minimum length.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Locale = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]


class CompanyOut(BaseModel):
    id: int
    slug: str
    name: str
    is_sample: bool
    default_locale: str
    retention_days: int
    kb_version: int
    reality_low_pct: int
    reality_high_pct: int
    reality_min_hired: int


class CompanyPatch(BaseModel):
    name: Optional[Name] = None
    default_locale: Optional[Locale] = None
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)
    reality_low_pct: Optional[int] = Field(default=None, ge=0, le=100)
    reality_high_pct: Optional[int] = Field(default=None, ge=0, le=100)
    reality_min_hired: Optional[int] = Field(default=None, ge=1)


class DepartmentCreate(BaseModel):
    name: Name
    parent_id: Optional[int] = None


class DepartmentPatch(BaseModel):
    name: Optional[Name] = None
    parent_id: Optional[int] = None


class DepartmentOut(BaseModel):
    id: int
    company_id: int
    parent_id: Optional[int]
    name: str


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: Optional[Name] = None
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
    existing_account: bool = False


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
    must_change_password: bool
    memberships: list[MembershipOut]


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
