import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.security import decode_access_token

LOGIN_LIMIT = "10/minute"
ASK_LIMIT = "20/hour"
# The recorded interview's candidate routes, per user. Each can cost AI calls. A 15 minute interview is a dozen answers
# with a few retries, and one question-audio request per question (cached afterwards), so these leave room to spare.
VOICE_START_LIMIT = "20/hour"  # a page reload resumes with a start
VOICE_ANSWER_LIMIT = "40/10 minutes"
VOICE_QUESTION_AUDIO_LIMIT = "60/10 minutes"

limiter = Limiter(key_func=get_remote_address, enabled=os.environ.get("APP_ENV") != "test")


def user_key(request) -> str:
    """The token's subject, so a new login keeps the same bucket. Without a valid token, the remote address."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    payload = decode_access_token(token) if scheme.lower() == "bearer" and token else None
    subject = payload.get("sub") if payload else None
    return f"user:{subject}" if subject else get_remote_address(request)
