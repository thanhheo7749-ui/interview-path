import os

from slowapi import Limiter
from slowapi.util import get_remote_address

LOGIN_LIMIT = "10/minute"

limiter = Limiter(key_func=get_remote_address, enabled=os.environ.get("APP_ENV") != "test")
