# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

import os
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer

from ..core import settings

SECRET_KEY = settings.secret_key()
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "3000"))
MIN_PASSWORD_LENGTH = 10

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": int(now.timestamp())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Decode and verify JWT token. Use through auth.dependencies.user_from_token, which also checks revocation.
def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

def mark_password_changed(user) -> None:
    """Ends the sessions issued before now. Whole seconds: MySQL DATETIME would round a fraction, possibly up,
    past the iat of the token issued right after."""
    user.password_changed_at = datetime.now(timezone.utc).replace(microsecond=0)

def token_predates_password_change(payload: dict, password_changed_at: datetime | None) -> bool:
    if password_changed_at is None:
        return False
    issued_at = payload.get("iat")
    if not isinstance(issued_at, (int, float)):
        return True
    # SQLite and MySQL return naive datetimes; they hold UTC.
    if password_changed_at.tzinfo is None:
        password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)
    return issued_at < int(password_changed_at.timestamp())