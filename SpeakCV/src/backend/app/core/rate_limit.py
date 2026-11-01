import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.security import decode_access_token

LOGIN_LIMIT = "10/minute"
ASK_LIMIT = "20/hour"

limiter = Limiter(key_func=get_remote_address, enabled=os.environ.get("APP_ENV") != "test")


def user_key(request) -> str:
    """The token's subject, so a new login keeps the same bucket. Without a valid token, the remote address."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    payload = decode_access_token(token) if scheme.lower() == "bearer" and token else None
    subject = payload.get("sub") if payload else None
    return f"user:{subject}" if subject else get_remote_address(request)
