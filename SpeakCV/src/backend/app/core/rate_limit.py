import os

from slowapi import Limiter
from slowapi.util import get_remote_address

LOGIN_LIMIT = "10/minute"
ASK_LIMIT = "20/hour"

limiter = Limiter(key_func=get_remote_address, enabled=os.environ.get("APP_ENV") != "test")


def user_key(request) -> str:
    header = request.headers.get("authorization", "")
    return header[-32:] if header else get_remote_address(request)
