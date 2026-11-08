from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth import security
from app.database.database import get_db
from app.database.sql_models import CompanyMember, User

MEMBER_ROLES = ("hr", "manager", "employee")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)


def user_from_token(db: Session, token: str) -> User | None:
    """The one way from a token to a user. None for a bad token, an unknown user, or a session ended by a password change."""
    payload = security.decode_access_token(token)
    email = payload.get("sub") if payload else None
    user = db.query(User).filter(User.email == email).first() if email else None
    if user is None or security.token_predates_password_change(payload, user.password_changed_at):
        return None
    return user


def get_authenticated_user(token: str = Depends(security.oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user = user_from_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def get_optional_user(token: str | None = Depends(optional_oauth2_scheme), db: Session = Depends(get_db)) -> User | None:
    if not token:
        return None
    return user_from_token(db, token)


def require_member(*roles: str):
    """Authorize against the database on each request, so revoking a membership takes effect at once."""
    unknown = set(roles) - set(MEMBER_ROLES)
    if unknown:
        raise ValueError(f"Unknown member roles: {sorted(unknown)}")

    def dependency(
        company_id: int,
        user: User = Depends(get_authenticated_user),
        db: Session = Depends(get_db),
    ) -> CompanyMember:
        # Enforced here, not in get_authenticated_user, so /api/me and /api/me/password keep working.
        if user.must_change_password:
            raise HTTPException(status_code=403, detail="password_change_required")
        member = (
            db.query(CompanyMember)
            .filter(CompanyMember.company_id == company_id, CompanyMember.user_id == user.id)
            .first()
        )
        if member is None or (roles and member.role not in roles):
            raise HTTPException(status_code=403, detail="You do not have access to this resource")
        return member

    return dependency
