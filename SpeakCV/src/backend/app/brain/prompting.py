"""Helpers for putting untrusted text into a prompt."""
import re

_DELIMITER = re.compile(r"<(?=\s*/?\s*(?:context|question|document|fact|statement|request|draft|history)\b)", re.IGNORECASE)


def as_data(text: str) -> str:
    """Stop text from closing or opening the tags that mark it as data."""
    return _DELIMITER.sub("&lt;", text)
