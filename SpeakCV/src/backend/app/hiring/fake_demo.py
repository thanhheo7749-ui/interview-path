"""Deterministic CV responses for demo and tests when the bulk slot is fake. Never used with a real vendor."""
import json
import re

from app.ai.config import get_config
from app.ai.providers import fake

_CV = re.compile(r"<cv>\n(.*)\n</cv>", re.DOTALL)
_REQUIREMENTS = re.compile(r"<requirements>\n(.*?)\n</requirements>", re.DOTALL)
_REQUIREMENT = re.compile(r"^- id=(\d+): (.*)$", re.MULTILINE)
_NAME_LINE = re.compile(r"^\s*Name\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_WORD = re.compile(r"\w+")
_MAX_NAME_WORDS = 5
_MAX_CLAIMS = 8
_GENDER_TERMS = ("he", "she", "him", "her", "his", "hers", "mr.", "mrs.", "ms.", "anh", "chị", "ông", "bà")
_STOP_WORDS = {"and", "the", "with", "for", "from", "that", "this", "years", "year", "experience", "kinh", "nghiệm", "năm", "của"}


def _cv_text(messages) -> str:
    match = _CV.search(messages[-1]["content"])
    return match.group(1) if match else ""


def _whole_word(term: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)


def _mask(_system, messages, _schema) -> str:
    text = _cv_text(messages)
    names: list[str] = []
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    candidates = [first_line] if len(first_line.split()) <= _MAX_NAME_WORDS else []
    candidates += _NAME_LINE.findall(text)
    for candidate in candidates:
        names.append(candidate)
        names.extend(candidate.split())
    gender_terms = [term for term in _GENDER_TERMS if _whole_word(term).search(text)]
    return json.dumps({"names": names, "gender_terms": gender_terms, "ages": [], "addresses": []}, ensure_ascii=False)


def _assess(_system, messages, _schema) -> str:
    content = messages[-1]["content"]
    text = _cv_text(messages)
    section = _REQUIREMENTS.search(content)
    requirements = []
    for requirement_id, requirement in _REQUIREMENT.findall(section.group(1) if section else ""):
        quote = ""
        for word in _WORD.findall(requirement):
            if len(word) >= 3 and word.casefold() not in _STOP_WORDS:
                found = _whole_word(word).search(text)
                if found:
                    quote = found.group(0)
                    break
        requirements.append({"requirement_id": int(requirement_id), "status": "met" if quote else "not_found", "quote": quote})
    lines = [line.strip() for line in text.splitlines() if any(char.isdigit() for char in line)]
    claims = [{"text": line, "quote": line} for line in lines[:_MAX_CLAIMS]]
    return json.dumps({"requirements": requirements, "claims": claims}, ensure_ascii=False)


def install() -> None:
    if get_config().slot("bulk").provider == "fake":
        fake.register("cv_mask", _mask)
        fake.register("cv_assess", _assess)
