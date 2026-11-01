"""Company, department and member management. Every lookup by ID also filters on company_id."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import security
from app.auth.dependencies import get_authenticated_user, require_member
from app.database.database import get_db
from app.database.sql_models import Company, CompanyMember, Department, User
from app.schemas.companies import (
    CompanyOut,
    CompanyPatch,
    DepartmentCreate,
    DepartmentOut,
    DepartmentPatch,
    MeOut,
    MemberCreate,
    MemberCreated,
    MemberOut,
    MemberPatch,
)

router = APIRouter()

COMPANY = "/api/companies/{company_id}"


def _commit_or_conflict(db: Session, detail: str) -> None:
    """A concurrent request can pass our checks and still lose to a database constraint."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail)


def _get_department(db: Session, company_id: int, department_id: int) -> Department:
    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.company_id == company_id)
        .first()
    )
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


def _get_member(db: Session, company_id: int, member_id: int) -> CompanyMember:
    member = (
        db.query(CompanyMember)
        .filter(CompanyMember.id == member_id, CompanyMember.company_id == company_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


def _reject_sibling_clash(db: Session, company_id: int, parent_id, name: str, exclude_id=None) -> None:
    query = db.query(Department.id).filter(
        Department.company_id == company_id,
        Department.parent_id == parent_id,
        Department.name == name,
    )
    if exclude_id is not None:
        query = query.filter(Department.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="A department with this name already exists here")


def _is_self_or_descendant(db: Session, company_id: int, department_id: int, candidate_id: int) -> bool:
    current, seen = candidate_id, set()
    while current is not None and current not in seen:
        if current == department_id:
            return True
        seen.add(current)
        current = (
            db.query(Department.parent_id)
            .filter(Department.id == current, Department.company_id == company_id)
            .scalar()
        )
    return False


def _reject_losing_the_last_hr(db: Session, company_id: int, member: CompanyMember) -> None:
    """Locks the company's HR rows so two simultaneous demotions cannot both pass."""
    if member.role != "hr":
        return
    hr_rows = (
        db.query(CompanyMember.id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.role == "hr")
        .with_for_update()
        .all()
    )
    if len(hr_rows) <= 1:
        raise HTTPException(status_code=409, detail="A company must keep at least one HR member")


def _member_out(member: CompanyMember, user: User) -> dict:
    return {
        "id": member.id,
        "user_id": member.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "department_id": member.department_id,
        "role": member.role,
    }


@router.get("/api/me", response_model=MeOut)
def get_me(user: User = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    rows = (
        db.query(CompanyMember, Company)
        .join(Company, Company.id == CompanyMember.company_id)
        .filter(CompanyMember.user_id == user.id)
        .order_by(CompanyMember.id)
        .all()
    )
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "memberships": [
            {
                "member_id": member.id,
                "company_id": company.id,
                "company_slug": company.slug,
                "company_name": company.name,
                "is_sample": company.is_sample,
                "role": member.role,
                "department_id": member.department_id,
            }
            for member, company in rows
        ],
    }


@router.get(COMPANY, response_model=CompanyOut)
def get_company(company_id: int, _: CompanyMember = Depends(require_member()), db: Session = Depends(get_db)):
    return db.get(Company, company_id)


@router.patch(COMPANY, response_model=CompanyOut)
def patch_company(
    company_id: int,
    body: CompanyPatch,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(company, field, value)
    db.commit()
    return company


@router.get(f"{COMPANY}/departments", response_model=list[DepartmentOut])
def list_departments(company_id: int, _: CompanyMember = Depends(require_member()), db: Session = Depends(get_db)):
    return db.query(Department).filter(Department.company_id == company_id).order_by(Department.id).all()


@router.post(f"{COMPANY}/departments", response_model=DepartmentOut, status_code=201)
def create_department(
    company_id: int,
    body: DepartmentCreate,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    if body.parent_id is not None:
        _get_department(db, company_id, body.parent_id)
    _reject_sibling_clash(db, company_id, body.parent_id, body.name)
    department = Department(company_id=company_id, parent_id=body.parent_id, name=body.name)
    db.add(department)
    _commit_or_conflict(db, "A department with this name already exists here")
    return department


@router.patch(f"{COMPANY}/departments/{{dept_id}}", response_model=DepartmentOut)
def patch_department(
    company_id: int,
    dept_id: int,
    body: DepartmentPatch,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    department = _get_department(db, company_id, dept_id)
    parent_id = body.parent_id if "parent_id" in body.model_fields_set else department.parent_id
    name = body.name if body.name is not None else department.name

    if parent_id is not None:
        _get_department(db, company_id, parent_id)
        if _is_self_or_descendant(db, company_id, department.id, parent_id):
            raise HTTPException(status_code=409, detail="A department cannot be moved under itself")
    _reject_sibling_clash(db, company_id, parent_id, name, exclude_id=department.id)

    department.parent_id = parent_id
    department.name = name
    _commit_or_conflict(db, "A department with this name already exists here")
    return department


@router.delete(f"{COMPANY}/departments/{{dept_id}}", status_code=204)
def delete_department(
    company_id: int,
    dept_id: int,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    department = _get_department(db, company_id, dept_id)
    has_child = (
        db.query(Department.id)
        .filter(Department.company_id == company_id, Department.parent_id == department.id)
        .first()
    )
    has_member = (
        db.query(CompanyMember.id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.department_id == department.id)
        .first()
    )
    if has_child or has_member:
        raise HTTPException(status_code=409, detail="This department still has child departments or members")
    db.delete(department)
    _commit_or_conflict(db, "This department still has child departments or members")
    return Response(status_code=204)


@router.get(f"{COMPANY}/members", response_model=list[MemberOut])
def list_members(company_id: int, _: CompanyMember = Depends(require_member("hr")), db: Session = Depends(get_db)):
    rows = (
        db.query(CompanyMember, User)
        .join(User, User.id == CompanyMember.user_id)
        .filter(CompanyMember.company_id == company_id)
        .order_by(CompanyMember.id)
        .all()
    )
    return [_member_out(member, user) for member, user in rows]


@router.post(f"{COMPANY}/members", response_model=MemberCreated, status_code=201)
def add_member(
    company_id: int,
    body: MemberCreate,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required")
    if body.department_id is not None:
        _get_department(db, company_id, body.department_id)

    user = db.query(User).filter(User.email == email).first()
    temporary_password = None
    if user is None:
        temporary_password = secrets.token_urlsafe(12)
        user = User(
            email=email,
            # /api/login cannot serve a user with no name.
            full_name=body.full_name or email.split("@")[0],
            hashed_password=security.get_password_hash(temporary_password),
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="This email was just registered. Please try again.")
    else:
        already_member = (
            db.query(CompanyMember.id)
            .filter(CompanyMember.company_id == company_id, CompanyMember.user_id == user.id)
            .first()
        )
        if already_member:
            raise HTTPException(status_code=409, detail="This person is already a member")

    member = CompanyMember(company_id=company_id, user_id=user.id, role=body.role, department_id=body.department_id)
    db.add(member)
    _commit_or_conflict(db, "This person is already a member")
    return {**_member_out(member, user), "temporary_password": temporary_password}


@router.patch(f"{COMPANY}/members/{{member_id}}", response_model=MemberOut)
def patch_member(
    company_id: int,
    member_id: int,
    body: MemberPatch,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    member = _get_member(db, company_id, member_id)
    if "department_id" in body.model_fields_set:
        if body.department_id is not None:
            _get_department(db, company_id, body.department_id)
        member.department_id = body.department_id
    if body.role is not None:
        if body.role != "hr":
            _reject_losing_the_last_hr(db, company_id, member)
        member.role = body.role
    _commit_or_conflict(db, "This member could not be updated")
    return _member_out(member, db.get(User, member.user_id))


@router.delete(f"{COMPANY}/members/{{member_id}}", status_code=204)
def remove_member(
    company_id: int,
    member_id: int,
    _: CompanyMember = Depends(require_member("hr")),
    db: Session = Depends(get_db),
):
    member = _get_member(db, company_id, member_id)
    _reject_losing_the_last_hr(db, company_id, member)
    db.delete(member)
    db.commit()
    return Response(status_code=204)
