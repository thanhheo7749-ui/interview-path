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


_ANALYSIS_ITEM = re.compile(r"^- id=(\d+): (.*)$", re.MULTILINE)
_TRANSCRIPT = re.compile(r'<transcript position="(\d+)">\n(.*?)\n</transcript>', re.DOTALL)
_QUESTION = re.compile(r"^- position=(\d+): (.*)$", re.MULTILINE)
_EXPLAIN_WORDS = 5


def _section(content: str, name: str) -> str:
    found = re.search(rf"<{name}>\n(.*?)\n</{name}>", content, re.DOTALL)
    return found.group(1) if found else ""


def _analyse(_system, messages, _schema) -> str:
    content = messages[-1]["content"]
    transcripts = [(int(position), text) for position, text in _TRANSCRIPT.findall(content)]
    questions = {int(position): text for position, text in _QUESTION.findall(_section(content, "questions"))}
    requirements = []
    for requirement_id, requirement in _ANALYSIS_ITEM.findall(_section(content, "requirements")):
        found = None
        for word in _WORD.findall(requirement):
            if len(word) < 3 or word.casefold() in _STOP_WORDS:
                continue
            for position, text in transcripts:
                match = _whole_word(word).search(text)
                if match:
                    found = (position, match.group(0))
                    break
            if found:
                break
        requirements.append({
            "requirement_id": int(requirement_id), "status": "evidence" if found else "none",
            "quote": found[1] if found else "", "position": found[0] if found else 0,
        })
    claims = []
    for claim_id, claim in _ANALYSIS_ITEM.findall(_section(content, "claims")):
        position = next((p for p, q in questions.items() if claim.casefold() in q.casefold()), None)
        text = dict(transcripts).get(position, "")
        words = text.split()
        explained = len(words) > _EXPLAIN_WORDS
        claims.append({
            "claim_id": int(claim_id), "status": "explained" if explained else "not_explained",
            "quote": " ".join(words[:_EXPLAIN_WORDS]) if explained else "", "position": position or 0,
        })
    return json.dumps({"requirements": requirements, "claims": claims, "culture_notes": [],
                       "suggestion": "Review the quoted answers before deciding."}, ensure_ascii=False)


def install() -> None:
    if get_config().slot("bulk").provider == "fake":
        fake.register("cv_mask", _mask)
        fake.register("cv_assess", _assess)
    if get_config().slot("reasoning").provider == "fake":
        fake.register("session_analysis", _analyse)
